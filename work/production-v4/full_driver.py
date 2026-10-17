"""Complete curated asset production; media exists independently of an edit."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import zipfile
from pathlib import Path
from core import atomic_json,load_state,run_logged,selected_scenes,sha256_file,wav_ok,image_ok


def execute_full(run,config,envs):
    run=Path(run)
    plan=json.loads((run/'job.json').read_text(encoding='utf-8'))['plan']
    pools=min(2,config['AVAILABLE_GPUS'])
    failures=[]
    def call(stage,worker,environment,device):
        child=dict(os.environ,CUDA_VISIBLE_DEVICES=str(device),PYTHONUNBUFFERED='1',
            PYTHONPATH=str(run/'scripts'),PRODUCTION_POOL=str(device))
        cmd=[envs[environment],str(run/'scripts'/worker)]
        cmd += [stage,str(run/'job.json')] if worker=='worker.py' else [str(run/'job.json')]
        run_logged(cmd,run/'logs'/f'{stage}.log',env=child,timeout=8*3600)
    def audio_then_images():
        device=1 if pools>1 else 0
        call('tts','worker.py','tts',device)
        call('align','worker.py','align',device)
        if pools>1:call('images-1','full_image_worker.py','image',1)
    def images():call('images-0','full_image_worker.py','image',0)
    if pools>1:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures={'audio/images-1':pool.submit(audio_then_images),'images-0':pool.submit(images)}
            for name,f in futures.items():
                try:f.result()
                except Exception as exc:failures.append({'stage':name,'error':str(exc)[:500],'required':True})
    else:
        for name,fn in [('audio',audio_then_images),('images',images)]:
            try:fn()
            except Exception as exc:failures.append({'stage':name,'error':str(exc)[:500],'required':True})
    scenes=selected_scenes(load_state(run),config)
    shots=[];media=[]
    indices=plan['pilot_shots'] if config['QUICK_TEST'] else plan['export_shots']
    for index in indices:
        shot=dict(plan['shots'][index]);file=run/'images'/f'{shot["id"]}.png'
        if image_ok(file) and file.with_suffix('.json').exists():
            generation=json.loads(file.with_suffix('.json').read_text(encoding='utf-8'))
            if generation['prompt']!=shot['prompt'] or generation['sha256']!=sha256_file(file):
                failures.append({'stage':'image cache validation','shot':shot['id'],'required':True})
            shot.update(image=file.relative_to(run).as_posix(),generation=generation)
            media.extend((file,file.with_suffix('.json')))
        else:
            shot['image']=None;failures.append({'stage':'image','shot':shot['id'],'required':True})
        shots.append(shot)
    for scene in scenes:
        file=run/scene.get('audio','missing.wav')
        if not wav_ok(file):failures.append({'stage':'audio','index':scene['index'],'required':True})
        else:media.append(file)
        if not scene.get('words'):failures.append({'stage':'alignment','index':scene['index'],'required':True})
    manifest={'schema':4,'kind':'production_assets','scope':'pilot' if config['QUICK_TEST'] else 'full',
        'title':plan['title'],'run_id':run.name,'source':'iliaskhan/videogenerator-v2-1',
        'story_sha256':hashlib.sha256(plan['story'].encode()).hexdigest(),'scenes':scenes,'shots':shots,
        'narration_seconds':sum(s.get('audio_duration',0) for s in scenes),
        'source_words':len(plan['story'].split()),'source_segments':len(plan['segments']),
        'source_shots':len(plan['shots']),'exported_shots':len(shots),'failures':failures,
        'quality_status':'editorial_review_required',
        'notes':['Only the curated shot selection is exported; rejected/unused frames are excluded.',
                 'No generated motion. Dry voice and PNGs remain separate for local editing.',
                 'ASR/VLM and continuous audiovisual approval are not implied by GPU completion.']}
    atomic_json(run/'production_manifest.json',manifest);atomic_json(run/'manifest.json',manifest)
    actors={name for index in indices for name in plan['shots'][index]['refs']}
    for name in sorted(actors):
        for suffix in ('.png','.json'):
            file=run/'references'/(name+suffix)
            if file.exists():media.append(file)
    files=media+[run/name for name in ('production_manifest.json','manifest.json','config.json','job.json',
            'environment.json','pipeline_state.json','story.txt','shot_plan.json','resume_lineage.json')]
    files+=list((run/'scripts').glob('*.py'))+list((run/'logs').glob('*.log'))
    hashes={p.relative_to(run).as_posix():sha256_file(p) for p in files}
    atomic_json(run/'checksums.json',hashes)
    archive=run/('production_assets_PILOT.zip' if config['QUICK_TEST'] else 'production_assets_FULL.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in files+[run/'checksums.json']:z.write(p,p.relative_to(run).as_posix())
    print(json.dumps({'archive':str(archive),'segments':len(scenes),'shots':len(shots),
        'dry_narration_seconds':manifest['narration_seconds'],'failures':failures}),flush=True)
    if failures:raise RuntimeError('Partial assets preserved; required checks failed: '+str(failures))
    return archive
