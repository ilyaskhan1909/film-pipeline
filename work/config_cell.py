# 1. Настройки. QUICK_TEST=False — вся история; True — первые TEST_SCENES сцен.
from pathlib import Path
import os, json, hashlib, platform

STORY_TEXT = __STORY_LITERAL__

CONFIG = {
    "QUICK_TEST": True,
    "TEST_SCENES": 2,
    "ASPECT": "16:9",                 # 16:9 | 9:16 | 1:1
    "FPS": 24,
    "OUTPUT_SCALE": 1.0,              # 1.0: 1080p; 2/3: 720p
    "MAX_WORDS": 55,
    "MIN_WORDS": 16,
    "SEED": 12345,
    "IMAGE_ENGINE": "flux2",         # flux2 | zimage
    "IMAGE_MODEL": "black-forest-labs/FLUX.2-klein-4B",
    "IMAGE_REFERENCES": [],           # ['/kaggle/input/my-data/character.png'] — FLUX only
    "USE_FIRST_FRAME_REFERENCE": True,
    "QUANTIZE_IMAGES": True,         # NF4; FP32 compute на T4/P100, BF16 на Ampere+
    "TTS_ENGINE": "qwen",            # qwen | kokoro (Kokoro: English only)
    "TTS_MODEL": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "LANGUAGE": "English",           # English | Russian | Chinese | ...
    "SPEAKER": "Ryan",               # English: Ryan/Aiden; список проверяется автоматически
    "VOICE_INSTRUCTION": "A restrained cinematic horror narrator. Speak clearly, slowly, with subtle tension.",
    "KOKORO_VOICE": "bm_george",
    "KOKORO_SPEED": 0.95,
    "TTS_MAX_SECONDS": 240,
    "SCENE_PAUSE": 0.0,              # хвост тишины; паузы монтажа добавим позже
    "ALIGN_WORDS": True,             # реальные тайминги слов, отдельным файлом
    "ALIGN_OPTIONAL": True,          # ошибка таймингов не теряет готовый материал
    "ALIGN_MODEL": "Qwen/Qwen3-ForcedAligner-0.6B-hf",
    "LLM_ENABLED": True,             # локально, без платных API и ключей
    "LLM_MODEL": "Qwen/Qwen3.5-2B",
    "QA_MAX_SCENES": 8,
    "ASR_CHECK": False,              # дополнительное скачивание Qwen3-ASR-0.6B
    "ASR_MODEL": "Qwen/Qwen3-ASR-0.6B-hf",
    "EXPORT_PREVIEW": True,          # только склейка для просмотра, не финальный монтаж
    "WORDS_PER_CAPTION": 5,
    "CRF": 18,                       # H.264; оригинальные PNG/WAV тоже сохраняются
    "ENCODE_PRESET": "fast",
    "OFFLINE": False,                # нужны локальные модели и установленные зависимости
    "MODEL_PATHS": {},               # {'Qwen/...': '/kaggle/input/models/model-dir'}
    "RESUME_FROM": "",              # папка run-* из Output предыдущей сохранённой версии
    "GPU_INDEX": 0,
    "MIN_FREE_SCRATCH_GB": 28,
    "STYLE": "Cinematic horror film still, natural anatomy, deep forest, restrained cold-blue shadows, muted ember-red light, subtle film grain. No captions or logos in the image.",
    "CHARACTERS": "Mark: young adult man, short dark hair, blue shirt. Chloe: young adult woman, shoulder-length brown hair, dark camping jacket. Jess: young adult woman, dark curly hair, olive jacket.",
}
REVISIONS = {
    "black-forest-labs/FLUX.2-klein-4B": "e7b7dc27f91deacad38e78976d1f2b499d76a294",
    "Tongyi-MAI/Z-Image-Turbo": "f332072aa78be7aecdf3ee76d5c247082da564a6",
    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice": "0c0e3051f131929182e2c023b9537f8b1c68adfe",
    "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice": "85e237c12c027371202489a0ec509ded67b5e4b5",
    "Qwen/Qwen3.5-2B": "15852e8c16360a2fea060d615a32b45270f8a8fc",
    "Qwen/Qwen3-ForcedAligner-0.6B-hf": "c07281df297b9905d24a508279258cccf987a064",
    "Qwen/Qwen3-ASR-0.6B-hf": "7f1569a48a89f3e3f4dc3a5c9d28bddd903bc76c",
}
PINS = {"image": ["diffusers==0.40.0", "transformers==5.18.0", "accelerate==1.15.0", "bitsandbytes==0.50.2", "huggingface-hub==1.33.0", "safetensors==0.8.0", "peft==0.21.2"],
        "tts": ["qwen-tts==0.1.1", "transformers==4.57.3", "accelerate==1.12.0", "huggingface-hub==0.36.0", "gradio==6.17.3", "librosa==0.11.0", "soundfile==0.14.0"],
        "align": ["transformers==5.18.0", "accelerate==1.15.0", "huggingface-hub==1.33.0", "safetensors==0.8.0", "librosa==0.11.0", "soundfile==0.14.0"],
        "kokoro": ["kokoro==0.9.4", "transformers==4.57.3", "huggingface-hub==0.36.0"]}
