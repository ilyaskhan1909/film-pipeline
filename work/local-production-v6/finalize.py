"""Validate actual exported media and package a separate review deliverable."""
import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/local-production-v6'
PROJECT=OUT/'edit/remotion'
SOURCE=PROJECT/'out/The_Last_Firework_v6_1080p.mp4'
FFMPEG=ROOT/'work/ffmpeg-full/ffmpeg.exe'


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):value.update(block)
    return value.hexdigest()


def run(args):
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:raise RuntimeError(result.stderr[-4000:])
    print(result.stdout[-1200:],flush=True)


def main():
    if not SOURCE.is_file():raise FileNotFoundError('Wait for Remotion to finish; no video export exists.')
    scripts=ROOT/'work/production-v4'
    timeline=PROJECT/'timeline.json'
    checks=[
        [sys.executable,'-X','utf8',str(scripts/'validate_video.py'),str(SOURCE),
         '--timeline',str(timeline),'--output',str(OUT/'video-validation.json')],
        [sys.executable,'-X','utf8',str(scripts/'validate_export_audio.py'),str(SOURCE),
         '--master',str(PROJECT/'public/sound/master.wav'),
         '--decoded',str(OUT/'audio-stems/export-decoded.wav'),
         '--output',str(OUT/'audio-validation.json')],
        [sys.executable,'-X','utf8',str(scripts/'review_film.py'),str(SOURCE),
         '--timeline',str(timeline),'--directory',str(OUT/'export-review')]
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run,checks))
    checksum=digest(SOURCE)
    target=OUT/SOURCE.name
    if target.exists() and digest(target)!=checksum:
        raise RuntimeError('A different v6 deliverable already exists; preserve it and use a new version.')
    if not target.exists():shutil.copy2(SOURCE,target)
    run([str(FFMPEG),'-hide_banner','-nostdin','-y','-v','error',
         '-ss','145','-i',str(target),'-t','60','-c:v','libx264','-crf','18',
         '-preset','fast','-c:a','aac','-b:a','256k','-movflags','+faststart',
         str(OUT/'v6-review-60s.mp4')])
    installation=json.loads((OUT/'edit/asset-installation.json').read_text())
    score=json.loads((PROJECT/'score-review.json').read_text())
    technical=json.loads((OUT/'video-validation.json').read_text())
    checkpoint=json.loads((ROOT/'outputs/animation-pilot/checkpoint-sha256.json').read_text())
    for relative,expected in checkpoint['files'].items():
        if digest(ROOT/relative)!=expected:
            raise RuntimeError('Checkpoint changed: '+relative)
    report={'video':str(target),'sha256':checksum,'seconds':technical['seconds'],
        'format':'1920x1080 24fps H264 BT.709 / stereo 48k AAC',
        'native_image_size':[1536,864],'selected_new_images':len(installation['installed']),
        'full_file_decode_passed':True,'audio_master_comparison_passed':True,
        'music_added':True,'original_score':True,'narration_regenerated':False,
        'voice_identity_issue_resolved':False,'native_generated_video_used':False,
        'encoded_audio_loudness':technical['encoded_audio_measured'],
        'original_checkpoint_files_verified_unchanged':len(checkpoint['files']),
        'user_approved':False,'continuous_viewing_approved':False,'listening_approved':False,
        'status':'technically_validated_separate_workprint',
        'remaining_editorial_issues':['Voice identity/emotion across segments still needs listening and controlled replacement.',
            'Night exposure is improved in selected frames; old/new shot continuity still needs final grading.',
            'Wooden creature/doll grip design remains unresolved.',
            'A few expressions and inherited tiny logos require finishing.',
            'Kaggle I2V tests wait for free GPU quota; no motion model result claimed.']}
    (OUT/'DELIVERY.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('video','seconds','selected_new_images','status')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
