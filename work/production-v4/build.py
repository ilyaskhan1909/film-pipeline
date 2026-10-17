"""Standalone production notebook, separate from both original notebooks."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import nbformat
from storyboard import make_plan

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full',action='store_true')
    parser.add_argument('--no-base',action='store_true')
    parser.add_argument('--refine',action='store_true')
    parser.add_argument('--size',default='1536x864')
    parser.add_argument('--kernel-source',default='')
    args = parser.parse_args()
    plan = make_plan()
    if args.refine:
        assert not args.full
        plan['pilot_shots']=[0,51,54,61,62]
    old = (ROOT/'work/config_cell.py').read_text(encoding='utf-8')
    values = {}
    for node in ast.parse(old).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {'CONFIG','PINS','REVISIONS'}:
            values[node.targets[0].id] = ast.literal_eval(node.value)
    c = values['CONFIG']
    width,height = map(int,args.size.split('x'))
    c.update(QUICK_TEST=not args.full, TEST_SCENES=3, PILOT_AUDIO_INDICES=plan['pilot_audio'],
             GEN_W=width, GEN_H=height, OUT_W=1920, OUT_H=1080,
             IMAGE_STEPS=4, IMAGE_GUIDANCE=1.0, COMPARE_BASE=not (args.no_base or args.refine),
             USE_FIRST_FRAME_REFERENCE=False, LLM_ENABLED=False, QA_MAX_SCENES=0,
             VOICE_INSTRUCTION='Natural clear American English, around 135 words per minute.',
             TTS_MAX_SECONDS=180, ALIGN_WORDS=True, ALIGN_OPTIONAL=True,
             TTS_TAKES={'19':1} if args.full else {},
             MIN_FREE_SCRATCH_GB=36, STYLE='Naturalistic cinematic photography.', CHARACTERS=plan['characters'])
    values['REVISIONS']['black-forest-labs/FLUX.2-klein-base-4B'] = 'a3b4f4849157f664bdbc776fd7453c2783562f4d'
    core = (ROOT/'work/core.py').read_text(encoding='utf-8')
    core = core.replace('return state["scenes"][:config["TEST_SCENES"]] if config["QUICK_TEST"] else state["scenes"]',
        'return [state["scenes"][i] for i in config["PILOT_AUDIO_INDICES"]] if config["QUICK_TEST"] else state["scenes"]')
    worker = (ROOT/'work/worker.py').read_text(encoding='utf-8').replace(
        'kwargs["instruct"]=C["VOICE_INSTRUCTION"]', 'kwargs["instruct"]=scene.get("voice_instruction",C["VOICE_INSTRUCTION"])')
    worker = worker.replace('s.get("audio") and wav_ok(RUN/s["audio"])',
        's.get("audio") and wav_ok(RUN/s["audio"]) and s.get("tts_take",0)==C.get("TTS_TAKES",{}).get(str(s["index"]),0)')
    worker = worker.replace('torch.manual_seed(C["SEED"]+scene["index"]+attempt)',
        'torch.manual_seed(C["SEED"]+scene["index"]+attempt+10000*C.get("TTS_TAKES",{}).get(str(scene["index"]),0))')
    worker = worker.replace('complete(scene,audio=filename,audio_duration=duration',
        'complete(scene,tts_take=C.get("TTS_TAKES",{}).get(str(scene["index"]),0),audio=filename,audio_duration=duration')
    sources = {'core.py':core, 'worker.py':worker,
               'image_worker.py':(HERE/'image_worker.py').read_text(encoding='utf-8'),
               'driver.py':(HERE/'driver.py').read_text(encoding='utf-8')}
    fingerprint = dict(c)
    for key in ['QUICK_TEST','TEST_SCENES','COMPARE_BASE','PILOT_AUDIO_INDICES']:
        fingerprint.pop(key,None)
    implementation = hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    runid = hashlib.sha256(json.dumps({'config':fingerprint,'plan':plan,'implementation':implementation,
                          'revisions':values['REVISIONS'],'pins':values['PINS']},sort_keys=True).encode()).hexdigest()[:16]
    code = 'from pathlib import Path\nimport os,json,hashlib,platform,sys,shutil\n'
    code += f'CONFIG={c!r}\nPINS={values["PINS"]!r}\nREVISIONS={values["REVISIONS"]!r}\nPLAN={plan!r}\n'
    code += f'IMPLEMENTATION_SHA={implementation!r}\nSTORY_TEXT=PLAN["story"]\n'
    code += '''# Recompute after user edits: test scope may change, cached content may not.
identity_config={k:v for k,v in CONFIG.items() if k not in ('QUICK_TEST','TEST_SCENES','COMPARE_BASE','PILOT_AUDIO_INDICES')}
RUN_ID=hashlib.sha256(json.dumps({'config':identity_config,'plan':PLAN,'implementation':IMPLEMENTATION_SHA,'revisions':REVISIONS,'pins':PINS},sort_keys=True).encode()).hexdigest()[:16]
assert CONFIG['GEN_W']%16==0 and CONFIG['GEN_H']%16==0, 'Image dimensions must be multiples of 16.'
assert CONFIG['IMAGE_STEPS']>=4 and CONFIG['TTS_MAX_SECONDS']>0
BASE=Path('/kaggle/working')
SCRATCH=Path('/tmp/videogenerator-production-v4')
RUN=BASE/('production-'+RUN_ID)
'''
    code += '''if not Path('/kaggle').exists(): raise RuntimeError('Run in Kaggle with GPU and Internet On.')
for folder in ('audio','images','references','comparisons','logs','scripts'): (RUN/folder).mkdir(parents=True,exist_ok=True)
SCRATCH.mkdir(parents=True,exist_ok=True)
os.environ.update(TOKENIZERS_PARALLELISM='false',HF_HOME=str(SCRATCH/'hf'),HF_HUB_CACHE=str(SCRATCH/'hf/hub'),HF_HUB_DOWNLOAD_TIMEOUT='120',HF_HUB_ETAG_TIMEOUT='30',HF_HUB_DISABLE_TELEMETRY='1',USE_TF='0',USE_FLAX='0')
'''
    runtime = 'sys.path.insert(0,str(RUN/"scripts"))\n'
    for name,source in sources.items():
        compile(source,name,'exec')
        runtime += f'(RUN/"scripts"/{name!r}).write_text({source!r},encoding="utf-8")\n'
    runtime += '''exec(compile((RUN/'scripts/core.py').read_text(encoding='utf-8'),'core.py','exec'))
# Reuse verified compatible speech; images additionally validate their own fingerprints.
for previous in Path('/kaggle/input').rglob('production_manifest.json'):
    try:
        old=json.loads(previous.read_text(encoding='utf-8'))
        if old.get('story_sha256')!=hashlib.sha256(STORY_TEXT.encode()).hexdigest(): continue
        source=previous.parent
        old_config=json.loads((source/'config.json').read_text(encoding='utf-8'))
        audio_keys=('TTS_MODEL','TTS_ENGINE','SPEAKER','LANGUAGE','SEED')
        if any(old_config['config'].get(k)!=CONFIG[k] for k in audio_keys): continue
        if old_config['pins']['tts']!=PINS['tts']: continue
        if old_config['revisions'].get(CONFIG['TTS_MODEL'])!=REVISIONS.get(CONFIG['TTS_MODEL']): continue
        saved_state=json.loads((source/'pipeline_state.json').read_text(encoding='utf-8'))
        if any(a['text']!=b['text'] or a.get('voice_instruction')!=b.get('voice_instruction') for a,b in zip(saved_state['scenes'],PLAN['segments'])): continue
        if len(saved_state['scenes'])!=len(PLAN['segments']): continue
        expected=json.loads((source/'checksums.json').read_text(encoding='utf-8'))
        for name,digest in expected.items():
            file=(source/name).resolve()
            if not file.is_relative_to(source.resolve()) or sha256_file(file)!=digest: raise ValueError('Unsafe or changed source asset')
        for folder in ('audio','images','references','comparisons'):
            if (source/folder).is_dir(): shutil.copytree(source/folder,RUN/folder,dirs_exist_ok=True)
        saved_state['run_id']=RUN.name
        save_state(RUN,saved_state)
        print('Resumed verified assets from',source)
        break
    except Exception as exc: print('Resume source skipped:',type(exc).__name__)
if not (RUN/'pipeline_state.json').exists():
    save_state(RUN,{'schema':4,'run_id':RUN.name,'scenes':PLAN['segments'],'stages':{}})
atomic_json(RUN/'job.json',{'run':str(RUN),'config':CONFIG,'revisions':REVISIONS,'pins':PINS,'plan':PLAN})
atomic_json(RUN/'config.json',{'config':CONFIG,'revisions':REVISIONS,'pins':PINS})
(RUN/'story.txt').write_text(STORY_TEXT,encoding='utf-8')
atomic_json(RUN/'shot_plan.json',PLAN)
print('Words:',len(STORY_TEXT.split()),'speech segments:',len(PLAN['segments']),'distinct shot assignments:',len(PLAN['shots']))
'''
    setup = (ROOT/'work/setup_cell.py').read_text(encoding='utf-8')
    setup += "\nCONFIG['AVAILABLE_GPUS']=torch.cuda.device_count()\njob=json.loads((RUN/'job.json').read_text(encoding='utf-8'));job['config']=CONFIG;atomic_json(RUN/'job.json',job)\n"
    cells = [nbformat.v4.new_markdown_cell('GPU T4 + Internet On. `Run All` → проверочный пакет PNG/WAV/таймкодов. `QUICK_TEST=False` → вся история. Исходные notebooks не изменяются; платных API нет. Движение и финальный монтаж выполняются отдельно.'),
             nbformat.v4.new_code_cell(code), nbformat.v4.new_code_cell(runtime),
             nbformat.v4.new_code_cell(setup),
             nbformat.v4.new_code_cell("from driver import execute\nARCHIVE=execute(RUN,CONFIG,ENVS)"),
             nbformat.v4.new_code_cell("from IPython.display import FileLink,display\ndisplay(FileLink(str(ARCHIVE)))\nprint('Материал требует визуальной проверки и проверки озвучки до финального монтажа.')")]
    nb = nbformat.v4.new_notebook(cells=cells,metadata={
        'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'},
        'language_info':{'name':'python'},'accelerator':'GPU',
        'kaggle':{'isInternetEnabled':True,'isGpuEnabled':True,'language':'python','sourceType':'notebook'},
        'videogenerator':{'version':'4.0-production-assets','run_id':runid,'source':'iliaskhan/videogenerator-v2-1','status':'not_yet_runtime_validated'}})
    nbformat.validate(nb)
    for i,cell in enumerate(nb.cells):
        if cell.cell_type=='code': compile(cell.source,f'cell-{i}','exec')
    remote = HERE/('remote-full' if args.full else 'remote-refinement' if args.refine else 'remote-pilot')
    remote.mkdir(exist_ok=True)
    nbformat.write(nb,remote/'production.ipynb')
    out = ROOT/'outputs'/('videogenerator-v4-production-FULL.ipynb' if args.full else 'videogenerator-v4-production-REFINEMENT.ipynb' if args.refine else 'videogenerator-v4-production-PILOT.ipynb')
    nbformat.write(nb,out)
    meta = {'id':'iliaskhan/videogenerator-v4-production-full' if args.full else 'iliaskhan/videogenerator-v4-refinement' if args.refine else 'iliaskhan/videogenerator-v4-production-assets',
        'title':'VideoGenerator v4 production full' if args.full else 'VideoGenerator v4 refinement' if args.refine else 'VideoGenerator v4 production assets',
        'code_file':'production.ipynb','language':'python','kernel_type':'notebook','is_private':True,
        'enable_gpu':True,'enable_tpu':False,'enable_internet':True,'dataset_sources':[],
        'kernel_sources':[args.kernel_source] if args.kernel_source else [],'competition_sources':[],
        'docker_image':'gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f',
        'machine_shape':'NvidiaTeslaT4'}
    (remote/'kernel-metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    (HERE/'shot_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'file':str(out),'remote':str(remote),'run_id':runid,'pilot':not args.full,'shots':len(plan['shots']),'words':len(plan['story'].split())},ensure_ascii=False))

if __name__ == '__main__':
    main()
