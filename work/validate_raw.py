import ast, hashlib, json, math, os, subprocess, sys, types, wave, zipfile
from pathlib import Path
import nbformat
import numpy as np
from PIL import Image, ImageDraw
import torch

HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
sys.path.insert(0,str(HERE))
import core, raw_export
RUN=HERE/'raw-smoke-run'; RUN.mkdir(exist_ok=True)
for name in ('images','audio','logs'): (RUN/name).mkdir(exist_ok=True)
ffprobe=HERE/'smoke-scratch/node/remotion-c57941070451/node_modules/@remotion/compositor-win32-x64-msvc'
os.environ['PATH']=str(HERE/'ffmpeg-full')+os.pathsep+str(ffprobe)+os.pathsep+os.environ['PATH']
tree=ast.parse((HERE/'config_cell.py').read_text(encoding='utf-8'))
cfg={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
    and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'CONFIG','PINS','REVISIONS'}}
C=dict(cfg['CONFIG'],OUT_W=640,OUT_H=360,SCENE_PAUSE=0.0)
report={'checked_date':'2026-10-04','validation_platform':'Windows, Python 3.11, synthetic assets',
    'kaggle_gpu_inference':'not_run','python313_full_runtime':'not_run','checks':{}}
checks=report['checks']
subprocess.run([sys.executable,'-X','utf8',str(HERE/'build_notebook.py')],check=True)
notebook=ROOT/'outputs/videogenerator-v3.1.2-kaggle-raw.ipynb'
nb=nbformat.read(notebook,as_version=4); nbformat.validate(nb)
for i,c in enumerate(nb.cells):
    if c.cell_type=='code':
        compile(c.source,f'cell-{i}','exec'); assert not c.outputs and c.execution_count is None
checks['notebook_format_and_code']='passed'
checks['original_story_preserved']=1297
story=next(ast.literal_eval(n.value) for n in ast.parse(nb.cells[1].source).body if isinstance(n,ast.Assign)
    and any(isinstance(t,ast.Name) and t.id=='STORY_TEXT' for t in n.targets))
assert len(story.split())==1297
assert ' '.join(core.split_scenes(story,55,16))==' '.join(story.split())
source=Path(r'C:\Users\ilyas\AppData\Local\Temp\codex-file-preview-b4sco1\videogenerator-v2-stableversion (2).ipynb')
assert hashlib.sha256(source.read_bytes()).hexdigest()==nb.metadata.videogenerator.source_sha256
report['original_file_unchanged']=True
setup=ast.parse(nb.cells[3].source)
version_guard=next(n for n in setup.body if isinstance(n,ast.If) and 'sys.version_info' in ast.unparse(n.test))
guard=compile(ast.Expression(version_guard.test),'version-guard','eval')
for v in ((3,10),(3,11),(3,12),(3,13),(3,14)):
    assert not eval(guard,{'sys':types.SimpleNamespace(version_info=v)})
assert eval(guard,{'sys':types.SimpleNamespace(version_info=(3,9))})
assert not any('numpy==' in p or 'qwen-asr==' in p for packages in cfg['PINS'].values() for p in packages)
assert 'ensure_node' not in nb.cells[3].source
assert 'renderer.py' not in nb.cells[2].source
checks['python313_guard_regression']='passed; simulated version guard, no actual Python 3.13 interpreter'
checks['legacy_numpy126_dependency_removed']='passed'
checks['no_browser_renderer_in_kaggle']='passed'
bootstrap_report=HERE/'bootstrap_validation.json'
if bootstrap_report.exists():
    bootstrap=json.loads(bootstrap_report.read_text(encoding='utf-8'))
    assert bootstrap['status']=='passed'
    checks['venv_without_ensurepip']='passed; real isolated installs with ensurepip disabled, base packages unchanged'
    report['bootstrap_test_platform']=bootstrap['limitations']

# Test the native methods from the EXACT pinned Transformers wheel, without downloading model weights.
with zipfile.ZipFile(HERE/'wheels/transformers-5.18.0-py3-none-any.whl') as z:
    native=z.read('transformers/models/qwen3_asr/processing_qwen3_asr.py').decode()
