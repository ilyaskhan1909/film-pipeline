"""One standalone, minimal-Markdown notebook; historical originals stay frozen."""
import ast
import copy
import hashlib
import json
import pprint
import argparse
from pathlib import Path
import nbformat
from repair_briefs import make_spec
from focused_edits import apply_edits

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--focus',action='store_true')
    args=parser.parse_args()
    nb=copy.deepcopy(nbformat.read(ROOT/'outputs/videogenerator-v4-production-FULL.ipynb',as_version=4))
    values={}
    for node in ast.parse(nb.cells[1].source).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('CONFIG','PLAN','PINS','REVISIONS','IMPLEMENTATION_SHA'):
            values[node.targets[0].id]=ast.literal_eval(node.value)
    choices=json.loads((HERE/'control-choices.json').read_text(encoding='utf-8'))
    for ident,patch in make_spec(choices).items():values['PLAN']['shots'][int(ident[5:])].update(patch)
    values['PLAN']['export_shots']=[i for i in range(71) if i not in (2,21,26,31,55,61,65,67)]
    values['PLAN']['excluded_shots']={2:'extra tent / redundant establishing',21:'hand on knee rather than forearm',
        26:'duplicated woman',31:'empty hands contradict carried torch',
        55:'wrong blue-cloth and lighting continuity',61:'extra doll / inconsistent cloth prop',
        65:'ambiguous branch hand / pointing anatomy',67:'unused redundant object insert'}
    values['CONFIG'].update(QUICK_TEST=False,COMPARE_BASE=False,Z_IMAGE_STEPS=9,Z_IMAGE_GUIDANCE=0.0)
    focus_indices=apply_edits(values['PLAN'])
    if args.focus:
        values['CONFIG'].update(QUICK_TEST=True,PILOT_AUDIO_INDICES=[])
        values['PLAN']['pilot_shots']=focus_indices
    assert len(values['PLAN']['export_shots'])==63
    scripts={name:(HERE/name).read_text(encoding='utf-8') for name in ('full_image_worker.py','full_driver.py','resume_assets.py','edit_reference_loader.py')}
    values['IMPLEMENTATION_SHA']=hashlib.sha256(json.dumps({'frozen_base':values['IMPLEMENTATION_SHA'],
        'v41_sources':scripts},sort_keys=True).encode()).hexdigest()
    identity={k:v for k,v in values['CONFIG'].items() if k not in ('QUICK_TEST','TEST_SCENES','COMPARE_BASE','PILOT_AUDIO_INDICES')}
    runid=hashlib.sha256(json.dumps({'config':identity,'plan':values['PLAN'],'implementation':values['IMPLEMENTATION_SHA'],
        'revisions':values['REVISIONS'],'pins':values['PINS']},sort_keys=True).encode()).hexdigest()[:16]
    nb.cells[1].source='\n'.join(f'{key}={pprint.pformat(values[key],width=105,sort_dicts=False)}' if (key:=line.split('=',1)[0]) in values else line
                             for line in nb.cells[1].source.splitlines())+'\n'
    runtime=nb.cells[2].source
    start=runtime.index('# Reuse verified compatible speech;')
    end=runtime.index("atomic_json(RUN/'job.json'")
    code=''
    for name,source in scripts.items():
        compile(source,name,'exec')
        code+=f'(RUN/"scripts"/{name!r}).write_text({source!r},encoding="utf-8")\n'
    code+='from resume_assets import resume\nresume(RUN,CONFIG,PLAN,PINS,REVISIONS)\n'
    nb.cells[2].source=runtime[:start]+code+runtime[end:]
    nb.cells[4].source='from full_driver import execute_full\nARCHIVE=execute_full(RUN,CONFIG,ENVS)'
    nb.cells[0].source='T4 ×2 + Internet On → Run All. 26 сухих WAV, 63 PNG, таймкоды и manifest; история без сокращений. QUICK_TEST=True → малый тест. Платных API и генерации видео нет. Результат требует просмотра и прослушивания перед монтажом.'
    nb.metadata.videogenerator.update(version='4.1-curated-assets',run_id=runid,status='not_yet_runtime_validated',
        model_routing='Klein actors/props, Z-Image selected forest frames; immutable revisions and per-image fingerprints.')
    nbformat.validate(nb)
    for i,cell in enumerate(nb.cells):
        if cell.cell_type=='code':compile(cell.source,f'v41-cell-{i}','exec')
    folder=HERE/('remote-focus' if args.focus else 'remote-v41')
    folder.mkdir(exist_ok=True)
    nbformat.write(nb,folder/'production.ipynb')
    output=ROOT/'outputs'/('videogenerator-v4.1-focused-edits.ipynb' if args.focus else 'videogenerator-v4.1-kaggle-assets.ipynb')
    nbformat.write(nb,output)
    meta=json.loads((HERE/'remote-full/kernel-metadata.json').read_text(encoding='utf-8'))
    meta.update(id='iliaskhan/videogenerator-v4-1-focused-edits' if args.focus else 'iliaskhan/videogenerator-v4-1-curated-assets',
        title='VideoGenerator v4.1 focused edits' if args.focus else 'VideoGenerator v4.1 curated assets',
        kernel_sources=['iliaskhan/videogenerator-v4-production-full','iliaskhan/videogenerator-v4-quality-repair'])
    if not args.focus:meta['kernel_sources'].append('iliaskhan/videogenerator-v4-1-focused-edits')
    (folder/'kernel-metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps({'notebook':str(output),'run_id':runid,'shots':len(focus_indices) if args.focus else 63,
        'audio_segments':0 if args.focus else 26,'status':'not_yet_runtime_validated'}),flush=True)


if __name__=='__main__':main()
