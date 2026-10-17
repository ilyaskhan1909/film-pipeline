"""Bind the separate notebook to bounded evidence; never upgrades a smoke test into full validation."""
import argparse
import ast
import json
from pathlib import Path

import nbformat

from common import atomic_json, sha256

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT/'outputs/animation-pilot/videogenerator-v4.2-kaggle-animation-pilot.ipynb'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    parser.add_argument('--version',type=int,required=True)
    args = parser.parse_args()
    notebook = nbformat.read(NOTEBOOK,as_version=4)
    bundle = None
    for node in ast.parse(notebook.cells[2].source).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id == 'BUNDLE':
            bundle = ast.literal_eval(node.value)
    assert bundle
    for name,source in bundle.items():
        assert source == (args.run/'scripts'/name).read_text(encoding='utf-8'), name
    job = json.loads((args.run/'job.json').read_text(encoding='utf-8'))
    manifest = json.loads((args.run/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['failures'] == []
    expected = 1 if job['config']['SMOKE_ONLY'] else 8
    assert manifest['completed_i2v_clips'] == expected
    for clip in manifest['clips']:
        assert clip['technical_pass'] and sha256(args.run/clip['path']) == clip['sha256']
    environment = json.loads((args.run/'environment.json').read_text(encoding='utf-8'))
    proof = {'status':'gpu_smoke_passed_full_pilot_unverified' if expected == 1 else 'gpu_full_pilot_passed_editorial_review_pending',
        'kernel':'iliaskhan/videogenerator-v4-2-motion-pilot','kernel_version':args.version,
        'run_id':args.run.name,'generated_clips':expected,'depth_controls':4,'static_controls':4,
        'native_resolution':manifest['native_resolution'],'fps':24,
        'duration_seconds':manifest['duration_seconds'],'python':environment['python'],
        'gpu':environment['gpu'],'model_revision':job['models']['wan']['revision'],
        'manifest_sha256':sha256(args.run/'manifest.json'),
        'limits':['Only the configuration recorded in this run is GPU-proven.',
                  '512x288 probes do not validate 1024x576 memory use or final YouTube quality.',
                  'No continuous viewing, identity preservation or editorial acceptance is claimed.',
                  'The frozen v4.1 checkpoint is not replaced.']}
    notebook.metadata.animation_pilot.update(status=proof['status'],runtime_evidence=proof)
    nbformat.validate(notebook)
    nbformat.write(notebook,NOTEBOOK)
    atomic_json(NOTEBOOK.parent/'runtime-validation.json',proof)
    print(json.dumps(proof,ensure_ascii=False))


if __name__ == '__main__':
    main()