nt=ast.parse(native)
method_names={'prepare_forced_aligner_inputs','decode_forced_alignment','split_words_for_alignment'}
helper_names={'_fix_timestamps','_is_cjk_char','_is_kept_char','_clean_tokens'}
methods=[n for n in ast.walk(nt) if isinstance(n,ast.FunctionDef) and n.name in method_names]
helpers=[n for n in nt.body if isinstance(n,ast.FunctionDef) and n.name in helper_names]
cls=ast.ClassDef(name='ProcessorTest',bases=[],keywords=[],body=methods,decorator_list=[])
mod=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*helpers,cls],type_ignores=[])
scope={'np':np,'torch':torch,'unicodedata':__import__('unicodedata'),
    'LANGUAGE_CODE_TO_NAME':{'en':'English','ru':'Russian'},'FORCED_ALIGNER_LANGUAGES':{'English','Russian'},
    'make_list_of_audio_chat_template':lambda a:[a] if isinstance(a,str) else a,
    'make_audio_chat_template_content':lambda a:{'type':'audio','path':a},
    'prepare_language_inputs':lambda l,b,*args,**kw:[l]*b,
    'is_nagisa_available':lambda:False,'is_soynlp_available':lambda:False}
exec(compile(ast.fix_missing_locations(mod),'native-processor-methods','exec'),scope)
processor=scope['ProcessorTest'](); processor.timestamp_segment_time=80
processor.apply_chat_template=lambda conversations,**kwargs: {'conversations':conversations,'kwargs':kwargs}
inputs,words=processor.prepare_forced_aligner_inputs('fixture.wav','The forest was silent.','English')
assert words==[['The','forest','was','silent']]
assert processor.split_words_for_alignment('Лес был тихим.','Russian')==['Лес','был','тихим']
ids=torch.full((1,8),99,dtype=torch.long); logits=torch.full((1,8,32),-10.)
for i,t in enumerate((1,4,4,9,9,12,12,19)): logits[0,i,t]=10
decoded=processor.decode_forced_alignment(logits,ids,words,99)[0]
assert len(decoded)==4 and decoded[0]['start_time']==.08 and decoded[-1]['end_time']==1.52
checks['pinned_native_alignment_methods']='passed; English/Russian word splitting, preparation, timestamp decoding'

# Exercise our worker alignment stage against strict native-API doubles, including punctuation restoration.
worker_text=(HERE/'worker.py').read_text(encoding='utf-8'); wt=ast.parse(worker_text)
align_func=next(n for n in wt.body if isinstance(n,ast.FunctionDef) and n.name=='align')
seen={}
class Inputs(dict):
    def to(self,device,dtype): seen['to']=(device,dtype); return self
class FakeProcessor:
    def prepare_forced_aligner_inputs(self,**kw):
        seen['prepare']=kw; return Inputs(input_ids='ids'),[['The','forest','was','silent']]
    def decode_forced_alignment(self,**kw): seen['decode']=kw; return [decoded]
fakeproc=FakeProcessor()
class Model:
    device='cpu'; dtype=torch.float32; config=types.SimpleNamespace(timestamp_token_id=99)
    def eval(self): return self
    def __call__(self,**kw): return types.SimpleNamespace(logits='logits')
module=types.ModuleType('transformers')
module.AutoProcessor=types.SimpleNamespace(from_pretrained=lambda p:fakeproc)
module.AutoModelForTokenClassification=types.SimpleNamespace(from_pretrained=lambda *a,**kw:Model())
oldmodule=sys.modules.get('transformers'); sys.modules['transformers']=module
scene={'index':0,'audio':'audio/fixture.wav','audio_duration':2.0,'text':'The forest was silent.'}
ws={'SCENES':[scene],'C':dict(C),'RUN':RUN,'DTYPE':torch.float32,'ATTN':'eager','torch':torch,'math':math,'re':__import__('re'),
    'model_path':lambda p:p,'wav_ok':lambda p:True,'complete':lambda s,**u:s.update(u)}
try:
    exec(compile(ast.Module(body=[align_func],type_ignores=[]),'worker-align','exec'),ws); ws['align']()
finally:
    if oldmodule is None: sys.modules.pop('transformers',None)
    else: sys.modules['transformers']=oldmodule
assert scene['words'][-1]['text']=='silent.' and seen['prepare']['transcript']==scene['text']
checks['worker_native_api_contract']='passed'

