"""Prepare only two reviewed keyframes for a silent motion proof; no remote writes."""
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/local-production-v6'
sys.path.insert(0,str(ROOT/'work/video-roundtrip'))
from contract import digest, identity, save_json, validate_inputs


def main():
    selections=json.loads((OUT/'editorial-selection.json').read_text(encoding='utf-8'))
    selected={s['id']:s for s in selections['candidates'] if s['decision']=='select_for_workprint'}
    installed=json.loads((OUT/'edit/asset-installation.json').read_text())
    hashes={s['id']:s['sha256'] for s in installed['installed']}
    plan=json.loads((ROOT/'outputs/a14b-dual/experiment-plan.json').read_text())
    assets=[];requests=[]
    for index,ident in enumerate(('shot-029','shot-039')):
        if ident not in selected or hashes.get(ident)!=selected[ident]['sha256']:
            continue
        candidate=json.loads((OUT/'assets'/selected[ident]['report']).read_text(encoding='utf-8'))
        if digest(candidate['image'])!=candidate['sha256']:
            raise ValueError('Reviewed image changed before packaging.')
        assets.append({'id':ident,'file':f'frames/{ident}.png','sha256':candidate['sha256'],
            'native_size':[1536,864],'origin':'Local ComfyUI FLUX.2 Klein 4B candidate, visually selected for workprint.',
            'provenance':{'prompt_id':candidate['prompt_id'],'fingerprint':candidate['fingerprint'],
                          'seed':candidate['job']['seed'],'models':candidate['models']},
            'editorial_status':'codex_selected_motion_proof_not_user_approved'})
        prompt=('Locked camera, preserve the exact composition, face identities, age, hair and costumes. '
                'The campers remain still, maintaining the same gaze and expression throughout. '
                'Only subtle natural breathing and very restrained campfire flicker. '
                'The forest and tent remain stationary; same true night lighting. '
                'No dialogue, no lip movement, no new people, props or text. '
                'A single continuous naturalistic live-action shot, no cuts or camera shake.')
        config=dict(plan['config']);config['SEED']=20261005+index
        requests.append({'id':ident+'-motion-v6','asset_id':ident,'prompt':prompt,'config':config,
                         'intent':'Two-second identity/temporal-stability proof, not automatic production approval.'})
    manifest={'schema':'video-inputs/v1','project_id':'the-last-firework-local-v6',
        'assets':assets,'requests':requests,
        'negative_prompt':plan['negative_prompt']+', changing identity, changing facial expression, speaking, duplicate person, waxy skin',
        'profile':{'engine':'wan22-a14b-q8-fp32-two-t4','models':plan['models'],
                   'pins':plan['pins'],'gpu_validated':False},
        'policy':{'kaggle_scope':'silent_image_to_video_only','paid_apis':False,
                  'automatic_edit_insertion':False,'automatic_upscale_interpolation_looping':False,
                  'music_narration_titles_captions':'local_only','original_checkpoint':'read_only',
                  'maximum_batch_worker_seconds':7200,'user_approved':False}}
    manifest['handoff_id']='video-'+identity(manifest)[:16]
    validate_inputs(manifest)
    folder=OUT/'kaggle-inputs'/manifest['handoff_id']
    for asset in assets:
        target=folder/asset['file'];target.parent.mkdir(parents=True,exist_ok=True)
        source=json.loads((OUT/'assets'/selected[asset['id']]['report']).read_text(encoding='utf-8'))['image']
        if target.exists() and digest(target)!=asset['sha256']:
            raise ValueError('Existing handoff frame changed; do not overwrite.')
        shutil.copy2(source,target)
    save_json(folder/'video-inputs.json',manifest)
    save_json(folder/'checksums.json',{p.relative_to(folder).as_posix():digest(p)
        for p in folder.rglob('*') if p.is_file() and p.name!='checksums.json'})
    archive=OUT/'kaggle-inputs'/f'{manifest["handoff_id"]}-inputs.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as bundle:
        for path in sorted(folder.rglob('*')):
            if path.is_file():bundle.write(path,path.relative_to(folder).as_posix())
    save_json(OUT/'kaggle-handoff.json',{'handoff_id':manifest['handoff_id'],'archive':str(archive),
        'manifest':str(folder/'video-inputs.json'),'remote_uploaded':False,'gpu_run_submitted':False,
        'gpu_backend_verified':False,'contains_audio':False,'reason_not_submitted':'GPU quota is zero until 2026-10-10 00:00 UTC.'})
    print('LOCAL ONLY',archive,'requests',len(requests),flush=True)


if __name__=='__main__':main()
