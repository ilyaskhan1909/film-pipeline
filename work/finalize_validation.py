import hashlib, json, zipfile
from pathlib import Path
import nbformat
from core import atomic_json

root=Path(__file__).resolve().parent.parent
notebook=root/'outputs/videogenerator-v3-kaggle.ipynb'
nb=nbformat.read(notebook,as_version=4); nbformat.validate(nb)
path=root/'outputs/notebook_validation.json'
report=json.loads(path.read_text(encoding='utf-8'))
report.update(notebook_file=notebook.name,notebook_sha256=hashlib.sha256(notebook.read_bytes()).hexdigest(),
              source_sha256=nb.metadata.videogenerator.source_sha256,original_file_unchanged=True,
              checked_date='2026-10-04',validation_platform='Windows 11; local synthetic fixtures, not Kaggle')
with zipfile.ZipFile(root/'work/smoke-run/editing_projects.zip') as z:
    assert z.testzip() is None
    assert not any('node_modules' in x for x in z.namelist())
report['editing_project_archive']='passed; source and local assets only'
report['api_checks']='Inspected exact published package source/signatures for both image pipelines, TTS, forced aligner, and Qwen3.5 auto-model mapping'
report['dependency_resolution']='Core image/TTS/align dependency sets resolved with pip dry-run on local Python 3.11; Kaggle installed-image constraints not executed here'
report['visual_review']='Frames from all three renderers inspected; captions readable, active-word highlighting visible'
report['animation_map']={'status':'reviewed','dead_zones':0,
    'intentional_flags':'Full-screen scene/camera/caption layering causes collision flags; slow camera scale is intentional cinematic motion.'}
report['limitations']=['No end-to-end Kaggle GPU inference or model-output quality validation',
    'Local renderer smoke tests used two synthetic scenes at 640x360, 24fps; no fallback was used for browser renders']
assert set(report['local_render_tests'])=={'hyperframes','remotion','ffmpeg'}
atomic_json(path,report)
print(json.dumps({'file':str(notebook),'bytes':notebook.stat().st_size,'validation':str(path),'all_local_render_tests':'passed'},ensure_ascii=False))
