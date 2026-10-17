"""Kaggle execution and review delivery; never replaces checkpoint assets."""
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

from common import atomic_json, fingerprint, sha256, validate_config


def import_sources(run, shots, input_root):
    input_root = Path(input_root)
    for shot in shots:
        target = run/'source'/f'{shot["id"]}.png'
        if target.exists() and sha256(target) == shot['sha256']:
            continue
        found = False
        for path in input_root.rglob(target.name):
            if sha256(path) == shot['sha256']:
                shutil.copy2(path, target)
                found = True
                break
        if not found:
            for archive in input_root.rglob('*.zip'):
                try:
                    with zipfile.ZipFile(archive) as bundle:
                        for name in bundle.namelist():
                            if Path(name).name != target.name:
                                continue
                            # Extract exactly one member into a fixed path, never arbitrary ZIP paths.
                            data = bundle.read(name)
                            import hashlib
                            if hashlib.sha256(data).hexdigest() == shot['sha256']:
                                target.write_bytes(data)
                                found = True
                                break
                except zipfile.BadZipFile:
                    continue
                if found:
                    break
        if not found:
            raise FileNotFoundError(f'Checkpoint image {shot["id"]} with the expected SHA256 not found. '
                'Attach outputs from iliaskhan/videogenerator-v4-1-curated-assets.')
        if sha256(target) != shot['sha256']:
            raise ValueError('Source checksum mismatch.')
        atomic_json(target.with_suffix('.json'), shot)


def run_worker(job, python, stage, gpu, tasks=None):
    run = Path(job['run'])
    command = [str(python), '-u', str(run/'scripts/worker.py'), stage, str(run/'job.json')]
    suffix = stage if tasks is None else f'{stage}-{gpu}-{fingerprint(tasks)[:8]}'
    if tasks is not None:
        task_file = run/'tasks'/f'{suffix}.json'
        atomic_json(task_file, tasks)
        command.append(str(task_file))
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu),
        HF_HOME=job['model_cache'], HF_HUB_DISABLE_XET='1',
        TOKENIZERS_PARALLELISM='false', PYTHONUNBUFFERED='1',
        PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
    started = time.monotonic()
    log_path = run/'logs'/f'{suffix}.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
        expired = threading.Event()
        def expire():
            expired.set()
            if process.poll() is None:
                process.kill()
        timer = threading.Timer(3*3600, expire)
        timer.daemon = True
        timer.start()
        try:
            for line in process.stdout:
                log.write(line)
                log.flush()
                if any(word in line for word in ('CONTROL ', 'EMBEDDING ', 'I2V ', 'DONE ', 'CACHED ',
                                                 'Traceback', 'Error:', 'Exception:')):
                    print(f'GPU{gpu} {line.rstrip()}', flush=True)
                if time.monotonic() - started > 3*3600:
                    raise TimeoutError('Worker exceeded the three-hour safety budget.')
            if expired.is_set():
                raise TimeoutError('Worker exceeded the three-hour safety budget.')
            if process.wait() != 0:
                raise RuntimeError(f'{suffix} failed. See {log_path.name}: '
                    + log_path.read_text(encoding='utf-8')[-2000:])
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
        finally:
            timer.cancel()
            process.stdout.close()


def package(job, failures):
    run = Path(job['run'])
    completed = []
    for path in sorted((run/'clips').glob('*.json')):
        record = json.loads(path.read_text())
        video = path.with_suffix('.mp4')
        if video.exists() and record['sha256'] == sha256(video):
            completed.append(dict(record, path=video.relative_to(run).as_posix()))
    manifest = {'schema': 1, 'kind': 'animation_experiment_not_production',
        'run_id': run.name, 'checkpoint': job['checkpoint'], 'job_fingerprint': job['fingerprint'],
        'native_resolution': [job['config']['WIDTH'], job['config']['HEIGHT']],
        'duration_seconds': job['config']['FRAMES']/job['config']['FPS'],
        'requested_i2v_clips': 1 if job['config']['SMOKE_ONLY'] else 8,
        'completed_i2v_clips': len(completed), 'clips': completed, 'failures': failures,
        'production_approved': False, 'checkpoint_modified': False,
        'models': job['models'], 'paid_apis': False,
        'limits': ['512x288 is a hardware/motion pilot, not a native 1080p master.',
                  'Depth control is a gentle image warp, not separated 3D layers.',
                  'Technical checks do not prove identity preservation or editorial quality.',
                  'No generated clip is automatically inserted in the checkpoint film.']}
    atomic_json(run/'manifest.json', manifest)
    checksums = {p.relative_to(run).as_posix(): sha256(p) for p in sorted(run.rglob('*'))
                 if p.is_file() and p.parts[-2] != 'embeddings' and
                    not any(part == '__pycache__' for part in p.parts) and
                    p.name != 'checksums.json' and '.partial' not in p.name}
    atomic_json(run/'checksums.json', checksums)
    archive = run.parent/f'{run.name}-assets.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
        for relative in checksums:
            bundle.write(run/relative, relative)
        bundle.write(run/'checksums.json', 'checksums.json')
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('ZIP CRC validation failed.')
    print(f'EXPORT {archive.name}: {len(completed)} generated clips; review required.', flush=True)
    return archive


def execute(job, python, gpu_count):
    run, config = Path(job['run']), job['config']
    validate_config(config)
    failures = []
    try:
        prepared = run/'prepared.json'
        if not prepared.exists() or json.loads(prepared.read_text())['job_fingerprint'] != job['fingerprint']:
            run_worker(job, python, 'prepare', 0)
        tasks = [{'id': shot['id'], 'seed': seed} for shot in job['shots'] for seed in config['SEEDS']]
        # The first genuine clip must decode and contain valid latents before allocating another GPU.
        run_worker(job, python, 'generate', 0, tasks[:1])
        first = run/'clips'/f'{tasks[0]["id"]}-seed-{tasks[0]["seed"]}.json'
        first_report = json.loads(first.read_text())
        if first_report.get('warning_black_frames'):
            raise RuntimeError('Black-frame warning in the first clip; remaining generation stopped.')
        if not config['SMOKE_ONLY']:
            workers = min(config['MAX_GPU_WORKERS'], gpu_count)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(run_worker, job, python, 'generate', gpu, tasks[1:][gpu::workers])
                           for gpu in range(workers)]
                for future in futures:
                    future.result()
    except Exception as exc:
        failures.append({'stage': 'animation_pilot', 'error': str(exc)[-3500:]})
    if not failures:
        from comparison import compare
        try:
            compare(job)
        except Exception as exc:
            failures.append({'stage':'comparison_export','error':str(exc)[-2000:]})
    archive = package(job, failures)
    if failures:
        raise RuntimeError('Pilot failed; diagnostics and successful controls saved separately: ' + str(archive))
    return archive
