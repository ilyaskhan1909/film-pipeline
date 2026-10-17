"""Explicit per-shot model routing; verified control outputs can be reused."""
import gc
import hashlib
import json
import shutil
from pathlib import Path
import torch
from image_worker import JOB,C,RUN,SELECT,pipeline,generate

MODELS={'klein':('black-forest-labs/FLUX.2-klein-4B',4,1.0),
        'zimage':('Tongyi-MAI/Z-Image-Turbo',9,0.0)}


def reuse_control(shot,repo):
    for report in Path('/kaggle/input').rglob('control_report.json'):
        file=report.parent/'comparisons/control'/f'{shot["engine"]}-{shot["id"]}.png'
        if not file.exists() or not file.with_suffix('.json').exists():continue
        meta=json.loads(file.with_suffix('.json').read_text(encoding='utf-8'))
        if meta['prompt']!=shot['prompt'] or meta['model']!=repo:continue
        if meta['revision']!=JOB['revisions'][repo] or meta['seed']!=C['SEED']+shot['index']:continue
        if meta['sha256']!=hashlib.sha256(file.read_bytes()).hexdigest():continue
        target=RUN/'images'/f'{shot["id"]}.png'
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(file,target)
        shutil.copy2(file.with_suffix('.json'),target.with_suffix('.json'))
        print('REUSED CONTROL',shot['id'],shot['engine'],flush=True)
        return


def main():
    shots=[JOB['plan']['shots'][i] for i in SELECT]
    assert all(s['engine'] in MODELS and s['refs']==[] for s in shots)
    for engine,(repo,steps,guidance) in MODELS.items():
        group=[s for s in shots if s['engine']==engine]
        if not group:continue
        pipe=pipeline(repo)
        for shot in group:
            reuse_control(shot,repo)
            generate(pipe,shot['prompt'],RUN/'images'/f'{shot["id"]}.png',[],repo,
                     C['SEED']+shot['index'],C['GEN_W'],C['GEN_H'],steps,guidance)
        del pipe
        gc.collect();torch.cuda.empty_cache()
    print('REPAIR IMAGE POOL COMPLETE',flush=True)


if __name__=='__main__':main()
