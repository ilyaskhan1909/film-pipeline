"""Concurrent real GPU comparison; never marks successful execution as quality."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import os
import zipfile
from core import run_logged,atomic_json


def execute_control(run,config,envs):
    run=Path(run)
    def call(engine,device):
        env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(device),PYTHONUNBUFFERED='1',PYTHONPATH=str(run/'scripts'))
        run_logged([envs['image'],str(run/'scripts/control_worker.py'),str(run/'job.json'),engine],
                   run/'logs'/f'control-{engine}.log',env=env,timeout=7200)
    assert config['AVAILABLE_GPUS']==2,'This comparison is configured for two independent T4 devices.'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(call,'klein',0),pool.submit(call,'zimage',1)]
        for future in futures:future.result()
    images=sorted((run/'comparisons/control').glob('*.png'))
    job=json.loads((run/'job.json').read_text(encoding='utf-8'))
    assert len(images)==2*len(job['plan']['control_tasks'])
    report={'run_id':run.name,'tasks':job['plan']['control_tasks'],
            'conditions':'Same prompt, seed, 1536x864, T4 FP32/NF4. No image references. Model-recommended steps/guidance.',
            'images':{p.name:json.loads(p.with_suffix('.json').read_text(encoding='utf-8')) for p in images},
            'quality_approval':False}
    atomic_json(run/'control_report.json',report)
    files=images+[p.with_suffix('.json') for p in images]+[run/'control_report.json',run/'job.json',run/'environment.json']
    files += list((run/'logs').glob('*.log'))+list((run/'scripts').glob('*.py'))
    hashes={p.relative_to(run).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    archive=run/'control_assets.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in files:z.write(p,p.relative_to(run).as_posix())
        z.writestr('checksums.json',json.dumps(hashes,indent=2))
    print(json.dumps({'archive':str(archive),'images':len(images),'quality_approval':False}),flush=True)
    return archive
