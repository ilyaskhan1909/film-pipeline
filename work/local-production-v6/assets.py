"""Native Comfy core graphs, pinned provenance, bounded batches and no auto approval."""
import argparse
import hashlib
import json
import shutil
import sys
import threading
import time
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/local-production-v6'
COMFY=ROOT/'local-comfy'
sys.path.insert(0,str(COMFY))
from comfy_client import call, run_graph, save
from download_models import digest

FOCUS=['shot-015','shot-017','shot-019','shot-023','shot-029',
       'shot-030','shot-037','shot-038','shot-039','shot-041','shot-060','shot-062']
REPAIR=('Use image 1 as the exact scene, composition and camera reference. '
        'The subsequent reference images establish the identities of the fictional campers. '
        'Create a refined naturalistic live-action horror-film frame of this SAME moment. '
        'Preserve each person\'s identity, age, hairstyle, clothing, body position, gaze, '
        'expression and all named props. Correct facial anatomy, eyes, eyelids, teeth and '
        'hands where visible, without cosmetic beautification or changing the person. '
        'Keep skin textured and physically plausible, without waxy smoothing. '
        'The campfire is the motivated warm key light; this is real night, with a nearly '
        'black sky and restrained neutral-cool fill, NOT bright blue twilight. '
        'Keep faces readable and nuanced, with retained highlight detail and deep readable '
        'shadows. Preserve the lake/forest geography and exact number of people. '
        'No extra limbs, no duplicated people, no added text, logos, collage or borders. ')
