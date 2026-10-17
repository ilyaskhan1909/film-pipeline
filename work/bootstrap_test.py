import io, json, tarfile, urllib.request
from pathlib import Path

root=Path(__file__).resolve().parent
target=root/'npm'
target.mkdir(exist_ok=True)
if not (target/'package/bin/npm-cli.js').exists():
    with urllib.request.urlopen('https://registry.npmjs.org/npm/latest',timeout=30) as r:
        metadata=json.load(r)
    with urllib.request.urlopen(metadata['dist']['tarball'],timeout=60) as r:
        data=r.read()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t:
        t.extractall(target,filter='data')
    print('npm',metadata['version'])
