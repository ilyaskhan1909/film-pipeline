"""Portable raw assets only. No browser, transitions, music or burned-in captions."""
import hashlib, json, math, subprocess, wave, zipfile
from pathlib import Path
from core import atomic_json, image_ok, wav_ok, load_state, selected_scenes, run_logged, probe, sha256_file


def srt_time(seconds):
    ms=max(0,round(seconds*1000)); hours,ms=divmod(ms,3600000)
    minutes,ms=divmod(ms,60000); seconds,ms=divmod(ms,1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def check_video(path, width, height, fps, frames, log):
    info=probe(path)
    video=next((x for x in info["streams"] if x["codec_type"]=="video"),None)
    audio=next((x for x in info["streams"] if x["codec_type"]=="audio"),None)
    if not video or not audio: raise RuntimeError(f"Video/audio stream missing: {path}")
    num,den=map(int,video["avg_frame_rate"].split("/"))
    if (video["width"],video["height"])!=(width,height) or abs(num/den-fps)>1e-4:
        raise RuntimeError(f"Unexpected size/fps: {path}")
    count=video.get("nb_frames")
    if count in (None,"N/A"):
        counted=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-count_frames",
            "-show_entries","stream=nb_read_frames","-of","json",str(path)],capture_output=True,text=True,check=True)
        count=json.loads(counted.stdout)["streams"][0]["nb_read_frames"]
    if int(count)!=frames: raise RuntimeError(f"Wrong frame count: {path}: {count} != {frames}")
    if abs(float(info["format"]["duration"])-frames/fps)>.1:
        raise RuntimeError(f"Wrong duration: {path}")
    run_logged(["ffmpeg","-v","error","-xerror","-i",path,"-f","null","-"],log,timeout=1800)
    return {"width":width,"height":height,"fps":fps,"frames":int(count),"duration":frames/fps,
            "video_codec":video["codec_name"],"audio_codec":audio["codec_name"],"full_decode":"passed"}