PROP_PROMPTS={
    'shot-060':('Refine image 1 as a restrained live-action horror-film NIGHT frame. '
        'Preserve its exact tree positions, framing, and every existing extremely tall '
        'thin dead-wood effigy in its same position. The figures are inhuman rough '
        'bark and branches, never human skin or clothed actors. Keep elongated narrow '
        'bodies and twig limbs, small entirely featureless matte-black heads, no faces. '
        'Make the wood look physically real, irregular, weathered and partly occluded '
        'by the pines, not smooth carved mannequins or a neat display of sculptures. '
        'Deep natural black night, only very low motivated cold offscreen flashlight '
        'illumination with readable bark detail and restrained reflections. No bright '
        'blue twilight, no sky glow, no airborne beam, no added torch or visible hand. '
        'Preserve all figures and story geography. No text, logos, additional figures, '
        'gore, blood, light-emitting eyes, cartoons, artificial fog or visual-effects flare.'),
    'shot-062':('Refine image 1 as a practical live-action horror prop close-up. '
        'Keep ONE tiny crude tan burlap doll and ONE dark dead-wood branch hand. '
        'The hand has four slender irregular solid bark-covered twig fingers, curled '
        'around only the upper cloth arm of the much smaller doll, visibly holding it '
        'suspended. Not a leafy branch or a decorative wreath behind the doll. '
        'Preserve the doll identity: rectangular sack head, two mismatched black button '
        'eyes, clumsy straight black cross-stitch mouth, plain tan body, closed fabric '
        'mittens holding exactly one thumbnail-sized torn cobalt-blue woven shirt '
        'scrap at its lap. Weathered uneven handmade seams, not a cute plush mascot, '
        'no smile, no eyebrows, no living face. Keep the blue scrap clearly readable '
        'and made of woven shirt fabric rather than glowing plastic. Real rough wood '
        'and frayed opaque cloth, low cold sidelight, softly defocused dark forest. '
        'One deliberate macro composition. No extra doll, human hand, extra fingers, '
        'blood, gore, text, logo, borders or added objects.')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_copy(source,role):
    checksum=sha(source)
    name=f'v6-{role}-{checksum[:12]}.png'
    destination=COMFY/'data/input'/name
    if destination.exists() and sha(destination)!=checksum:
        raise RuntimeError('Input collision; existing file preserved.')
    if not destination.exists():
        shutil.copy2(source,destination)
    with Image.open(source) as image:
        width,height=image.size
    return {'image':name,'source':str(source),'sha256':checksum,'size':[width,height]}


def graph(job,profile):
    width,height=job['size']
    quality=profile=='quality'
    nodes={
        '1':{'class_type':'UNETLoader','inputs':{'unet_name':
            'flux-2-klein-base-4b-fp8.safetensors' if quality else 'flux-2-klein-4b-fp8.safetensors','weight_dtype':'default'}},
        '2':{'class_type':'CLIPLoader','inputs':{'clip_name':'qwen_3_4b_fp4_flux2.safetensors','type':'flux2','device':'default'}},
        '3':{'class_type':'VAELoader','inputs':{'vae_name':'flux2-vae.safetensors'}},
        '4':{'class_type':'CLIPTextEncode','inputs':{'clip':['2',0],'text':job['prompt']}},
        '5':({'class_type':'CLIPTextEncode','inputs':{'clip':['2',0],'text':''}} if quality else
             {'class_type':'ConditioningZeroOut','inputs':{'conditioning':['4',0]}}),
        '6':{'class_type':'EmptyFlux2LatentImage','inputs':{'width':width,'height':height,'batch_size':1}},
        '7':{'class_type':'RandomNoise','inputs':{'noise_seed':job['seed']}},
        '8':{'class_type':'KSamplerSelect','inputs':{'sampler_name':'euler'}},
        '9':{'class_type':'Flux2Scheduler','inputs':{'steps':28 if quality else 4,'width':width,'height':height}},
        '11':{'class_type':'SamplerCustomAdvanced','inputs':{'noise':['7',0],'guider':['10',0],
            'sampler':['8',0],'sigmas':['9',0],'latent_image':['6',0]}},
        '12':{'class_type':'VAEDecodeTiled','inputs':{'samples':['11',0],'vae':['3',0],
            'tile_size':512,'overlap':64,'temporal_size':64,'temporal_overlap':8}},
        '13':{'class_type':'SaveImage','inputs':{'images':['12',0],
            'filename_prefix':f'v6/{job["id"]}-{profile}-r{job["prompt_revision"]}'}},
    }
    positive,negative=['4',0],['5',0]
    for index,reference in enumerate(job['references']):
        start=20+index*5
        load,scale,encode,pos,neg=map(str,range(start,start+5))
        # Scene reference is 0.59 MP; identity references are kept smaller to bound VRAM.
        rw,rh=reference['size']
        factor=(.60*1024*1024/(rw*rh))**.5 if index==0 else (.30*1024*1024/(rw*rh))**.5
        rw,rh=max(32,round(rw*factor/32)*32),max(32,round(rh*factor/32)*32)
        nodes[load]={'class_type':'LoadImage','inputs':{'image':reference['image']}}
        nodes[scale]={'class_type':'ImageScale','inputs':{'image':[load,0],
            'upscale_method':'lanczos','width':rw,'height':rh,'crop':'disabled'}}
        nodes[encode]={'class_type':'VAEEncode','inputs':{'pixels':[scale,0],'vae':['3',0]}}
        nodes[pos]={'class_type':'ReferenceLatent','inputs':{'conditioning':positive,'latent':[encode,0]}}
        nodes[neg]={'class_type':'ReferenceLatent','inputs':{'conditioning':negative,'latent':[encode,0]}}
        positive,negative=[pos,0],[neg,0]
    nodes['10']={'class_type':'CFGGuider','inputs':{'model':['1',0],'positive':positive,
                                                'negative':negative,'cfg':5.0 if quality else 1.0}}
    return nodes


def prepare():
    plan=json.loads((ROOT/'outputs/first-film/curated/assets/shot_plan.json').read_text(encoding='utf-8'))
    by_id={shot['id']:shot for shot in plan['shots']}
    jobs=[]
    for index,name in enumerate(FOCUS):
        shot=by_id[name]
        references=[input_copy(ROOT/'outputs/first-film/curated/assets/images'/f'{name}.png',name)]
        for person in shot['refs']:
            if person in ('mark','chloe','jess'):
                references.append(input_copy(ROOT/'outputs/first-film/curated/assets/references'/f'{person}.png','ref-'+person))
        intent=shot['prompt'].split('Reference images define appearance and clothing only;')[0].strip()
        revision=3 if name=='shot-038' else 2
        correction=(' Exactly ONE person is visible: Jess, in a tight chest-up close-up. '
                    'Image 2 is a face-identity guide for that SAME single person, NOT '
                    'another person to include. No second Jess, no foreground visitor, '
                    'no cup or added hand gesture. Preserve the original head framing. '
                    'Her mouth is slightly parted, brows gently tense; she is not smiling. '
                    'Remove any garment branding. ') if name=='shot-038' else ''
        jobs.append({'id':name,'seed':20261005+index,'size':[1536,864],'prompt_revision':revision,
            'prompt':PROP_PROMPTS.get(name,REPAIR+correction+'Authored shot intent: '+intent),
            'references':references,'editorial_approved':False})
    save(OUT/'asset-jobs.json',jobs)
    for job in jobs:
        for profile in ('fast','quality'):
            save(OUT/'workflows'/f'{job["id"]}-{profile}-r{job["prompt_revision"]}-api.json',graph(job,profile))
    print('PREPARED',len(jobs),'identity-preserving jobs; original assets are read-only.')


def run(profile,ids):
    jobs=json.loads((OUT/'asset-jobs.json').read_text())
    lock=json.loads((OUT/'research/model-lock.json').read_text())
    needed=[item for item in lock if item['profile'] in (profile,'shared')]
    for item in needed:
        path=COMFY/'data/models'/item['file']
        if not path.exists() or path.stat().st_size!=item['size']:
            raise RuntimeError('Required verified model not installed: '+item['file'])
        if digest(path)!=item['sha256']:
            raise RuntimeError('Model checksum changed; refusing inference: '+item['file'])
    if call('/queue').get('queue_running') or call('/queue').get('queue_pending'):
        raise RuntimeError('Another ComfyUI task is queued; no queue was changed.')
    for job in jobs:
        if ids and job['id'] not in ids:
            continue
        for reference in job['references']:
            copied=COMFY/'data/input'/reference['image']
            if sha(copied)!=reference['sha256'] or sha(Path(reference['source']))!=reference['sha256']:
                raise RuntimeError('Reference bytes changed; refusing stale provenance.')
        workflow=graph(job,profile)
        fingerprint=hashlib.sha256(json.dumps({'workflow':workflow,'models':needed,
            'source_checksums':[r['sha256'] for r in job['references']]},sort_keys=True).encode()).hexdigest()
        suffix=f'{job["id"]}-{profile}-r{job["prompt_revision"]}'
        report_path=OUT/'assets'/f'{suffix}.json'
        if report_path.exists():
            previous=json.loads(report_path.read_text())
            if previous['fingerprint']==fingerprint and sha(Path(previous['image']))==previous['sha256']:
                print('CACHED',job['id'],profile,flush=True)
                continue
            raise RuntimeError('Existing candidate differs; create a new version instead.')
        workflow_path=OUT/'workflows'/f'{suffix}-api.json'
        save(workflow_path,workflow)
        started=time.monotonic()
        print('GENERATING',job['id'],profile,flush=True)
        samples=[]
        stop=threading.Event()
        def monitor():
            while not stop.is_set():
                try:
                    info=call('/system_stats')
                    samples.append({'elapsed':round(time.monotonic()-started,2),
                        'ram_free':info['system']['ram_free'],'devices':info['devices']})
                except Exception as exc:
                    samples.append({'monitor_error':type(exc).__name__})
                stop.wait(2)
        observer=threading.Thread(target=monitor,daemon=True)
        observer.start()
        try:
            result=run_graph(workflow_path,1800)
        finally:
            stop.set()
            observer.join(timeout=1)
            save(OUT/'telemetry'/f'{suffix}.json',list(samples))
        if not result['completed'] or len(result['outputs'])!=1:
            raise RuntimeError('Comfy did not return one completed image.')
        source=Path(result['outputs'][0]['file'])
        with Image.open(source) as image:
            pixels=np.asarray(image.convert('RGB'))
            if list(image.size)!=job['size'] or pixels.std()<2:
                raise RuntimeError('Invalid generated image dimensions/contrast.')
        destination=OUT/'assets'/source.name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
        save(report_path,{'id':job['id'],'profile':profile,'image':str(destination),
            'sha256':sha(destination),'fingerprint':fingerprint,'prompt_id':result['prompt_id'],
            'seconds':round(time.monotonic()-started,2),'job':job,'models':needed,
            'telemetry':str(OUT/'telemetry'/f'{suffix}.json'),
            'image_stats':{'mean':float(pixels.mean()),'std':float(pixels.std())},
            'editorial_approved':False,'automatic_kaggle_upload':False})
        print('CANDIDATE',destination.name,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--profile',choices=['fast','quality'],default='fast')
    parser.add_argument('--shots',nargs='*')
    args=parser.parse_args()
    prepare() if args.action=='prepare' else run(args.profile,args.shots)