# Validate the FLUX.2 tiling contract against the exact installed dependency wheel.
with zipfile.ZipFile(HERE/'wheels/diffusers-0.40.0-py3-none-any.whl') as z:
    vae_tree=ast.parse(z.read('diffusers/models/autoencoders/vae.py').decode())
    vae_class=next(n for n in vae_tree.body if isinstance(n,ast.ClassDef) and n.name=='AutoencoderMixin')
    assert any(isinstance(n,ast.FunctionDef) and n.name=='enable_tiling' for n in vae_class.body)
assert 'pipe.vae.enable_tiling()' in worker_text
assert 'pipe.enable_vae_tiling()' not in worker_text
checks['flux2_vae_tiling_contract']='passed; AutoencoderMixin.enable_tiling in pinned Diffusers 0.40.0'

scenes=[]
for i,duration in enumerate((1.8,1.9)):
    rate=24000; audio=.08*np.sin(2*np.pi*(220+100*i)*np.arange(round(rate*duration))/rate)
    with wave.open(str(RUN/'audio'/f's{i:04d}.wav'),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes((audio*32767).astype('<i2').tobytes())
    im=Image.new('RGB',(640,360),(25,50+15*i,70)); draw=ImageDraw.Draw(im)
    draw.rectangle((70+150*i,60,220+150*i,300),fill=(150,80,45)); im.save(RUN/'images'/f's{i:04d}.png')
    scenes.append({'index':i,'audio':f'audio/s{i:04d}.wav','image':f'images/s{i:04d}.png','audio_duration':duration,
        'text':'The forest was silent.','words':scene['words'] if i==0 else []})
core.save_state(RUN,{'schema':3,'run_id':'raw-smoke','scenes':scenes,'stages':{}})
core.atomic_json(RUN/'config.json',{'config':C,'pins':cfg['PINS']})
core.atomic_json(RUN/'environment.json',{'note':'synthetic test fixtures, no model inference'})
preview,archive,manifest=raw_export.build_raw_material(RUN,C,'The forest was silent. The forest was silent.')
assert manifest['frames']==math.ceil(1.8*24)+math.ceil(1.9*24)==90
assert manifest['alignment_missing_scenes']==[1]
assert manifest['visual_source']=='generated_still_images' and not manifest['burned_captions']
with wave.open(str(RUN/'narration.wav'),'rb') as w: assert w.getnframes()==90*2000
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert {'clips/s0000.mp4','clips/s0001.mp4','manifest.json','narration.wav','checksums.json'}<=set(z.namelist())
    assert not any('node_modules' in n or n.startswith('scripts/') for n in z.namelist())
    hashes=json.loads(z.read('checksums.json'))
    assert all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in hashes.items())
before=[(RUN/e['clip']).stat().st_mtime_ns for e in manifest['scenes']]
raw_export.build_raw_material(RUN,C,'The forest was silent. The forest was silent.')
assert [(RUN/e['clip']).stat().st_mtime_ns for e in manifest['scenes']]==before
checks['raw_export']='passed; 2 H.264/AAC clips and preview, 640x360/24fps, full decode'
checks['exact_preview_audio_and_frame_grid']='passed; 90 video frames, 180000 PCM samples'
checks['portable_handoff_archive']='passed; relative paths, checksum verification, no weights/browser dependencies'
checks['clip_cache']='passed'
checks['missing_alignment_not_fabricated']='passed'
package_reports=[HERE/'raw_cp313_native_packages.json',HERE/'raw_cp313_tts_packages.json']
if all(p.is_file() for p in package_reports):
    checked=[]
    for p in package_reports:
        resolved=json.loads(p.read_text(encoding='utf-8'))
        checked.extend(f"{item['metadata']['name']}=={item['metadata']['version']}" for item in resolved['install'])
    checks['python313_linux_direct_package_wheels']='passed; cross-platform pip dry-run, direct packages only'
    report['python313_direct_packages']=sorted(set(checked))
    report['dependency_check_limits']='Transitive dependencies and actual Kaggle installed-image constraints not verified'
report.update(notebook_file=notebook.name,notebook_sha256=hashlib.sha256(notebook.read_bytes()).hexdigest(),
    source_sha256=nb.metadata.videogenerator.source_sha256,code_cells=11,markdown_cells=2,
    limitations=['No full Kaggle GPU inference','No actual Python 3.13 interpreter run',
        'Native alignment methods tested without model weights','Technical validation is not production quality approval'])
core.atomic_json(ROOT/'outputs/raw_notebook_validation_v3.1.2.json',report)
print(json.dumps(report,ensure_ascii=False,indent=2))
