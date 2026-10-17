"""Build a NEW notebook; never overwrite v4.1 or the rejected v4.2 pilot."""
import ast
import json
import pprint
from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / 'outputs/a14b-dual'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    previous = ROOT / 'work/animation-pilot'
    old_driver = (previous / 'driver.py').read_text(encoding='utf-8')
    tree = ast.parse(old_driver)
    source_function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'import_sources')
    source_code = 'import json, shutil, zipfile\nfrom pathlib import Path\nfrom common import atomic_json, sha256\n\n' + ast.get_source_segment(old_driver, source_function)
    scripts = {name: (HERE / name).read_text(encoding='utf-8') for name in
               ('bootstrap.py', 'worker.py', 'driver.py')}
    scripts['common.py'] = (previous / 'common.py').read_text(encoding='utf-8')
    scripts['source_import.py'] = source_code
    for name, text in scripts.items():
        compile(text, name, 'exec')
    config = {'WIDTH': 768, 'HEIGHT': 432, 'FRAMES': 49, 'FPS': 24,
        'STEPS': 40, 'GUIDANCE': 3.5, 'SEED': 20261005, 'MAX_SEQUENCE': 256,
        'ATTENTION_QUERY_CHUNK': 256, 'MAX_WORKER_SECONDS': 7200}
    models = {'original': {'repo': 'Wan-AI/Wan2.2-I2V-A14B-Diffusers',
        'revision': '596658fd9ca6b7b71d5057529bbf319ecbc61d74'},
        'quantized': {'repo': 'QuantStack/Wan2.2-I2V-A14B-GGUF',
            'revision': '6c6717459277b9cd1f72579d78a0fd62a79e57dc',
            'files': {'high': {'name': 'HighNoise/Wan2.2-I2V-A14B-HighNoise-Q8_0.gguf',
                'sha256': '619a66032c28e1b27882dfccc0bf93e51edb1491e8d4e4c6f291726abe4de8aa'},
                'low': {'name': 'LowNoise/Wan2.2-I2V-A14B-LowNoise-Q8_0.gguf',
                'sha256': '029c7adc74de4f7804905c5e4fb9335d0862cd2fc37191df526aeac13b64425e'}}}}
    pins = ['diffusers==0.40.0', 'transformers==5.18.0', 'accelerate==1.15.0',
            'bitsandbytes==0.50.2', 'gguf==0.19.0', 'sentencepiece==0.2.1', 'ftfy==6.3.1']
    old_plan = json.loads((ROOT / 'outputs/animation-pilot/experiment-plan.json').read_text(encoding='utf-8'))
    shots = [old_plan['shots'][0]]
    shots[0]['prompt'] = ('A locked-off tripod landscape shot of this exact lake and tree-lined shore. '
        'Small gentle ripples move across the water and softly disturb the reflections. '
        'The shoreline, trees and sky retain their appearance and positions. '
        'The camera is completely stationary. Calm, natural, restrained motion. '
        'Preserve the source photograph; no new objects or scene change.')
    negative = ('Camera movement, zoom, pan, shake, cuts, new objects, boats, people, animals, '
        'changing trees, changing shoreline, changing sky, exaggerated motion, deformation, '
        'melting, flicker, strobing, oversaturated, cartoon, blur, text, watermark.')
    variables = [('CONFIG', config), ('PINS', pins), ('MODELS', models),
                 ('SHOTS', shots), ('NEGATIVE_PROMPT', negative)]
    specification = {'config': config, 'pins': pins, 'models': models,
                     'shots': shots, 'negative_prompt': negative}
    config_cell = '\n'.join(f'{k} = {pprint.pformat(v, width=110, sort_dicts=False)}' for k, v in variables)
    setup = '''import hashlib, json, sys
from pathlib import Path
SCRATCH = Path('/tmp/videogenerator-v4-3-a14b-dual')
SCRATCH.mkdir(parents=True, exist_ok=True)
BUNDLE = __BUNDLE__
if CONFIG['WIDTH'] % 16 or CONFIG['HEIGHT'] % 16 or CONFIG['WIDTH']*9 != CONFIG['HEIGHT']*16:
    raise ValueError('Native 16:9 resolution must be divisible by 16.')
if CONFIG['FRAMES'] < 9 or (CONFIG['FRAMES']-1) % 4 or CONFIG['FPS'] != 24:
    raise ValueError('Use 4n+1 frames and 24 fps.')
if not 20 <= CONFIG['STEPS'] <= 80 or not 1 < CONFIG['GUIDANCE'] <= 10:
    raise ValueError('Use 20..80 steps and 1 < guidance <= 10.')
spec = {'config':CONFIG,'pins':PINS,'models':MODELS,'shots':SHOTS,
        'negative_prompt':NEGATIVE_PROMPT,'scripts':BUNDLE}
identity = hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
RUN = Path('/kaggle/working') / ('a14b-dual-' + identity[:16])
for folder in ('scripts','source','embeddings','clips','diagnostics','review','logs'):
    (RUN/folder).mkdir(parents=True,exist_ok=True)
for name,source in BUNDLE.items():
    (RUN/'scripts'/name).write_text(source,encoding='utf-8')
sys.path.insert(0,str(RUN/'scripts'))
from common import atomic_json
from source_import import import_sources
import_sources(RUN,SHOTS,Path('/kaggle/input'))
JOB = {'run':str(RUN),'fingerprint':identity,'config':CONFIG,'models':MODELS,
       'shots':SHOTS,'negative_prompt':NEGATIVE_PROMPT,'model_cache':str(SCRATCH/'models'),
       'checkpoint':{'kernel':'iliaskhan/videogenerator-v4-1-curated-assets','version':3,
           'source_run':'production-12d2331428ec739d','policy':'read-only SHA256-bound images'}}
atomic_json(RUN/'job.json',JOB)
from bootstrap import bootstrap
PYTHON = bootstrap(RUN,SCRATCH,PINS)
print('Separate experiment:',RUN)
'''.replace('__BUNDLE__', repr(scripts))
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell('Отдельный тест A14B; v4.1/v4.2 не изменяются. T4 ×2, Internet On; '
            'Input: outputs `iliaskhan/videogenerator-v4-1-curated-assets`. Run All: диагностика '
            '256×144/9 кадров/2 шага, затем один клип 768×432/49 кадров/40 шагов (2.04 с). '
            'Q8 diffusion + NF4 T5, FP32; активный эксперт распределён между GPU, без обещания 2× скорости. '
            'Лимит worker 2 часа. Клип требует просмотра, в фильм автоматически не вставляется. Платных API нет.'),
        nbformat.v4.new_code_cell(config_cell),
        nbformat.v4.new_code_cell(setup),
        nbformat.v4.new_code_cell('from driver import execute\nARCHIVE = execute(JOB,PYTHON)'),
        nbformat.v4.new_code_cell('from IPython.display import FileLink, Video, display\n'
            'print(json.dumps(json.loads((RUN/"manifest.json").read_text()),ensure_ascii=False,indent=2))\n'
            'display(FileLink(str(ARCHIVE)))\n'
            'for clip in sorted((RUN/"clips").glob("*.mp4")):\n'
            '    display(Video(str(clip),embed=False,width=768))')])
    notebook.metadata.update(kernelspec={'display_name':'Python 3','language':'python','name':'python3'},
        language_info={'name':'python','version':'3.13'}, a14b_dual={
            'version':'4.3','status':'not_yet_gpu_validated','production_approved':False,
            'scope':'separate experiment; checkpoint unchanged',
            'runtime_validation':'Pending Kaggle T4 x2 Run All; local validation is static only.'})
    nbformat.validate(notebook)
    for i, cell in enumerate(notebook.cells):
        if cell.cell_type == 'code':
            compile(cell.source, f'cell-{i}', 'exec')
    path = OUTPUT / 'videogenerator-v4.3-kaggle-a14b-dual.ipynb'
    nbformat.write(notebook, path)
    remote = HERE / 'remote'
    remote.mkdir(exist_ok=True)
    nbformat.write(notebook, remote / 'a14b.ipynb')
    meta = json.loads((previous / 'remote/kernel-metadata.json').read_text())
    meta.update(id='iliaskhan/videogenerator-v4-3-a14b-dual',
        title='VideoGenerator v4.3 A14B dual', code_file='a14b.ipynb')
    (remote / 'kernel-metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    (OUTPUT / 'experiment-plan.json').write_text(json.dumps(
        specification, indent=2), encoding='utf-8')
    print('SAVED', path, len(notebook.cells), 'cells; one short Markdown cell')


if __name__ == '__main__':
    main()
