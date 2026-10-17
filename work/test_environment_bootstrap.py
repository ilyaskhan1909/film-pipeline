"""Regression: install into two real pip-less venvs while ensurepip is unavailable."""
import ast, hashlib, importlib.metadata as metadata, json, os, subprocess, sys, time, venv, zipfile
from pathlib import Path
from packaging.version import Version
from core import atomic_json, run_logged

HERE=Path(__file__).resolve().parent
TEST_ROOT=HERE/'bootstrap-validation'
TEST_ROOT.mkdir(exist_ok=True)
RUN=TEST_ROOT/'run'; (RUN/'logs').mkdir(parents=True,exist_ok=True)
SCRATCH=TEST_ROOT/'scratch'; SCRATCH.mkdir(exist_ok=True)
protected={}
for name in ('torch','torchvision','torchaudio','numpy','Pillow'):
    try: protected[name]=metadata.version(name)
    except metadata.PackageNotFoundError: pass
package='codex_kaggle_bootstrap_probe'
try: metadata.version(package)
except metadata.PackageNotFoundError: pass
else: raise AssertionError('Test package already exists in base environment')

def wheel(version):
    dist=f'{package}-{version}.dist-info'
    path=TEST_ROOT/f'{package}-{version}-py3-none-any.whl'
    data={f'{package}/__init__.py':f'__version__ = {version!r}\n',
        f'{dist}/METADATA':f'Metadata-Version: 2.1\nName: {package}\nVersion: {version}\n',
        f'{dist}/WHEEL':'Wheel-Version: 1.0\nGenerator: bootstrap-regression\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
    data[f'{dist}/RECORD']=''.join(f'{p},,\n' for p in data)+f'{dist}/RECORD,,\n'
    with zipfile.ZipFile(path,'w') as z:
        for name,content in data.items(): z.writestr(name,content)
    return str(path)

text=(HERE/'setup_cell.py').read_text(encoding='utf-8'); tree=ast.parse(text)
function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install_environment')
scope={**globals(),'CONFIG':{'OFFLINE':False}}
exec(compile(ast.Module(body=[function],type_ignores=[]),'notebook-install-environment','exec'),scope)
original=venv.EnvBuilder._setup_pip
def unavailable(*args,**kwargs):
    raise RuntimeError('ensurepip intentionally unavailable for regression test')
venv.EnvBuilder._setup_pip=unavailable
try:
    interpreters=[]
    for name,version in (('image','1.0.0'),('tts','2.0.0')):
        packages=[wheel(version)]; python=scope['install_environment'](name,packages)
        output=json.loads(subprocess.check_output([python,'-c',
            f'import json,sys,{package} as p; print(json.dumps({{"prefix":sys.prefix,"base":sys.base_prefix,"module":p.__file__,"version":p.__version__}}))'],text=True))
        assert output['version']==version
        assert Path(output['module']).resolve().is_relative_to(Path(output['prefix']).resolve())
        assert output['prefix']!=output['base']
        marker=Path(output['prefix'])/'installed.json'
        assert json.loads(marker.read_text())['bootstrap']=='parent-pip--python-v1'
        # A successful marker can be reused even with internet explicitly unavailable.
        scope['CONFIG']['OFFLINE']=True
        assert scope['install_environment'](name,packages)==python
        scope['CONFIG']['OFFLINE']=False
        interpreters.append(output)
finally:
    venv.EnvBuilder._setup_pip=original
for name,version in protected.items(): assert metadata.version(name)==version
try: metadata.version(package)
except metadata.PackageNotFoundError: pass
else: raise AssertionError('Probe leaked into base environment')
report={'status':'passed','ensurepip':'disabled by a raising stub during actual venv creation',
    'pip_source':'parent interpreter, --python target','network':'not required; local test wheels',
    'isolated_stages':interpreters,'base_packages_unchanged':protected,'offline_marker_reuse':'passed',
    'limitations':'Windows/Python 3.11 regression, not actual Kaggle Python 3.13 execution'}
atomic_json(HERE/'bootstrap_validation.json',report)
print(json.dumps(report,indent=2,ensure_ascii=False))