if CONFIG["LANGUAGE"] in {"Japanese", "ja"}:
    PINS["align"].append("nagisa==0.3.0")
elif CONFIG["LANGUAGE"] in {"Korean", "ko"}:
    PINS["align"].append("soynlp==0.0.493")
if CONFIG["IMAGE_ENGINE"] == "zimage":
    CONFIG["IMAGE_MODEL"] = "Tongyi-MAI/Z-Image-Turbo"
assert CONFIG["ASPECT"] in {"16:9", "9:16", "1:1"}
assert CONFIG["FPS"] in {24, 30, 60}
assert CONFIG["IMAGE_ENGINE"] in {"flux2", "zimage"}
assert CONFIG["TTS_ENGINE"] in {"qwen", "kokoro"}
assert 1 <= CONFIG["MIN_WORDS"] <= CONFIG["MAX_WORDS"]
assert 0 < CONFIG["OUTPUT_SCALE"] <= 1 and 1 <= CONFIG["TEST_SCENES"]
assert 0 < CONFIG["TTS_MAX_SECONDS"] <= 300 and 0 <= CONFIG["SCENE_PAUSE"] <= 5
assert 1 <= CONFIG["WORDS_PER_CAPTION"] <= 8 and 12 <= CONFIG["CRF"] <= 28
assert CONFIG["ENCODE_PRESET"] in {"veryfast", "fast", "medium", "slow"}
assert STORY_TEXT.strip(), "Введите историю."
if CONFIG["TTS_ENGINE"] == "kokoro" and CONFIG["LANGUAGE"] != "English":
    raise ValueError("Для русского языка выберите TTS_ENGINE='qwen'.")
if CONFIG["IMAGE_ENGINE"] == "zimage" and CONFIG["IMAGE_REFERENCES"]:
    raise ValueError("IMAGE_REFERENCES поддерживается только в режиме flux2.")
SIZES = {"16:9": (1920, 1080, 1024, 576), "9:16": (1080, 1920, 576, 1024), "1:1": (1080, 1080, 768, 768)}
ow, oh, gw, gh = SIZES[CONFIG["ASPECT"]]
CONFIG.update(OUT_W=int(ow*CONFIG["OUTPUT_SCALE"])//2*2, OUT_H=int(oh*CONFIG["OUTPUT_SCALE"])//2*2,
              GEN_W=gw, GEN_H=gh)
BASE = Path("/kaggle/working")
SCRATCH = Path("/tmp/kaggle-videogenerator-raw-v31")
if not Path("/kaggle").exists():
    raise RuntimeError("Этот notebook запускается в Kaggle. Создайте Notebook → Import .ipynb → GPU + Internet On.")
BASE.mkdir(parents=True, exist_ok=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update(TOKENIZERS_PARALLELISM="false", HF_HOME=str(SCRATCH/"hf"),
                  HF_HUB_CACHE=str(SCRATCH/"hf"/"hub"), HF_HUB_DOWNLOAD_TIMEOUT="120",
                  HF_HUB_ETAG_TIMEOUT="30", HF_HUB_DISABLE_TELEMETRY="1")
os.environ.update(USE_TF="0",USE_FLAX="0")
if CONFIG["OFFLINE"]:
    os.environ["HF_HUB_OFFLINE"] = "1"
try:
    from kaggle_secrets import UserSecretsClient
    if not os.environ.get("HF_TOKEN"):
        os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:
    pass  # публичные модели не требуют ключа
reference_hashes = {}
for ref in CONFIG["IMAGE_REFERENCES"]:
    p = Path(ref)
    if not p.is_file(): raise FileNotFoundError(p)
    reference_hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
identity = {k:v for k,v in CONFIG.items() if k not in {"QUICK_TEST", "TEST_SCENES", "RESUME_FROM", "OFFLINE", "GPU_INDEX", "MIN_FREE_SCRATCH_GB", "EXPORT_PREVIEW"}}
RUN_ID = hashlib.sha256(json.dumps({"config":identity,"story":STORY_TEXT,"revisions":REVISIONS,
                                    "pins":PINS,"references":reference_hashes,"schema":3},sort_keys=True).encode()).hexdigest()[:16]
RUN = BASE / f"run-{RUN_ID}"
RUN.mkdir(exist_ok=True)
for folder in ("audio", "images", "clips", "logs", "scripts"):
    (RUN/folder).mkdir(exist_ok=True)
print(f"{'TEST: '+str(CONFIG['TEST_SCENES'])+' scenes' if CONFIG['QUICK_TEST'] else 'FULL STORY'} | RAW MP4 | {CONFIG['IMAGE_ENGINE']} / {CONFIG['TTS_ENGINE']} | {CONFIG['OUT_W']}x{CONFIG['OUT_H']}")
print("Результаты:", RUN)
