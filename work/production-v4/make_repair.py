"""A separate, explicit shot/take repair notebook from the frozen full notebook."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path

import nbformat


def make(notebook, spec):
    nb = copy.deepcopy(notebook)
    values = {}
    for node in ast.parse(nb.cells[1].source).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ('CONFIG', 'PLAN', 'PINS', 'REVISIONS', 'IMPLEMENTATION_SHA'):
                values[name] = ast.literal_eval(node.value)
    c, plan = values['CONFIG'], values['PLAN']
    assert not c['QUICK_TEST'], 'Start from the frozen full production notebook.'
    assert set(spec) <= {'shots', 'audio_takes'}, 'Unexpected repair fields.'
    changes = spec.get('shots', {})
    audio = spec.get('audio_takes', {})
    assert changes or audio, 'Empty repair request.'
    selected = []
    for ident, patch in changes.items():
        assert ident.startswith('shot-') and isinstance(patch, dict)
        index = int(ident[5:])
        shot = plan['shots'][index]
        assert shot['id'] == ident
        assert set(patch) <= {'prompt', 'description', 'lens', 'refs', 'motion'}
        assert patch, 'Explicit changed prompt or framing is required.'
        if 'prompt' in patch:
            assert isinstance(patch['prompt'], str) and patch['prompt'].strip()
        if 'refs' in patch:
            assert isinstance(patch['refs'], list) and all(n in plan['characters'] for n in patch['refs'])
        if 'motion' in patch:
            assert patch['motion'] in ('push-in', 'pan-left', 'pan-right', 'hold')
        # Framing/description changes alone must also change the actual model prompt.
        assert 'prompt' in patch or 'refs' in patch, 'A lens label alone does not change generation.'
        assert patch.get('prompt', shot['prompt']) != shot['prompt'] or patch.get('refs', shot['refs']) != shot['refs'], 'Generation inputs did not change.'
        shot.update(patch)
        selected.append(index)
    audio_indices = []
    for index, take in audio.items():
        assert str(int(index)) == index and 0 <= int(index) < len(plan['segments'])
        assert type(take) is int and take > c.get('TTS_TAKES', {}).get(index, 0)
        c.setdefault('TTS_TAKES', {})[index] = take
        audio_indices.append(int(index))
    c.update(QUICK_TEST=True, PILOT_AUDIO_INDICES=sorted(audio_indices), COMPARE_BASE=False)
    plan['pilot_shots'] = sorted(selected)
    plan['pilot_audio'] = sorted(audio_indices)
    config_id = {k:v for k,v in c.items() if k not in ('QUICK_TEST','TEST_SCENES','COMPARE_BASE','PILOT_AUDIO_INDICES')}
    runid = hashlib.sha256(json.dumps({'config':config_id, 'plan':plan,
        'implementation':values['IMPLEMENTATION_SHA'], 'revisions':values['REVISIONS'],
        'pins':values['PINS']}, sort_keys=True).encode()).hexdigest()[:16]
    replacements = {'CONFIG':repr(c), 'PLAN':repr(plan)}
    nb.cells[1].source = '\n'.join(
        f'{name}={replacements[name]}' if (name:=line.split('=',1)[0]) in replacements else line
        for line in nb.cells[1].source.splitlines())+'\n'
    nb.cells[0].source = 'GPU T4 + Internet On. Только явно указанные кадры/дубли. Полный пакет подключён как Input; исходные материалы не изменяются. Результат требует повторной проверки.'
    nb.metadata.videogenerator.run_id = runid
    nb.metadata.videogenerator.status = 'repair_not_yet_runtime_validated'
    nb.metadata.videogenerator.repair_spec = spec
    nbformat.validate(nb)
    for i, cell in enumerate(nb.cells):
        if cell.cell_type == 'code':
            compile(cell.source, f'repair-cell-{i}', 'exec')
    return nb


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('full_notebook', type=Path)
    parser.add_argument('spec', type=Path)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--source', default='iliaskhan/videogenerator-v4-production-full')
    args = parser.parse_args()
    assert not (args.directory/'production.ipynb').exists(), 'Use a new repair directory.'
    nb = make(nbformat.read(args.full_notebook, as_version=4), json.loads(args.spec.read_text(encoding='utf-8')))
    args.directory.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, args.directory/'production.ipynb')
    metadata = {'id':'iliaskhan/videogenerator-v4-corrections', 'title':'VideoGenerator v4 corrections',
        'code_file':'production.ipynb','language':'python','kernel_type':'notebook','is_private':True,
        'enable_gpu':True,'enable_tpu':False,'enable_internet':True,
        'dataset_sources':[], 'kernel_sources':[args.source], 'competition_sources':[],
        'docker_image':'gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f',
        'machine_shape':'NvidiaTeslaT4'}
    (args.directory/'kernel-metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps({'notebook':str(args.directory/'production.ipynb'),
                      'run_id':nb.metadata.videogenerator.run_id,'repair':nb.metadata.videogenerator.repair_spec}))


if __name__ == '__main__':
    main()
