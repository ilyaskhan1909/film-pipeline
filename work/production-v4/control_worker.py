"""Same short physical scene briefs, each model's recommended sampler, no refs."""
import sys
from pathlib import Path
from image_worker import JOB, C, RUN, pipeline, generate

engine=sys.argv[2]
repo={'klein':'black-forest-labs/FLUX.2-klein-4B','zimage':'Tongyi-MAI/Z-Image-Turbo'}[engine]
steps,guidance=(4,1.0) if engine=='klein' else (9,0.0)
pipe=pipeline(repo)
for item in JOB['plan']['control_tasks']:
    target=RUN/'comparisons/control'/f'{engine}-{item["id"]}.png'
    generate(pipe,item['prompt'],target,[],repo,C['SEED']+item['index'],1536,864,steps,guidance)
print('CONTROL ENGINE COMPLETE',engine,flush=True)