def build_raw_material(run, config, story):
    run=Path(run); state=load_state(run); scenes=selected_scenes(state,config)
    if not scenes: raise RuntimeError("No scenes selected")
    for scene in scenes:
        if not image_ok(run/scene.get("image","missing")) or not wav_ok(run/scene.get("audio","missing")):
            raise RuntimeError(f"Scene {scene['index']+1}: incomplete image/audio")
    for folder in ("clips","audio","logs"): (run/folder).mkdir(exist_ok=True)
    fps=config["FPS"]; sr=48000; width=config["OUT_W"]; height=config["OUT_H"]
    narration=run/"narration.wav"; cursor=0; entries=[]; global_words=[]; subtitles=[]
    with wave.open(str(narration),"wb") as combined:
        combined.setnchannels(1); combined.setsampwidth(2); combined.setframerate(sr)
        for scene in scenes:
            index=scene["index"]; normalized=run/"audio"/f"normalized-{index:04d}.wav"
            run_logged(["ffmpeg","-y","-v","error","-i",run/scene["audio"],"-ar",str(sr),"-ac","1",
                "-c:a","pcm_s16le",normalized],run/"logs"/f"normalize-{index:04d}.log",timeout=300)
            with wave.open(str(normalized),"rb") as inp:
                samples=inp.getnframes(); audio_duration=samples/sr
                frames=math.ceil((samples+round(config["SCENE_PAUSE"]*sr))*fps/sr)
                target_samples=frames*(sr//fps); remaining=target_samples
                while remaining:
                    count=min(sr,remaining); pcm=inp.readframes(count)
                    combined.writeframes(pcm+bytes(count*2-len(pcm))); remaining-=count
            relative=f"clips/s{index:04d}.mp4"; clip=run/relative
            settings={"image_sha256":sha256_file(run/scene["image"]),"audio_sha256":sha256_file(run/scene["audio"]),
                "width":width,"height":height,"fps":fps,"frames":frames,"crf":config["CRF"],
                "preset":config["ENCODE_PRESET"],"export_version":1}
            signature=hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()
            marker=clip.with_suffix(".json"); cached=False
            if clip.is_file() and marker.is_file():
                saved=json.loads(marker.read_text(encoding="utf-8"))
                cached=saved.get("signature")==signature and saved.get("sha256")==sha256_file(clip)
            if not cached:
                temp=clip.with_name(clip.stem+".tmp.mp4")
                filters=(f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,format=yuv420p")
                run_logged(["ffmpeg","-y","-v","error","-loop","1","-framerate",str(fps),"-i",run/scene["image"],
                    "-i",normalized,"-vf",filters,"-map","0:v:0","-map","1:a:0","-c:v","libx264",
                    "-preset",config["ENCODE_PRESET"],"-crf",str(config["CRF"]),"-pix_fmt","yuv420p",
                    "-frames:v",str(frames),"-r",str(fps),"-c:a","aac","-b:a","192k","-ar",str(sr),"-ac","1",
                    "-af","apad","-t",str(frames/fps),"-movflags","+faststart",temp],
                    run/"logs"/f"raw-clip-{index:04d}.log",timeout=3600)
                verified=check_video(temp,width,height,fps,frames,run/"logs"/f"decode-{index:04d}.log")
                temp.replace(clip)
                atomic_json(marker,{"signature":signature,"sha256":sha256_file(clip),"verified":verified})
            else:
                verified=saved["verified"]
            words=scene.get("words",[]) if config["ALIGN_WORDS"] else []
            clean_words=[]
            for word in words:
                a=float(word["start"]); b=float(word["end"])
                if not math.isfinite(a+b) or a<0 or b<=a or b>audio_duration+.05:
                    raise ValueError(f"Invalid word timestamp in scene {index+1}")
                clean_words.append({"text":word["text"],"start":a,"end":b})
                global_words.append({"text":word["text"],"start":cursor/fps+a,"end":cursor/fps+b,"scene":index})
            for start in range(0,len(clean_words),config["WORDS_PER_CAPTION"]):
                group=clean_words[start:start+config["WORDS_PER_CAPTION"]]
                subtitles.append({"start":cursor/fps+group[0]["start"],"end":cursor/fps+group[-1]["end"],
                    "text":" ".join(w["text"] for w in group)})
            entry={"index":index,"clip":relative,"image":scene["image"],"audio":scene["audio"],
                "start_frame":cursor,"frames":frames,"start":cursor/fps,"duration":frames/fps,
                "audio_duration":audio_duration,"tail_padding":frames/fps-audio_duration,
                "text":scene["text"],"prompt":scene.get("prompt",""),"mood":scene.get("mood",""),
                "words":clean_words,"alignment":"measured" if clean_words else "missing",
                "qa":scene.get("qa"),"asr":scene.get("asr"),"verified":verified}
            entries.append(entry); cursor+=frames
            print(f"RAW scene {index+1}: {frames/fps:.2f}s ({'cached' if cached else 'encoded'})",flush=True)
    manifest={"schema":1,"kind":"raw_material_handoff","run_id":state["run_id"],
        "scope":"test" if config["QUICK_TEST"] else "full","source_scene_count":len(state["scenes"]),
        "selected_scene_count":len(entries),"fps":fps,"width":width,"height":height,
        "frames":cursor,"duration":cursor/fps,"narration":"narration.wav","scenes":entries,
        "visual_source":"generated_still_images","motion":"none; static holds, not generative video",
        "burned_captions":False,"music":False,"transitions":False,"paths":"relative to this manifest",
        "editing":"HyperFrames/Remotion composition will be created after reviewing these assets",
        "alignment_missing_scenes":[e["index"] for e in entries if e["alignment"]=="missing"]}
    atomic_json(run/"manifest.json",manifest)
    atomic_json(run/"word_timestamps.json",{"timebase":"seconds","global_words":global_words,
        "scenes":[{"index":e["index"],"audio":e["audio"],"words":e["words"]} for e in entries]})
    captions=[{"text":" "+w["text"],"startMs":round(w["start"]*1000),"endMs":round(w["end"]*1000),
        "timestampMs":round((w["start"]+w["end"])*500),"confidence":None} for w in global_words]
    atomic_json(run/"captions.json",captions)
    srt="\n\n".join(f"{i+1}\n{srt_time(g['start'])} --> {srt_time(g['end'])}\n{g['text']}" for i,g in enumerate(subtitles))
    (run/"subtitles.srt").write_text(srt+"\n" if srt else "",encoding="utf-8")
    (run/"story.txt").write_text(story,encoding="utf-8")
    preview=None; preview_verified=None
    if config["EXPORT_PREVIEW"]:
        playlist="ffconcat version 1.0\n"+"".join(f"file '{e['clip']}'\nduration {e['duration']:.9f}\n" for e in entries)
        (run/"preview.ffconcat").write_text(playlist,encoding="utf-8")
        preview=run/("PREVIEW_raw.mp4" if config["QUICK_TEST"] else "RAW_review.mp4")
        temp=preview.with_name(preview.stem+".tmp.mp4")
        run_logged(["ffmpeg","-y","-v","error","-f","concat","-safe","1","-i","preview.ffconcat",
            "-i","narration.wav","-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k",
            "-t",str(cursor/fps),"-movflags","+faststart",temp.name],run/"logs"/"raw-preview.log",cwd=run,timeout=3600)
        preview_verified=check_video(temp,width,height,fps,cursor,run/"logs"/"preview-decode.log")
        temp.replace(preview)
    report={"kind":"raw_material_quality_report","scope":manifest["scope"],"clips":len(entries),
        "technical_validation":"passed","preview":preview_verified,"alignment_missing_scenes":manifest["alignment_missing_scenes"],
        "stages":state.get("stages",{}),"qa_advisory":True,"production_master":False,
        "limitations":["Static image holds, not generated motion","No edit/color/sound-design pass",
            "Technical checks do not prove narrative/visual quality"],"paths":"relative"}
    atomic_json(run/"quality_report.json",report)
    files={run/e[key] for e in entries for key in ("clip","image","audio")}
    files.update(run/e["clip"].replace(".mp4",".json") for e in entries)
    files.update(run/name for name in ("manifest.json","word_timestamps.json","captions.json","subtitles.srt",
        "story.txt","narration.wav","quality_report.json","pipeline_state.json","config.json","environment.json"))
    if preview: files.add(preview)
    files={p for p in files if p.is_file()}
    atomic_json(run/"checksums.json",{p.relative_to(run).as_posix():sha256_file(p) for p in sorted(files)})
    files.add(run/"checksums.json")
    archive=run/("raw_material_TEST.zip" if config["QUICK_TEST"] else "raw_material_FULL.zip")
    temp=archive.with_name(archive.name+".tmp")
    with zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=1,strict_timestamps=False) as z:
        for path in sorted(files):
            compressed=zipfile.ZIP_STORED if path.suffix.lower() in {".mp4",".png"} else zipfile.ZIP_DEFLATED
            z.write(path,path.relative_to(run).as_posix(),compress_type=compressed)
    with zipfile.ZipFile(temp) as z:
        if z.testzip() is not None: raise RuntimeError("Raw archive validation failed")
    temp.replace(archive)
    print("Материал для монтажа:",archive)
    if manifest["alignment_missing_scenes"]: print("Внимание: отсутствуют тайминги в сценах",manifest["alignment_missing_scenes"])
    return preview,archive,manifest
