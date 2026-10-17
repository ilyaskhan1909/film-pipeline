# 4. Сцены и состояние. Файлы восстанавливаются из прежнего Kaggle Output при RESUME_FROM.
if CONFIG["RESUME_FROM"] and not (RUN/"pipeline_state.json").exists():
    source=Path(CONFIG["RESUME_FROM"])
    old=json.loads((source/"pipeline_state.json").read_text(encoding="utf-8"))
    if old.get("run_id")!=RUN_ID: raise ValueError("RESUME_FROM относится к другой истории/конфигурации.")
    shutil.copytree(source,RUN,dirs_exist_ok=True,ignore=shutil.ignore_patterns("scripts","node_modules",".hyperframes",".remotion"))
state_path=RUN/"pipeline_state.json"
if state_path.exists():
    STATE=load_state(RUN)
    if STATE.get("run_id")!=RUN_ID: raise ValueError("State fingerprint mismatch.")
else:
    texts=split_scenes(STORY_TEXT,CONFIG["MAX_WORDS"],CONFIG["MIN_WORDS"])
    STATE={"schema":3,"run_id":RUN_ID,"scenes":[{"index":i,"text":t,**default_direction(t,i,CONFIG)} for i,t in enumerate(texts)],"stages":{}}
    save_state(RUN,STATE)
for scene in STATE["scenes"]:
    if scene.get("audio") and not wav_ok(RUN/scene["audio"]):
        for key in ("audio","audio_duration","words","asr"): scene.pop(key,None)
    if scene.get("image") and not image_ok(RUN/scene["image"]):
        for key in ("image","qa"): scene.pop(key,None)
save_state(RUN,STATE)
assert " ".join(s["text"] for s in STATE["scenes"])==" ".join(STORY_TEXT.split())
JOB_FILE=RUN/"job.json"
atomic_json(JOB_FILE,{"run":str(RUN),"config":CONFIG,"revisions":REVISIONS,"pins":PINS})
atomic_json(RUN/"config.json",{"config":CONFIG,"revisions":REVISIONS,"pins":PINS})

def run_stage(stage, environment, optional=False):
    child_env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(CONFIG["GPU_INDEX"]),PYTHONUNBUFFERED="1",
                   PYTHONPATH=str(RUN/"scripts"))
    try:
        run_logged([ENVS[environment],str(RUN/"scripts"/"worker.py"),stage,str(JOB_FILE)],
                   RUN/"logs"/f"{stage}.log",env=child_env,timeout=3*3600)
    except Exception as exc:
        if not optional: raise
        state=load_state(RUN)
        state.setdefault("stages",{})[stage]={"status":"failed_optional","error":str(exc)[:500]}
        save_state(RUN,state)
        print(f"Опциональный этап {stage} не выполнен. Причина в logs/{stage}.log. Экспорт материала продолжится.")

print(f"Текст сохранён полностью: {len(STORY_TEXT.split())} слов, {len(STATE['scenes'])} сцен; выбранных: {len(selected_scenes(STATE,CONFIG))}.")
