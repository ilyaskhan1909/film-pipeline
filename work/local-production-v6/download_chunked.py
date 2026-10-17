"""Bounded public HTTP ranges, resumable and end-to-end SHA256 verified."""
import concurrent.futures
import json
import shutil
import time
from pathlib import Path
from urllib.parse import quote
import requests
from download_models import MODELS, RESEARCH, ROOT, digest, manifest

CHUNK = 64*1024*1024


def get_chunk(job):
    item,start,end,path = job
    expected = end-start+1
    if path.exists() and path.stat().st_size==expected:
        return path
    for attempt in range(5):
        offset = path.stat().st_size if path.exists() else 0
        if offset>expected:
            raise RuntimeError('Oversized range file, preserved.')
        url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{quote(item['remote_file'],safe='/')}?download=true"
        try:
            with requests.get(url,headers={'Range':f'bytes={start+offset}-{end}'},
                              stream=True,timeout=(20,60)) as response:
                response.raise_for_status()
                if response.status_code!=206 or response.headers.get('Content-Range')!=f'bytes {start+offset}-{end}/{item["size"]}':
                    raise RuntimeError('Server did not honor the exact pinned range.')
                with path.open('ab' if offset else 'wb') as stream:
                    for data in response.iter_content(1024*1024):
                        offset += len(data)
                        if offset>expected:
                            raise RuntimeError('HTTP range exceeds expected length.')
                        stream.write(data)
            if offset==expected:
                return path
        except requests.RequestException:
            time.sleep(min(attempt+1,5))
    raise RuntimeError('Range incomplete; rerun to resume verified-length chunks.')


def install(item):
    target = MODELS/item['file']
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if target.stat().st_size!=item['size'] or digest(target)!=item['sha256']:
            raise RuntimeError('Existing model mismatch; not overwritten.')
        print('VERIFIED',item['file'],flush=True)
        return
    prefix = target.with_suffix(target.suffix+'.partial')
    offset = prefix.stat().st_size if prefix.exists() else 0
    if offset>item['size']:
        raise RuntimeError('Oversized prior partial; not overwritten.')
    chunks = target.parent/(target.name+'.ranges')
    chunks.mkdir(exist_ok=True)
    prior_starts=[int(p.name.split('-')[0]) for p in chunks.glob('*.part')]
    if prior_starts:
        offset=min(offset,min(prior_starts))
    jobs = [(item,start,min(start+CHUNK,item['size'])-1,
             chunks/f'{start}-{min(start+CHUNK,item["size"])-1}.part')
            for start in range(offset,item['size'],CHUNK)]
    completed = offset
    last_report = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(get_chunk,job):job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            path = future.result()
            completed += path.stat().st_size
            if time.monotonic()-last_report>20:
                print('RANGES',item['file'],f'{completed/item["size"]:.1%}',flush=True)
                last_report = time.monotonic()
    # Concatenate into a new artifact, keeping every partial until validation passes.
    assembled = target.with_suffix(target.suffix+'.assembled.partial')
    with assembled.open('wb') as output:
        if prefix.exists():
            with prefix.open('rb') as source:
                remaining=offset
                while remaining:
                    data=source.read(min(remaining,8*1024*1024))
                    if not data:
                        raise RuntimeError('Prior sequential prefix is incomplete.')
                    output.write(data)
                    remaining-=len(data)
        for _,_,_,path in jobs:
            with path.open('rb') as source:
                shutil.copyfileobj(source,output,8*1024*1024)
    if assembled.stat().st_size!=item['size'] or digest(assembled)!=item['sha256']:
        raise RuntimeError('Model integrity mismatch; all download parts preserved.')
    assembled.replace(target)
    print('INSTALLED',item['file'],flush=True)
    for filename in ('LICENSE.md','LICENSE','README.md'):
        response = requests.get(f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{filename}",timeout=30)
        if response.status_code==200:
            (RESEARCH/(item['repo'].replace('/','--')+'--'+filename.replace('.md','.txt'))).write_bytes(response.content)


if __name__=='__main__':
    items=manifest()
    # Fast model + shared encoder/VAE first, then the slower quality candidate.
    order={'fast':0,'shared':1,'quality':2}
    items.sort(key=lambda i:order[i['profile']])
    if shutil.disk_usage(ROOT).free<sum(i['size']*2 for i in items)+8*1024**3:
        raise RuntimeError('Insufficient disk for preserved range downloads and final weights.')
    for item in items:
        install(item)
    print(json.dumps({'all_weights_verified':True,'download_parts_preserved':True}))
