"""Attach bounded runtime evidence without changing any executable notebook cell."""
import hashlib
import json
from pathlib import Path
import nbformat

ROOT=Path(__file__).resolve().parents[2]
target=ROOT/'outputs/videogenerator-v4.1-kaggle-assets.ipynb'
remote=ROOT/'work/production-v4/evidence-v41-v3/final/videogenerator-v4-1-curated-assets.ipynb'
local_nb=nbformat.read(target,as_version=4)
remote_nb=nbformat.read(remote,as_version=4)
assert [(c.cell_type,c.source) for c in local_nb.cells]==[(c.cell_type,c.source) for c in remote_nb.cells]
assets=ROOT/'outputs/first-film/curated/assets'
manifest=json.loads((assets/'production_manifest.json').read_text(encoding='utf-8'))
assert manifest['run_id']=='production-'+local_nb.metadata.videogenerator.run_id
assert len(manifest['shots'])==63 and len(manifest['scenes'])==26 and manifest['failures']==[]
environment=json.loads((assets/'environment.json').read_text(encoding='utf-8'))
evidence={'status':'gpu_run_all_passed_with_verified_resume_inputs',
          'kernel':'iliaskhan/videogenerator-v4-1-curated-assets','kernel_version':3,
          'gpu':environment['gpu'],'exported_images':63,'dry_audio_clips':26,
          'dry_narration_seconds':manifest['narration_seconds'],
          'executed_source_sha256':hashlib.sha256(remote.read_bytes()).hexdigest(),
          'manifest_sha256':hashlib.sha256((assets/'production_manifest.json').read_bytes()).hexdigest(),
          'generation_evidence':['Full v4.0 generated 71 PNG and 26 WAV on Kaggle.',
                                 'Controlled Klein/Z-Image comparison and 46-shot repair generated on Kaggle.',
                                 '12 focused reference edits generated on Kaggle; 10 selected in the final pool.'],
          'limits':['Final Run All reused verified assets rather than regenerating all images.',
                    'Cold reference bootstrap without attached source outputs has not been GPU-tested.',
                    'No continuous audiovisual or user voice-acting approval is claimed.']}
local_nb.metadata.videogenerator.update(status=evidence['status'],runtime_evidence=evidence)
nbformat.validate(local_nb)
for i,cell in enumerate(local_nb.cells):
    if cell.cell_type=='code':compile(cell.source,f'cell-{i}','exec')
nbformat.write(local_nb,target)
(assets.parent/'notebook_validation.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps({'saved':str(target),'status':evidence['status'],'executable_cells_changed':False}),flush=True)
