"""Two-T4, pip-less bootstrap; does not replace Kaggle's Torch/CUDA/NumPy."""
import importlib.metadata as metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import venv

from common import atomic_json, fingerprint


def bootstrap(run, scratch, packages):
    import torch
    if platform.system() != 'Linux' or torch.cuda.device_count() != 2:
        raise RuntimeError('Select Kaggle T4 x2 and Internet On. Exactly two GPUs are required.')
    if any(torch.cuda.get_device_capability(i) != (7, 5) for i in range(2)):
        raise RuntimeError('This controlled experiment is configured for two Tesla T4 cards.')
    if not all(shutil.which(tool) for tool in ('ffmpeg', 'ffprobe', 'nvidia-smi')):
        raise RuntimeError('ffmpeg, ffprobe and nvidia-smi are required.')
    free = shutil.disk_usage(scratch).free
    if free < 48 * 2**30:
        raise RuntimeError(f'Need 48 GiB free scratch; found {free / 2**30:.1f}. Full FP32 experts are NOT downloaded.')
    protected = {}
    for name in ('torch', 'torchvision', 'torchaudio', 'numpy', 'Pillow'):
        try:
            protected[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    signature = {'python': sys.version, 'packages': packages, 'protected': protected,
                 'bootstrap': 'pipless-parent-pip-v1'}
    environment = scratch / 'venvs' / fingerprint(signature)[:16]
    python = environment / 'bin/python'
    marker = environment / 'installed.json'
    if not marker.exists() or json.loads(marker.read_text()) != signature:
        venv.EnvBuilder(with_pip=False, system_site_packages=True).create(environment)
        prefixes = json.loads(subprocess.check_output([str(python), '-c',
            'import sys,json;print(json.dumps([sys.prefix,sys.base_prefix]))'], text=True))
        if prefixes[0] == prefixes[1] or environment.resolve() != __import__('pathlib').Path(prefixes[0]).resolve():
            raise RuntimeError('Environment isolation failed; installation cancelled.')
        constraints = environment / 'protected.txt'
        constraints.write_text('\n'.join(f'{k}=={v}' for k, v in protected.items()) + '\n')
        with (run / 'logs/install.log').open('w') as stream:
            result = subprocess.run([sys.executable, '-m', 'pip', '--python', str(python),
                'install', '--disable-pip-version-check', '--prefer-binary', '-c', str(constraints),
                *packages], stdout=stream, stderr=subprocess.STDOUT, timeout=1800)
        if result.returncode:
            raise RuntimeError('Isolated install failed: ' + (run / 'logs/install.log').read_text()[-3000:])
        atomic_json(marker, signature)
    if any(metadata.version(k) != v for k, v in protected.items()):
        raise RuntimeError('Protected parent package changed.')
    probe = subprocess.run([str(python), '-c',
        'import torch,gguf,bitsandbytes as b; '
        'from diffusers import GGUFQuantizationConfig,WanTransformer3DModel,WanImageToVideoPipeline; '
        'from accelerate import dispatch_model; '
        'assert torch.cuda.device_count()==2; '
        'x=torch.randn(64,64,device="cuda:0"); q,s=b.functional.quantize_4bit(x,quant_type="nf4"); '
        'assert torch.isfinite(b.functional.dequantize_4bit(q,s)).all().item(); '
        'print("Two-GPU imports and text-encoder kernel probe passed")'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=180)
    (run / 'logs/import-probe.log').write_text(probe.stdout, encoding='utf-8')
    if probe.returncode:
        raise RuntimeError(probe.stdout[-3000:])
    info = {'python': sys.version, 'torch': torch.__version__, 'cuda': torch.version.cuda,
        'scratch_free_gib': free / 2**30, 'protected': protected, 'pins': packages,
        'system_packages_replaced': False, 'gpu': [
            {'index': i, 'name': torch.cuda.get_device_name(i),
             'capability': list(torch.cuda.get_device_capability(i)),
             'vram_gib': torch.cuda.get_device_properties(i).total_memory / 2**30}
            for i in range(2)]}
    atomic_json(run / 'environment.json', info)
    print('TWO T4:', info['gpu'], flush=True)
    return str(python)
