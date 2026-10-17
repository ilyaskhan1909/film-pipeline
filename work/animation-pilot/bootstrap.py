"""Kaggle Python 3.13-compatible, pip-less isolated environment bootstrap."""
import importlib.metadata as metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path

from common import atomic_json, fingerprint


def bootstrap(run, scratch, packages):
    import torch
    if platform.system() != 'Linux' or not torch.cuda.is_available():
        raise RuntimeError('Use Kaggle Linux with GPU and Internet On.')
    if sys.version_info < (3, 10):
        raise RuntimeError('Python >=3.10 is required; Python 3.13 is supported.')
    if not all(shutil.which(tool) for tool in ('ffmpeg', 'ffprobe')):
        raise RuntimeError('Kaggle image must include ffmpeg and ffprobe.')
    if shutil.disk_usage(scratch).free < 35*2**30:
        raise RuntimeError('At least 35 GiB free scratch space is needed for model weights.')
    protected = {}
    for name in ('torch','torchvision','torchaudio','numpy','Pillow'):
        try:
            protected[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    signature = {'python': sys.version, 'packages': packages, 'protected': protected,
                 'bootstrap': 'parent-pip--python-no-ensurepip'}
    environment = scratch/'venvs'/fingerprint(signature)[:16]
    python = environment/'bin/python'
    marker = environment/'installed.json'
    if not marker.exists() or json.loads(marker.read_text()) != signature:
        venv.EnvBuilder(with_pip=False, system_site_packages=True).create(environment)
        identity = json.loads(subprocess.check_output([str(python), '-c',
            'import sys,json;print(json.dumps([sys.prefix,sys.base_prefix]))'], text=True))
        if Path(identity[0]).resolve() != environment.resolve() or identity[0] == identity[1]:
            raise RuntimeError('Virtual environment isolation failed; installation cancelled.')
        constraints = environment/'protected.txt'
        constraints.write_text('\n'.join(f'{name}=={version}' for name, version in protected.items())+'\n')
        command = [sys.executable, '-m', 'pip', '--python', str(python), 'install',
            '--disable-pip-version-check', '--prefer-binary', '-c', str(constraints), *packages]
        log = run/'logs/install.log'
        with log.open('w') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
        if result.returncode:
            raise RuntimeError('Isolated package installation failed: '+log.read_text()[-2500:])
        atomic_json(marker, signature)
    if any(metadata.version(name) != version for name,version in protected.items()):
        raise RuntimeError('A protected parent package changed; pilot stopped.')
    command = [str(python), '-c',
        'import torch,bitsandbytes as b; '
        'from diffusers import WanImageToVideoPipeline,WanTransformer3DModel,AutoencoderKLWan; '
        'from transformers import UMT5EncoderModel,AutoModelForDepthEstimation; '
        'x=torch.randn(64,64,device="cuda:0"); '
        'q,s=b.functional.quantize_4bit(x,quant_type="nf4"); '
        'assert torch.isfinite(b.functional.dequantize_4bit(q,s)).all().item(); '
        'print("NF4 import/kernel smoke passed")']
    probe = subprocess.run(command, env=dict(os.environ, CUDA_VISIBLE_DEVICES='0'),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    (run/'logs/kernel-probe.log').write_text(probe.stdout, encoding='utf-8')
    if probe.returncode:
        raise RuntimeError('Import/NF4 probe failed before model download: '+probe.stdout[-2500:])
    info = {'python': sys.version, 'torch': torch.__version__, 'cuda': torch.version.cuda,
        'gpu_count': torch.cuda.device_count(), 'gpu': [
            {'name': torch.cuda.get_device_name(index),
             'capability': list(torch.cuda.get_device_capability(index)),
             'vram_gib': round(torch.cuda.get_device_properties(index).total_memory/2**30, 2)}
            for index in range(torch.cuda.device_count())], 'protected': protected,
        'pins': packages, 'nf4_kernel_probe': 'passed', 'system_packages_replaced': False}
    atomic_json(run/'environment.json', info)
    print('GPU:', info['gpu'], '| separate experimental environment ready', flush=True)
    return str(python), info['gpu_count']
