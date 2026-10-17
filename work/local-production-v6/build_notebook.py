"""Separate v6 notebook bound to reviewed local keyframes; never submit a GPU run."""
import ast
import json
from pathlib import Path
import nbformat

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'outputs/local-production-v6'


def main():
    handoff=json.loads((OUT/'kaggle-handoff.json').read_text())
    source=ROOT/'outputs/video-roundtrip/videogenerator-v5-kaggle-video-only.ipynb'
    notebook=nbformat.read(source,as_version=4)
    notebook.cells[0].source=('Только немое I2V. T4 ×2, Internet On, 48 GiB свободного scratch. '
        'Добавьте отдельный v6 inputs.zip как Input. Два коротких теста сохранения лиц; '
        'A14B/Q8/FP32 на двух T4 ещё НЕ проверен реальным запуском. '
        'Локальные кадры, голос, музыка, титры и монтаж не генерируются здесь. '
        'Run All → results.zip; клипы проверяются до монтажа. '
        'Текущая GPU-квота 0 до 2026-10-10 00:00 UTC: запуск пока не отправлять.')
    notebook.cells[1].source=f'EXPECTED_HANDOFF_ID = {handoff["handoff_id"]!r}\n'
    notebook.cells[2].source=notebook.cells[2].source.replace(
        '/tmp/videogenerator-v5-video-only','/tmp/videogenerator-v6-video-only')
    notebook.metadata.video_only.update(version='6.0',handoff_id=handoff['handoff_id'],
        status='local_assets_and_contract_verified_kaggle_gpu_pending',
        source_keyframes_generated_locally=True,production_approved=False,
        gpu_run_submitted=False,paid_api=False)
    for index,cell in enumerate(notebook.cells):
        if cell.cell_type!='code':continue
        cell.execution_count=None;cell.outputs=[]
        compile(cell.source,f'v6-cell-{index}','exec')
        tree=ast.parse(cell.source)
        for node in tree.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BUNDLE' for t in node.targets):
                for name,script in ast.literal_eval(node.value).items():compile(script,name,'exec')
    nbformat.validate(notebook)
    target=OUT/'videogenerator-v6-kaggle-video-only.ipynb'
    nbformat.write(notebook,target)
    report={'notebook':str(target),'handoff_id':handoff['handoff_id'],'cells':len(notebook.cells),
        'nbformat_valid':True,'code_cells_compile':True,'embedded_workers_compile':True,
        'gpu_runtime_tested':False,'gpu_run_submitted':False,'original_notebooks_modified':False}
    (OUT/'notebook-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('SAVED',target.name,'static validation only; no Kaggle job submitted.')


if __name__=='__main__':main()
