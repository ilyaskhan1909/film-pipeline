"""Create a separate minimal-Markdown notebook and immutable checkpoint hash inventory."""
import argparse
import json
import pprint
from pathlib import Path

import nbformat

from common import atomic_json, sha256

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT/'outputs/animation-pilot'


def checkpoint_files():
    paths = [ROOT/'outputs/videogenerator-v4.1-kaggle-assets.ipynb']
    film = ROOT/'outputs/first-film'
    for name in ('The_Last_Firework_1080p.mp4', 'The_Last_Firework_assets.zip',
                 'The_Last_Firework_editable.zip', 'PIPELINE.txt', 'DELIVERY.txt',
                 'The_Last_Firework.en.srt', 'The_Last_Firework.en.json'):
        paths.append(film/name)
    paths.extend(p for p in (film/'curated/assets').rglob('*') if p.is_file())
    paths.extend(p for p in (film/'edit').rglob('*') if p.is_file() and
                 not any(part in ('node_modules', '__pycache__', '.cache', 'out') for part in p.parts))
    return paths


def verify_checkpoint():
    frozen = json.loads((OUTPUT/'checkpoint-sha256.json').read_text(encoding='utf-8'))
    changed = [name for name, digest in frozen['files'].items()
               if not (ROOT/name).is_file() or sha256(ROOT/name) != digest]
    if changed:
        raise AssertionError('Checkpoint changed: '+repr(changed))
    print(f'CHECKPOINT: {len(frozen["files"])} files unchanged.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full-pilot', action='store_true')
    parser.add_argument('--verify-checkpoint', action='store_true')
    args = parser.parse_args()
    if args.verify_checkpoint:
        verify_checkpoint()
        return
    OUTPUT.mkdir(exist_ok=True)
    frozen_path = OUTPUT/'checkpoint-sha256.json'
    if frozen_path.exists():
        verify_checkpoint()
    else:
        atomic_json(frozen_path, {'checkpoint': 'The Last Firework v4.1',
            'kernel': 'iliaskhan/videogenerator-v4-1-curated-assets', 'kernel_version': 3,
            'files': {p.relative_to(ROOT).as_posix(): sha256(p) for p in checkpoint_files()}})
    config = {'SMOKE_ONLY': not args.full_pilot, 'WIDTH': 512, 'HEIGHT': 288, 'FRAMES': 73,
        'FPS': 24, 'STEPS': 40, 'GUIDANCE': 5.0, 'SEEDS': [20261005, 20261006],
        'MAX_SEQUENCE': 256, 'MAX_GPU_WORKERS': 2, 'ATTENTION_QUERY_CHUNK': 256}
    packages = ['diffusers==0.40.0', 'transformers==5.18.0', 'accelerate==1.15.0',
                'bitsandbytes==0.50.2', 'sentencepiece==0.2.1', 'ftfy==6.3.1']
    models = {'wan': {'repo': 'Wan-AI/Wan2.2-TI2V-5B-Diffusers',
                     'revision': 'b8fff7315c768468a5333511427288870b2e9635'},
              'depth': {'repo': 'depth-anything/Depth-Anything-V2-Small-hf',
                        'revision': '5426e4f0f36572d16453bbda7a8389317b1bef99'}}
    motion_prompts = {
        1: 'Locked-off live-action landscape shot. Keep the original lake, shore, trees, daylight '
           'and composition unchanged. Barely perceptible small ripples slowly travel across the lake '
           'surface and gently disturb its existing reflection. The far trees and camera remain still. '
           'Natural restrained motion, peaceful summer atmosphere. No new objects or events.',
        14: 'Locked-off macro shot of the same charred stick, ash and orange campfire embers. '
            'Only the existing coals glow subtly brighter and darker, with a very thin wisp of smoke '
            'drifting upwards. The logs, ash, camera and framing remain fixed. No large flame, '
            'no explosive sparks, no new objects. Restrained natural campfire detail.',
        44: 'Locked-off night forest shot. Preserve every tree trunk, path, original darkness and '
            'cold illumination. Only a few small leaves near the frame edges move almost imperceptibly '
            'in a weak breeze. Tree trunks and ground are still. No people, no animal, no handheld '
            'light, no new silhouette, no camera movement or sudden reveal.',
        51: 'Locked-off close shot of the EXACT SAME inanimate tan burlap doll in leaves beneath '
            'roots. Preserve both mismatched black button eyes, stitched mouth, closed cloth mittens '
            'and single loose blue cloth without any change. The doll is completely motionless. '
            'Only extremely subtle soft illumination varies across the distant background. '
            'Keep the prop position, texture and silhouette unchanged. No blink or facial movement.'}
    shots = []
    for index, prompt in motion_prompts.items():
        ident = f'shot-{index:03d}'
        original = ROOT/'outputs/first-film/curated/assets/images'/f'{ident}.png'
        record = json.loads(original.with_suffix('.json').read_text(encoding='utf-8'))
        assert record['sha256'] == sha256(original)
        shots.append({'id': ident, 'sha256': record['sha256'], 'prompt': prompt,
                      'checkpoint_generation': record})
    negative = ('Camera movement, zoom, pan, shake, cut, scene change, new objects, extra people, '
        'moving doll, blinking, speaking, changing buttons, changing mouth, extra limbs, '
        'deformed prop, melting texture, flicker, strobing, heavy fog, bright daytime night forest, '
        'text, subtitles, watermark, blurry, oversaturated, cartoon.')
    scripts = {name: (HERE/name).read_text(encoding='utf-8') for name in
               ('common.py', 'worker.py', 'driver.py', 'bootstrap.py', 'comparison.py')}
    for name, source in scripts.items():
        compile(source, name, 'exec')
    specification = dict(config=config, pins=packages, models=models, shots=shots,
                         negative_prompt=negative, scripts=scripts)
    cell_config = '\n'.join(f'{name} = {pprint.pformat(value, width=110, sort_dicts=False)}'
                            for name, value in [('CONFIG', config), ('PINS', packages),
                                               ('MODELS', models), ('SHOTS', shots),
                                               ('NEGATIVE_PROMPT', negative)])
    bootstrap_cell = '''import hashlib, json, os, sys
from pathlib import Path
SCRATCH = Path('/tmp/videogenerator-v4-2-animation')
SCRATCH.mkdir(parents=True, exist_ok=True)
BUNDLE = __BUNDLE__
spec = {'config':CONFIG, 'pins':PINS, 'models':MODELS, 'shots':SHOTS,
        'negative_prompt':NEGATIVE_PROMPT, 'scripts':BUNDLE}
identity = hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
RUN = Path('/kaggle/working') / ('animation-' + identity[:16])
for folder in ('source','depth','controls','embeddings','clips','review','logs','scripts','tasks'):
    (RUN/folder).mkdir(parents=True,exist_ok=True)
for name, source in BUNDLE.items():
    (RUN/'scripts'/name).write_text(source,encoding='utf-8')
if str(RUN/'scripts') not in sys.path: sys.path.insert(0,str(RUN/'scripts'))
from common import atomic_json, validate_config
from driver import import_sources
validate_config(CONFIG)
import_sources(RUN,SHOTS,Path('/kaggle/input'))
JOB = {'run':str(RUN), 'fingerprint':identity, 'config':CONFIG, 'models':MODELS,
       'shots':SHOTS, 'negative_prompt':NEGATIVE_PROMPT,
       'model_cache':str(SCRATCH/'models'),
       'checkpoint':{'kernel':'iliaskhan/videogenerator-v4-1-curated-assets','version':3,
                     'source_run':'production-12d2331428ec739d', 'policy':'read-only SHA256-bound inputs'}}
atomic_json(RUN/'job.json',JOB)
from bootstrap import bootstrap
PYTHON, GPU_COUNT = bootstrap(RUN,SCRATCH,PINS)
print('Separate run:',RUN,'| SMOKE_ONLY:',CONFIG['SMOKE_ONLY'])
'''.replace('__BUNDLE__', repr(scripts))
    nb = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell('Отдельный пилот; чекпоинт v4.1 не изменяется. T4 ×2 + Internet On. '
            'Input: outputs `iliaskhan/videogenerator-v4-1-curated-assets`. Run All → один тестовый I2V-клип '
            'и 4 пары static/depth. `SMOKE_ONLY=False` → 4 кадра × 2 seed. '
            '512×288, 24 fps, 3.04 с — проверка движения, не финальный 1080p. '
            'Ни один клип не принимается автоматически. Платных API нет.'),
        nbformat.v4.new_code_cell(cell_config),
        nbformat.v4.new_code_cell(bootstrap_cell),
        nbformat.v4.new_code_cell('from driver import execute\nARCHIVE = execute(JOB,PYTHON,GPU_COUNT)'),
        nbformat.v4.new_code_cell('from IPython.display import FileLink, Video, display\n'
            'print(json.dumps(json.loads((RUN/"manifest.json").read_text()),ensure_ascii=False,indent=2))\n'
            'display(FileLink(str(ARCHIVE)))\n'
            'for clip in sorted((RUN/"clips").glob("*.mp4")):\n'
            '    print(clip.name)\n'
            '    display(Video(str(clip),embed=False,width=640))\n'
            'for comparison in sorted((RUN/"review").glob("*-comparison.mp4")):\n'
            '    display(Video(str(comparison),embed=False,width=1024))')])
    nb.metadata.update(kernelspec={'display_name':'Python 3','language':'python','name':'python3'},
        language_info={'name':'python','version':'3.13'}, animation_pilot={
            'version':'4.2-motion-pilot','status':'not_yet_gpu_validated',
            'checkpoint_kernel':'iliaskhan/videogenerator-v4-1-curated-assets',
            'scope':'separate experiment; checkpoint never edited',
            'engine':'Official Wan2.2 via isolated Diffusers, NF4/FP32; no Wan2GP UI dependency',
            'validation_limit':'GPU allocation and actual generated motion require Kaggle Run All.'})
    nbformat.validate(nb)
    for index, cell in enumerate(nb.cells):
        if cell.cell_type == 'code':
            compile(cell.source, f'pilot-cell-{index}', 'exec')
    notebook = OUTPUT/'videogenerator-v4.2-kaggle-animation-pilot.ipynb'
    nbformat.write(nb, notebook)
    remote = HERE/'remote'
    remote.mkdir(exist_ok=True)
    nbformat.write(nb, remote/'animation.ipynb')
    previous = json.loads((ROOT/'work/production-v4/remote-v41/kernel-metadata.json').read_text())
    previous.update(id='iliaskhan/videogenerator-v4-2-motion-pilot', title='VideoGenerator v4.2 motion pilot',
        code_file='animation.ipynb', kernel_sources=['iliaskhan/videogenerator-v4-1-curated-assets'])
    atomic_json(remote/'kernel-metadata.json', previous)
    atomic_json(OUTPUT/'experiment-plan.json', {k:v for k,v in specification.items() if k != 'scripts'})
    verify_checkpoint()
    print(f'SAVED {notebook}; {len(nb.cells)} cells, one short Markdown cell.')


if __name__ == '__main__':
    main()
