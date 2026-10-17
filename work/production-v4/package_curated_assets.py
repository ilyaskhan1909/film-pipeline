"""Deliver only image hashes explicitly approved for the actual edit."""
import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('assets',type=Path)
    p.add_argument('--timeline',type=Path,required=True)
    p.add_argument('--review',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    manifest=json.loads((args.assets/'production_manifest.json').read_text(encoding='utf-8'))
    timeline=json.loads(args.timeline.read_text(encoding='utf-8'))
    review=json.loads(args.review.read_text(encoding='utf-8'))
    assert timeline['source_run_id']==review['source_run_id']==manifest['run_id']
    used={shot['id'] for beat in timeline['beats'] for shot in beat['shots']}
    accepted={r['id']:r['sha256'] for r in review['shots'] if r['decision']=='accepted_for_this_edit'}
    originals={shot['id']:shot for shot in manifest['shots']}
    assert used<=accepted.keys(),'An image was not explicitly approved.'
    files={}
    def include(relative):
        file=(args.assets/relative).resolve()
        assert file.is_relative_to(args.assets.resolve()) and file.is_file()
        files[relative]=file
    for ident in sorted(used):
        shot=originals[ident];file=args.assets/shot['image']
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        assert digest==accepted[ident]==shot['generation']['sha256']
        include(shot['image']);include(str(Path(shot['image']).with_suffix('.json')).replace('\\','/'))
    for scene in manifest['scenes']:include(scene['audio'])
    for name in ('shot_plan.json','story.txt','config.json','job.json','environment.json'):
        include(name)
    # The delivery manifest must not point at two omitted alternate images.
    files['source/full_production_manifest.json']=args.assets/'production_manifest.json'
    selected_manifest=copy.deepcopy(manifest)
    selected_manifest.update(kind='curated_editorial_assets',source_pool_images=len(manifest['shots']),
        exported_shots=len(used),shots=[s for s in manifest['shots'] if s['id'] in used],
        quality_status='selected_for_illustrated_edit_not_listening_approved')
    selected_manifest['notes'].append('Only actual timeline images are included; the full source manifest is preserved under source/.')
    selection_file=args.assets.parent/'curated_bundle_manifest.json'
    selection_file.write_text(json.dumps(selected_manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    files['production_manifest.json']=selection_file
    files['quality/editorial-review.json']=args.review
    for name in ('speech_review.json','speech_adjudication.json','subtitle_validation.json','asset_validation.json','vision-observations.json'):
        file=args.assets.parent/name
        if file.is_file():files['quality/'+name]=file
    hashes={name:hashlib.sha256(file.read_bytes()).hexdigest() for name,file in files.items()}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for name,file in files.items():z.write(file,name)
        z.writestr('checksums.json',json.dumps(hashes,indent=2))
        z.writestr('selection.json',json.dumps({'source_run_id':manifest['run_id'],'images':sorted(used),
            'audio_clips':len(manifest['scenes']),'motion_generation':False,'listening_approval':False},indent=2))
    with zipfile.ZipFile(args.output) as z:
        assert z.testzip() is None
        for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    print(json.dumps({'archive':str(args.output),'approved_images':len(used),'audio_clips':len(manifest['scenes']),
        'bytes':args.output.stat().st_size}),flush=True)


if __name__=='__main__':main()
