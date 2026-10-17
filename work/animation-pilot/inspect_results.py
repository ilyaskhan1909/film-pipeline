"""Verify returned clips independently and create compact sampling evidence for visual review."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from common import atomic_json, inspect_video, sha256

ROOT = Path(__file__).resolve().parents[2]
FFMPEG = ROOT/'work/ffmpeg-full/ffmpeg.exe'
FFPROBE = ROOT/'work/smoke-scratch/node/remotion-c57941070451/node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    job = json.loads((args.run/'job.json').read_text(encoding='utf-8'))
    checksums = json.loads((args.run/'checksums.json').read_text())
    for name,digest in checksums.items():
        assert sha256(args.run/name) == digest, name
    rows, reports = [], []
    for folder in ('controls','clips'):
        for video in sorted((args.run/folder).glob('*.mp4')):
            image = Image.open(args.run/'source'/f'{video.stem[:8]}.png').convert('RGB')
            report,samples = inspect_video(video,job['config'],image,FFMPEG,FFPROBE)
            report['file'] = video.relative_to(args.run).as_posix()
            reports.append(report)
            row = Image.new('RGB',(1280,174),'#151515')
            ImageDraw.Draw(row).text((8,7),video.name,fill='white')
            for index,sample in enumerate(samples):
                row.paste(Image.fromarray(sample),(index*256,30))
            row.save(args.output/f'{video.stem}-samples.jpg',quality=95)
            rows.append(row)
    panel = Image.new('RGB',(1280,174*len(rows)),'#151515')
    for index,row in enumerate(rows):
        panel.paste(row,(0,174*index))
    panel.save(args.output/'motion-contact-sheet.jpg',quality=95)
    atomic_json(args.output/'independent-validation.json',{
        'checksum_files_verified':len(checksums),'videos':reports,
        'all_frame_decode_passed':True,'continuous_viewing_approved':False,
        'identity_preservation_approved':False,'checkpoint_changed':False})
    print(json.dumps({'videos':len(reports),'checksum_files':len(checksums),
                      'contact_sheet':str(args.output/'motion-contact-sheet.jpg')}))


if __name__ == '__main__':
    main()
