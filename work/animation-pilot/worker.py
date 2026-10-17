"""Isolated Kaggle workers: depth/text preparation, then NF4 FP32 Wan2.2 I2V."""
import gc
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from common import atomic_json, control_frames, encode_frames, fingerprint, inspect_video, sha256


def load_job(path):
    job = json.loads(Path(path).read_text(encoding='utf-8'))
    return job, Path(job['run']), job['config']


def model_snapshot(job, key):
    from huggingface_hub import snapshot_download
    record = job['models'][key]
    patterns = ['model_index.json', 'scheduler/*', 'tokenizer/*', 'text_encoder/*',
                'transformer/*', 'vae/*'] if key == 'wan' else None
    return snapshot_download(record['repo'], revision=record['revision'],
        allow_patterns=patterns, ignore_patterns=['*.md', '*.jpg', '*.png', '*.bin', '*.onnx'],
        max_workers=4, cache_dir=job['model_cache'])


def quantization(kind):
    if kind == 'transformers':
        from transformers import BitsAndBytesConfig
    else:
        from diffusers import BitsAndBytesConfig
    return BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float32)


def prepare(job_path):
    job, run, config = load_job(job_path)
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation, T5TokenizerFast, UMT5EncoderModel
    # No simultaneous resident depth/T5/diffusion models.
    depth_path = model_snapshot(job, 'depth')
    processor = AutoImageProcessor.from_pretrained(depth_path)
    depth_model = AutoModelForDepthEstimation.from_pretrained(depth_path, dtype=torch.float32).to('cuda').eval()
    for shot in job['shots']:
        ident = shot['id']
        image = Image.open(run/'source'/f'{ident}.png').convert('RGB')
        inputs = processor(images=image, return_tensors='pt').to('cuda')
        with torch.inference_mode():
            predicted = depth_model(**inputs).predicted_depth
            predicted = torch.nn.functional.interpolate(predicted.unsqueeze(1),
                size=(config['HEIGHT'], config['WIDTH']), mode='bicubic', align_corners=False)[0, 0]
        array = predicted.float().cpu().numpy()
        if not np.isfinite(array).all():
            raise ValueError('Non-finite depth map.')
        low, high = np.percentile(array, [2, 98])
        depth = np.clip((array - low) / max(1e-6, high - low), 0, 1).astype(np.float32)
        np.save(run/'depth'/f'{ident}.npy', depth)
        Image.fromarray(np.round(depth*65535).astype(np.uint16)).save(run/'depth'/f'{ident}.png')
        image = image.resize((config['WIDTH'], config['HEIGHT']), Image.Resampling.LANCZOS)
        for mode, field in [('static', None), ('depth', depth)]:
            target = run/'controls'/f'{ident}-{mode}.mp4'
            encode_frames(control_frames(image, config['FRAMES'], field), target, config['FPS'])
            report, samples = inspect_video(target, config, image)
            report['kind'] = 'static_reference' if field is None else 'depth_guided_backward_warp'
            report['layer_separation'] = False
            atomic_json(target.with_suffix('.json'), report)
        print(f'CONTROL {ident}: depth + static, {config["WIDTH"]}x{config["HEIGHT"]}', flush=True)
    del depth_model, processor, inputs, predicted
    gc.collect()
    torch.cuda.empty_cache()
    snapshot = model_snapshot(job, 'wan')
    tokenizer = T5TokenizerFast.from_pretrained(snapshot, subfolder='tokenizer')
    encoder = UMT5EncoderModel.from_pretrained(snapshot, subfolder='text_encoder', dtype=torch.float32,
        device_map={'': 0}, quantization_config=quantization('transformers'), attn_implementation='eager').eval()
    from diffusers.pipelines.wan.pipeline_wan import prompt_clean
    prompts = {s['id']: s['prompt'] for s in job['shots']}
    prompts['negative'] = job['negative_prompt']
    for ident, prompt in prompts.items():
        tokens = tokenizer(prompt_clean(prompt), padding='max_length', max_length=config['MAX_SEQUENCE'],
            truncation=True, add_special_tokens=True, return_attention_mask=True, return_tensors='pt').to('cuda')
        length = int(tokens.attention_mask.sum().item())
        with torch.inference_mode():
            embedding = encoder(tokens.input_ids, tokens.attention_mask).last_hidden_state.float()
            embedding[:, length:] = 0
        if not torch.isfinite(embedding).all().item():
            raise ValueError('Non-finite text embedding.')
        torch.save(embedding.cpu(), run/'embeddings'/f'{ident}.pt')
        print(f'EMBEDDING {ident}: {length} tokens', flush=True)
    atomic_json(run/'prepared.json', {'job_fingerprint': job['fingerprint'], 'snapshot': snapshot,
        'depth_revision': job['models']['depth']['revision'], 'status': 'prepared'})


