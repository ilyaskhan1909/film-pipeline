"""Derive an ink dependency lock from the preserved installed full-film lock.

Writes only a new tools/locks snapshot, never the existing checkpoint lockfiles.
All tarball URLs/integrities and resolved package versions are preserved.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'outputs/local-production-v6/edit/remotion/package-lock.json'
    target = ROOT / 'tools/locks/ink-package-lock.json'
    package = json.loads((ROOT / 'outputs/graphic-novel-v8/edit/remotion/package.json').read_text())
    lock = json.loads(source.read_text())
    lock['name'] = package['name']
    lock['packages']['']['name'] = package['name']
    lock['packages']['']['dependencies'] = package['dependencies']
    for name, version in package['dependencies'].items():
        if lock['packages']['node_modules/' + name]['version'] != version:
            raise RuntimeError('Dependency does not match the preserved lock: ' + name)
    content = json.dumps(lock, indent=2) + '\n'
    for target in (target, ROOT / 'outputs/graphic-novel-v8/edit/remotion/package-lock.json'):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_text() != content:
                raise FileExistsError('Different existing lock preserved')
        else:
            target.write_text(content, encoding='utf-8')
        print(target)


if __name__ == '__main__':
    main()
