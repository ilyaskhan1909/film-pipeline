"""Separate quality-control notebook; never overwrites the completed full run."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import nbformat

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TASKS=[
    {'id':'shot-042','index':42,'prompt':
     'A naturalistic first-person photograph looking along a dark pine forest footpath at night. Only damp leaves, exposed roots and tall tree trunks fill the frame. A small soft oval pool of cold white illumination falls on the path low in the image, and fades naturally into deep black shadows farther away. Empty foreground. The observer and every piece of equipment are behind the camera. Clear sharp bark, quiet air, subdued neutral color, 35mm lens, understated live-action horror cinematography.'},
    {'id':'shot-047','index':47,'prompt':
     'Close naturalistic night photograph of a heavy black cylindrical electric torch lying horizontally on damp fallen leaves at the roots of an old oak. Its handle is on the LEFT and its glass lens is on the RIGHT. Camera sees the SIDE of the cylinder, the rim of the lens visible only edge-on. One narrow pale cone of light travels RIGHTWARD from that lens along the soil onto the oak roots at the right edge of the photograph. Forest behind falls into darkness. Physically plausible metal, glass, leaf texture and modest exposure, 65mm lens.'},
    {'id':'shot-051','index':51,'prompt':
     'Close night photograph of a palm-sized crude rag doll resting in damp leaves beneath rough oak roots. Entirely coarse stained TAN burlap, clumsily hand-sewn, lumpy rectangular sack head, one large black button eye and one smaller black button eye, a short straight black stitch for its expressionless mouth. Its two closed stuffed burlap mitten-shaped hands touch together in front of its lap, holding ONE loose tiny torn square of COBALT-BLUE shirt cloth. The blue square is separate from the tan doll, its frayed edge hanging freely below those cloth mittens. Cold camera-side illumination on the passive cloth object, dark blurred forest background, unsettling handmade prop photograph, 85mm lens.'},
    {'id':'shot-053','index':53,'prompt':
     'Extreme close photograph of just TWO small CLOSED mitten-shaped stubs of coarse stained tan burlap, stitched shut and stuffed with cotton, with clumsy black seams. These small doll mittens pinch ONE loose thumbnail-sized torn square of cobalt-blue woven cloth between them. Frayed blue threads are clearly visible. Every part of the mitten surfaces is continuous opaque tan fabric, including their closed tips. The cloth mittens and blue scrap fill the image; nothing of the doll above its wrists is included. Dark defocused oak leaves behind. A soft cold patch of camera-side illumination reveals tactile cloth weave. Real handmade prop, naturalistic macro photography, 100mm lens.'}
]


def main():
    nb=copy.deepcopy(nbformat.read(ROOT/'outputs/videogenerator-v4-production-FULL.ipynb',as_version=4))
    values={}
    for node in ast.parse(nb.cells[1].source).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('CONFIG','PLAN','PINS','REVISIONS','IMPLEMENTATION_SHA'):
            values[node.targets[0].id]=ast.literal_eval(node.value)
    values['CONFIG'].update(QUICK_TEST=True,PILOT_AUDIO_INDICES=[],COMPARE_BASE=False)
    values['PLAN']['control_tasks']=TASKS
    scripts={name:(HERE/name).read_text(encoding='utf-8') for name in ('control_worker.py','control_driver.py')}
    for source in scripts.values():compile(source,'control-source','exec')
    values['IMPLEMENTATION_SHA']=hashlib.sha256(json.dumps({'original':values['IMPLEMENTATION_SHA'],'control':scripts},sort_keys=True).encode()).hexdigest()
    id_config={k:v for k,v in values['CONFIG'].items() if k not in ('QUICK_TEST','TEST_SCENES','COMPARE_BASE','PILOT_AUDIO_INDICES')}
    runid=hashlib.sha256(json.dumps({'config':id_config,'plan':values['PLAN'],'implementation':values['IMPLEMENTATION_SHA'],
        'revisions':values['REVISIONS'],'pins':values['PINS']},sort_keys=True).encode()).hexdigest()[:16]
    nb.cells[1].source='\n'.join(f'{key}={values[key]!r}' if (key:=line.split('=',1)[0]) in values else line
                              for line in nb.cells[1].source.splitlines())+'\n'
    for name,source in scripts.items():
        nb.cells[2].source+=f'\n(RUN/"scripts"/{name!r}).write_text({source!r},encoding="utf-8")\n'
    nb.cells[4].source='from control_driver import execute_control\nARCHIVE=execute_control(RUN,CONFIG,ENVS)'
    nb.cells[0].source='GPU T4 ×2 + Internet On. Контроль качества: одинаковые короткие промпты, seed и размер; Klein 4B и Z-Image Turbo с рекомендуемыми настройками. Только PNG, без платных API. Выполнение не означает визуального одобрения.'
    nb.metadata.videogenerator.update(run_id=runid,status='control_not_yet_runtime_validated')
    nbformat.validate(nb)
    for i,cell in enumerate(nb.cells):
        if cell.cell_type=='code':compile(cell.source,f'control-cell-{i}','exec')
    folder=HERE/'remote-control'
    folder.mkdir(exist_ok=True)
    nbformat.write(nb,folder/'production.ipynb')
    nbformat.write(nb,ROOT/'outputs/videogenerator-v4-image-control.ipynb')
    meta=json.loads((HERE/'remote-full/kernel-metadata.json').read_text(encoding='utf-8'))
    meta.update(id='iliaskhan/videogenerator-v4-image-control',title='VideoGenerator v4 image control',kernel_sources=[])
    (folder/'kernel-metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps({'run_id':runid,'directory':str(folder),'tasks':len(TASKS)}),flush=True)


if __name__=='__main__':main()
