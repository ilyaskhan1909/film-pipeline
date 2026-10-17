import ast, hashlib, json, sys
from pathlib import Path
import nbformat

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SOURCE=Path(r"C:\Users\ilyas\AppData\Local\Temp\codex-file-preview-b4sco1\videogenerator-v2-stableversion (2).ipynb")
OUT=ROOT/"outputs"/"videogenerator-v3.1.2-kaggle-raw.ipynb"
source_bytes=SOURCE.read_bytes()
source=json.loads(source_bytes)
story=None
for cell in source["cells"]:
    if cell["cell_type"]!="code": continue
    text="".join(cell["source"])
    try: tree=ast.parse(text)
    except SyntaxError: continue
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=="STORY_TEXT" for target in node.targets):
            story=ast.literal_eval(node.value)
if not isinstance(story,str) or not story: raise RuntimeError("Original STORY_TEXT not found")
sources={name:(HERE/name).read_text(encoding="utf-8") for name in ("core.py","worker.py","raw_export.py")}
code_sha=hashlib.sha256("".join(sources.values()).encode()).hexdigest()
config=(HERE/"config_cell.py").read_text(encoding="utf-8").replace("__STORY_LITERAL__",repr(story))
config=config.replace('"schema":3}',f'"schema":3,"implementation":{code_sha!r}}}')
runtime="""# 2. Служебный код сохраняется автоматически; внешние файлы для запуска не нужны.
import sys
sys.path.insert(0,str(RUN/'scripts'))
"""
for name,content in sources.items():
    runtime+=f"(RUN/'scripts'/{name!r}).write_text({content!r},encoding='utf-8')\n"
