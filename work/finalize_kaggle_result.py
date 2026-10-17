"""Package verified execution evidence without changing the tested code or originals."""
import hashlib
import json
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parent.parent
ACTUAL = ROOT / "outputs/kaggle-test-v2"
uploaded = ROOT / "work/remote-run-02/notebook6c8f01ed68.ipynb"
nb = nbformat.read(uploaded, as_version=4)
technical = json.loads((ACTUAL / "actual_kaggle_validation.json").read_text(encoding="utf-8"))
remote = json.loads((ACTUAL / "evidence/remote_status.json").read_text(encoding="utf-8"))
asr = json.loads((ACTUAL / "independent_asr.json").read_text(encoding="utf-8"))
state = json.loads((ACTUAL / "assets/pipeline_state.json").read_text(encoding="utf-8"))
assert technical["status"] == "passed" and remote["status"] == "KernelWorkerStatus.COMPLETE"
assert technical["selected_scene_count"] == 2 and technical["scope"] == "test"
implementation = hashlib.sha256("".join((ROOT / "work" / name).read_text(encoding="utf-8")
                                     for name in ("core.py", "worker.py", "raw_export.py")).encode()).hexdigest()
assert implementation == nb.metadata.videogenerator.implementation_sha256
tested_code = [c.source for c in nb.cells if c.cell_type == "code"]
nb.cells[-1].source = """Проверено: Kaggle Save & Run All, версия 2 — COMPLETE; Python 3.13.15, Tesla T4, 2 сцены, 37,17 с. MP4 1920×1080/24 fps полностью декодированы; 19 контрольных сумм ZIP совпали. Независимый offline-ASR: WER 0% после нормализации Fourth/4th.

Это технически проверенный тест, не production master. Кадры статические и слишком похожи; первая сцена содержит тайминги 47 из 48 слов. Один промпт ЛЛМ заменён шаблоном. Субтитры требуют проверки при монтаже. Полная история (36 сцен), Z-Image, Kokoro и другие языки этим запуском не проверены.

Ошибки: logs/. QUICK_TEST=False — вся история. LLM_ENABLED=False — без локальной ЛЛМ; ALIGN_WORDS=False — без таймингов. Исходный notebook не изменён. Результат запуска: kaggle_run_result.json рядом с этой копией.
"""
verification = {"status": "COMPLETE", "notebook": remote["notebook"], "version": 2,
                "scope": "test", "scenes": 2, "duration_seconds": technical["duration"],
                "gpu": "Tesla T4", "python": "3.13.15", "video_size": [1920, 1080], "fps": 24,
                "uploaded_notebook_sha256": hashlib.sha256(uploaded.read_bytes()).hexdigest(),
                "implementation_sha256": implementation, "code_unchanged_since_execution": True,
                "archive_sha256": technical["archive_sha256"], "independent_asr_wer": asr["word_error_rate"]}
nb.metadata.videogenerator.validation = "Actual Kaggle v2 Run All and independent local verification passed for 2 scenes only."
nb.metadata.videogenerator.execution_verification = verification
assert tested_code == [c.source for c in nb.cells if c.cell_type == "code"]
nbformat.validate(nb)
for i, cell in enumerate(nb.cells):
    if cell.cell_type == "code":
        compile(cell.source, f"cell-{i}", "exec")
output = ROOT / "outputs/videogenerator-v3.1.2-kaggle-raw-tested.ipynb"
nbformat.write(nb, output)
result = dict(verification,
              url="https://www.kaggle.com/code/iliaskhan/notebook6c8f01ed68",
              tested_notebook=str(output), tested_notebook_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
              source_notebook_unchanged=True, source_sha256=nb.metadata.videogenerator.source_sha256,
              backup="work/remote-backup/notebook6c8f01ed68.ipynb",
              credentials_exposed=False, browser_used=False, transport="Official Kaggle API/SDK",
              models=state["model_snapshots"], stages=state["stages"],
              validation_report="kaggle-test-v2/actual_kaggle_validation.json",
              independent_asr_report="kaggle-test-v2/independent_asr.json",
              quality_limitations=["Static images, not generated motion",
                                   "Two frames are too similar; reference-image strategy needs editorial improvement",
                                   "First scene's alignment contains 47 of 48 space-separated words",
                                   "Second scene's director JSON failed; deterministic template retained",
                                   "Local visual QA is advisory; match scores are 0.65 for both frames",
                                   "Full 36-scene story and alternative models/languages not executed",
                                   "No edit, music, sound design, or listening approval"])
result_path = ROOT / "outputs/kaggle_run_result.json"
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"notebook": str(output), "report": str(result_path), "status": "COMPLETE",
                  "scenes": 2, "duration": technical["duration"]}, ensure_ascii=False))
