"""Kaggle stage: condition images/prompts, generate silent clips, export diagnostics."""
import json
import shutil
import sys
from pathlib import Path

import torch

import wan_worker as engine
from contract import digest, save_json, validate_inputs


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    run = Path(job['run'])
    manifest = validate_inputs(job['inputs'])
    if torch.cuda.device_count() != 2:
        raise RuntimeError('Two T4 GPUs required; no automatic single-GPU/other-model fallback.')
    engine.install_chunked_attention(job['config']['ATTENTION_QUERY_CHUNK'])
    with engine.Telemetry(run):
        pending = [r for r in manifest['requests'] if not (run / 'clips' / f'{r["id"]}.mp4').is_file()]
        if not pending:
            print('CACHED all requested clips', flush=True)
            return
        snapshot, experts = engine.download_models(job, run)
        assets = {a['id']: a for a in manifest['assets']}
        shots = [{'id': r['id'], 'sha256': assets[r['asset_id']]['sha256'], 'prompt': r['prompt']}
                 for r in pending]
        embedding_job = dict(job, shots=shots)
        engine.prepare_embeddings(embedding_job, run, snapshot)
        for number, request in enumerate(pending):
            ident = request['id']
            asset = assets[request['asset_id']]
            if digest(run / asset['file']) != asset['sha256']:
                raise ValueError('Source frame changed after input validation.')
            clip_run = run / 'requests' / ident
            for folder in ('source', 'embeddings', 'clips', 'diagnostics', 'review', 'logs'):
                (clip_run / folder).mkdir(parents=True, exist_ok=True)
            shutil.copy2(run / asset['file'], clip_run / 'source' / f'{ident}.png')
            for name in (ident, 'negative'):
                shutil.copy2(run / 'embeddings' / f'{name}.pt', clip_run / 'embeddings' / f'{name}.pt')
            shot = {'id': ident, 'sha256': asset['sha256'], 'prompt': request['prompt']}
            clip_job = dict(job, run=str(clip_run), shots=[shot], config=request['config'])
            if number == 0:
                sanity = dict(request['config'], WIDTH=256, HEIGHT=144, FRAMES=9, STEPS=2)
                engine.generate(clip_job, clip_run, snapshot, experts, 'sanity', sanity)
                engine.clean_cuda()
            report = engine.generate(clip_job, clip_run, snapshot, experts, 'quality', request['config'])
            generated = clip_run / 'clips' / f'{ident}-quality-seed-{request["config"]["SEED"]}.mp4'
            target = run / 'clips' / f'{ident}.mp4'
            generated.replace(target)
            report.update(id=ident, asset_id=asset['id'], handoff_id=manifest['handoff_id'],
                job_fingerprint=job['fingerprint'], prompt=request['prompt'],
                negative_prompt=manifest['negative_prompt'], production_approved=False)
            save_json(run / 'reports' / f'{ident}.json', report)
            engine.clean_cuda()
            print('RETURN', ident, flush=True)


if __name__ == '__main__':
    main()
