"""Wan A14B Q8/FP32. One active expert at a time, its blocks split across two T4s.

Denoising, conditioning and decoding match Diffusers 0.40 Wan I2V. The scheduler
is never restarted at the high/low-noise boundary. No TeaCache or distilled LoRA.
"""
import contextlib
import gc
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from common import atomic_json, encode_frames, inspect_video, sha256


def stage_for(timestep, boundary):
    return 'high' if float(timestep) >= boundary else 'low'


def device_map_for(num_layers=40):
    result = {'': 0, 'norm_out': 1, 'proj_out': 1}
    result.update({f'blocks.{i}': 0 if i < num_layers // 2 else 1 for i in range(num_layers)})
    return result


def install_chunked_attention(chunk_size):
    original = torch.nn.functional.scaled_dot_product_attention

    def chunked(query, key, value, attn_mask=None, dropout_p=0.0, is_causal=False, **kwargs):
        if is_causal or dropout_p or query.shape[-2] <= chunk_size:
            return original(query, key, value, attn_mask=attn_mask, dropout_p=dropout_p,
                            is_causal=is_causal, **kwargs)
        parts = []
        for start in range(0, query.shape[-2], chunk_size):
            mask = attn_mask
            if mask is not None and mask.ndim >= 2 and mask.shape[-2] == query.shape[-2]:
                mask = mask[..., start:start + chunk_size, :]
            parts.append(original(query[..., start:start + chunk_size, :], key, value,
                attn_mask=mask, dropout_p=0.0, is_causal=False, **kwargs))
        return torch.cat(parts, dim=-2)

    torch.nn.functional.scaled_dot_product_attention = chunked


def clean_cuda():
    gc.collect()
    for i in range(2):
        with torch.cuda.device(i):
            torch.cuda.empty_cache()
    # Return freed Python/C allocations where the Linux allocator supports it.
    with contextlib.suppress(Exception):
        import ctypes
        ctypes.CDLL(None).malloc_trim(0)


class Telemetry:
    def __init__(self, run):
        self.run = run
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        with (self.run / 'gpu-telemetry.jsonl').open('a', encoding='utf-8') as stream:
            while not self.stop.is_set():
                try:
                    raw = subprocess.check_output(['nvidia-smi',
                        '--query-gpu=index,utilization.gpu,memory.used,memory.total',
                        '--format=csv,noheader,nounits'], text=True, timeout=10)
                    values = [[int(x.strip()) for x in line.split(',')] for line in raw.splitlines()]
                    stream.write(json.dumps({'time': time.time(), 'gpu': values}) + '\n')
                    stream.flush()
                except Exception as exc:
                    stream.write(json.dumps({'telemetry_error': type(exc).__name__}) + '\n')
                    stream.flush()
                self.stop.wait(5)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=15)


def download_models(job, run):
    from huggingface_hub import hf_hub_download, snapshot_download
    original = job['models']['original']
    # Explicit allowlist: never download the ~106 GiB FP32 diffusion experts.
    snapshot = snapshot_download(original['repo'], revision=original['revision'],
        allow_patterns=['model_index.json', 'scheduler/*', 'tokenizer/*', 'text_encoder/*',
                        'transformer/config.json', 'transformer_2/config.json', 'vae/*'],
        ignore_patterns=['*.md', '*.bin', '*.jpg', '*.png', '*.onnx'],
        cache_dir=job['model_cache'], max_workers=4)
    quant = job['models']['quantized']
    files = {}
    for stage, record in quant['files'].items():
        print('DOWNLOAD', stage, 'Q8 expert', flush=True)
        filename = hf_hub_download(quant['repo'], record['name'], revision=quant['revision'],
                                   cache_dir=job['model_cache'])
        if sha256(filename) != record['sha256']:
            raise ValueError('Q8 expert checksum mismatch: ' + stage)
        files[stage] = filename
    atomic_json(run / 'model-files.json', {'snapshot': snapshot, 'experts': files,
                                         'expert_checksums_verified': True})
    return snapshot, files


def prepare_embeddings(job, run, snapshot):
    from transformers import BitsAndBytesConfig, T5TokenizerFast, UMT5EncoderModel
    from diffusers.pipelines.wan.pipeline_wan import prompt_clean
    tokenizer = T5TokenizerFast.from_pretrained(snapshot, subfolder='tokenizer')
    encoder = UMT5EncoderModel.from_pretrained(snapshot, subfolder='text_encoder',
        dtype=torch.float32, device_map={'': 0}, attn_implementation='eager',
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float32)).eval()
    prompts = {shot['id']: shot['prompt'] for shot in job['shots']}
    prompts['negative'] = job['negative_prompt']
    for ident, text in prompts.items():
        tokens = tokenizer(prompt_clean(text), padding='max_length',
            max_length=job['config']['MAX_SEQUENCE'], truncation=True,
            add_special_tokens=True, return_attention_mask=True, return_tensors='pt').to('cuda:0')
        length = int(tokens.attention_mask.sum().item())
        with torch.inference_mode():
            embedding = encoder(tokens.input_ids, tokens.attention_mask).last_hidden_state.float()
            embedding[:, length:] = 0
        if not torch.isfinite(embedding).all().item():
            raise ValueError('Non-finite text embedding.')
        torch.save(embedding.cpu(), run / 'embeddings' / f'{ident}.pt')
        print('EMBEDDING', ident, length, flush=True)
    del encoder, tokenizer, tokens, embedding
    clean_cuda()


