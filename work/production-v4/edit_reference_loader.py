"""Verified reference recipes, including bootstrapping when no Kaggle Input exists."""
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image
from image_worker import JOB,C,RUN,DTYPE,REFERENCE_SEEDS,signature,valid,generate
from core import atomic_json

PLAN=JOB['plan']
REPO='black-forest-labs/FLUX.2-klein-4B'


def canonical_prompt(name):
    text=PLAN.get('reference_characters',PLAN['characters'])[name]
    if name=='figure':
        text+=' A single full-length practical horror-film creature design reference among tall dark pine trunks. Three-quarter side silhouette, flashlight side lighting, subtle readable bark texture. An elongated wooden effigy rather than a person, face entirely a black void. Its twig fingers are empty; no doll or camp equipment.'
    elif name!='doll':
        text+=' Waist-up neutral character reference photograph, natural relaxed expression, hands out of frame, plain softly blurred dark green background, diffuse neutral daylight. Realistic skin, no glamour retouch, no accessories, words or logos.'
    else:
        text+=' Clear isolated object reference on a plain dark matte surface, diffuse neutral light. Full doll visible, no human hands, no text, no blood.'
    return text


def identity(prompt,refs,seed,width,height):
    return signature({'prompt':prompt,'refs':[(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in refs],
        'model':REPO,'revision':JOB['revisions'][REPO],'seed':seed,'size':[width,height],
        'steps':4,'guidance':1.0,'dtype':str(DTYPE),'schema':4})


def recipe_hash(name):
    return signature({'name':name,'recipe':PLAN['edit_references'][name],
        'revision':JOB['revisions'][REPO],'dtype':str(DTYPE),'schema':1})


def ready(name):
    target=RUN/'references'/f'{name}.png'
    if name not in PLAN.get('edit_references',{}):
        return valid(target,identity(canonical_prompt(name),[],C['SEED']+REFERENCE_SEEDS[name],768,768))
    meta=target.with_suffix('.json')
    if not target.exists() or not meta.exists():return False
    data=json.loads(meta.read_text(encoding='utf-8'))
    return data.get('recipe_fingerprint')==recipe_hash(name) and data.get('sha256')==hashlib.sha256(target.read_bytes()).hexdigest()


def prepare(name,get_pipe,ancestors=()):
    assert name not in ancestors,'Cyclic reference recipe.'
    target=RUN/'references'/f'{name}.png'
    if ready(name):return target
    if name not in PLAN.get('edit_references',{}):
        generate(get_pipe(),canonical_prompt(name),target,[],REPO,
                 C['SEED']+REFERENCE_SEEDS[name],768,768,4,1.0)
        return target
    spec=PLAN['edit_references'][name]
    if spec.get('canonical'):
        base=prepare(spec['canonical'],get_pipe,ancestors+(name,))
    else:
        base=RUN/'references/sources'/f'{name}.png'
        parents=[prepare(p,get_pipe,ancestors+(name,)) for p in spec['refs']]
        fingerprint=identity(spec['prompt'],parents,spec['seed'],*spec['size'])
        if not valid(base,fingerprint):
            for manifest in Path('/kaggle/input').rglob('production_manifest.json'):
                data=json.loads(manifest.read_text(encoding='utf-8'))
                if data.get('run_id')!=spec['source_run_id']:continue
                src=(manifest.parent/spec['source_image']).resolve()
                assert src.is_relative_to(manifest.parent.resolve())
                if not src.exists() or hashlib.sha256(src.read_bytes()).hexdigest()!=spec['source_sha256']:continue
                meta=src.with_suffix('.json')
                candidate=json.loads(meta.read_text(encoding='utf-8'))
                if candidate.get('fingerprint')!=fingerprint:continue
                base.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(src,base);shutil.copy2(meta,base.with_suffix('.json'))
                break
        if not valid(base,fingerprint):
            generate(get_pipe(),spec['prompt'],base,parents,REPO,spec['seed'],*spec['size'],4,1.0)
    with Image.open(base) as im:
        im=im.convert('RGB')
        crop=spec.get('crop')
        if crop:
            left,top,right,bottom=crop
            assert 0<=left<right<=im.width and 0<=top<bottom<=im.height
            im=im.crop(tuple(crop))
        target.parent.mkdir(parents=True,exist_ok=True)
        im.save(target)
    atomic_json(target.with_suffix('.json'),{'recipe_fingerprint':recipe_hash(name),'recipe':spec,
        'source_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'crop':spec.get('crop'),
        'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'model':REPO,
        'revision':JOB['revisions'][REPO],'status':'conditioning_reference_not_delivery_frame'})
    print('REFERENCE PREPARED',name,flush=True)
    return target
