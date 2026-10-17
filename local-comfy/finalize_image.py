"""Drop an unused inherited developer CLI from our image, not from the host."""
import importlib.metadata as metadata
import json
import subprocess
import sys
from pathlib import Path

from packaging.requirements import Requirement

record_path = Path('/opt/image-build.json')
record = json.loads(record_path.read_text())
if sys.prefix == sys.base_prefix:
    raise RuntimeError('Finalization must run inside the ComfyUI venv.')
spin = metadata.distribution('spin')
location = Path(spin.locate_file('')).resolve()
if location != Path('/usr/local/lib/python3.12/dist-packages'):
    raise RuntimeError('Unexpected inherited build-tool location; refuse removal.')
for distribution in metadata.distributions():
    for requirement in distribution.requires or []:
        req = Requirement(requirement)
        if req.name.lower() == 'spin' and (req.marker is None or req.marker.evaluate()):
            raise RuntimeError('An installed runtime package depends on spin; refuse removal.')
removed = {'name':'spin', 'version':spin.version, 'role':'unused inherited developer build CLI'}
# Only our new image layer is modified. Torch/NumPy and the host are untouched.
subprocess.run([sys._base_executable,'-m','pip','uninstall',
                '--break-system-packages','-y','spin'],check=True)
subprocess.run([sys.executable,'-m','pip','check'],check=True)
if {name:metadata.version(name) for name in record['protected']} != record['protected']:
    raise RuntimeError('Protected CUDA/NumPy stack changed.')
names = {d.metadata['Name'] for d in metadata.distributions()}
record['packages'] = {name:metadata.version(name) for name in sorted(names)}
record['removed_inherited_build_tool'] = removed
record['pip_check'] = 'passed'
record_path.write_text(json.dumps(record,indent=2),encoding='utf-8')
