"""Task-local vision QA dependencies, without replacing the user's Torch stack."""
import importlib.metadata as metadata
import os
import subprocess
import sys
import venv
from pathlib import Path

folder = Path(__file__).resolve().parent
environment = folder/'.venv-vision-qa'
venv.EnvBuilder(with_pip=False,system_site_packages=True).create(environment)
python = environment/'Scripts/python.exe'
protected = {name:metadata.version(name) for name in ('torch','torchvision','numpy','Pillow')}
constraints = folder/'vision-protected.txt'
constraints.write_text('\n'.join(f'{k}=={v}' for k,v in protected.items())+'\n',encoding='utf-8')
env = dict(os.environ,PIP_CACHE_DIR=str(folder/'pip-cache'),PIP_DISABLE_PIP_VERSION_CHECK='1')
packages = ['transformers==5.18.0','accelerate==1.15.0','huggingface-hub==1.33.0',
            'safetensors==0.8.0','librosa==0.11.0','soundfile==0.14.0']
with (folder/'vision-install.log').open('w',encoding='utf-8') as log:
    subprocess.run([sys.executable,'-m','pip','--python',str(python),'install',
                    '-c',str(constraints)]+packages,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
print({'environment':str(environment),'protected':protected},flush=True)
