# 2. Проверка среды и изолированные зависимости. Системные torch/numpy/Pillow сохраняются.
import importlib.metadata as metadata
import shutil, subprocess, sys, urllib.request, venv, time
import torch
from packaging.version import Version

if platform.system()!="Linux": raise RuntimeError("Kaggle использует Linux.")
if sys.version_info[:2] < (3,10):
    raise RuntimeError('Требуется Python >=3.10. Python 3.13 не блокируется; NumPy 1.26 не устанавливается.')
if not torch.cuda.is_available(): raise RuntimeError("Session options → Accelerator → GPU. Затем Run All.")
if Version(torch.__version__.split('+')[0])<Version('2.6'):
    raise RuntimeError('Требуется Kaggle Environment с PyTorch >=2.6; системный PyTorch автоматически не заменяется.')
device=CONFIG["GPU_INDEX"]
if device>=torch.cuda.device_count(): raise ValueError("GPU_INDEX вне диапазона.")
torch.cuda.set_device(device)
try:
    x=torch.ones((8,8),device=f"cuda:{device}"); (x@x).sum().item(); del x
except Exception as exc:
    raise RuntimeError("Текущий Kaggle-образ не поддерживает выбранную GPU. Выберите другую GPU/Environment.") from exc
gpu={"name":torch.cuda.get_device_name(device),"capability":list(torch.cuda.get_device_capability(device)),
     "vram_gib":round(torch.cuda.get_device_properties(device).total_memory/2**30,2),"torch":torch.__version__,"cuda":torch.version.cuda}
print("GPU:",gpu,"| доступно GPU:",torch.cuda.device_count())
torch.cuda.empty_cache()
missing=[tool for tool in ("ffmpeg","ffprobe") if not shutil.which(tool)]
if missing: raise RuntimeError("В образе отсутствует "+", ".join(missing)+". Выберите актуальный Kaggle Python image.")
if shutil.disk_usage(SCRATCH).free/2**30 < CONFIG["MIN_FREE_SCRATCH_GB"]:
    raise RuntimeError("Недостаточно временного диска для весов. Освободите место или подключите MODEL_PATHS.")
if not CONFIG["OFFLINE"]:
    for url in ("https://huggingface.co", "https://pypi.org/simple/"):
        try:
            with urllib.request.urlopen(url,timeout=25) as response: assert response.status==200
        except Exception as exc: raise RuntimeError("Internet → On; сеть недоступна: "+url) from exc
protected={}
for name in ("torch","torchvision","torchaudio","numpy","Pillow"):
    try: protected[name]=metadata.version(name)
    except metadata.PackageNotFoundError: pass
constraints=SCRATCH/"protected.txt"
constraints.write_text("\n".join(f"{k}=={v}" for k,v in protected.items())+"\n",encoding="utf-8")

def install_environment(name, packages):
    signature={"packages":packages,"protected":protected,"python":sys.version.split()[0],
               "bootstrap":"parent-pip--python-v1"}
    fingerprint=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()[:12]
    path=SCRATCH/"venvs"/f"{name}-{fingerprint}"
    python=path/("Scripts/python.exe" if os.name=="nt" else "bin/python")
    marker=path/"installed.json"
    if python.exists() and marker.exists() and json.loads(marker.read_text())==signature:
        return str(python)
    if CONFIG["OFFLINE"]: raise RuntimeError(f"OFFLINE: среда {name} не установлена в этой сессии.")
    # Kaggle's Python image can fail ensurepip. The parent pip can manage a pip-less venv.
    # https://pip.pypa.io/en/stable/topics/python-option/ (pip >=22.3)
    if Version(metadata.version("pip")) < Version("22.3"):
        raise RuntimeError("Для установки в отдельную среду требуется pip >=22.3 в Kaggle image.")
    venv.EnvBuilder(with_pip=False,system_site_packages=True).create(path)
    prefix=json.loads(subprocess.check_output([str(python),"-c",
        "import json,sys; print(json.dumps({'prefix':sys.prefix,'base':sys.base_prefix}))"],text=True))
    if Path(prefix["prefix"]).resolve()!=path.resolve() or prefix["prefix"]==prefix["base"]:
        raise RuntimeError("Изоляция среды не подтверждена; установка отменена для защиты системных пакетов.")
    env_constraints=path/"protected.txt"
    env_constraints.write_text("\n".join(f"{k}=={v}" for k,v in protected.items())+"\n",encoding="utf-8")
    command=[sys.executable,"-m","pip","--python",str(python),"install","--disable-pip-version-check","--prefer-binary",
             "--constraint",str(env_constraints),*packages]
    for attempt in range(3):
        try:
            run_logged(command,RUN/"logs"/f"install-{name}.log",timeout=1800)
            atomic_json(marker,signature); break
        except Exception:
            if attempt==2: raise
            time.sleep(3*(attempt+1))
    return str(python)

ENVS={"image":install_environment("image",PINS["image"]),
      "tts":install_environment(CONFIG["TTS_ENGINE"],PINS["tts" if CONFIG["TTS_ENGINE"]=="qwen" else "kokoro"])}
if CONFIG["ALIGN_WORDS"] or CONFIG["ASR_CHECK"]:
    ENVS["align"]=install_environment("align-native",PINS["align"])

# Check imports and a real NF4 kernel before downloading gigabytes of weights.
checks={"image":"from diffusers import DiffusionPipeline, AutoModel; from transformers import AutoModelForImageTextToText; "
        "import torch,bitsandbytes as b; x=torch.randn(32,32,device='cuda:0'); q,s=b.functional.quantize_4bit(x,quant_type='nf4'); "
        "assert torch.isfinite(b.functional.dequantize_4bit(q,s)).all().item()",
        "tts":"from qwen_tts import Qwen3TTSModel" if CONFIG["TTS_ENGINE"]=="qwen" else "from kokoro import KPipeline",
        "align":"from transformers import AutoProcessor, AutoModelForTokenClassification, Qwen3ASRForConditionalGeneration, Qwen3ASRProcessor; "
                "assert hasattr(Qwen3ASRProcessor,'prepare_forced_aligner_inputs') and hasattr(Qwen3ASRProcessor,'decode_forced_alignment')"}
for name,code in checks.items():
    if name not in ENVS: continue
    run_logged([ENVS[name],"-c",code],RUN/"logs"/f"check-{name}.log",
               env=dict(os.environ,CUDA_VISIBLE_DEVICES=str(CONFIG["GPU_INDEX"])),timeout=180)

atomic_json(RUN/"environment.json",{"gpu":gpu,"system_packages":protected,"pins":PINS,"python":sys.version,"platform":platform.platform()})
print("Среды готовы. Рестарт ядра не требуется.")
