"""Resume voice and images independently, accepting only hash-verified files."""
import copy
import hashlib
import json
import shutil
from pathlib import Path
from core import atomic_json,save_state,sha256_file,wav_ok


def resume(run,config,plan,pins,revisions,input_root=Path('/kaggle/input')):
    run=Path(run)
    state_file=run/'pipeline_state.json'
    state=json.loads(state_file.read_text(encoding='utf-8')) if state_file.exists() else {
        'schema':4,'run_id':run.name,'scenes':copy.deepcopy(plan['segments']),'stages':{}}
    assert state['run_id']==run.name and len(state['scenes'])==len(plan['segments'])
    story_sha=hashlib.sha256(plan['story'].encode()).hexdigest()
    sources=[]
    for manifest in input_root.rglob('production_manifest.json'):
        try:
            old=json.loads(manifest.read_text(encoding='utf-8'))
            if old.get('story_sha256')==story_sha:sources.append((old,manifest.parent))
        except (OSError,ValueError):continue
    # Complete voice first; later, explicitly repaired images supersede old pixels.
    sources.sort(key=lambda pair:(pair[0].get('scope')!='full',str(pair[1])))
    lineage=[]
    for old,source in sources:
        try:
            check_file=source/'repair_checksums.json' if (source/'repair_checksums.json').exists() else source/'checksums.json'
            hashes=json.loads(check_file.read_text(encoding='utf-8'))
            for name,digest in hashes.items():
                file=(source/name).resolve()
                if not file.is_relative_to(source.resolve()) or sha256_file(file)!=digest:
                    raise ValueError('Unsafe or changed input asset')
            settings=json.loads((source/'config.json').read_text(encoding='utf-8'))
            def verified_copy(relative):
                assert relative in hashes,'Undeclared source file: '+relative
                src=(source/relative).resolve();dest=(run/relative).resolve()
                assert src.is_relative_to(source.resolve()) and dest.is_relative_to(run.resolve())
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(src,dest)
            image_count=voice_count=0
            if settings['pins']['image']==pins['image']:
                for shot in old.get('shots',[]):
                    generation=shot.get('generation',{})
                    repo=generation.get('model')
                    if shot['index'] not in plan['export_shots'] or generation.get('revision')!=revisions.get(repo):continue
                    wanted=plan['shots'][shot['index']]
                    expected_model={'klein':'black-forest-labs/FLUX.2-klein-4B','zimage':'Tongyi-MAI/Z-Image-Turbo'}[wanted.get('engine','klein')]
                    if generation.get('prompt')!=wanted['prompt'] or repo!=expected_model:continue
                    if not shot.get('image') or shot['image'] not in hashes:continue
                    verified_copy(shot['image'])
                    verified_copy(str(Path(shot['image']).with_suffix('.json')).replace('\\','/'))
                    image_count+=1
                for file in (source/'references').glob('*.png'):
                    image_relative=file.relative_to(source).as_posix()
                    meta_relative=file.with_suffix('.json').relative_to(source).as_posix()
                    # Kaggle's directory output can contain non-exported cached files.
                    # Undeclared leftovers are ignored, never copied or treated as a bad whole source.
                    if image_relative not in hashes or meta_relative not in hashes:continue
                    meta=json.loads(file.with_suffix('.json').read_text(encoding='utf-8'))
                    if meta.get('revision')!=revisions.get(meta.get('model')):continue
                    verified_copy(image_relative)
                    verified_copy(meta_relative)
            audio_keys=('TTS_MODEL','TTS_ENGINE','SPEAKER','LANGUAGE','SEED')
            voice_compatible=(all(settings['config'].get(k)==config[k] for k in audio_keys)
                and settings['pins']['tts']==pins['tts']
                and settings['revisions'].get(config['TTS_MODEL'])==revisions.get(config['TTS_MODEL']))
            if voice_compatible:
                for scene in old.get('scenes',[]):
                    target=state['scenes'][scene['index']]
                    if scene['text']!=target['text'] or scene.get('voice_instruction')!=target.get('voice_instruction'):continue
                    if scene.get('tts_take',0)!=config.get('TTS_TAKES',{}).get(str(scene['index']),0):continue
                    if not scene.get('audio') or not wav_ok(source/scene['audio']):continue
                    verified_copy(scene['audio']);target.update(scene);voice_count+=1
                    align_model=config['ALIGN_MODEL']
                    if settings['pins']['align']!=pins['align'] or settings['revisions'].get(align_model)!=revisions.get(align_model):
                        target['words']=[];target.pop('alignment_source',None)
            lineage.append({'source_run_id':old['run_id'],'images_imported':image_count,'voice_imported':voice_count})
            print('Resumed verified independent assets',old['run_id'],image_count,'images',voice_count,'voice clips',flush=True)
        except Exception as exc:
            print('Resume source skipped:',source.name,type(exc).__name__,flush=True)
    save_state(run,state)
    atomic_json(run/'resume_lineage.json',{'sources':lineage,
        'note':'Every imported image must still pass its own complete generation fingerprint.'})

