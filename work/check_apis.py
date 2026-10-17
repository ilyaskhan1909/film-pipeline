import ast, json, zipfile
from pathlib import Path

root=Path(__file__).resolve().parent
out={}
for wheel in (root/'wheels').glob('*.whl'):
    with zipfile.ZipFile(wheel) as z:
        metadata=next(x for x in z.namelist() if x.endswith('.dist-info/METADATA'))
        deps=[x.removeprefix('Requires-Dist: ') for x in z.read(metadata).decode().splitlines() if x.startswith('Requires-Dist: ')]
        checks={}
        for name in z.namelist():
            if (name.endswith('pipeline_flux2_klein.py') or name.endswith('pipeline_z_image.py')
                or name.endswith('qwen3_tts_model.py') or name.endswith('qwen3_forced_aligner.py')
                or name.endswith('qwen3_asr_model.py')):
                code=z.read(name).decode(); tree=ast.parse(code)
                classes={}
                for node in ast.walk(tree):
                    if isinstance(node,ast.FunctionDef) and node.name in {'__call__','from_pretrained','generate_custom_voice','align','get_supported_speakers','transcribe'}:
                        classes[f'{node.name}:{node.lineno}']=[x.arg for x in node.args.args]+[x.arg for x in node.args.kwonlyargs]
                checks[name]=classes
        if wheel.name.startswith('transformers'):
            automapping=z.read('transformers/models/auto/modeling_auto.py').decode()
            checks['qwen3_5_image_text_mapping']='("qwen3_5", "Qwen3_5ForConditionalGeneration")' in automapping
            checks['AutoModelForImageTextToText']='class AutoModelForImageTextToText' in automapping
        if wheel.name.startswith('diffusers'):
            for filename in ('diffusers/models/modeling_utils.py','diffusers/pipelines/pipeline_utils.py'):
                checks[filename]=[line.strip() for line in z.read(filename).decode().splitlines()
                    if 'kwargs.pop(' in line and ('torch_dtype' in line or '"dtype"' in line)]
        out[wheel.name]={'dependencies':deps,'api_signatures':checks}
(root/'api_validation.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
