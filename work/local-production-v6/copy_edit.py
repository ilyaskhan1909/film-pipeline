"""Non-destructive clone of the existing editable film, excluding runtime/cache files."""
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'outputs/first-film/edit/remotion'
DESTINATION=ROOT/'outputs/local-production-v6/edit/remotion'
if DESTINATION.exists():
    raise RuntimeError('v6 edit folder already exists; not overwritten.')
DESTINATION.mkdir(parents=True)
for name in ('src','scripts'):
    shutil.copytree(SOURCE/name,DESTINATION/name)
for name in ('package.json','package-lock.json','timeline.json','DESIGN.md'):
    if (SOURCE/name).exists():
        shutil.copy2(SOURCE/name,DESTINATION/name)
shutil.copytree(SOURCE/'public/assets',DESTINATION/'public/assets')
shutil.copy2(SOURCE/'public/title.webm',DESTINATION/'public/title.webm')
sound=DESTINATION/'public/sound'
sound.mkdir()
for name in ('narration.wav','atmosphere.wav','effects.wav'):
    shutil.copy2(SOURCE/'public/sound'/name,sound/name)
(DESTINATION/'lineage.json').write_text(json.dumps({'source_edit':str(SOURCE),
    'source_film':str(ROOT/'outputs/first-film/The_Last_Firework_1080p.mp4'),
    'original_modified':False,'narration_regenerated':False,
    'new_kaggle_i2v_used':False,'production_approved':False},indent=2),encoding='utf-8')
print('CLONED',DESTINATION)
