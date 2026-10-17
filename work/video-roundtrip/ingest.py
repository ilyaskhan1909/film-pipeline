"""Verify returned Kaggle clips before making a LOCAL edit asset catalogue."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from contract import (check_zip, digest, read_json_member, safe_relative, save_json,
                      validate_inputs, validate_return_manifest)

ROOT = Path(__file__).resolve().parents[2]
FFMPEG = ROOT / 'work/ffmpeg-full/ffmpeg.exe'
FFPROBE = ROOT / 'work/smoke-scratch/node/remotion-c57941070451/node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe'


def verify_media(path, config, ffmpeg=FFMPEG, ffprobe=FFPROBE):
    response = subprocess.check_output([str(ffprobe), '-v', 'error', '-count_frames',
        '-show_streams', '-show_format', '-of', 'json', str(path)], text=True)
    metadata = json.loads(response)
    streams = metadata['streams']
    if len(streams) != 1 or streams[0]['codec_type'] != 'video':
        raise ValueError('Kaggle result must be one silent video stream.')
    video = streams[0]
    if (video['width'], video['height']) != (config['WIDTH'], config['HEIGHT']):
        raise ValueError('Returned clip native dimensions differ.')
    if (video['avg_frame_rate'] != '24/1' or video['codec_name'] != 'h264' or
            int(video['nb_read_frames']) != config['FRAMES']):
        raise ValueError('Returned clip codec/fps/frame count differ.')
    duration = float(metadata['format']['duration'])
    if abs(duration - config['FRAMES'] / config['FPS']) > .06:
        raise ValueError('Returned clip duration differs.')
    result = subprocess.run([str(ffmpeg), '-hide_banner', '-nostdin', '-loglevel', 'error',
        '-i', str(path), '-f', 'null', '-'], capture_output=True, text=True, timeout=300)
    if result.returncode or result.stderr.strip():
        raise ValueError('Returned clip full decode failed: ' + result.stderr[-1000:])
    return {'native_size':[video['width'], video['height']], 'fps':24,
            'frames':int(video['nb_read_frames']), 'seconds':duration, 'full_decode_passed':True}


def ingest(archive, inputs_path, destination_root, ffmpeg=FFMPEG, ffprobe=FFPROBE):
    inputs = validate_inputs(json.loads(Path(inputs_path).read_text(encoding='utf-8')))
    with zipfile.ZipFile(archive) as bundle:
        check_zip(bundle)
        results = validate_return_manifest(read_json_member(bundle, 'video-results.json'), inputs)
        checksums = read_json_member(bundle, 'checksums.json')
        members = {i.filename for i in bundle.infolist() if not i.is_dir()}
        if members != set(checksums) | {'checksums.json'}:
            raise ValueError('Unlisted/missing result archive members.')
        required = {'video-results.json'} | {c[k] for c in results['clips'] for k in ('file','report')}
        if not required <= set(checksums):
            raise ValueError('Result checksums omit required media/metadata.')
        # Validate EVERY checksum before writing any untrusted archive content.
        for name, expected in checksums.items():
            safe_relative(name)
            hasher = hashlib.sha256()
            with bundle.open(name) as stream:
                for block in iter(lambda: stream.read(2**20), b''):
                    hasher.update(block)
            if hasher.hexdigest() != expected:
                raise ValueError('Archive checksum mismatch: ' + name)
        for clip in results['clips']:
            report = read_json_member(bundle, clip['report'])
            if (checksums[clip['file']] != clip['sha256'] or report['sha256'] != clip['sha256']
                    or report['config'] != clip['config'] or report['source_sha256'] != clip['source_sha256']
                    or report.get('job_fingerprint') != results['job_fingerprint']):
                raise ValueError('Clip metadata is inconsistent.')
        destination = Path(destination_root) / inputs['handoff_id'] / ('return-' + digest(archive)[:16])
        destination.mkdir(parents=True, exist_ok=True)
        for name in required:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(name) as incoming, target.open('wb') as outgoing:
                __import__('shutil').copyfileobj(incoming, outgoing, 2**20)
    catalogue = []
    for clip in results['clips']:
        path = destination / clip['file']
        technical = verify_media(path, clip['config'], ffmpeg, ffprobe)
        catalogue.append({'clip_id':clip['id'],'source_asset_id':clip['asset_id'],
            'source_sha256':clip['source_sha256'],'file':clip['file'],'sha256':clip['sha256'],
            **technical,'editorial_approved':False,'identity_preservation_verified':False,
            'automatic_timeline_insertion':False,'loop_or_upscale_applied':False})
    save_json(destination / 'edit-assets.json', {'schema':'local-edit-assets/v1',
        'handoff_id':inputs['handoff_id'],'clips':catalogue,
        'review_required':True,'intended_local_editors':['Remotion','HyperFrames'],
        'renderer_adapter_installed':False,
        'audio_music_captions':'Add locally; never generated or mixed by this Kaggle stage.'})
    print('IMPORTED', len(catalogue), 'technically verified clips; visual review required.', destination)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/video-roundtrip/returned')
    args = parser.parse_args()
    ingest(args.archive, args.inputs, args.output)