def install_chunked_attention(chunk_size):
    # Inference-only exact query splitting, not a sparse/approximate attention algorithm.
    # Patching is confined to this disposable worker process. Causal/dropout attention is untouched.
    original = torch.nn.functional.scaled_dot_product_attention

    def chunked(query, key, value, attn_mask=None, dropout_p=0.0, is_causal=False, **kwargs):
        if is_causal or dropout_p or query.shape[-2] <= chunk_size:
            return original(query, key, value, attn_mask=attn_mask, dropout_p=dropout_p,
                            is_causal=is_causal, **kwargs)
        pieces = []
        for start in range(0, query.shape[-2], chunk_size):
            mask = attn_mask
            if mask is not None and mask.ndim >= 2 and mask.shape[-2] == query.shape[-2]:
                mask = mask[..., start:start+chunk_size, :]
            pieces.append(original(query[..., start:start+chunk_size, :], key, value,
                attn_mask=mask, dropout_p=0.0, is_causal=False, **kwargs))
        return torch.cat(pieces, dim=-2)

    torch.nn.functional.scaled_dot_product_attention = chunked
    return original


def generate(job_path, tasks_path):
    job, run, config = load_job(job_path)
    tasks = json.loads(Path(tasks_path).read_text(encoding='utf-8'))
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline, WanTransformer3DModel
    snapshot = json.loads((run/'prepared.json').read_text())['snapshot']
    install_chunked_attention(config['ATTENTION_QUERY_CHUNK'])
    transformer = WanTransformer3DModel.from_pretrained(snapshot, subfolder='transformer',
        torch_dtype=torch.float32, device_map={'': 0}, quantization_config=quantization('diffusers'))
    vae = AutoencoderKLWan.from_pretrained(snapshot, subfolder='vae', torch_dtype=torch.float32)
    vae.enable_tiling()
    vae.enable_slicing()
    pipe = WanImageToVideoPipeline.from_pretrained(snapshot, transformer=transformer, vae=vae,
        text_encoder=None, tokenizer=None, torch_dtype=torch.float32)
    vae.to('cuda')
    transformer.set_attention_backend('native')
    pipe.set_progress_bar_config(disable=True)
    negatives = torch.load(run/'embeddings/negative.pt', weights_only=True).to('cuda')
    lookup = {s['id']: s for s in job['shots']}
    for task in tasks:
        ident, seed = task['id'], task['seed']
        target = run/'clips'/f'{ident}-seed-{seed}.mp4'
        signature = fingerprint({'job': job['fingerprint'], 'task': task})
        sidecar = target.with_suffix('.json')
        if target.exists() and sidecar.exists():
            previous = json.loads(sidecar.read_text())
            if previous.get('fingerprint') == signature and previous['sha256'] == sha256(target):
                print(f'CACHED {target.name}', flush=True)
                continue
        image = Image.open(run/'source'/f'{ident}.png').convert('RGB').resize(
            (config['WIDTH'], config['HEIGHT']), Image.Resampling.LANCZOS)
        embedding = torch.load(run/'embeddings'/f'{ident}.pt', weights_only=True).to('cuda')
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()

        def progress(pipeline, step, timestep, values):
            if not torch.isfinite(values['latents']).all().item():
                raise ValueError('Non-finite denoising latents; clip rejected.')
            if step == 0 or (step+1) % 5 == 0:
                print(f'I2V {ident} seed={seed} step={step+1}/{config["STEPS"]} '
                      f'elapsed={time.monotonic()-started:.1f}s', flush=True)
            return values

        with torch.inference_mode():
            output = pipe(image=image, prompt_embeds=embedding, negative_prompt_embeds=negatives,
                width=config['WIDTH'], height=config['HEIGHT'], num_frames=config['FRAMES'],
                num_inference_steps=config['STEPS'], guidance_scale=config['GUIDANCE'],
                generator=torch.Generator(device='cpu').manual_seed(seed), output_type='np',
                callback_on_step_end=progress, max_sequence_length=config['MAX_SEQUENCE']).frames[0]
        if not np.isfinite(output).all():
            raise ValueError('Non-finite video output; clip rejected.')
        frames = np.clip(output*255, 0, 255).round().astype(np.uint8)
        encode_frames(frames, target, config['FPS'])
        report, samples = inspect_video(target, config, image)
        report.update(fingerprint=signature, seed=seed, prompt=lookup[ident]['prompt'],
            source_sha256=lookup[ident]['sha256'], model=job['models']['wan'],
            quantization='NF4 weights, FP32 compute; T5 released before diffusion',
            inference_seconds=round(time.monotonic()-started, 2),
            peak_vram_gib=round(torch.cuda.max_memory_allocated()/2**30, 3),
            camera='requested locked-off; not guaranteed by text conditioning')
        atomic_json(sidecar, report)
        panel = Image.new('RGB', (256*len(samples), 174), '#151515')
        draw = ImageDraw.Draw(panel)
        draw.text((8, 7), f'{ident} seed {seed} | samples, not approval', fill='white')
        for index, sample in enumerate(samples):
            panel.paste(Image.fromarray(sample), (256*index, 30))
        panel.save(run/'review'/f'{target.stem}-samples.jpg', quality=95)
        del output, frames
        gc.collect()
        torch.cuda.empty_cache()
        print(f'DONE {target.name}: {report["inference_seconds"]}s; '
              f'VRAM {report["peak_vram_gib"]} GiB; editorial review required', flush=True)


if __name__ == '__main__':
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    if sys.argv[1] == 'prepare':
        prepare(sys.argv[2])
    else:
        generate(sys.argv[2], sys.argv[3])
