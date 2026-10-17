"""Image build only. No modification of host Python, Torch or NVIDIA drivers."""
import importlib.metadata as metadata
import grp
import json
import os
import pwd
import re
import subprocess
import sys
import venv
from pathlib import Path


def run(*command):
    subprocess.run(command, check=True)


commit = os.environ['COMFY_COMMIT']
if not re.fullmatch('[0-9a-f]{40}', commit):
    raise ValueError('ComfyUI must be pinned to an exact official source revision.')
run('apt-get', 'update')
run('apt-get', 'install', '-y', '--no-install-recommends', 'git', 'ffmpeg',
    'libgl1', 'libglib2.0-0', 'libsndfile1', 'ca-certificates', 'python3-venv')
run('apt-get', 'clean')
folder = Path('/opt/ComfyUI')
folder.mkdir()
run('git', '-C', str(folder), 'init')
run('git', '-C', str(folder), 'remote', 'add', 'origin', 'https://github.com/Comfy-Org/ComfyUI.git')
run('git', '-C', str(folder), 'fetch', '--depth', '1', 'origin', commit)
run('git', '-C', str(folder), 'checkout', '--detach', 'FETCH_HEAD')
actual = subprocess.check_output(['git', '-C', str(folder), 'rev-parse', 'HEAD'], text=True).strip()
if actual != commit:
    raise ValueError('Official source revision mismatch.')
protected = {name: metadata.version(name) for name in ('torch', 'torchvision', 'torchaudio', 'numpy')}
constraints = Path('/opt/protected-stack.txt')
constraints.write_text('\n'.join(f'{k}=={v}' for k, v in protected.items()) + '\n')
# Reuse the official CUDA stack without changing Ubuntu's managed Python.
# Parent pip installs into a pip-less venv; this never calls ensurepip.
venv_path = Path('/opt/comfy-env')
venv.EnvBuilder(with_pip=False, system_site_packages=True).create(venv_path)
python = str(venv_path / 'bin' / 'python')
run(sys.executable, '-m', 'pip', '--python', python, 'install', '--no-cache-dir', '--prefer-binary',
    '-c', str(constraints), '-r', str(folder / 'requirements.txt'))
environment = json.loads(subprocess.check_output([python, '-c',
    "import importlib.metadata as m,json,sys,torch; "
    "print(json.dumps({'cuda':torch.version.cuda,'python':sys.version,"
    "'packages':{d.metadata['Name']:d.version for d in m.distributions()},"
    "'protected':{n:m.version(n) for n in ('torch','torchvision','torchaudio','numpy')}}))"
], text=True))
if environment['protected'] != protected:
    raise RuntimeError('Protected image Torch/NumPy stack changed.')
if not environment['cuda'] or not environment['cuda'].startswith('13.0'):
    raise RuntimeError('Unexpected image CUDA runtime.')
record = {'comfy_commit':commit, 'comfy_release':'v0.38.0', 'protected':protected,
          'cuda':environment['cuda'], 'python':environment['python'],
          'packages':environment['packages'], 'venv':str(venv_path),
          'custom_nodes_installed':False, 'paid_api_nodes_enabled':False}
Path('/opt/image-build.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
try:
    grp.getgrgid(1000)
except KeyError:
    run('groupadd', '--gid', '1000', 'comfy')
try:
    pwd.getpwuid(1000)
except KeyError:
    run('useradd', '--uid', '1000', '--gid', '1000', '--no-create-home', '--home-dir', '/data/cache/home', 'comfy')
