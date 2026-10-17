import gc, hashlib, json, math, os, re, shutil, subprocess, sys, time, wave, threading, signal
from pathlib import Path

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,path)

def split_scenes(text, max_words, min_words):
    normalized = " ".join(text.split())
    if not normalized: return []
    chunks = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        current = []
        for sentence in re.split(r"(?<=[.!?。！？])\s+", paragraph.strip()):
            tokens = sentence.split()
            for start in range(0,len(tokens),max_words):
                part = tokens[start:start+max_words]
                if current and len(current)+len(part)>max_words:
                    chunks.append(" ".join(current)); current=[]
                current.extend(part)
        if current: chunks.append(" ".join(current))
    merged=[]
    for part in chunks:
        if merged and len(part.split())<min_words and len(merged[-1].split())+len(part.split())<=max_words:
            merged[-1]+=" "+part
        else: merged.append(part)
    assert " ".join(merged)==normalized, "Сегментация изменила текст."
    assert all(len(x.split())<=max_words for x in merged)
    return merged

def default_direction(text, index, config):
    lower=text.lower()
    cues=[("doll","a small worn burlap doll with mismatched black button eyes beside tree roots"),
          ("flashlight","a flashlight beam cutting through dense forest at night"),
          ("figure","tall indistinct silhouettes among trees beyond the reach of a flashlight"),
          ("fire","a secluded lakeside campsite, ember-lit faces and tall pine trees"),
          ("lake","an isolated still lake surrounded by tall pine trees"),
          ("forest","a narrow path beneath a dense black forest canopy")]
    subject=next((v for k,v in cues if k in lower),"a secluded lakeside campground and the surrounding pine forest")
    mood="shock" if any(k in lower for k in ("scream","terror","crack")) else "dread"
    if any(k in lower for k in ("idyllic","peaceful","swam")): mood="calm"
    shot=["wide establishing shot","medium shot","close-up","point-of-view shot"][index%4]
    return {"prompt":f"{shot} of {subject}. {config['STYLE']} Scene context: {text[:280]}","mood":mood,"prompt_source":"template"}

def wav_ok(path):
    try:
        with wave.open(str(path),"rb") as w:
            return w.getnframes()>0 and w.getnchannels()==1 and w.getsampwidth()==2
    except Exception: return False

def image_ok(path):
    try:
        from PIL import Image
        with Image.open(path) as im: im.verify()
        return True
    except Exception: return False

def probe(path):
    out=subprocess.run(["ffprobe","-v","error","-show_format","-show_streams","-of","json",str(path)],capture_output=True,text=True,check=True)
    return json.loads(out.stdout)

def selected_scenes(state, config):
    return state["scenes"][:config["TEST_SCENES"]] if config["QUICK_TEST"] else state["scenes"]

def load_state(run):
    return json.loads((Path(run)/"pipeline_state.json").read_text(encoding="utf-8"))

def save_state(run,state): atomic_json(Path(run)/"pipeline_state.json",state)

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def run_logged(args, log, cwd=None, env=None, timeout=3600):
    # stderr объединяется с stdout; долгий процесс виден в notebook и в log-файле.
    with open(log,"w",encoding="utf-8") as f:
        process=subprocess.Popen([str(x) for x in args],cwd=cwd,env=env,stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",start_new_session=os.name!="nt")
        def stop_process():
            if process.poll() is not None: return
            try:
                if os.name=="nt": process.kill()
                else: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
        expired=threading.Event()
        def stop_overdue():
            expired.set()
            stop_process()
        watchdog=threading.Timer(timeout,stop_overdue)
        watchdog.daemon=True
        watchdog.start()
        try:
            for line in process.stdout:
                f.write(line); f.flush()
                print(line.rstrip(),flush=True)
            code=process.wait(timeout=30)
        except BaseException:
            stop_process(); process.wait(); raise
        finally:
            watchdog.cancel()
    if expired.is_set(): raise TimeoutError(f"Превышен лимит {timeout}s. Лог: {log}")
    if code: raise RuntimeError(f"Процесс завершился с кодом {code}. Лог: {log}")
