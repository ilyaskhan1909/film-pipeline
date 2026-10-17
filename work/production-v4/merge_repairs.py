"""Keep original generation intact; merge only explicitly regenerated media."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def load(folder,name):
    return json.loads((folder/name).read_text(encoding='utf-8'))


def verify(folder):
    for name,digest in load(folder,'checksums.json').items():
        file=(folder/name).resolve()
        assert file.is_relative_to(folder.resolve()),name
        assert hashlib.sha256(file.read_bytes()).hexdigest()==digest,name


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('full',type=Path)
    parser.add_argument('repair',type=Path)
    parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args()
    assert not args.directory.exists(),'Merge into a NEW directory; originals stay unchanged.'
    verify(args.full);verify(args.repair)
    full,repair=load(args.full,'production_manifest.json'),load(args.repair,'production_manifest.json')
    assert full['scope']=='full' and full['story_sha256']==repair['story_sha256']
    assert not any(f.get('required') for f in full['failures']+repair['failures'])
    shutil.copytree(args.full,args.directory)
    differences=[]
    def copy_media(relative):
        src=(args.repair/relative).resolve()
        dst=(args.directory/relative).resolve()
        assert src.is_relative_to(args.repair.resolve()) and dst.is_relative_to(args.directory.resolve())
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        if src.suffix=='.png':
            shutil.copy2(src.with_suffix('.json'),dst.with_suffix('.json'))
    lookup={s['id']:i for i,s in enumerate(full['shots'])}
    plan=load(args.full,'shot_plan.json')
    for shot in repair['shots']:
        index=lookup[shot['id']]
        previous=full['shots'][index]
        assert previous['beat']==shot['beat'] and previous['index']==shot['index']
        copy_media(shot['image'])
        full['shots'][index]=shot
        replacement={k:v for k,v in shot.items() if k not in ('image','generation')}
        plan['shots'][shot['index']]=replacement
        differences.append({'shot':shot['id'],'before_sha256':previous['generation']['sha256'],
                            'after_sha256':shot['generation']['sha256']})
    for scene in repair['scenes']:
        index=scene['index']
        previous=full['scenes'][index]
        assert previous['index']==index and previous['text']==scene['text']
        assert previous.get('voice_instruction')==scene.get('voice_instruction')
        copy_media(scene['audio'])
        full['scenes'][index]=scene
        differences.append({'beat':index,'previous_take':previous.get('tts_take',0),'new_take':scene.get('tts_take',0)})
    lineage=full.get('repair_lineage',[])+[{'source_run_id':repair['run_id'],'changes':differences}]
    digest=hashlib.sha256(json.dumps(lineage,sort_keys=True).encode()).hexdigest()[:12]
    full['original_run_id']=full.get('original_run_id',full['run_id'])
    full['run_id']=full['original_run_id']+'-edit-'+digest
    full['repair_lineage']=lineage
    full['narration_seconds']=sum(s['audio_duration'] for s in full['scenes'])
    full['quality_status']='editorial_review_required_after_repairs'
    for name,value in [('production_manifest.json',full),('manifest.json',full),('shot_plan.json',plan)]:
        (args.directory/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    state=load(args.directory,'pipeline_state.json')
    state['run_id']=full['run_id'];state['scenes']=full['scenes']
    (args.directory/'pipeline_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.directory/'repair-provenance.json').write_text(json.dumps({'lineage':lineage,
        'warning':'Original scripts/config belong to the original run; exact repair prompts/generation are in manifest sidecars and provenance.',
        'quality_approval':False},indent=2),encoding='utf-8')
    for name in ('config.json','job.json','shot_plan.json'):
        target=args.directory/'repair-evidence'/repair['run_id']/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(args.repair/name,target)
    checks={p.relative_to(args.directory).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in args.directory.rglob('*') if p.is_file() and p.name!='checksums.json' and p.suffix!='.zip'}
    (args.directory/'checksums.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps({'merged':str(args.directory),'run_id':full['run_id'],'changes':differences,
                      'quality_approval':False}),flush=True)


if __name__=='__main__':
    main()
