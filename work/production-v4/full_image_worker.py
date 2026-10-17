"""Lazy model loading, content-valid cache and a two-GPU work-stealing queue."""
import fcntl
import gc
import os
import time
from pathlib import Path
import torch
from image_worker import JOB,C,RUN,DTYPE,REFERENCE_SEEDS,pipeline,generate,signature,valid
from edit_reference_loader import ready as reference_ready,prepare as prepare_reference

MODELS={'klein':('black-forest-labs/FLUX.2-klein-4B',int(C['IMAGE_STEPS']),float(C['IMAGE_GUIDANCE'])),
        'zimage':('Tongyi-MAI/Z-Image-Turbo',int(C.get('Z_IMAGE_STEPS',9)),float(C.get('Z_IMAGE_GUIDANCE',0.0)))}
PLAN=JOB['plan']
POOL=int(os.environ.get('PRODUCTION_POOL','0'))
INDICES=PLAN['pilot_shots'] if C['QUICK_TEST'] else PLAN['export_shots']


def identity(prompt,refs,repo,seed,width,height,steps,guidance):
    import hashlib
    return signature({'prompt':prompt,'refs':[(p.name,hashlib.sha256(p.read_bytes()).hexdigest()) for p in refs],
        'model':repo,'revision':JOB['revisions'][repo],'seed':seed,'size':[width,height],
        'steps':steps,'guidance':guidance,'dtype':str(DTYPE),'schema':4})


def reference_prompt(name):
    assert name in ('mark','chloe','jess'),'Only the actor references are used by this curated plan.'
    return PLAN.get('reference_characters',PLAN['characters'])[name]+(
        ' Waist-up neutral character reference photograph, natural relaxed expression, hands out of frame, plain softly blurred dark green background, diffuse neutral daylight. Realistic skin, no glamour retouch, no accessories, words or logos.')


def main():
    pipe=None
    def get_reference_pipe():
        nonlocal pipe
        if pipe is None:pipe=pipeline(MODELS['klein'][0])
        return pipe
    actor_names=sorted({name for i in INDICES for name in PLAN['shots'][i]['refs']})
    repo,steps,guidance=MODELS['klein']
    for name in actor_names:
        target=RUN/'references'/f'{name}.png'
        if POOL:
            deadline=time.monotonic()+1800
            while not reference_ready(name):
                if time.monotonic()>deadline:raise TimeoutError('Reference not ready: '+name)
                time.sleep(2)
        else:prepare_reference(name,get_reference_pipe)
    (RUN/'claims').mkdir(exist_ok=True)
    cached=generated=0
    for engine,(repo,steps,guidance) in MODELS.items():
        for index in INDICES:
            shot=PLAN['shots'][index]
            if shot.get('engine','klein')!=engine:continue
            refs=[RUN/'references'/f'{name}.png' for name in shot['refs']]
            assert not refs or engine=='klein','Z-Image Turbo cannot accept these image references.'
            target=RUN/'images'/f'{shot["id"]}.png'
            fingerprint=identity(shot['prompt'],refs,repo,C['SEED']+index,C['GEN_W'],C['GEN_H'],steps,guidance)
            if valid(target,fingerprint):cached+=1;continue
            # Advisory locks are released even when a worker crashes. No stale-claim cleanup.
            with (RUN/'claims'/f'{shot["id"]}.lock').open('a') as lock:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:continue
                try:
                    if valid(target,fingerprint):cached+=1;continue
                    if pipe is None:pipe=pipeline(repo)
                    generate(pipe,shot['prompt'],target,refs,repo,C['SEED']+index,
                             C['GEN_W'],C['GEN_H'],steps,guidance)
                    generated+=1
                finally:fcntl.flock(lock,fcntl.LOCK_UN)
        if pipe is not None:
            del pipe;pipe=None;gc.collect();torch.cuda.empty_cache()
    print('IMAGE POOL COMPLETE',POOL,'generated',generated,'valid cached',cached,flush=True)


if __name__=='__main__':main()
