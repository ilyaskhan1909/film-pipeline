"""Independent image assets; per-file sidecars allow safe multi-GPU workers."""
import gc
import hashlib
import json
import os
import sys
import time
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from core import atomic_json, image_ok

JOB = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
C = JOB['config']
RUN = Path(JOB['run'])
PLAN = JOB['plan']
REFERENCE_SEEDS = {'chloe':900,'doll':901,'jess':902,'mark':903,'figure':904}
SELECT = PLAN['pilot_shots'] if C['QUICK_TEST'] else list(range(len(PLAN['shots'])))
GPU = int(os.environ.get('PRODUCTION_POOL', '0'))
POOL_COUNT = int(os.environ.get('PRODUCTION_POOL_COUNT', '1'))
SELECT = [i for offset, i in enumerate(SELECT) if offset % POOL_COUNT == GPU]
CAP = torch.cuda.get_device_capability(0)
DTYPE = torch.bfloat16 if CAP[0] >= 8 and torch.cuda.is_bf16_supported() else torch.float32
ATTN = 'sdpa' if CAP[0] >= 8 else 'eager'
torch.set_num_threads(min(4, os.cpu_count() or 1))

def signature(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

def valid(path, fingerprint):
    meta = path.with_suffix('.json')
    if not image_ok(path) or not meta.exists():
        return False
    data = json.loads(meta.read_text(encoding='utf-8'))
    return data.get('fingerprint') == fingerprint and data.get('sha256') == hashlib.sha256(path.read_bytes()).hexdigest()

def snapshot(repo):
    from huggingface_hub import snapshot_download
    revision = JOB['revisions'][repo]
    return snapshot_download(repo, revision=revision,
        allow_patterns=['model_index.json','scheduler/*','tokenizer/*','text_encoder/*','transformer/*','vae/*'],
        ignore_patterns=['*.bin','*.onnx','*.gguf','*.md','*.jpg','*.png'], max_workers=2)

def pipeline(repo):
    from diffusers import DiffusionPipeline, AutoModel, BitsAndBytesConfig as DQ
    from transformers import BitsAndBytesConfig as TQ
    import transformers
    path = snapshot(repo)
    settings = dict(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=DTYPE)
    transformer = AutoModel.from_pretrained(path, subfolder='transformer', quantization_config=DQ(**settings),
                                           dtype=DTYPE, device_map={'':0}, low_cpu_mem_usage=True)
    index = json.loads((Path(path)/'model_index.json').read_text(encoding='utf-8'))
    encoder_class = getattr(transformers, index['text_encoder'][1])
    encoder = encoder_class.from_pretrained(path, subfolder='text_encoder', quantization_config=TQ(**settings),
                    dtype=DTYPE, device_map={'':0}, attn_implementation=ATTN, low_cpu_mem_usage=True)
    pipe = DiffusionPipeline.from_pretrained(path, transformer=transformer, text_encoder=encoder,
                                             dtype=DTYPE, low_cpu_mem_usage=True).to('cuda:0')
    pipe.vae.enable_tiling()
    pipe.set_progress_bar_config(disable=True)
    return pipe

def generate(pipe, prompt, path, refs, repo, seed, width, height, steps, guidance):
    identity = {'prompt':prompt, 'refs':[(p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in refs],
                'model':repo, 'revision':JOB['revisions'][repo], 'seed':seed,
                'size':[width,height], 'steps':steps, 'guidance':guidance, 'dtype':str(DTYPE), 'schema':4}
    fingerprint = signature(identity)
    if valid(path, fingerprint):
        print('CACHED', path.name, flush=True)
        return
    images = []
    for reference in refs:
        with Image.open(reference) as im:
            im = im.convert('RGB')
            im.thumbnail((512,768))
            images.append(im.copy())
    kwargs = dict(prompt=prompt, width=width, height=height, num_inference_steps=steps,
                  guidance_scale=guidance, max_sequence_length=512,
                  generator=torch.Generator(device='cpu').manual_seed(seed))
    if images:
        kwargs['image'] = images
    began = time.monotonic()
    with torch.inference_mode():
        image = pipe(**kwargs).images[0].convert('RGB')
    pixels = np.asarray(image, dtype=np.float32)
    if pixels.std() < 1 or pixels.mean() < 1 or not np.isfinite(pixels).all():
        raise RuntimeError('Uniform or invalid image: '+path.name)
    assert image.size == (width,height), 'Unexpected generated resolution'
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    atomic_json(path.with_suffix('.json'), dict(identity, fingerprint=fingerprint,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(), seconds=round(time.monotonic()-began,2),
        mean=float(pixels.mean()), std=float(pixels.std()), status='generated_not_editorially_approved'))
    print('IMAGE', path.name, width, height, 'seconds', round(time.monotonic()-began,2), flush=True)

def main():
    repo = C['IMAGE_MODEL']
    pipe = pipeline(repo)
    references = RUN/'references'
    # Pool 0 builds refs before a second pool can use them; initial run uses one image worker.
    names = sorted(PLAN['characters']) if not C['QUICK_TEST'] and GPU == 0 else sorted({name for i in SELECT for name in PLAN['shots'][i]['refs']})
    for name in names:
        prompt = PLAN.get('reference_characters',PLAN['characters'])[name]
        if name == 'figure':
            prompt += ' A single full-length practical horror-film creature design reference among tall dark pine trunks. Three-quarter side silhouette, flashlight side lighting, subtle readable bark texture. An elongated wooden effigy rather than a person, face entirely a black void. Its twig fingers are empty; no doll or camp equipment.'
        elif name != 'doll':
            prompt += ' Waist-up neutral character reference photograph, natural relaxed expression, hands out of frame, plain softly blurred dark green background, diffuse neutral daylight. Realistic skin, no glamour retouch, no accessories, words or logos.'
        else:
            prompt += ' Clear isolated object reference on a plain dark matte surface, diffuse neutral light. Full doll visible, no human hands, no text, no blood.'
        target = references/f'{name}.png'
        if GPU > 0:
            deadline = time.monotonic()+1800
            while not (target.exists() and target.with_suffix('.json').exists()):
                if time.monotonic()>deadline: raise TimeoutError('Reference not ready: '+name)
                time.sleep(2)
            continue
        generate(pipe, prompt, target, [], repo, C['SEED']+REFERENCE_SEEDS[name], 768, 768, 4, 1.0)
    for i in SELECT:
        shot = PLAN['shots'][i]
        refs = [references/f'{name}.png' for name in shot['refs']]
        generate(pipe, shot['prompt'], RUN/'images'/f'{shot["id"]}.png', refs, repo,
                 C['SEED']+i, C['GEN_W'], C['GEN_H'], C['IMAGE_STEPS'], C['IMAGE_GUIDANCE'])
    del pipe
    gc.collect()
    torch.cuda.empty_cache()
    if C['QUICK_TEST'] and C.get('COMPARE_BASE'):
        candidate = 'black-forest-labs/FLUX.2-klein-base-4B'
        pipe = pipeline(candidate)
        shot = PLAN['shots'][15]
        generate(pipe, shot['prompt'], RUN/'comparisons'/'mark-base-24.png',
                 [references/'mark.png'], candidate, C['SEED']+15, C['GEN_W'], C['GEN_H'], 24, 4.0)

if __name__ == '__main__':
    main()