runtime+="exec(compile((RUN/'scripts'/'core.py').read_text(encoding='utf-8'),'core.py','exec'))\n"
intro="""Kaggle → сырой материал → отдельный монтаж HyperFrames/Remotion.

Session options: GPU + Internet On; Python ≥3.10, PyTorch ≥2.6. Ограничения на Python 3.13 и NumPy 1.26 нет. Системный PyTorch не переустанавливается.

`Run All` → первые 2 сцены, MP4-клипы с озвучкой, PNG/WAV, реальные тайминги при успешном aligner и `raw_material_TEST.zip`. Для всей истории: `QUICK_TEST=False` → `Run All` → `raw_material_FULL.zip`. Видео — статические сгенерированные кадры, не генерация движения. Субтитры, музыка и переходы не встроены.

Результаты: `/kaggle/working/run-<hash>/`. Сохраните Output через Save Version. Передайте ZIP для монтажа; приватные ключи не нужны. `RESUME_FROM` — папка run-* из подключённого Output той же конфигурации. Платных API нет; Node/Chromium и монтажные движки в Kaggle не устанавливаются.
"""
cells=[nbformat.v4.new_markdown_cell(intro),nbformat.v4.new_code_cell(config),nbformat.v4.new_code_cell(runtime),
       nbformat.v4.new_code_cell((HERE/"setup_cell.py").read_text(encoding="utf-8")),
       nbformat.v4.new_code_cell((HERE/"segment_cell.py").read_text(encoding="utf-8")),
       nbformat.v4.new_code_cell("# 5. Промпты: локальная ЛЛМ или детерминированный шаблон.\nif CONFIG['LLM_ENABLED']:\n    run_stage('direct','image',optional=True)\nelse:\n    print('LLM отключена; используются шаблоны сцен.')"),
       nbformat.v4.new_code_cell("# 6. Озвучка.\nrun_stage('tts','tts')"),
       nbformat.v4.new_code_cell("# 7. Тайминги сохраняются отдельно; ошибки не подменяются выдуманными метками.\nif CONFIG['ALIGN_WORDS']:\n    run_stage('align','align',optional=CONFIG['ALIGN_OPTIONAL'])\nif CONFIG['ASR_CHECK']:\n    run_stage('asr','align',optional=True)"),
       nbformat.v4.new_code_cell("# 8. Изображения. Каждый worker освобождает GPU при завершении.\nrun_stage('images','image')"),
       nbformat.v4.new_code_cell("# 9. Проверка кадров. Оценки ЛЛМ носят рекомендательный характер.\nif CONFIG['LLM_ENABLED']:\n    run_stage('qa','image',optional=True)\nelse:\n    print('Локальная проверка кадров отключена.')"),
       nbformat.v4.new_code_cell("# 10. Чистые MP4 по сценам + исходники и переносимый пакет для монтажёра.\nexec(compile((RUN/'scripts'/'raw_export.py').read_text(encoding='utf-8'),'raw_export.py','exec'))\nPREVIEW, ARCHIVE, MANIFEST = build_raw_material(RUN,CONFIG,STORY_TEXT)"),
       nbformat.v4.new_code_cell("# 11. Скачать ZIP из Output и передать для монтажа.\nfrom IPython.display import Video, FileLink, display\nif PREVIEW:\n    display(Video(str(PREVIEW),embed=False,width=720))\nfor name in (ARCHIVE.name,'manifest.json','word_timestamps.json','subtitles.srt','quality_report.json','pipeline_state.json'):\n    path=RUN/name\n    if path.exists():\n        print(f'{name}: {path.stat().st_size/1024**2:.2f} MiB')\n        display(FileLink(str(path)))\nprint('Скачать: Output →',RUN.name)\nprint('Это сырой материал, не production master. Для всей истории: QUICK_TEST=False.')"),
       nbformat.v4.new_markdown_cell("Ошибки: `logs/`. `LLM_ENABLED=False` сокращает время/скачивание. `ALIGN_WORDS=False` отключает тайминги. Отсутствующие тайминги явно отмечены в manifest; их можно получить на этапе монтажа. Оценки ЛЛМ рекомендательные, не гарантия качества.\n\nИсправлены установка без ensurepip и вызов VAE tiling в FLUX.2 Klein. Отчёт реального запуска будет сохранён отдельно; полная история пока не проверена.\n\nИсточники 04.10.2026: [Kaggle](https://www.kaggle.com/docs/notebooks), [FLUX.2](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), [Native Qwen3-ASR/Aligner](https://huggingface.co/docs/transformers/main/model_doc/qwen3_asr), [pip --python](https://pip.pypa.io/en/stable/topics/python-option/).")]
nb=nbformat.v4.new_notebook(cells=cells,metadata={
    "kernelspec":{"name":"python3","display_name":"Python 3","language":"python"},
    "language_info":{"name":"python","file_extension":".py","mimetype":"text/x-python","pygments_lexer":"ipython3"},
    "accelerator":"GPU","kaggle":{"isInternetEnabled":True,"isGpuEnabled":True,"language":"python","sourceType":"notebook","dataSources":[]},
    "videogenerator":{"version":"3.1.2-raw","source_file":SOURCE.name,"source_sha256":hashlib.sha256(source_bytes).hexdigest(),
        "implementation_sha256":code_sha,"verified_sources_date":"2026-10-04","validation":"Runtime fixes based on actual Kaggle v1 failure; full-story success is not yet claimed."}})
nbformat.validate(nb)
for i,cell in enumerate(nb.cells):
    if cell.cell_type=="code": compile(cell.source,f"cell-{i}","exec")
OUT.parent.mkdir(parents=True,exist_ok=True)
nbformat.write(nb,OUT)
assert SOURCE.read_bytes()==source_bytes
print(json.dumps({"file":str(OUT),"bytes":OUT.stat().st_size,"code_cells":sum(c.cell_type=="code" for c in cells),
                  "markdown_cells":sum(c.cell_type=="markdown" for c in cells),"story_words":len(story.split()),"source_sha256":hashlib.sha256(source_bytes).hexdigest()},ensure_ascii=False))
