"""Portable editable project with evidence; excludes caches, dependencies and tests."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=ROOT/'outputs/first-film')
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--notebook',type=Path,required=True)
    args=parser.parse_args()
    film=args.directory
    edit=film/'edit'
    timeline=json.loads((edit/'remotion/timeline.json').read_text(encoding='utf-8'))
    manifest=json.loads((args.assets/'production_manifest.json').read_text(encoding='utf-8'))
    checks=json.loads((film/'video_validation.json').read_text(encoding='utf-8'))
    assert timeline['source_run_id']==manifest['run_id']
    assert checks['full_file_decode_passed']
    assert checks['source_run_id']==timeline['source_run_id']
    files={}
    used_images={shot['id']+'.png' for beat in timeline['beats'] for shot in beat['shots']}
    def include(file,name):
        assert file.is_file(),str(file)
        assert name not in files,name
        files[name]=file
    for file in (edit/'remotion/src').rglob('*'):
        if file.is_file(): include(file,'remotion/'+file.relative_to(edit/'remotion').as_posix())
    for file in (edit/'remotion/scripts').rglob('*'):
        if file.is_file(): include(file,'remotion/'+file.relative_to(edit/'remotion').as_posix())
    for name in ('package.json','package-lock.json','DESIGN.md','timeline.json','sound_review.json'):
        include(edit/'remotion'/name,'remotion/'+name)
    for file in (edit/'remotion/public').rglob('*'):
        if file.suffix=='.png' and file.parent.name=='assets' and file.name not in used_images:
            continue
        if file.is_file() and file.name not in ('narration-raw48.wav','mix-pre-master.wav','forest-day.wav'):
            include(file,'remotion/'+file.relative_to(edit/'remotion').as_posix())
    for file in (edit/'hyperframes-title').rglob('*'):
        if file.is_file() and file.name not in ('AGENTS.md','CLAUDE.md') and not any(p in ('node_modules','review','.hyperframes') for p in file.relative_to(edit/'hyperframes-title').parts):
            include(file,'hyperframes-title/'+file.relative_to(edit/'hyperframes-title').as_posix())
    include(edit/'asset-credits.json','asset-credits.json')
    include(film/'The_Last_Firework.en.srt','The_Last_Firework.en.srt')
    include(film/'The_Last_Firework.en.json','The_Last_Firework.en.json')
    include(film/'video_validation.json','video_validation.json')
    include(film/'audio_validation.json','audio_validation.json')
    include(film/'PIPELINE.txt','PIPELINE.txt')
    include(film/'export-review/frame-review.json','quality/exported_frame_review.json')
    include(args.notebook,'kaggle/production.ipynb')
    include(ROOT/'work/production-v4/remote-v41/kernel-metadata.json','kaggle/kernel-metadata.json')
    include(args.assets/'story.txt','source/story.txt')
    include(args.assets/'production_manifest.json','source/production_manifest.json')
    include(args.assets/'shot_plan.json','source/shot_plan.json')
    for name in ('speech_review.json','speech_adjudication.json','subtitle_validation.json','vision-observations.json','editorial-review.json','asset_validation.json','notebook_validation.json'):
        file=args.assets.parent/name
        if file.exists(): include(file,'quality/'+name)
    duration=f"{int(timeline['seconds']//60)}:{int(timeline['seconds']%60):02}"
    notes=[f'The Last Firework — {duration}, 1920×1080, 24 fps.',
        'Kaggle создаёт отдельные изображения, сухой голос, таймкоды и проверяемый manifest; генерации движения пока нет.',
        'Remotion: npm ci → npm run preview. Film — итоговый мастер; Dry-Film и Story-beats — сухая речь для правок.',
        'Повторный экспорт: npm run render → remotion/out/The_Last_Firework_1080p.mp4. npm run captions обновляет remotion/public/captions.en.json.',
        'HyperFrames: отдельный редактируемый шестисекундный титр; его прозрачный рендер — remotion/public/title.webm.',
        'Слои звука: narration.wav, atmosphere.wav, effects.wav, master.wav. Субтитры поставляются отдельно.',
        'Кадры 1536×864 масштабированы до 1080p; это не нативная генерация 1080p.',
        'Технические проверки экспорта пройдены. Полное прослушивание и пользовательское одобрение подачи не заявлены.',
        'Видео не загружалось на YouTube. Перед публикацией проверьте звук и авторство исходного текста.',
        'Фотореалистичные вымышленные AI-сцены: при загрузке укажите AI use: Yes. Источник: https://support.google.com/youtube/answer/14328491',
        'Настройки кодирования: https://support.google.com/youtube/answer/1722171']
    readme=film/'DELIVERY.txt'
    readme.write_text('\n'.join(notes)+'\n',encoding='utf-8')
    include(readme,'DELIVERY.txt')
    hashes={name:hashlib.sha256(file.read_bytes()).hexdigest() for name,file in files.items()}
    target=film/'The_Last_Firework_editable.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for name,file in sorted(files.items()): archive.write(file,name)
        archive.writestr('checksums.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for name,digest in hashes.items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest
    print(json.dumps({'archive':str(target),'files':len(files),'bytes':target.stat().st_size,
                      'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
