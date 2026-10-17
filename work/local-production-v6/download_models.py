"""Download only pinned public weights; verify size+SHA256, preserve partials."""
import argparse
import concurrent.futures
import hashlib
import json
import shutil
import time
from pathlib import Path
from urllib.parse import quote
import requests

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / 'outputs/local-production-v6/research'
MODELS = ROOT / 'local-comfy/data/models'
SELECTION = [
    ('black-forest-labs/FLUX.2-klein-4b-fp8','flux-2-klein-4b-fp8.safetensors','diffusion_models','fast'),
    ('black-forest-labs/FLUX.2-klein-base-4b-fp8','flux-2-klein-base-4b-fp8.safetensors','diffusion_models','quality'),
    ('Comfy-Org/vae-text-encorder-for-flux-klein-4b','split_files/text_encoders/qwen_3_4b_fp4_flux2.safetensors','text_encoders','shared'),
    ('Comfy-Org/vae-text-encorder-for-flux-klein-4b','split_files/vae/flux2-vae.safetensors','vae','shared'),
]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def manifest():
    result = []
    for repo,remote,category,profile in SELECTION:
        info = json.loads((RESEARCH / (repo.replace('/','--')+'.json')).read_text())
        source = next(s for s in info['siblings'] if s['rfilename']==remote)
        if info.get('cardData',{}).get('license') != 'apache-2.0':
            raise RuntimeError('Unexpected model license; manual review required.')
        result.append({'repo':repo,'revision':info['sha'],'remote_file':remote,
            'file':f'{category}/{Path(remote).name}','size':source['lfs']['size'],
            'sha256':source['lfs']['sha256'],'profile':profile,'license':'Apache-2.0'})
    (RESEARCH/'model-lock.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def download(item):
    target = MODELS / item['file']
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if target.stat().st_size==item['size'] and digest(target)==item['sha256']:
            print('VERIFIED',item['file'],flush=True)
            return
        raise RuntimeError(f'Existing weight mismatch; preserved without overwriting: {target}')
    partial = target.with_suffix(target.suffix+'.partial')
    url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{quote(item['remote_file'],safe='/')}"
    last_progress = 0
    for attempt in range(8):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset == item['size']:
            break
        if offset > item['size']:
            raise RuntimeError('Oversized partial download, preserved for inspection.')
        try:
            with requests.get(url,headers={'Range':f'bytes={offset}-'} if offset else {},
                              stream=True,timeout=(20,60)) as response:
                response.raise_for_status()
                if offset and response.status_code != 206:
                    raise RuntimeError('Server refused ranged resume; partial is preserved.')
                mode = 'ab' if offset else 'wb'
                with partial.open(mode) as stream:
                    for chunk in response.iter_content(4*1024*1024):
                        if not chunk:
                            continue
                        stream.write(chunk)
                        offset += len(chunk)
                        if offset > item['size']:
                            raise RuntimeError('Download exceeded pinned size.')
                        now = time.monotonic()
                        if now-last_progress > 30:
                            print('DOWNLOAD',item['file'],f'{offset/item["size"]:.1%}',flush=True)
                            last_progress = now
            if offset != item['size']:
                raise requests.ConnectionError('Incomplete transfer')
            break
        except requests.RequestException as exc:
            print('RETRY',item['file'],attempt+1,type(exc).__name__,flush=True)
            time.sleep(min(2*(attempt+1),10))
    if not partial.exists() or partial.stat().st_size != item['size']:
        raise RuntimeError('Download not completed; rerun to resume.')
    if digest(partial) != item['sha256']:
        raise RuntimeError('SHA256 mismatch; partial preserved, not installed.')
    partial.replace(target)
    print('INSTALLED',item['file'],item['sha256'],flush=True)
    # Keep original licensing alongside weights, without using credentials.
    for filename in ('LICENSE.md','LICENSE','README.md'):
        response = requests.get(f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{filename}",timeout=30)
        if response.status_code == 200:
            destination = RESEARCH / (item['repo'].replace('/','--')+'--'+filename.replace('.md','.txt'))
            destination.write_bytes(response.content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile',choices=['fast','quality','all'],default='all')
    args = parser.parse_args()
    items = [i for i in manifest() if args.profile=='all' or i['profile'] in ('shared',args.profile)]
    needed = sum(max(0,i['size']-(MODELS/i['file']).with_suffix('.safetensors.partial').stat().st_size)
                 if (MODELS/i['file']).with_suffix('.safetensors.partial').exists()
                 else 0 if (MODELS/i['file']).exists() else i['size'] for i in items)
    if shutil.disk_usage(ROOT).free < needed + 8*1024**3:
        raise RuntimeError('Insufficient free disk for pinned downloads plus safety reserve.')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download,items))
