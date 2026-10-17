"""Package selected local drawings and validate an editable style pilot."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pipeline import ROOT, OUT, COMFY, PILOT_SHOTS, sha, save

EDIT = OUT / 'edit/remotion'
FFMPEG = ROOT / 'work/ffmpeg-full/ffmpeg.exe'


def selection(filename):
    items = json.loads((OUT / filename).read_text(encoding='utf-8'))
    for item in items.values():
        path = (OUT / item['file']).resolve()
        if not path.is_relative_to(OUT.resolve()) or sha(path) != item['sha256']:
            raise RuntimeError('Selected asset has changed or escapes this delivery.')
    return items


def copy_exact(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha(source) != sha(target):
            raise RuntimeError(f'Different existing delivery preserved: {target}')
    else:
        shutil.copy2(source, target)


def contact_board(filename, cells, columns, width=512, height=320):
    gap, label = 18, 38
    rows = (len(cells) + columns - 1) // columns
    canvas = Image.new('RGB', (columns * (width + gap) + gap,
        rows * (height + label + gap) + gap), '#151719')
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 20)
    for index, (caption, source) in enumerate(cells):
        x, y = gap + (index % columns) * (width + gap), gap + (index // columns) * (height + label + gap)
        with Image.open(source) as original:
            image = original.convert('RGB')
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
            canvas.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
        draw.text((x, y + height + 6), caption, fill='#d1d4d8', font=font)
    canvas.save(OUT / filename, quality=95, subsampling=0)


def character_pack():
    fronts, views = selection('character-selection.json'), selection('view-selection.json')
    cells = []
    for name in ('mark', 'chloe', 'jess'):
        item = fronts[name]
        source = OUT / item['file']
        copy_exact(source, OUT / 'characters' / f'{name}-front.png')
        cells.append((name.title() + ' / canonical', source))
    contact_board('canonical-characters.jpg', cells, 3, height=512)
    cells = []
    for name in ('mark', 'chloe', 'jess'):
        for view in ('profile', 'expressions'):
            item = views[f'{name}-{view}']
            source = OUT / item['file']
            copy_exact(source, OUT / 'characters' / f'{name}-{view}.png')
            cells.append((name.title() + (' / oblique' if 'oblique' in item['decision'] else f' / {view}'), source))
    contact_board('character-views.jpg', cells, 2, height=384)
    print('CHARACTER_PACK', 9, flush=True)


def pcm_hash(path, trim=False):
    cmd = [str(FFMPEG), '-v', 'error', '-i', str(path)]
    if trim:
        cmd += ['-af', 'atrim=start_sample=16504000:end_sample=20758000,asetpts=PTS-STARTPTS']
    cmd += ['-c:a', 'pcm_s24le', '-f', 'hash', '-hash', 'sha256', '-']
    return subprocess.check_output(cmd, text=True).strip().split('=', 1)[1]


def riff_metadata(path):
    # Handle WAVE_FORMAT_EXTENSIBLE without installing or changing host libraries.
    import struct
    with path.open('rb') as stream:
        if stream.read(4) != b'RIFF':
            raise RuntimeError('Expected RIFF WAV')
        stream.read(4)
        if stream.read(4) != b'WAVE':
            raise RuntimeError('Expected WAVE')
        result = {}
        while chunk := stream.read(8):
            tag, size = struct.unpack('<4sI', chunk)
            if tag == b'fmt ':
                data = stream.read(size)
                code, channels, rate, byte_rate, block, bits = struct.unpack('<HHIIHH', data[:16])
                result.update(format_tag=code, channels=channels, sample_rate=rate, bits_per_sample=bits, block_align=block)
            elif tag == b'data':
                result['pcm_bytes'] = size
                stream.seek(size, 1)
            else:
                stream.seek(size, 1)
            if size & 1:
                stream.seek(1, 1)
        result['samples'] = result['pcm_bytes'] // result['block_align']
        return result


def assemble():
    items = selection('scene-selection.json')
    timeline = json.loads((ROOT / 'outputs/local-production-v6/edit/remotion/timeline.json').read_text())
    beats = timeline['beats'][13:16]
    shots = [shot for beat in beats for shot in beat['shots']]
    if [shot['id'] for shot in shots] != PILOT_SHOTS:
        raise RuntimeError('Unexpected source timeline.')
    for shot in shots:
        item = items[shot['id']]
        if item['decision'] != 'use_in_style_pilot':
            raise RuntimeError('Each preview shot must have a manual visual selection.')
        preview_name = item.get('preview_filename', f'{shot["id"]}.png')
        if Path(preview_name).name != preview_name or not preview_name.endswith('.png'):
            raise RuntimeError('Preview filename must be a safe PNG basename.')
        copy_exact(OUT / item['file'], EDIT / 'public/assets' / preview_name)
    contact_board('sequence-keyframes.jpg', [(shot['id'], OUT / items[shot['id']]['file']) for shot in shots], 2)
    probes = [key for key in items if key not in PILOT_SHOTS]
    if probes:
        contact_board('mark-continuity.jpg', [(key + ' / probe', OUT / items[key]['file']) for key in probes], 2)
    audio_source = ROOT / 'outputs/local-production-v6/edit/remotion/public/sound/master.wav'
    audio_trim = EDIT / 'public/sound/pilot-master-pcm24.wav'
    audio_info = riff_metadata(audio_trim)
    if audio_info['samples'] != 4254000 or audio_info['sample_rate'] != 48000 or audio_info['bits_per_sample'] != 24:
        raise RuntimeError('Wrong sample-exact audio trim.')
    original_pcm, pilot_pcm = pcm_hash(audio_source, True), pcm_hash(audio_trim)
    if original_pcm != pilot_pcm:
        raise RuntimeError('Pilot audio differs from original v6 source samples.')
    save(OUT / 'pilot-timeline.json', {'source': 'v6 beats 13-15', 'source_start_frame': 8252,
        'fps': 24, 'frames': 2127, 'seconds': 88.625,
        'scenes': [{**beat, 'pilot_start_frame': beat['start_frame'] - 8252} for beat in beats],
        'shots': [{**shot, 'pilot_start_frame': shot['start_frame'] - 8252} for shot in shots],
        'audio': {'source': str(audio_source), 'source_sha256': sha(audio_source),
            'file': str(audio_trim), 'sha256': sha(audio_trim), **audio_info,
            'start_sample': 16504000, 'end_sample_exclusive': 20758000,
            'source_trim_pcm_sha256': original_pcm, 'pilot_pcm_sha256': pilot_pcm, 'exact_original_samples': True},
        'native_video_generation': False, 'movement': '2D editorial pan and up to 2.5 percent push-in only',
        'new_narration': False, 'full_film_restyled': False, 'mp4_exported': False,
        'specific_new_images_user_approved': False})
    print('ASSEMBLED 8 consecutive shots / 88.625 seconds / original sample-exact audio', flush=True)


def audit():
    fronts, views, scenes = (selection(f) for f in ('character-selection.json', 'view-selection.json', 'scene-selection.json'))
    reports = sorted((OUT / 'candidates').glob('*.json'))
    histories = []
    input_names = set()
    for path in reports:
        report = json.loads(path.read_text())
        if sha(report['image']) != report['sha256']:
            raise RuntimeError('Candidate checksum mismatch.')
        workflow = json.loads(Path(report['workflow']).read_text())
        history_file = COMFY / 'reports' / f'{report["prompt_id"]}.json'
        evidence = json.loads(history_file.read_text())
        if not evidence['completed'] or evidence['history']['prompt'][2] != workflow:
            raise RuntimeError('Missing completed GPU history or workflow differs.')
        if evidence['outputs'][0]['sha256'] != report['sha256']:
            raise RuntimeError('GPU output checksum mismatch.')
        for ref in report['job']['references']:
            if sha(ref['source']) != ref['sha256'] or sha(COMFY / 'data/input' / ref['image']) != ref['sha256']:
                raise RuntimeError('Reference has changed.')
            copy_exact(Path(ref['source']), OUT / 'inputs' / ref['image'])
            input_names.add(ref['image'])
        copy_exact(history_file, OUT / 'evidence' / history_file.name)
        histories.append(report['prompt_id'])
    source_dir = ROOT / 'work/graphic-novel-v8'
    sources = []
    for name in ('pipeline.py', 'delivery.py', 'test_pipeline.py', 'qa_preview.cjs'):
        path = source_dir / name
        if path.exists():
            target = OUT / 'source' / name
            if target.exists() and sha(target) != sha(path):
                target = target.with_name(f'{path.stem}-{sha(path)[:12]}{path.suffix}')
            copy_exact(path, target)
            sources.append({'name': name, 'snapshot': target.relative_to(OUT).as_posix(), 'sha256': sha(path)})
    save(OUT / 'source-lock.json', sources)
    save(OUT / 'delivery-validation.json', {'completed_local_gpu_jobs': len(histories),
        'prompt_ids': histories, 'verified_reference_files': len(input_names),
        'selected_front_references': len(fronts), 'selected_view_references': len(views),
        'selected_scene_drawings': len(scenes), 'candidate_and_workflow_checksums_valid': True,
        'paid_api': False, 'kaggle_uploaded': False, 'native_animation_tested': False,
        'whole_film_restyled': False, 'user_approved_individual_images': False})
    print('AUDIT', len(histories), 'completed local GPU jobs', flush=True)


def package():
    archive = OUT / 'The_Last_Firework_Ink_v8_Assets.zip'
    if archive.exists():
        raise RuntimeError('Archive already exists; preserve it and choose a new revision.')
    files = [p for p in OUT.glob('*') if p.is_file() and p.suffix in ('.json', '.jpg', '.txt') and p.name != 'package-validation.json']
    for folder in ('candidates', 'characters', 'workflows', 'inputs', 'evidence', 'source', 'qa', 'qa-r2'):
        files += [p for p in (OUT / folder).rglob('*') if p.is_file()]
    files += [EDIT / 'package.json', EDIT / 'remotion.config.ts', EDIT / 'tsconfig.json']
    files += [p for p in (EDIT / 'src').rglob('*') if p.is_file()]
    files += [p for p in (EDIT / 'scripts').rglob('*') if p.is_file()]
    files += [p for p in (EDIT / 'public/assets').glob('*.png')]
    files += [EDIT / 'public/sound/pilot-master-pcm24.wav']
    files = sorted(set(files))
    inventory = [{'file': p.relative_to(OUT).as_posix(), 'size': p.stat().st_size, 'sha256': sha(p)} for p in files]
    save(OUT / 'bundle-manifest.json', inventory)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
        for file in files + [OUT / 'bundle-manifest.json']:
            bundle.write(file, file.relative_to(OUT).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError('Archive CRC failed.')
        for item in inventory:
            if hashlib.sha256(bundle.read(item['file'])).hexdigest() != item['sha256']:
                raise RuntimeError('Archive checksum failed.')
    save(OUT / 'package-validation.json', {'archive': str(archive), 'size': archive.stat().st_size,
        'sha256': sha(archive), 'files': len(files) + 1, 'crc_valid': True,
        'payload_hashes_valid': True, 'models_included': False, 'node_modules_included': False})
    print('PACKAGE', archive, archive.stat().st_size, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['characters', 'assemble', 'audit', 'package'])
    args = parser.parse_args()
    {'characters': character_pack, 'assemble': assemble, 'audit': audit, 'package': package}[args.action]()
