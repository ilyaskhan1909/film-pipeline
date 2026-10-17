"""Run one bounded batch; retain completed clips and diagnostics on failure."""
import json
import os
import shutil
import subprocess
import threading
import zipfile
from pathlib import Path

from contract import (check_zip, digest, make_archive, read_json_member, save_json,
                      validate_return_manifest)


def clip_records(job):
    run = Path(job['run'])
    inputs = job['inputs']
    records = []
    for request in inputs['requests']:
        ident = request['id']
        video, sidecar = run / 'clips' / f'{ident}.mp4', run / 'reports' / f'{ident}.json'
        if not video.exists() or not sidecar.exists():
            continue
        report = json.loads(sidecar.read_text(encoding='utf-8'))
        if report.get('job_fingerprint') != job['fingerprint'] or report['sha256'] != digest(video):
            continue
        records.append({'id': ident, 'asset_id': request['asset_id'], 'config': request['config'],
            'file': f'clips/{ident}.mp4', 'report': f'reports/{ident}.json',
            'sha256': report['sha256'], 'source_sha256': report['source_sha256'],
            'technical_pass': report['technical_pass'], 'production_approved': False})
    return records


def restore_completed(job, input_root):
    """Optional attach of the SAME batch's previous result ZIP. Never executes imported code."""
    run = Path(job['run'])
    for archive in Path(input_root).rglob('*results.zip'):
        with zipfile.ZipFile(archive) as bundle:
            check_zip(bundle)
            if 'video-results.json' not in bundle.namelist():
                continue
            manifest = read_json_member(bundle, 'video-results.json')
            if manifest.get('job_fingerprint') != job['fingerprint']:
                continue
            validate_return_manifest(manifest, job['inputs'], job['fingerprint'])
            for clip in manifest['clips']:
                report = read_json_member(bundle, clip['report'])
                import hashlib
                data = bundle.read(clip['file'])
                if (hashlib.sha256(data).hexdigest() != clip['sha256'] or
                        report.get('job_fingerprint') != job['fingerprint'] or
                        report.get('sha256') != clip['sha256'] or
                        report.get('source_sha256') != clip['source_sha256'] or
                        report.get('config') != clip['config'] or not report.get('technical_pass')):
                    raise ValueError('Invalid previous result; will not resume.')
                (run / clip['file']).write_bytes(data)
                save_json(run / clip['report'], report)
                print('RESTORED', clip['id'], flush=True)
    # An interrupted write with no matching report must not count as cached output.
    good = {r['file'] for r in clip_records(job)}
    for video in (run / 'clips').glob('*.mp4'):
        if video.relative_to(run).as_posix() not in good:
            # Keep it as diagnostics rather than deleting a recoverable candidate.
            destination = run / 'diagnostics' / (video.stem + '-unverified.mp4')
            if destination.exists():
                raise RuntimeError('Unverified diagnostic already exists; inspect it before rerunning.')
            shutil.move(str(video), str(destination))


def execute(job, python):
    run = Path(job['run'])
    restore_completed(job, '/kaggle/input')
    failure = None
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES='0,1', HF_HOME=job['model_cache'],
        HF_HUB_DISABLE_XET='1', TOKENIZERS_PARALLELISM='false', PYTHONUNBUFFERED='1',
        PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
    expired = threading.Event()
    with (run / 'logs/worker.log').open('w', encoding='utf-8') as stream:
        process = subprocess.Popen([python, '-u', str(run / 'scripts/batch_worker.py'), str(run / 'job.json')],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        def expire():
            expired.set()
            if process.poll() is None:
                process.kill()
        timer = threading.Timer(job['inputs']['policy']['maximum_batch_worker_seconds'], expire)
        timer.daemon = True
        timer.start()
        try:
            for line in process.stdout:
                stream.write(line)
                stream.flush()
                if any(word in line for word in ('DOWNLOAD', 'EMBEDDING', 'LOAD ', 'STEP ', 'DONE ',
                                                  'RETURN ', 'CACHED ', 'Traceback', 'Error:')):
                    print(line.rstrip(), flush=True)
            if process.wait() or expired.is_set():
                failure = 'batch timeout' if expired.is_set() else 'See logs/worker.log'
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
        finally:
            timer.cancel()
            process.stdout.close()
    records = clip_records(job)
    result = {'schema': 'video-results/v1', 'handoff_id': job['inputs']['handoff_id'],
        'job_fingerprint': job['fingerprint'], 'clips': records,
        'requested_clips': len(job['inputs']['requests']), 'completed_clips': len(records),
        'failure': failure, 'production_approved': False, 'checkpoint_modified': False,
        'kaggle_scope': 'silent_image_to_video_only', 'paid_apis': False,
        'limits': ['Experimental Q8/FP32 backend has not yet passed Kaggle T4 x2 runtime validation.',
                   'Technical validation is not visual approval. No automatic edit insertion.',
                   'Only finished, checksum-bound clips can resume; mid-clip latents are not resumed.']}
    validate_return_manifest(result, job['inputs'], job['fingerprint'])
    save_json(run / 'video-results.json', result)
    archive = make_archive(run, run.parent / (run.name + '-results.zip'))
    print('EXPORT', archive.name, len(records), 'raw clip(s)', flush=True)
    if failure:
        raise RuntimeError('Batch failed; completed clips and diagnostics saved: ' + str(archive))
    return archive