def load_expert(stage, filename, snapshot, run, trial):
    from accelerate import dispatch_model
    from diffusers import GGUFQuantizationConfig, WanTransformer3DModel
    clean_cuda()
    print('LOAD', trial, stage, flush=True)
    started = time.monotonic()
    # Single-file loader first materializes compressed Q8 on CPU. Explicit dispatch
    # afterwards avoids its version-specific automatic device-map estimation.
    model = WanTransformer3DModel.from_single_file(filename,
        config=snapshot, subfolder='transformer' if stage == 'high' else 'transformer_2',
        torch_dtype=torch.float32, quantization_config=GGUFQuantizationConfig(compute_dtype=torch.float32),
        low_cpu_mem_usage=True, local_files_only=True)
    if any(p.device.type == 'meta' for p in model.parameters()):
        raise RuntimeError('Missing model parameters: cannot dispatch a partial checkpoint.')
    mapping = device_map_for(model.config.num_layers)
    model = dispatch_model(model, device_map=mapping, main_device=0,
                           force_hooks=True, offload_buffers=False)
    model.set_attention_backend('native')
    model.eval()
    residency = {}
    for name, param in model.named_parameters():
        key = str(param.device)
        residency[key] = residency.get(key, 0) + param.numel() * param.element_size()
    if set(residency) != {'cuda:0', 'cuda:1'}:
        raise RuntimeError('Expert did not distribute onto both GPUs: ' + repr(residency))
    hits = {0: 0, 1: 0}

    def note_forward(module, args, result):
        tensor = result[0] if isinstance(result, tuple) else result
        if tensor.device.type != 'cuda':
            raise RuntimeError('Transformer block executed outside CUDA.')
        hits[tensor.device.index] += 1

    for block in model.blocks:
        block.register_forward_hook(note_forward)
    info = {'stage': stage, 'trial': trial, 'load_seconds': time.monotonic() - started,
        'device_map': mapping, 'parameter_bytes_by_device': residency,
        'weight_format': 'GGUF Q8_0', 'compute_dtype': 'float32',
        'quantization_warning': 'Q8 is not an unquantized reference; T5 uses NF4/FP32.'}
    atomic_json(run / 'diagnostics' / f'{trial}-{stage}-distribution.json', info)
    print('RESIDENT', stage, {k: round(v / 2**30, 3) for k, v in residency.items()}, flush=True)
    return model, hits


