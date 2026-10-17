"""Runs GPU stages and exports transparent, portable asset evidence."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

from core import atomic_json, load_state, run_logged, selected_scenes, sha256_file

def execute(run, config, envs):
    run = Path(run)
    job = json.loads((run/'job.json').read_text(encoding='utf-8'))
    plan = job['plan']
    failures = []
    def call(name, worker, environment, device, timeout, extra=None):
        child = dict(os.environ, CUDA_VISIBLE_DEVICES=str(device), PYTHONUNBUFFERED='1', PYTHONPATH=str(run/'scripts'))
        child.update(extra or {})
        args = [envs[environment], str(run/'scripts'/worker)]
        args += [name, str(run/'job.json')] if worker == 'worker.py' else [str(run/'job.json')]
        run_logged(args, run/'logs'/f'{name}.log', env=child, timeout=timeout)
    def audio():
        device = 1 if config['AVAILABLE_GPUS'] > 1 else 0
        call('tts', 'worker.py', 'tts', device, 4*3600)
        try:
            call('align', 'worker.py', 'align', device, 2*3600)
        except Exception as exc:
            failures.append({'stage':'alignment', 'error':str(exc)[:500], 'required_before_final_subtitles':True})
        if config['AVAILABLE_GPUS'] > 1 and not config['QUICK_TEST']:
            try:
                images(1)
            except Exception as exc:
                failures.append({'stage':'images-gpu1','error':str(exc)[:500],'required':True})
    def images(pool=0):
        pools = 2 if config['AVAILABLE_GPUS'] > 1 and not config['QUICK_TEST'] else 1
        call(f'images-{pool}', 'image_worker.py', 'image', pool, 8*3600,
             {'PRODUCTION_POOL':str(pool),'PRODUCTION_POOL_COUNT':str(pools)})
    if config['AVAILABLE_GPUS'] > 1:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {'audio':pool.submit(audio), 'images':pool.submit(images)}
            for name,future in futures.items():
                try:
                    future.result()
                except Exception as exc:
                    failures.append({'stage':name, 'error':str(exc)[:500], 'required':True})
    else:
        for name,function in [('audio',audio),('images',images)]:
            try:
                function()
            except Exception as exc:
                failures.append({'stage':name, 'error':str(exc)[:500], 'required':True})

    state = load_state(run)
    scenes = selected_scenes(state,config)
    indices = plan['pilot_shots'] if config['QUICK_TEST'] else range(len(plan['shots']))
    shots = []
    for index in indices:
        shot = dict(plan['shots'][index])
        file = run/'images'/f'{shot["id"]}.png'
        meta = file.with_suffix('.json')
        if file.exists() and meta.exists():
            shot['image'] = file.relative_to(run).as_posix()
            shot['generation'] = json.loads(meta.read_text(encoding='utf-8'))
        else:
            shot['image'] = None
            failures.append({'stage':'image', 'shot':shot['id'], 'required':True})
        shots.append(shot)
    duration = sum(s.get('audio_duration',0) for s in scenes)
    manifest = {'schema':4, 'kind':'production_assets', 'scope':'pilot' if config['QUICK_TEST'] else 'full',
        'title':plan['title'], 'run_id':run.name, 'source':'iliaskhan/videogenerator-v2-1',
        'story_sha256':hashlib.sha256(plan['story'].encode()).hexdigest(),
        'scenes':scenes, 'shots':shots, 'narration_seconds':duration,
        'source_words':len(plan['story'].split()), 'source_segments':len(plan['segments']),
        'source_shots':len(plan['shots']), 'failures':failures,
        'quality_status':'editorial_review_required',
        'notes':['No generated motion; deliberate camera movement will be added during editing.',
                 'Word alignment must be independently checked; zero-length native units may be missing.',
                 'No claim of full viewing or voice-quality approval at asset generation time.']}
    atomic_json(run/'production_manifest.json',manifest)
    atomic_json(run/'manifest.json',dict(manifest, selected_scene_count=len(scenes)))
    eligible = []
    for path in run.rglob('*'):
        if path.is_file() and path.suffix in {'.json','.wav','.png','.txt','.log','.py'}:
            eligible.append(path)
    checksums = {p.relative_to(run).as_posix():sha256_file(p) for p in eligible}
    atomic_json(run/'checksums.json', checksums)
    archive = run/('production_assets_PILOT.zip' if config['QUICK_TEST'] else 'production_assets_FULL.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for path in eligible + [run/'checksums.json']:
            z.write(path,path.relative_to(run).as_posix())
    print(json.dumps({'archive':str(archive),'segments':len(scenes),'shots':len(shots),
                      'dry_narration_seconds':round(duration,2),'failures':failures},ensure_ascii=False),flush=True)
    if any(f.get('required') for f in failures):
        raise RuntimeError('Partial assets preserved; required stages failed: '+str(failures))
    return archive
