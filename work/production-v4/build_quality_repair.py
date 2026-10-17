"""Freeze an explicit image-only correction notebook with no original mutation."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import nbformat
from make_repair import make
from repair_briefs import make_spec

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('choices',type=Path)
    p.add_argument('--directory',type=Path,default=HERE/'remote-quality-repair')
    args=p.parse_args()
    assert not (args.directory/'production.ipynb').exists(),'Use a new output directory.'
    choices=json.loads(args.choices.read_text(encoding='utf-8'))
    shots=make_spec(choices)
    assert all(s['engine'] in ('klein','zimage') for s in shots.values())
    nb=make(nbformat.read(ROOT/'outputs/videogenerator-v4-production-FULL.ipynb',as_version=4),
        {'shots':{k:{a:b for a,b in v.items() if a!='engine'} for k,v in shots.items()}})
    values={}
    for node in ast.parse(nb.cells[1].source).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('CONFIG','PLAN','PINS','REVISIONS','IMPLEMENTATION_SHA'):
            values[node.targets[0].id]=ast.literal_eval(node.value)
    for ident,patch in shots.items():values['PLAN']['shots'][int(ident[5:])]['engine']=patch['engine']
    sources={name:(HERE/name).read_text(encoding='utf-8') for name in ('repair_image_worker.py','repair_driver.py')}
    values['IMPLEMENTATION_SHA']=hashlib.sha256(json.dumps({'frozen_base':values['IMPLEMENTATION_SHA'],
        'repair_sources':sources},sort_keys=True).encode()).hexdigest()
    identity={k:v for k,v in values['CONFIG'].items() if k not in ('QUICK_TEST','TEST_SCENES','COMPARE_BASE','PILOT_AUDIO_INDICES')}
    runid=hashlib.sha256(json.dumps({'config':identity,'plan':values['PLAN'],'implementation':values['IMPLEMENTATION_SHA'],
        'revisions':values['REVISIONS'],'pins':values['PINS']},sort_keys=True).encode()).hexdigest()[:16]
    nb.cells[1].source='\n'.join(f'{key}={values[key]!r}' if (key:=line.split('=',1)[0]) in values else line
                             for line in nb.cells[1].source.splitlines())+'\n'
    for name,source in sources.items():
        compile(source,name,'exec')
        nb.cells[2].source+=f'\n(RUN/"scripts"/{name!r}).write_text({source!r},encoding="utf-8")\n'
    nb.cells[4].source='from repair_driver import execute_repair\nARCHIVE=execute_repair(RUN,CONFIG,ENVS)'
    nb.cells[0].source='T4 ×2 + Internet On. Только исправления PNG: исходная история и WAV неизменны. Проверенные контрольные кадры переиспользуются по fingerprint. Результат требует визуального отбора; платных API и генерации видео нет.'
    nb.metadata.videogenerator.update(run_id=runid,status='quality_repair_not_yet_runtime_validated',
        repair_spec={'shots':shots},control_choices=choices)
    nbformat.validate(nb)
    for i,cell in enumerate(nb.cells):
        if cell.cell_type=='code':compile(cell.source,f'repair-cell-{i}','exec')
    args.directory.mkdir(parents=True,exist_ok=True)
    nbformat.write(nb,args.directory/'production.ipynb')
    nbformat.write(nb,ROOT/'outputs/videogenerator-v4-quality-repair.ipynb')
    meta=json.loads((HERE/'remote-full/kernel-metadata.json').read_text(encoding='utf-8'))
    meta.update(id='iliaskhan/videogenerator-v4-quality-repair',title='VideoGenerator v4 quality repair',
        kernel_sources=['iliaskhan/videogenerator-v4-production-full','iliaskhan/videogenerator-v4-image-control'])
    (args.directory/'kernel-metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps({'run_id':runid,'directory':str(args.directory),'shots':len(shots),'audio_regenerated':False}),flush=True)


if __name__=='__main__':main()
