"""Image-only corrections: no model reload or rewriting of approved dry speech."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import zipfile
from pathlib import Path
from core import atomic_json,run_logged,image_ok


def execute_repair(run,config,envs):
    run=Path(run)
    job=json.loads((run/'job.json').read_text(encoding='utf-8'))
    plan=job['plan']
    pools=min(2,config['AVAILABLE_GPUS'])
    def call(pool):
        child=dict(os.environ,CUDA_VISIBLE_DEVICES=str(pool),PYTHONUNBUFFERED='1',
            PYTHONPATH=str(run/'scripts'),PRODUCTION_POOL=str(pool),PRODUCTION_POOL_COUNT=str(pools))
        run_logged([envs['image'],str(run/'scripts/repair_image_worker.py'),str(run/'job.json')],
                   run/'logs'/f'images-{pool}.log',env=child,timeout=8*3600)
    with ThreadPoolExecutor(max_workers=pools) as executor:
        futures=[executor.submit(call,p) for p in range(pools)]
        for f in futures:f.result()
    shots=[];files=[]
    for index in plan['pilot_shots']:
        shot=dict(plan['shots'][index])
        file=run/'images'/f'{shot["id"]}.png'
        assert image_ok(file),shot['id']
        meta=file.with_suffix('.json')
        generation=json.loads(meta.read_text(encoding='utf-8'))
        assert generation['prompt']==shot['prompt']
        assert generation['sha256']==hashlib.sha256(file.read_bytes()).hexdigest()
        assert generation['model']=={'klein':'black-forest-labs/FLUX.2-klein-4B','zimage':'Tongyi-MAI/Z-Image-Turbo'}[shot['engine']]
        shot.update(image=file.relative_to(run).as_posix(),generation=generation)
        shots.append(shot);files.extend((file,meta))
    manifest={'schema':4,'kind':'production_assets','scope':'pilot','title':plan['title'],
        'run_id':run.name,'source':'iliaskhan/videogenerator-v2-1',
        'story_sha256':hashlib.sha256(plan['story'].encode()).hexdigest(),
        'scenes':[],'shots':shots,'narration_seconds':0,'source_words':len(plan['story'].split()),
        'source_segments':len(plan['segments']),'source_shots':len(plan['shots']),'failures':[],
        'quality_status':'editorial_review_required','notes':['Image-only corrections; original narration unchanged.']}
    atomic_json(run/'production_manifest.json',manifest)
    atomic_json(run/'manifest.json',manifest)
    files += [run/name for name in ('production_manifest.json','manifest.json','job.json','config.json',
        'shot_plan.json','story.txt','environment.json','pipeline_state.json')]
    files += list((run/'scripts').glob('*.py'))+list((run/'logs').glob('*.log'))
    hashes={f.relative_to(run).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    atomic_json(run/'repair_checksums.json',hashes)
    archive=run/'production_assets_REPAIR.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for f in files:z.write(f,f.relative_to(run).as_posix())
        z.writestr('checksums.json',json.dumps(hashes,indent=2))
    print(json.dumps({'archive':str(archive),'shots':len(shots),'audio_regenerated':False,
                     'quality_approval':False}),flush=True)
    return archive
