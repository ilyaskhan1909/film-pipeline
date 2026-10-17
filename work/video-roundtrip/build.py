"""Separate video-only Kaggle notebook; image/voice/music/edit assets stay local."""
import json
from pathlib import Path

import nbformat

from contract import identity, save_json
from prepare import DATASET, OUTPUT, ROOT, prepare

HERE = Path(__file__).resolve().parent


def main():
    inputs = prepare()
    scripts = {name: (HERE / name).read_text(encoding='utf-8') for name in
               ('contract.py', 'driver.py', 'batch_worker.py')}
    scripts.update({
        'wan_worker.py': (ROOT / 'work/a14b-dual/worker.py').read_text(encoding='utf-8'),
        'bootstrap.py': (ROOT / 'work/a14b-dual/bootstrap.py').read_text(encoding='utf-8'),
        'common.py': (ROOT / 'work/animation-pilot/common.py').read_text(encoding='utf-8')})
    for name, source in scripts.items():
        compile(source, name, 'exec')
    configuration = f'EXPECTED_HANDOFF_ID = {inputs["handoff_id"]!r}\n'
    setup = '''import json, sys
from pathlib import Path
SCRATCH = Path('/tmp/videogenerator-v5-video-only')
SCRATCH.mkdir(parents=True,exist_ok=True)
BUNDLE = __BUNDLE__
# Stage contract code in scratch, then validate the attached LOCAL asset bundle.
STAGING = SCRATCH/'contract'
STAGING.mkdir(parents=True,exist_ok=True)
for name,source in BUNDLE.items():
    (STAGING/name).write_text(source,encoding='utf-8')
sys.path.insert(0,str(STAGING))
from contract import identity,load_inputs,save_json
INPUTS = load_inputs(Path('/kaggle/input'),EXPECTED_HANDOFF_ID,SCRATCH/'inputs'/EXPECTED_HANDOFF_ID)
if len({r['config']['MAX_SEQUENCE'] for r in INPUTS['requests']}) != 1:
    raise ValueError('All requests in this batch must use the same text context length.')
signature = identity({'inputs':INPUTS,'scripts':BUNDLE})
RUN = Path('/kaggle/working')/('video-only-'+signature[:16])
for folder in ('scripts','frames','source','embeddings','clips','reports','requests','diagnostics','logs'):
    (RUN/folder).mkdir(parents=True,exist_ok=True)
for name,source in BUNDLE.items():
    (RUN/'scripts'/name).write_text(source,encoding='utf-8')
# Copy only checksum-bound frames. No TTS, ASR, music, titles or montage here.
load_inputs(SCRATCH/'inputs',EXPECTED_HANDOFF_ID,RUN)
JOB = {'run':str(RUN),'fingerprint':signature,'inputs':INPUTS,
    'models':INPUTS['profile']['models'],'config':INPUTS['requests'][0]['config'],
    'model_cache':str(SCRATCH/'models'),'negative_prompt':INPUTS['negative_prompt']}
save_json(RUN/'job.json',JOB)
from bootstrap import bootstrap
PYTHON = bootstrap(RUN,SCRATCH,INPUTS['profile']['pins'])
print('Kaggle stage: silent video only | batch:',EXPECTED_HANDOFF_ID)
'''.replace('__BUNDLE__', repr(scripts))
    notebook = nbformat.v4.new_notebook(cells=[
        nbformat.v4.new_markdown_cell('Только I2V-видео. T4 ×2 + Internet On; Input: private '
            '`iliaskhan/the-last-firework-video-inputs-v5` (или подготовленный inputs.zip). '
            'Run All → results.zip с немыми клипами, параметрами и логами. '
            'Голос, музыка, титры и монтаж — локально. Первый пакет: один короткий тест A14B/Q8/FP32, '
            'GPU ещё не проверен. Готовые клипы проходят просмотр, автоматически в фильм не вставляются. '
            'Для продолжения того же пакета можно приложить предыдущий results.zip.'),
        nbformat.v4.new_code_cell(configuration),
        nbformat.v4.new_code_cell(setup),
        nbformat.v4.new_code_cell('from driver import execute\nRESULTS = execute(JOB,PYTHON)'),
        nbformat.v4.new_code_cell('from IPython.display import FileLink,Video,display\n'
            'print(json.dumps(json.loads((RUN/"video-results.json").read_text()),indent=2))\n'
            'display(FileLink(str(RESULTS)))\n'
            'for clip in sorted((RUN/"clips").glob("*.mp4")):\n'
            '    display(Video(str(clip),embed=False,width=768))')])
    notebook.metadata.update(kernelspec={'display_name':'Python 3','language':'python','name':'python3'},
        language_info={'name':'python','version':'3.13'}, video_only={
            'version':'5.0','status':'local_contract_validated_gpu_execution_pending',
            'scope':'Local assets -> Kaggle silent video -> local editing',
            'handoff_id':inputs['handoff_id'],'production_approved':False})
    nbformat.validate(notebook)
    for i, cell in enumerate(notebook.cells):
        if cell.cell_type == 'code':
            compile(cell.source, f'cell-{i}', 'exec')
    path = OUTPUT / 'videogenerator-v5-kaggle-video-only.ipynb'
    nbformat.write(notebook, path)
    remote = HERE / 'remote'
    remote.mkdir(exist_ok=True)
    nbformat.write(notebook, remote / 'video-only.ipynb')
    metadata = json.loads((ROOT / 'work/a14b-dual/remote/kernel-metadata.json').read_text())
    metadata.update(id='iliaskhan/videogenerator-v5-video-only', title='VideoGenerator v5 video only',
        code_file='video-only.ipynb', kernel_sources=[], dataset_sources=[DATASET])
    save_json(remote / 'kernel-metadata.json', metadata)
    save_json(OUTPUT / 'pipeline-state.json', {'handoff_id':inputs['handoff_id'],
        'notebook':str(path),'requested_video_clips':len(inputs['requests']),
        'kaggle_stage':'video_only','local_stage':'keyframes, prompts, narration, music, QA and editing',
        'checkpoint_modified':False,'gpu_run_submitted':False,'new_video_generated':False,
        'backend_runtime_verified':False,'new_audio_or_images_generated':False,
        'resume_scope':'Only complete verified clips from the identical job fingerprint.',
        'no_persistent_model_cache_claim':True})
    print('SAVED', path, len(notebook.cells), 'cells')


if __name__ == '__main__':
    main()