def denoise(scheduler, latents, condition, positive, negative, steps, guidance,
            boundary_ratio, load_model, release_model, on_step):
    """Exact reference CFG/UniPC semantics; expert swap does not reset scheduler."""
    scheduler.set_timesteps(steps, device=latents.device)
    boundary = boundary_ratio * scheduler.config.num_train_timesteps
    model = None
    active = None
    try:
        for index, timestep in enumerate(scheduler.timesteps):
            stage = stage_for(timestep, boundary)
            if stage != active:
                if model is not None:
                    release_model(model, active)
                    model = None
                model = load_model(stage)
                active = stage
            inputs = torch.cat([latents, condition], dim=1)
            timestamp = timestep.expand(latents.shape[0])
            with model.cache_context('cond'):
                conditional = model(hidden_states=inputs, timestep=timestamp,
                    encoder_hidden_states=positive, return_dict=False)[0]
            with model.cache_context('uncond'):
                unconditional = model(hidden_states=inputs, timestep=timestamp,
                    encoder_hidden_states=negative, return_dict=False)[0]
            prediction = unconditional + guidance * (conditional - unconditional)
            if not torch.isfinite(prediction).all().item():
                raise ValueError(f'Non-finite prediction at {stage} step {index + 1}.')
            latents = scheduler.step(prediction, timestep, latents, return_dict=False)[0]
            if not torch.isfinite(latents).all().item():
                raise ValueError(f'Non-finite latents at step {index + 1}.')
            del conditional, unconditional, prediction, inputs
            on_step(index, timestep, stage, latents)
    finally:
        if model is not None:
            release_model(model, active)
    return latents


