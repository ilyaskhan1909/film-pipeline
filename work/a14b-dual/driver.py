"""Bounded dual-GPU worker and diagnostic archive. Does not edit input assets."""
import json
import os
import subprocess
import threading
import zipfile
from pathlib import Path

from common import atomic_json, sha256


def execute(job, python):
    run = Path(job['run'])
    failure = None
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES='0,1',
        HF_HOME=job['model_cache'], HF_HUB_DISABLE_XET='1',
        TOKENIZERS_PARALLELISM='false', PYTHONUNBUFFERED='1',
        PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
    command = [python, '-u', str(run / 'scripts/worker.py'), str(run / 'job.json')]
    expired = threading.Event()
    with (run / 'logs/worker.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
        def expire():
            expired.set()
            if process.poll() is None:
                process.kill()
        timer = threading.Timer(job['config']['MAX_WORKER_SECONDS'], expire)
        timer.daemon = True
        timer.start()
        try:
            for line in process.stdout:
                log.write(line)
                log.flush()
                if any(word in line for word in ('DOWNLOAD', 'EMBEDDING', 'LOAD ', 'RESIDENT',
                                                  'STEP ', 'DONE ', 'Traceback', 'Error:')):
                    print(line.rstrip(), flush=True)
            if process.wait() or expired.is_set():
                failure = 'worker timeout' if expired.is_set() else log.name
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
        finally:
            timer.cancel()
            process.stdout.close()
    clips = []
    for path in sorted((run / 'clips').glob('*.json')):
        report = json.loads(path.read_text())
        if path.with_suffix('.mp4').is_file() and sha256(path.with_suffix('.mp4')) == report['sha256']:
            clips.append(report)
    manifest = {'schema': 1, 'kind': 'separate_A14B_two_T4_experiment',
        'run_id': run.name, 'config': job['config'], 'models': job['models'],
        'checkpoint': job['checkpoint'], 'checkpoint_modified': False,
        'clips': clips, 'completed_quality_clips': len(clips), 'failure': failure,
        'production_approved': False, 'paid_apis': False,
        'gpu_strategy': 'One active Q8 expert, 20 blocks on each T4; high/low experts swapped once.',
        'speedup_claim': None, 'free_runtime': 'Kaggle account GPU quota is consumed.',
        'quality_limit': 'Full GPU execution and technical QA do not establish editorial quality.'}
    atomic_json(run / 'manifest.json', manifest)
    checksums = {p.relative_to(run).as_posix(): sha256(p) for p in sorted(run.rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and '.partial' not in p.name
        and p.name != 'checksums.json'}
    atomic_json(run / 'checksums.json', checksums)
    archive = run.parent / f'{run.name}-assets.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
        for relative in checksums:
            bundle.write(run / relative, relative)
        bundle.write(run / 'checksums.json', 'checksums.json')
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip():
            raise ValueError('ZIP CRC validation failed.')
    print('EXPORT', archive.name, len(clips), 'quality candidate(s)', flush=True)
    if failure:
        raise RuntimeError('Separate experiment failed; diagnostics exported: ' + str(archive))
    return archive
