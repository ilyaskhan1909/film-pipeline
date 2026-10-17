import ast, importlib.util, json, os, shutil, subprocess, sys, time, wave
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import nbformat

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(HERE))
import core, renderer
def literals():
    tree=ast.parse((HERE/'config_cell.py').read_text(encoding='utf-8'))
    return {n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
            and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'CONFIG','PINS','REVISIONS'}}
cfg=literals(); C=dict(cfg['CONFIG']); PINS=cfg['PINS']
os.environ['PATH']=str(HERE/'test-bin')+os.pathsep+r'C:\Users\ilyas\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin'+os.pathsep+os.environ['PATH']
os.environ['npm_config_cache']=str(HERE/'npm-cache')
os.environ['XDG_CACHE_HOME']=str(HERE/'browser-cache')
os.environ['LOCALAPPDATA_ORIGINAL']=os.environ.get('LOCALAPPDATA','')
# Browser downloads for validation stay inside the task directory.
os.environ['LOCALAPPDATA']=str(HERE/'browser-cache')
os.environ['HYPERFRAMES_NO_TELEMETRY']='1'
os.environ['HYPERFRAMES_FONT_CACHE_DIR']=str(HERE/'font-cache')
os.environ['PRODUCER_BROWSER_GPU_MODE']='software'
SCRATCH=HERE/'smoke-scratch'
RUN=HERE/'smoke-run'
for name in ('audio','images','logs','projects'): (RUN/name).mkdir(parents=True,exist_ok=True)
C.update(OUT_W=640,OUT_H=360,GEN_W=640,GEN_H=360,AMBIENCE=True,SCENE_PAUSE=.2,ALLOW_FFMPEG_FALLBACK=False)