def generate(job, run, snapshot, experts, trial, config):
    from diffusers import AutoencoderKLWan, UniPCMultistepScheduler, WanImageToVideoPipeline
    shot = job['shots'][0]
    image = Image.open(run / 'source' / f'{shot["id"]}.png').convert('RGB')
    positive = torch.load(run / 'embeddings' / f'{shot["id"]}.pt', weights_only=True).to('cuda:0')
    negative = torch.load(run / 'embeddings/negative.pt', weights_only=True).to('cuda:0')
    vae = AutoencoderKLWan.from_pretrained(snapshot, subfolder='vae', torch_dtype=torch.float32).to('cuda:0')
    vae.enable_tiling()
    vae.enable_slicing()
    scheduler = UniPCMultistepScheduler.from_pretrained(snapshot, subfolder='scheduler')
    index = json.loads((Path(snapshot) / 'model_index.json').read_text())
    pipe = WanImageToVideoPipeline(tokenizer=None, text_encoder=None,
        transformer=None, transformer_2=None, vae=vae, scheduler=scheduler,
        boundary_ratio=index['boundary_ratio'], expand_timesteps=False)
    resized = pipe.video_processor.preprocess(image, height=config['HEIGHT'], width=config['WIDTH']).to('cuda:0', torch.float32)
    with torch.inference_mode():
        latents, condition = pipe.prepare_latents(resized, 1, vae.config.z_dim,
            config['HEIGHT'], config['WIDTH'], config['FRAMES'], torch.float32,
            torch.device('cuda:0'), torch.Generator(device='cuda:0').manual_seed(config['SEED']))
    if not torch.isfinite(condition).all().item():
        raise ValueError('Non-finite VAE image conditioning.')
    vae.to('cpu')
    del resized
    clean_cuda()
    for gpu in range(2):
        torch.cuda.reset_peak_memory_stats(gpu)
    started = time.monotonic()
    stats = {'trial': trial, 'steps': [], 'expert_forward_hits': {}, 'completed': False}
    current_hits = {}

    def load(stage):
        model, hits = load_expert(stage, experts[stage], snapshot, run, trial)
        current_hits[stage] = hits
        return model

    def release(model, stage):
        stats['expert_forward_hits'][stage] = dict(current_hits[stage])
        # Move the compressed weights off GPUs, then remove the only model reference
        # in denoise before the next load. CPU temporary allocation is ~14.35 GiB.
        from accelerate.hooks import remove_hook_from_module
        remove_hook_from_module(model, recurse=True)
        model.to('cpu')

    def step(index, timestep, stage, values):
        clean_cuda() if index == 0 else None
        progress = {'step': index + 1, 'timestep': float(timestep), 'expert': stage,
                    'elapsed_seconds': time.monotonic() - started}
        stats['steps'].append(progress)
        atomic_json(run / 'diagnostics' / f'{trial}-progress.json', stats)
        print('STEP', trial, index + 1, '/', config['STEPS'], stage,
              round(progress['elapsed_seconds'], 1), flush=True)

    with torch.inference_mode():
        latents = denoise(scheduler, latents, condition, positive, negative,
            config['STEPS'], config['GUIDANCE'], index['boundary_ratio'], load, release, step)
    clean_cuda()
    if set(stats['expert_forward_hits']) != {'high', 'low'} or any(
            not hits.get(gpu) for hits in stats['expert_forward_hits'].values() for gpu in range(2)):
        raise RuntimeError('Both experts must execute blocks on both GPUs.')
    stats['denoise_seconds'] = time.monotonic() - started
    stats['peak_allocated_gib'] = [torch.cuda.max_memory_allocated(i) / 2**30 for i in range(2)]
    vae.to('cuda:0')
    with torch.inference_mode():
        mean = torch.tensor(vae.config.latents_mean, device='cuda:0').view(1, vae.config.z_dim, 1, 1, 1)
        std = torch.tensor(vae.config.latents_std, device='cuda:0').view(1, vae.config.z_dim, 1, 1, 1)
        decoded = vae.decode(latents * std + mean, return_dict=False)[0]
        if not torch.isfinite(decoded).all().item():
            raise ValueError('Non-finite VAE decoded frames.')
        frames = pipe.video_processor.postprocess_video(decoded, output_type='np')[0]
    if not np.isfinite(frames).all():
        raise ValueError('Non-finite output pixels.')
    folder = 'diagnostics' if trial == 'sanity' else 'clips'
    target = run / folder / f'{shot["id"]}-{trial}-seed-{config["SEED"]}.mp4'
    encode_frames(np.clip(frames * 255, 0, 255).round().astype(np.uint8), target, 24)
    report, samples = inspect_video(target, config, image)
    if report.get('warning_black_frames'):
        raise RuntimeError('Black-frame warning; output rejected.')
    for sample_index, sample in enumerate(samples):
        Image.fromarray(sample).save(run / 'review' / f'{trial}-{sample_index}.png')
    stats.update(completed=True, total_seconds=time.monotonic() - started)
    report.update(kind='sanity_not_quality' if trial == 'sanity' else 'i2v_quality_candidate',
        config=config, runtime=stats, source_sha256=shot['sha256'], models=job['models'],
        identity_preservation_verified=False, production_approved=False,
        limitations=['Two GPUs shard each active expert; compute is sequential between layer groups.',
                     'Q8 diffusion and NF4 T5 are quantized, not full-precision weights.',
                     'No interpolation, upscale, sound, postprocessing, cache or motion LoRA.'])
    atomic_json(target.with_suffix('.json'), report)
    atomic_json(run / 'diagnostics' / f'{trial}-progress.json', stats)
    print('DONE', target.name, stats['total_seconds'], flush=True)
    return report


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    run = Path(job['run'])
    if torch.cuda.device_count() != 2:
        raise RuntimeError('Two visible GPUs are mandatory; no silent single-GPU fallback.')
    install_chunked_attention(job['config']['ATTENTION_QUERY_CHUNK'])
    with Telemetry(run):
        snapshot, experts = download_models(job, run)
        prepare_embeddings(job, run, snapshot)
        sanity = dict(job['config'], WIDTH=256, HEIGHT=144, FRAMES=9, STEPS=2)
        generate(job, run, snapshot, experts, 'sanity', sanity)
        clean_cuda()
        generate(job, run, snapshot, experts, 'quality', job['config'])


if __name__ == '__main__':
    main()
