"""Read-only model/core-node discovery from official sources and our local Comfy."""
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/local-production-v6/research'
OUT.mkdir(parents=True,exist_ok=True)
repos = ['black-forest-labs/FLUX.2-klein-4b-fp8',
         'black-forest-labs/FLUX.2-klein-base-4b-fp8',
         'Comfy-Org/vae-text-encorder-for-flux-klein-4b',
         'Comfy-Org/z_image_turbo', 'Qwen/Qwen-Image-2.1']
for repo in repos:
    response = requests.get(f'https://huggingface.co/api/models/{repo}',
                            params={'blobs':'true'},timeout=40)
    if response.status_code != 200:
        print(repo, response.status_code)
        continue
    info = response.json()
    (OUT / (repo.replace('/','--')+'.json')).write_text(json.dumps(info,indent=2),encoding='utf-8')
    weights = [{'file':s['rfilename'],'size':s.get('size'), 'lfs':s.get('lfs')}
               for s in info.get('siblings',[]) if s['rfilename'].endswith('.safetensors')]
    print(json.dumps({'repo':repo,'revision':info['sha'],'weights':weights,
                      'license':info.get('cardData',{}).get('license')}))
nodes = requests.get('http://127.0.0.1:8188/object_info',timeout=30).json()
(OUT/'comfy-object-info.json').write_text(json.dumps(nodes,indent=2),encoding='utf-8')
names = ['UNETLoader','CLIPLoader','VAELoader','CLIPTextEncode','EmptyFlux2LatentImage',
         'Flux2Scheduler','KSamplerSelect','SamplerCustomAdvanced','BasicGuider',
         'CFGGuider','RandomNoise','VAEDecode','VAEDecodeTiled','ReferenceLatent','VAEEncode',
         'ImageScale','ImageCompositeMasked','LoadImage','SaveImage']
for name in names:
    print(json.dumps({'node':name, 'schema':nodes.get(name,{}).get('input')}))
print('QWEN21_NODES',[n for n in nodes if 'Qwen' in n and ('2' in n or '21' in n)])
