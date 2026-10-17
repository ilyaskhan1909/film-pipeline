import html, json, math, os, shutil, subprocess, wave, zipfile
from pathlib import Path
import numpy as np
from core import atomic_json, load_state, selected_scenes, wav_ok, image_ok, probe, run_logged, sha256_file

DESIGN = """# Cinematic campfire horror
## Style Prompt
Quiet forest dread, restrained camera movement, ember-lit faces and cool shadows. Images carry the story; captions stay legible and do not compete with the scene.
## Colors
- #101820: background
- #F6F0E3: caption text
- #D8604B: spoken-word highlight
- #283B49: shadow tint
## Typography
DejaVu Sans, bold for captions. A local font file is embedded for English and Cyrillic.
## Motion
Slow 1.00–1.09 camera drift, 450ms crossfades, gentle caption entrances; no flashing.
## What NOT to Do
- No neon graphics or promotional titles.
- No rapid flashing or random frame-time effects.
- No captions over the central subject area.
- No transitions that shorten the narration.
"""

def caption_groups(words, max_words, max_chars):
    groups=[]; current=[]
    for word in words:
        if current and (len(current)>=max_words or len(" ".join(x["text"] for x in current))+len(word["text"])+1>max_chars
                        or word["start"]-current[-1]["end"]>0.35):
            groups.append(current); current=[]
        current.append(word)
        if word["text"].endswith((".","!","?","。","！","？")):
            groups.append(current); current=[]
    if current: groups.append(current)
    out=[]
    for i,group in enumerate(groups):
        start=group[0]["start"]; end=max(group[-1]["end"],start+0.06)
        if i+1<len(groups): end=min(end,groups[i+1][0]["start"])
        if end>start: out.append({"start":start,"end":end,"words":group,"text":" ".join(x["text"] for x in group)})
    return out