def fixtures():
    scenes=[]
    for i in range(2):
        sr=24000; duration=1.8+i*.1
        audio=.07*np.sin(2*np.pi*(220+110*i)*np.arange(round(sr*duration))/sr)
        with wave.open(str(RUN/'audio'/f's{i:04d}.wav'),'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(sr)
            out.writeframes((audio*32767).astype('<i2').tobytes())
        im=Image.new('RGB',(640,360),(18+8*i,36,48+12*i)); d=ImageDraw.Draw(im)
        for x in range(0,640,40):
            d.rectangle((x,0,x+12,240+x%80),fill=(6,15,18))
        d.ellipse((240+i*80,165,360+i*80,310),fill=(187,95,61)); im.save(RUN/'images'/f's{i:04d}.png')
        words=[{'text':text,'start':a,'end':b} for text,a,b in [('The',.12,.32),('forest',.32,.7),('was',.7,.95),('silent.',.95,1.5)]]
        scenes.append({'index':i,'text':'The forest was silent.','mood':'dread','audio':f'audio/s{i:04d}.wav',
            'audio_duration':duration,'sample_rate':sr,'image':f'images/s{i:04d}.png','words':words})
    core.save_state(RUN,{'schema':3,'run_id':'smoke','scenes':scenes,'stages':{}})
    core.atomic_json(RUN/'environment.json',{'validation':'synthetic fixtures, no ML model inference'})

def static():
    subprocess.run([sys.executable,'-X','utf8',str(HERE/'build_notebook.py')],check=True)
    nb=nbformat.read(ROOT/'outputs/videogenerator-v3-kaggle.ipynb',as_version=4); nbformat.validate(nb)
    for i,cell in enumerate(nb.cells):
        if cell.cell_type=='code':
            compile(cell.source,f'cell-{i}','exec'); assert not cell.outputs and cell.execution_count is None
    for text in ('One word.\n\nAnother sentence.', ' '.join('w'+str(i) for i in range(200)),
                 'Лес был тихим.\n\nВнезапно раздался голос! Ничего не пропало.', '', ' \'quote\'   and\t spaces. '):
        for max_words in (1,5,55):
            parts=core.split_scenes(text,max_words,1)
            assert ' '.join(parts)==' '.join(text.split())
            assert all(len(x.split())<=max_words for x in parts)
    # Validate source extraction and exact story preservation without executing old code.
    story=next(ast.literal_eval(n.value) for n in ast.parse(nb.cells[1].source).body if isinstance(n,ast.Assign)
               and any(isinstance(x,ast.Name) and x.id=='STORY_TEXT' for x in n.targets))
    assert len(story.split())==1297
    parts=core.split_scenes(story,C['MAX_WORDS'],C['MIN_WORDS'])
    assert ' '.join(parts)==' '.join(story.split())
    start=time.monotonic()
    try: core.run_logged([sys.executable,'-c','import time; time.sleep(30)'],RUN/'logs/timeout-test.log',timeout=.25)
    except TimeoutError: pass
    else: raise AssertionError('Silent subprocess timeout did not fire')
    assert time.monotonic()-start<5
    runtime=nb.cells[2].source
    # Exercise the notebook-generated files and their imports in a local sandbox.
    temp=HERE/'runtime-import-test'; (temp/'scripts').mkdir(parents=True,exist_ok=True)
    scope={'RUN':temp}; exec(runtime,scope)
    exec(compile((temp/'scripts'/'renderer.py').read_text(encoding='utf-8'),'renderer.py','exec'),scope)
    assert callable(scope['build_video'])
    # Resume must preserve completed assets and must not execute copied scripts.
    source=HERE/'resume-test-source'; resumed=HERE/'resume-test-target'
    for path in (source,resumed):
        for folder in ('audio','images','scripts','logs'): (path/folder).mkdir(parents=True,exist_ok=True)
    resume_text='The forest was silent. Another scene remained intact.'
    resume_state={'schema':3,'run_id':'resume-test','scenes':[
        {'index':0,'text':resume_text,'audio':'audio/done.wav','audio_duration':1,'words':[{'text':'The','start':0,'end':.2}],
         'image':'images/done.png',**core.default_direction(resume_text,0,C)}],'stages':{}}
    with wave.open(str(source/'audio/done.wav'),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(bytes(48000))
    Image.new('RGB',(32,32),(150,30,10)).save(source/'images/done.png')
    core.save_state(source,resume_state)
    (source/'scripts/marker.py').write_text('copied output script',encoding='utf-8')
    (resumed/'scripts/marker.py').write_text('embedded notebook script',encoding='utf-8')
    resumed_state=resumed/'pipeline_state.json'
    # Repeated validation creates a fresh scoped test target, retaining any prior test state.
    if resumed_state.exists(): resumed_state.rename(resumed/f'previous-test-state-{time.time_ns()}.json')
    rscope={**vars(core),'RUN':resumed,'RUN_ID':'resume-test','CONFIG':dict(C,RESUME_FROM=str(source)),
            'STORY_TEXT':resume_text,'REVISIONS':cfg['REVISIONS'],'PINS':PINS}
    segment=(HERE/'segment_cell.py').read_text(encoding='utf-8')
    exec(segment,rscope); first=core.load_state(resumed)
    exec(segment,rscope); assert core.load_state(resumed)==first
    assert first['scenes'][0]['audio']=='audio/done.wav'
    assert (resumed/'scripts/marker.py').read_text(encoding='utf-8')=='embedded notebook script'
    (resumed/'audio/done.wav').write_bytes(b'corrupt fixture')
    exec(segment,rscope); assert 'audio' not in core.load_state(resumed)['scenes'][0]
    for source in HERE.glob('*.py'): compile(source.read_text(encoding='utf-8'),str(source),'exec')
    return {'nbformat':'passed','all_code_cells_compile':'passed','source_story_preserved':True,
            'story_words':1297,'source_scenes':len(parts),'segmentation_edge_cases':'passed','silent_process_timeout':'passed',
            'embedded_runtime_import':'passed','resume_idempotence':'passed','resume_code_preserved':'passed',
            'corrupt_audio_invalidated':'passed','code_cells':11,'markdown_cells':2,'kaggle_gpu_inference':'not_run'}

def rendering(engine):
    # Remotion supplies platform-specific FFmpeg and FFprobe; both stay in work/.
    bins=list(SCRATCH.glob('node/remotion-*/node_modules/@remotion/compositor-win32-x64-msvc'))
    if bins: os.environ['PATH']=str(bins[0])+os.pathsep+os.environ['PATH']
    if (HERE/'ffmpeg-full/ffmpeg.exe').exists():
        os.environ['PATH']=str(HERE/'ffmpeg-full')+os.pathsep+os.environ['PATH']
    fixtures(); t=renderer.prepare_timeline(RUN,C)
    assert t['frames']==99 and abs(t['duration']-99/24)<1e-10
    with wave.open(str(RUN/'final_audio.wav'),'rb') as w:
        assert w.getnframes()==t['frames']*2000
    assert all(a['end']<=b['start'] for a,b in zip(t['groups'],t['groups'][1:]))
    c=dict(C,RENDER_ENGINE=engine)
    projects={e:(renderer.write_hyperframes if e=='hyperframes' else renderer.write_remotion)(RUN,t,c,PINS)
              for e in ('hyperframes','remotion')}
    video=renderer.render_ffmpeg(RUN,t,c) if engine=='ffmpeg' else renderer.render_browser(projects[engine],engine,RUN,t,c,SCRATCH)
    final,info=renderer.finalize(RUN,t,c,video,engine)
    saved=RUN/f'verified-{engine}.mp4'; shutil.copy2(final,saved)
    renderer.export_projects(RUN,projects)
    subprocess.run(['ffmpeg','-y','-v','error','-ss','0.8','-i',str(saved),'-frames:v','1',str(RUN/f'{engine}-frame.png')],check=True)
    return {'status':'passed','synthetic_fixture':True,'frames':t['frames'],'duration_seconds':t['duration'],
            'video_codec':info['streams'][0]['codec_name'],'audio_present':True,'full_decode':'passed','fallback_used':False}

if __name__=='__main__':
    action=sys.argv[1] if len(sys.argv)>1 else 'static'
    report_path=ROOT/'outputs/notebook_validation.json'
    report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    if action=='static': report.update(static())
    elif action=='install':
        fixtures()
        # Installation does not require FFmpeg yet.
        t={'scenes':[{'image':'images/s0000.png'}], 'width':640,'height':360,'duration':1,'fps':24,'frames':24,'groups':[]}
        t['scenes'][0].update(index=0,start=0,duration=1,start_frame=0,frames=24)
        (RUN/'final_audio.wav').write_bytes((RUN/'audio/s0000.wav').read_bytes())
        for engine in ('remotion','hyperframes'):
            project=(renderer.write_remotion if engine=='remotion' else renderer.write_hyperframes)(RUN,t,C,PINS)
            print(renderer.ensure_renderer(project,engine,SCRATCH))
        sys.exit(0)
    else: report.setdefault('local_render_tests',{})[action]=rendering(action)
    core.atomic_json(report_path,report); print(json.dumps(report,ensure_ascii=False,indent=2))