def srt_time(sec):
    ms=max(0,round(sec*1000)); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def ass_time(sec):
    cs=max(0,round(sec*100)); h,cs=divmod(cs,360000); m,cs=divmod(cs,6000); s,cs=divmod(cs,100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def write_subtitles(run,timeline,c):
    groups=timeline["groups"]
    srt="\n\n".join(f"{i+1}\n{srt_time(g['start'])} --> {srt_time(g['end'])}\n{g['text']}" for i,g in enumerate(groups))+"\n"
    (run/"subtitles.srt").write_text(srt,encoding="utf-8")
    fs=round(min(c["OUT_H"]*.051,c["OUT_W"]*.064)); mv=round(c["OUT_H"]*(.27 if c["ASPECT"]=="9:16" else .09))
    header=f"""[Script Info]
ScriptType: v4.00+
PlayResX: {c['OUT_W']}
PlayResY: {c['OUT_H']}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{fs},&H004B60D8,&H00E3F0F6,&H00201810,&H90201810,-1,0,0,0,100,100,0,0,1,3,1,2,70,70,{mv},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events=[]
    for group in groups:
        fragments=[]
        cursor=group["start"]
        for word in group["words"]:
            # \kt assigns the real start; \kf assigns the real spoken duration (including pauses).
            text=word["text"].replace("\\"," ").replace("{","(").replace("}",")").replace("\n"," ")
            offset=max(0,round((word["start"]-group["start"])*100))
            duration=max(1,round((word["end"]-word["start"])*100))
            fragments.append("{"+chr(92)+f"kt{offset}"+chr(92)+f"kf{duration}"+"}"+text)
            cursor=word["end"]
        events.append(f"Dialogue: 0,{ass_time(group['start'])},{ass_time(group['end'])},Default,,0,0,0,,{' '.join(fragments)}")
    (run/"subtitles.ass").write_text(header+"\n".join(events)+"\n",encoding="utf-8")
    captions=[{"text":" "+w["text"],"startMs":round(w["start"]*1000),"endMs":round(w["end"]*1000),
               "timestampMs":round((w["start"]+w["end"])*500),"confidence":None} for w in timeline["words"]]
    atomic_json(run/"captions.json",captions)

def prepare_timeline(run,c):
    run=Path(run); state=load_state(run); scenes=selected_scenes(state,c)
    errors=[]
    for s in scenes:
        if not s.get("audio") or not wav_ok(run/s["audio"]): errors.append(f"scene {s['index']+1}: audio")
        if not s.get("image") or not image_ok(run/s["image"]): errors.append(f"scene {s['index']+1}: image")
        if not s.get("words"): errors.append(f"scene {s['index']+1}: alignment")
    if not scenes or errors: raise RuntimeError("Incomplete pipeline: "+", ".join(errors))
    entries=[]; words=[]; frame_cursor=0; fps=c["FPS"]; sr=48000
    combined=run/"narration.wav"
    mixed=run/"final_audio.wav"
    rng=np.random.default_rng(c["SEED"])
    with wave.open(str(combined),"wb") as rawout, wave.open(str(mixed),"wb") as mixout:
        for out in (rawout,mixout): out.setnchannels(1); out.setsampwidth(2); out.setframerate(sr)
        sample_cursor=0
        for s in scenes:
            normalized=run/"audio"/f"normalized-{s['index']:04d}.wav"
            subprocess.run(["ffmpeg","-y","-v","error","-i",str(run/s["audio"]),"-ac","1","-ar",str(sr),"-c:a","pcm_s16le",str(normalized)],check=True)
            with wave.open(str(normalized),"rb") as inp:
                original_samples=inp.getnframes()
                frames=math.ceil((original_samples+round(c["SCENE_PAUSE"]*sr))*fps/sr)
                target_samples=frames*(sr//fps)
                entry={"index":s["index"],"start":frame_cursor/fps,"duration":frames/fps,
                       "start_frame":frame_cursor,"frames":frames,"image":s["image"],"mood":s.get("mood","dread")}
                entries.append(entry)
                for w in s["words"]:
                    start=entry["start"]+float(w["start"]); end=entry["start"]+float(w["end"])
                    if not math.isfinite(start+end) or start<entry["start"] or end>entry["start"]+original_samples/sr+0.05 or end<=start:
                        raise ValueError(f"Invalid word time in scene {s['index']+1}")
                    words.append({"text":w["text"],"start":start,"end":end,"scene":s["index"]})
                remaining=target_samples
                while remaining:
                    count=min(48000,remaining)
                    pcm=inp.readframes(count)
                    signal=np.frombuffer(pcm,dtype="<i2").astype(np.float32)/32768
                    if len(signal)<count: signal=np.pad(signal,(0,count-len(signal)))
                    rawout.writeframes((np.clip(signal,-1,1)*32767).astype("<i2").tobytes())
                    if c["AMBIENCE"]:
                        t=(np.arange(count,dtype=np.float64)+sample_cursor)/sr
                        bed=.55*np.sin(2*np.pi*55*t)+.25*np.sin(2*np.pi*55.4*t)+.12*np.sin(2*np.pi*82.4*t)
                        bed*=.55+.45*np.sin(2*np.pi*.035*t)**2
                        bed+=rng.normal(0,.035,count)
                        signal=signal*.88+bed.astype(np.float32)*c["AMBIENCE_VOLUME"]
                    mixout.writeframes((np.clip(signal,-1,1)*32767).astype("<i2").tobytes())
                    sample_cursor+=count; remaining-=count
            frame_cursor+=frames
    # Exact frame-grid audio offsets; crossfades affect images only.
    timeline={"fps":fps,"width":c["OUT_W"],"height":c["OUT_H"],"frames":frame_cursor,
              "duration":frame_cursor/fps,"scenes":entries,"words":words,
              "groups":caption_groups(words,c["WORDS_PER_CAPTION"],26 if c["ASPECT"]=="9:16" else 50)}
    atomic_json(run/"timeline.json",timeline)
    write_subtitles(run,timeline,c)
    return timeline

def copy_assets(run,project,timeline):
    assets=project/"public"; assets.mkdir(parents=True,exist_ok=True)
    for s in timeline["scenes"]:
        dest=assets/s["image"]; dest.parent.mkdir(exist_ok=True)
        shutil.copy2(run/s["image"],dest)
    shutil.copy2(run/"final_audio.wav",assets/"final_audio.wav")
    fonts=assets/"fonts"; fonts.mkdir(exist_ok=True)
    candidates=[Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts"/"arial.ttf"]
    font=next((x for x in candidates if x.exists()),None)
    if font: shutil.copy2(font,fonts/"caption.ttf")
    copyright_file=Path('/usr/share/doc/fonts-dejavu-core/copyright')
    if copyright_file.exists(): shutil.copy2(copyright_file,fonts/'LICENSE.txt')
    (project/"DESIGN.md").write_text(DESIGN,encoding="utf-8")
    return bool(font)

def write_hyperframes(run,t,c,pins):
    project=run/"projects"/"hyperframes"; project.mkdir(parents=True,exist_ok=True)
    copy_assets(run,project,t)
    atomic_json(project/"package.json",{"name":"kaggle-horror-hyperframes","private":True,"version":"1.0.0",
        "scripts":{"preview":"hyperframes preview","render":"hyperframes render --output FINAL_video.mp4"},
        "dependencies":{"hyperframes":pins["hyperframes"],"gsap":pins["gsap"]}})
    css=f"""@font-face{{font-family:Caption;src:url('public/fonts/caption.ttf')}}
html,body{{margin:0;width:{t['width']}px;height:{t['height']}px;overflow:hidden;background:#101820}}
#root,.scene,.camera{{position:absolute;inset:0;overflow:hidden}}
.scene{{background:#101820}}.camera img{{width:100%;height:100%;object-fit:cover}}
.vignette{{position:absolute;inset:0;background:radial-gradient(ellipse,rgba(16,24,32,0) 35%,rgba(16,24,32,.55) 100%);pointer-events:none}}
.caption{{position:absolute;inset:0;padding:0 7%;box-sizing:border-box;display:flex;align-items:flex-end;justify-content:center;
 padding-bottom:{round(t['height']*(.27 if c['ASPECT']=='9:16' else .09))}px;opacity:0;pointer-events:none}}
.caption-content{{font-family:Caption,'DejaVu Sans',sans-serif;font-size:{round(min(t['height']*.051,t['width']*.064))}px;
 font-weight:700;line-height:1.24;max-width:100%;text-align:center;color:#F6F0E3;text-shadow:0 2px 5px #101820;
 background:rgba(16,24,32,.86);border-radius:9px;padding:10px 20px;white-space:normal;box-sizing:border-box}}
.caption span{{display:inline-block;max-width:100%;overflow-wrap:anywhere}}"""
    scenes=[]; js=["window.__timelines=window.__timelines||{}; const tl=gsap.timeline({paused:true});"]
    transition=c["TRANSITION_SECONDS"]
    for i,s in enumerate(t["scenes"]):
        scenes.append(f'<div id="s{i}" class="scene" style="opacity:{1 if i==0 else 0};z-index:{i+1}"><div id="cam{i}" class="camera" data-layout-allow-overflow><img id="im{i}" src="public/{html.escape(s["image"],quote=True)}" alt="Scene {i+1}"></div><div class="vignette" data-layout-ignore></div></div>')
        start=s["start"]; end=start+s["duration"]
        if i:
            # Transition starts at the audio boundary, never reduces narration duration.
            js.append(f'tl.fromTo("#s{i}",{{opacity:0}},{{opacity:1,duration:{transition},ease:"sine.inOut",immediateRender:false}},{start});')
            js.append(f'tl.to("#s{i-1}",{{opacity:0,duration:{transition},ease:"sine.inOut"}},{start});')
        js.append(f'tl.from("#im{i}",{{opacity:0,duration:.3,ease:"power2.out",immediateRender:false}},{start+.12});')
        js.append(f'tl.from("#cam{i}",{{x:{12 if i%2 else -12},duration:.5,ease:"power3.out",immediateRender:false}},{start+.1});')
        js.append(f'tl.to("#cam{i}",{{scale:1.09,duration:{s["duration"]},ease:"sine.inOut"}},{start});')
        if i==len(t["scenes"])-1:
            js.append(f'tl.to("#s{i}",{{opacity:0,duration:.35,ease:"power1.in"}},{max(start,end-.35)});')
    groups=[]
    for i,g in enumerate(t["groups"]):
        spans=" ".join(f'<span id="w{i}-{j}">{html.escape(w["text"])}</span>' for j,w in enumerate(g["words"]))
        groups.append(f'<div id="cg{i}" class="caption"><div class="caption-content">{spans}</div></div>')
        js.append(f'tl.fromTo("#cg{i}",{{opacity:0}},{{opacity:1,duration:.10,ease:"power1.out",immediateRender:false}},{g["start"]});')
        js.append(f'tl.from("#cg{i} span",{{y:5,duration:.16,ease:"expo.out",stagger:.015,immediateRender:false}},{g["start"]});')
        for j,w in enumerate(g["words"]):
            js.append(f'tl.set("#w{i}-{j}",{{color:"#D8604B"}},{w["start"]});')
            js.append(f'tl.set("#w{i}-{j}",{{color:"#F6F0E3"}},{w["end"]});')
        js.append(f'tl.set("#cg{i}",{{opacity:0}},{g["end"]});')
    js.append('window.__timelines["main"]=tl;')
    document=f'''<!doctype html><html><head><meta charset="utf-8"><style>{css}</style>
<script src="node_modules/gsap/dist/gsap.min.js"></script></head><body>
<div id="root" class="clip" data-composition-id="main" data-start="0" data-duration="{t['duration']}" data-width="{t['width']}" data-height="{t['height']}">
{''.join(scenes)}<div style="position:absolute;inset:0;z-index:10000">{''.join(groups)}</div>
<audio id="narration" class="clip" src="public/final_audio.wav" data-start="0" data-duration="{t['duration']}" data-track-index="1" data-volume="1"></audio></div>
<script>{''.join(js)}</script></body></html>'''
    (project/"index.html").write_text(document,encoding="utf-8")
    return project

def write_remotion(run,t,c,pins):
    project=run/"projects"/"remotion"; project.mkdir(parents=True,exist_ok=True)
    copy_assets(run,project,t); (project/"src").mkdir(exist_ok=True)
    deps={name:pins["remotion"] for name in ("remotion","@remotion/cli","@remotion/media","@remotion/captions")}
    deps.update({"react":"19.2.0","react-dom":"19.2.0"})
    atomic_json(project/"package.json",{"name":"kaggle-horror-remotion","private":True,"version":"1.0.0",
        "scripts":{"preview":"remotion studio src/index.tsx --no-open","render":"remotion render src/index.tsx Film FINAL_video.mp4"},"dependencies":deps})
    atomic_json(project/"src"/"timeline.json",t)
    fs=round(min(t["height"]*.051,t["width"]*.064)); bottom=round(t["height"]*(.27 if c["ASPECT"]=="9:16" else .09))
    font_css="@font-face{font-family:Caption;src:url('/fonts/caption.ttf')}"
    sequences=[]
    for i,s in enumerate(t["scenes"]):
        sequences.append(f'<Sequence name="Scene-{i+1}" from={{{s["start_frame"]}}} durationInFrames={{{s["frames"]+ (round(c["TRANSITION_SECONDS"]*t["fps"])+1 if i<len(t["scenes"])-1 else 0)}}}><Scene image={{{json.dumps(s["image"])}}} frames={{{s["frames"]}}} first={{{str(i==0).lower()}}}/></Sequence>')
    source=f'''import React from 'react';
import {{AbsoluteFill,CanvasImage,Composition,Sequence,interpolate,useCurrentFrame,useVideoConfig,staticFile,registerRoot,delayRender,continueRender,cancelRender}} from 'remotion';
import {{Audio}} from '@remotion/media';
import timeline from './timeline.json';
const Font=()=>{{
 const [handle]=React.useState(()=>delayRender('Local caption font'));
 React.useEffect(()=>{{
  const font=new FontFace('Caption',`url("${{staticFile('fonts/caption.ttf')}}")`,{{weight:'700'}});
  font.load().then(f=>{{document.fonts.add(f);continueRender(handle);}}).catch(cancelRender);
 }},[handle]); return null;
}};
const Scene=({{image,frames,first}}:{{image:string;frames:number;first:boolean}})=>{{
 const frame=useCurrentFrame(); const {{fps}}=useVideoConfig();
 return <AbsoluteFill style={{{{opacity:interpolate(frame,[0,Math.max(1,Math.round(fps*{c['TRANSITION_SECONDS']}))],[0,1],{{extrapolateLeft:'clamp',extrapolateRight:'clamp'}}),backgroundColor:'#101820',overflow:'hidden'}}}}>
  <CanvasImage src={{staticFile(image)}} style={{{{width:'100%',height:'100%',objectFit:'cover',scale:interpolate(frame,[0,frames],[1,1.09],{{extrapolateLeft:'clamp',extrapolateRight:'clamp'}})}}}}/>
  <AbsoluteFill style={{{{background:'radial-gradient(ellipse,rgba(16,24,32,0) 35%,rgba(16,24,32,.55) 100%)'}}}}/>
 </AbsoluteFill>;
}};
const Captions=()=>{{ const time=useCurrentFrame()/{t['fps']};
 const group=timeline.groups.find(g=>time>=g.start&&time<g.end); if(!group)return null;
 return <AbsoluteFill style={{{{padding:'0 7%',boxSizing:'border-box',justifyContent:'flex-end',alignItems:'center',paddingBottom:{bottom},pointerEvents:'none'}}}}>
 <div style={{{{fontFamily:'Caption,DejaVu Sans,sans-serif',fontSize:{fs},fontWeight:700,lineHeight:1.24,textAlign:'center',maxWidth:'100%',boxSizing:'border-box',overflowWrap:'anywhere',padding:'10px 20px',borderRadius:9,background:'rgba(16,24,32,.86)',textShadow:'0 2px 5px #101820'}}}}>
 {{group.words.map((w,i)=><span key={{i}} style={{{{color:time>=w.start&&time<w.end?'#D8604B':'#F6F0E3',whiteSpace:'pre-wrap'}}}}>{{(i?' ':'')+w.text}}</span>)}}</div></AbsoluteFill>;
}};
const Film=()=> <AbsoluteFill style={{{{backgroundColor:'#101820'}}}}><Font/>{''.join(sequences)}<Captions/><Audio src={{staticFile('final_audio.wav')}}/></AbsoluteFill>;
const Root=()=> <Composition id="Film" component={{Film}} fps={{{t['fps']}}} width={{{t['width']}}} height={{{t['height']}}} durationInFrames={{{t['frames']}}} defaultProps={{{{}}}}/>;
registerRoot(Root);
'''
    (project/"src"/"index.tsx").write_text(source,encoding="utf-8")
    return project

def ensure_renderer(project,engine,scratch,offline=False):
    npm=shutil.which("npm.cmd" if os.name=="nt" else "npm")
    if not npm: raise RuntimeError("npm not found; install Node.js 22+.")
    # Dependencies in scratch, only source + assets in the saved project.
    package=(project/"package.json").read_bytes()
    import hashlib
    depot=Path(scratch)/"node"/(engine+"-"+hashlib.sha256(package).hexdigest()[:12])
    depot.mkdir(parents=True,exist_ok=True)
    (depot/"package.json").write_bytes(package)
    marker=depot/"installed.json"
    if not marker.exists():
        if offline: raise RuntimeError("OFFLINE: renderer dependencies not installed.")
        run_logged([npm,"install","--no-audit","--no-fund"],project/"install.log",cwd=depot,timeout=1200)
        atomic_json(marker,{"package_sha":hashlib.sha256(package).hexdigest()})
    source=depot/"node_modules"; link=project/"node_modules"
    if not link.exists():
        if os.name=="nt":
            # Junction needs no developer-mode symlink privilege on Windows.
            import _winapi
            _winapi.CreateJunction(str(source.resolve()),str(link.resolve()))
        else: link.symlink_to(source,target_is_directory=True)
    if (depot/"package-lock.json").exists(): shutil.copy2(depot/"package-lock.json",project/"package-lock.json")
    return project/"node_modules"/".bin"/(engine+(".cmd" if os.name=="nt" else ""))

def render_browser(project,engine,run,t,c,scratch):
    executable=ensure_renderer(project,engine,scratch,c["OFFLINE"])
    video=run/f"render-{engine}.mp4"
    if engine=="hyperframes":
        # doctor/lint/inspect run before export; all logs remain reviewable.
        for name,args in (("doctor",["doctor"]),("lint",["lint"]),("validate",["validate"]),("inspect",["inspect","--samples","5"])):
            run_logged([executable,*args],run/"logs"/f"hyperframes-{name}.log",cwd=project,timeout=600)
        run_logged([executable,"render","--output",video,"--fps",str(t["fps"]),"--quality","standard",
                    "--workers",str(c["RENDER_WORKERS"])],run/"logs"/"hyperframes-render.log",cwd=project,timeout=3*3600)
    else:
        run_logged([executable,"render","src/index.tsx","Film",video,"--codec","h264","--crf",str(c["CRF"]),
                    "--concurrency",str(c["RENDER_WORKERS"]),"--gl","swangle"],run/"logs"/"remotion-render.log",cwd=project,timeout=3*3600)
    if not video.exists() or video.stat().st_size==0: raise RuntimeError("Renderer returned no video")
    return video

def render_ffmpeg(run,t,c):
    clips=[]; width=t["width"]; height=t["height"]; fps=t["fps"]
    transition=max(1,round(c["TRANSITION_SECONDS"]*fps))
    for i,s in enumerate(t["scenes"]):
        # Extend each outgoing image beyond its audio slot; xfade overlap restores exact total length.
        frames=s["frames"]+(transition if i<len(t["scenes"])-1 else 0)
        dest=run/f"motion-{i:04d}.mp4"
        vf=(f"scale={width*2}:{height*2}:force_original_aspect_ratio=increase,crop={width*2}:{height*2},"
            f"zoompan=z='1+0.09*on/{max(1,frames-1)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s={width}x{height}:fps={fps}")
        subprocess.run(["ffmpeg","-y","-v","error","-i",str(run/s["image"]),"-vf",vf,"-frames:v",str(frames),
                        "-an","-c:v","libx264","-preset","veryfast","-crf",str(c["CRF"]),"-pix_fmt","yuv420p",str(dest)],check=True)
        clips.append(dest)
    out=run/"render-ffmpeg.mp4"
    if len(clips)==1: shutil.copy2(clips[0],out); return out
    # Pairwise transitions keep memory bounded for long stories.
    current=clips[0]; accumulated=t["scenes"][0]["frames"]/fps
    for i,clip in enumerate(clips[1:],1):
        joined=run/f"joined-{i:04d}.mp4"
        graph=f"[0:v]settb=AVTB[a];[1:v]settb=AVTB[b];[a][b]xfade=transition=fade:duration={transition/fps}:offset={accumulated}[v]"
        subprocess.run(["ffmpeg","-y","-v","error","-filter_complex_threads","1","-i",str(current),"-i",str(clip),
                        "-filter_complex",graph,"-map","[v]","-an","-c:v","libx264","-preset","veryfast",
                        "-crf",str(c["CRF"]),"-pix_fmt","yuv420p",str(joined)],check=True)
        current=joined; accumulated+=t["scenes"][i]["frames"]/fps
    shutil.copy2(current,out)
    return out

def finalize(run,t,c,video,engine):
    final=run/("PREVIEW_video.mp4" if c["QUICK_TEST"] else "FINAL_video.mp4")
    args=["ffmpeg","-y","-v","error","-i",str(video),"-i",str(run/"final_audio.wav"),"-map","0:v:0","-map","1:a:0"]
    if engine=="ffmpeg":
        # cwd gives ASS a portable relative path and avoids filter escaping issues.
        args += ["-vf","ass=subtitles.ass","-c:v","libx264","-preset","veryfast","-crf",str(c["CRF"])]
    else: args += ["-c:v","copy"]
    args += ["-c:a","aac","-b:a","192k","-t",str(t["duration"]),"-movflags","+faststart",str(final)]
    subprocess.run(args,cwd=run,check=True)
    info=probe(final); streams=info["streams"]
    videos=[s for s in streams if s["codec_type"]=="video"]; audios=[s for s in streams if s["codec_type"]=="audio"]
    if len(videos)!=1 or len(audios)!=1: raise RuntimeError("Final MP4 must contain video and audio")
    v=videos[0]; duration=float(info["format"]["duration"])
    if (v["width"],v["height"])!=(t["width"],t["height"]): raise RuntimeError("Output dimensions mismatch")
    if abs(duration-t["duration"])>max(.12,2/t["fps"]): raise RuntimeError("Output duration mismatch")
    if v.get("nb_frames") and abs(int(v["nb_frames"])-t["frames"])>1: raise RuntimeError("Output frame count mismatch")
    subprocess.run(["ffmpeg","-v","error","-i",str(final),"-f","null","-"],check=True)
    return final,info

def export_projects(run,projects):
    archive=run/"editing_projects.zip"
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3,strict_timestamps=False) as z:
        for project in projects.values():
            for base,dirs,files in os.walk(project,followlinks=False):
                dirs[:]=[d for d in dirs if d not in {".hyperframes",".remotion","renders"} and not d.startswith("node_modules")]
                for name in files:
                    p=Path(base)/name; rel=p.relative_to(project)
                    if p.suffix not in {".mp4",".log"}: z.write(p,str(Path(project.name)/rel))
    return archive

def build_video(run,c,pins,scratch):
    run=Path(run); timeline=prepare_timeline(run,c)
    projects={}
    for engine in ("hyperframes","remotion"):
        if c["EXPORT_OTHER_RENDERER"] or c["RENDER_ENGINE"]==engine:
            projects[engine]=(write_hyperframes if engine=="hyperframes" else write_remotion)(run,timeline,c,pins)
    requested=c["RENDER_ENGINE"]; actual=requested; fallback=None
    try:
        if requested=="ffmpeg": video=render_ffmpeg(run,timeline,c)
        else: video=render_browser(projects[requested],requested,run,timeline,c,scratch)
    except Exception as exc:
        if requested=="ffmpeg" or not c["ALLOW_FFMPEG_FALLBACK"]: raise
        actual="ffmpeg"; fallback=str(exc)
        print(f"{requested} не выполнил рендер; явно включён FFmpeg fallback. Причина: {exc}")
        video=render_ffmpeg(run,timeline,c)
    final,info=finalize(run,timeline,c,video,actual)
    if projects: export_projects(run,projects)
    state=load_state(run)
    report={"status":"completed","mode":"preview" if c["QUICK_TEST"] else "full","run_id":state["run_id"],
        "requested_renderer":requested,"actual_renderer":actual,"fallback_reason":fallback,"scenes_selected":len(timeline["scenes"]),
        "scenes_total":len(state["scenes"]),"frames":timeline["frames"],"duration_seconds":timeline["duration"],
        "output":final.name,"output_bytes":final.stat().st_size,"output_sha256":sha256_file(final),
        "stages":state.get("stages",{}),"checks":{"audio_video_streams":True,"dimensions":True,"duration":True,"decode":True},
        "qa":[{"index":s["index"],"visual":s.get("qa",{"status":"not_run"}),"asr":s.get("asr",{"status":"not_run"}),
               "director_source":s.get("prompt_source")} for s in selected_scenes(state,c)],"environment":json.loads((run/"environment.json").read_text(encoding="utf-8"))}
    atomic_json(run/"qa_report.json",report)
    print(f"Готово: {final.name}, {timeline['duration']:.2f}s, renderer={actual}")
    return final,report
