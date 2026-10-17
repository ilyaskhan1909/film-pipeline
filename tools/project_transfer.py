"""Source allowlist, secret checks and hash-verified, no-overwrite asset transfer."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ('production-v4', 'local-production-v6', 'style-lab-v7',
        'graphic-novel-v8', 'video-roundtrip', 'animation-pilot', 'a14b-dual')
EDITS = tuple(f'outputs/{name}/edit/remotion' for name in
              ('first-film', 'local-production-v6', 'graphic-novel-v8'))
PAYLOAD_ROOTS = (
    'outputs/graphic-novel-v8', 'outputs/style-lab-v7',
    'outputs/local-production-v6', 'outputs/first-film/curated',
    'outputs/first-film/edit/remotion/public',
    'outputs/first-film/The_Last_Firework_1080p.mp4',
    'outputs/first-film/edit/audio-stems',
    'outputs/animation-pilot/checkpoint-sha256.json',
    'local-comfy/data/input', 'work/ffmpeg-full',
)
SKIP_DIRS = {'.git', 'node_modules', 'node_modules-partial', '__pycache__',
             '.cache', '.remotion', 'cache', 'logs', '.venv', 'out'}
TEXT_SUFFIXES = {'.py', '.ps1', '.cjs', '.mjs', '.ts', '.tsx', '.json',
                 '.ipynb', '.txt', '.md', '.yaml', '.yml', '.toml'}
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}'
                    r'|hf_[A-Za-z0-9]{25,}|sk-(?:proj-)?[A-Za-z0-9_-]{25,}'
                    r'|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)),
            *(f'LPT{i}' for i in range(1, 10))}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def linked(path):
    data = path.lstat()
    return path.is_symlink() or bool(getattr(data, 'st_file_attributes', 0) & 0x400)


def walk(path):
    if not path.exists():
        return
    if linked(path):
        return
    if path.is_file():
        yield path
        return
    for base, dirs, files in os.walk(path, followlinks=False):
        base = Path(base)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and
                         not d.startswith('.venv') and not linked(base / d))
        for name in sorted(files):
            file = base / name
            if not linked(file):
                yield file


def sources(root=ROOT):
    paths = {root / name for name in ('.gitignore', '.gitattributes', 'README.md',
                                     'AGENTS.md', 'requirements-local.txt')}
    for folder in ('tools', 'docs'):
        paths.update(walk(root / folder))
    paths.update((root / 'work').glob('*.py'))
    for folder in WORK:
        paths.update(p for p in (root / 'work' / folder).glob('*')
                     if p.is_file() and p.suffix in ('.py', '.cjs', '.txt'))
    paths.update(p for p in (root / 'local-comfy').glob('*') if p.is_file() and
                 (p.suffix in ('.py', '.ps1') or p.name in
                  ('Dockerfile', '.dockerignore', 'compose.yaml', 'README.txt')))
    paths.update(walk(root / 'local-comfy/workflows'))
    for folder in EDITS:
        paths.update(root / folder / name for name in
                     ('package.json', 'package-lock.json', 'tsconfig.json', 'remotion.config.ts')
                     if (root / folder / name).is_file())
        paths.update(walk(root / folder / 'src'))
        paths.update(walk(root / folder / 'scripts'))
    for name in ('outputs/video-roundtrip/videogenerator-v5-kaggle-video-only.ipynb',
                 'outputs/local-production-v6/videogenerator-v6-kaggle-video-only.ipynb'):
        if (root / name).is_file():
            paths.add(root / name)
    return sorted(p for p in paths if p.is_file() and not linked(p))


def audit(paths, root=ROOT):
    issues = []
    for path in paths:
        name = path.relative_to(root).as_posix()
        if any(part.lower() in {'.env', 'kaggle.json', 'credentials.json'} for part in path.parts):
            issues.append(f'{name}: forbidden credential file')
        if path.stat().st_size > 2 * 1024**2:
            issues.append(f'{name}: oversized source file')
        if path.suffix in TEXT_SUFFIXES or path.name in ('Dockerfile', '.gitignore', '.gitattributes'):
            text = path.read_text(encoding='utf-8-sig')
            for number, line in enumerate(text.splitlines(), 1):
                if SECRET.search(line):
                    issues.append(f'{name}:{number}: possible credential (value withheld)')
            if path.suffix == '.ipynb':
                book = json.loads(text)
                if any(c.get('outputs') for c in book['cells']):
                    issues.append(f'{name}: notebook outputs must not enter Git')
    if issues:
        raise RuntimeError('\n'.join(issues))
    return {'source_files': len(paths), 'bytes': sum(p.stat().st_size for p in paths),
            'secret_patterns_checked': True, 'note': 'Pattern checks are not a security guarantee.'}


def payload_paths(root=ROOT, models=False):
    if models:
        lock = json.loads((root / 'outputs/graphic-novel-v8/model-lock.json').read_text())
        paths = []
        for item in lock:
            path = root / 'local-comfy/data/models' / item['file']
            if not path.is_file() or path.stat().st_size != item['size'] or digest(path) != item['sha256']:
                raise RuntimeError('Pinned model missing or different: ' + item['file'])
            paths.append(path)
        return paths
    code = set(sources(root))
    paths = {p for prefix in PAYLOAD_ROOTS for p in walk(root / prefix)
             if p not in code and p.suffix.lower() not in ('.zip', '.pyc', '.partial')}
    forbidden = {'.env', 'kaggle.json', 'credentials.json'}
    if any(p.name.lower() in forbidden or p.name.startswith('.env') for p in paths):
        raise RuntimeError('Credential-like file found in assets; not packed.')
    for path in paths:
        if path.suffix in TEXT_SUFFIXES and path.stat().st_size < 2 * 1024**2:
            text = path.read_text(encoding='utf-8-sig')
            if SECRET.search(text):
                raise RuntimeError('Possible secret in payload (value withheld): ' + str(path.relative_to(root)))
    return sorted(paths)


def pack(root=ROOT, models=False, destination=None):
    files = payload_paths(root, models)
    if not files:
        raise RuntimeError('No payload files. Run on the original machine after restoring assets.')
    destination = destination or root / 'transfers' / ('film-models.zip' if models else 'film-assets.zip')
    destination = Path(destination)
    partial = destination.with_suffix('.zip.partial')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or partial.exists():
        raise FileExistsError('Existing archive/partial preserved: ' + str(destination))
    total = sum(p.stat().st_size for p in files)
    if shutil.disk_usage(destination.parent).free < total + 1024**3:
        raise RuntimeError('Not enough space for archive plus 1 GiB reserve.')
    manifest = {'format': 'film-transfer-v1', 'kind': 'models' if models else 'assets', 'files': []}
    with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1,
                         allowZip64=True) as archive:
        for number, path in enumerate(files, 1):
            before = path.stat()
            h = hashlib.sha256()
            name = path.relative_to(root).as_posix()
            with path.open('rb') as source, archive.open(name, 'w', force_zip64=True) as output:
                for chunk in iter(lambda: source.read(8 * 1024**2), b''):
                    h.update(chunk)
                    output.write(chunk)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError('Source changed while packing: ' + name)
            manifest['files'].append({'file': name, 'size': before.st_size, 'sha256': h.hexdigest()})
            if number % 100 == 0:
                print(f'PACK {number}/{len(files)}', flush=True)
        archive.writestr('TRANSFER-MANIFEST.json', json.dumps(manifest, indent=2))
    partial.rename(destination)
    checksum = digest(destination)
    destination.with_suffix('.zip.sha256').write_text(f'{checksum}  {destination.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(destination), 'files': len(files), 'source_bytes': total,
                      'archive_bytes': destination.stat().st_size, 'sha256': checksum}, indent=2))
    return manifest


def safe_target(root, name):
    pure = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or pure.is_absolute() or
            name != pure.as_posix() or any(part in ('.', '..') or part.endswith((' ', '.')) or
            part.split('.')[0].upper() in RESERVED for part in pure.parts)):
        raise ValueError('Unsafe archive path')
    target = root.joinpath(*pure.parts)
    current = target
    while current != root:
        if os.path.lexists(current) and linked(current):
            raise ValueError('Symlink/junction destination rejected')
        current = current.parent
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Archive path escapes target')
    return target


def allowed(name, kind):
    if any(part.lower() in {'.git', '.env', 'kaggle.json', 'credentials.json'} or
           part.startswith('.env.') for part in PurePosixPath(name).parts):
        return False
    prefixes = ('local-comfy/data/models',) if kind == 'models' else PAYLOAD_ROOTS
    return any(name == p or name.startswith(p + '/') for p in prefixes)


def check_archive(archive, root):
    infos = archive.infolist()
    names = [i.filename for i in infos]
    if len(names) != len(set(n.casefold() for n in names)) or len(infos) > 20000:
        raise ValueError('Duplicate archive names or unreasonable member count')
    manifest_info = archive.getinfo('TRANSFER-MANIFEST.json')
    if manifest_info.file_size > 16 * 1024**2:
        raise ValueError('Oversized manifest')
    manifest = json.loads(archive.read(manifest_info))
    if manifest.get('format') != 'film-transfer-v1' or manifest.get('kind') not in ('assets', 'models'):
        raise ValueError('Unsupported transfer format')
    entries = manifest['files']
    entry_names = [e['file'] for e in entries]
    if len(entry_names) != len(set(entry_names)) or set(entry_names) != set(names) - {'TRANSFER-MANIFEST.json'}:
        raise ValueError('Manifest/member mismatch')
    if sum(i.file_size for i in infos) > 200 * 1024**3:
        raise ValueError('Archive exceeds 200 GiB safety limit')
    for entry in entries:
        name = entry['file']
        safe_target(root, name)
        info = archive.getinfo(name)
        mode = info.external_attr >> 16
        if (not allowed(name, manifest['kind']) or stat.S_ISLNK(mode) or info.is_dir() or
                entry['size'] != info.file_size or not re.fullmatch('[0-9a-f]{64}', entry['sha256'])):
            raise ValueError('Invalid payload entry: ' + name)
        h = hashlib.sha256()
        with archive.open(name) as source:
            for chunk in iter(lambda: source.read(8 * 1024**2), b''):
                h.update(chunk)
        if h.hexdigest() != entry['sha256']:
            raise ValueError('Archive SHA256 mismatch: ' + name)
    return manifest


def restore(path, root=ROOT, verify_only=False):
    root = root.resolve()
    with zipfile.ZipFile(path) as archive:
        manifest = check_archive(archive, root)
        pending = []
        for entry in manifest['files']:
            target = safe_target(root, entry['file'])
            if target.exists():
                if not target.is_file() or target.stat().st_size != entry['size'] or digest(target) != entry['sha256']:
                    raise FileExistsError('Different existing file preserved: ' + entry['file'])
            elif verify_only:
                raise FileNotFoundError('Not restored: ' + entry['file'])
            else:
                pending.append((entry, target))
        needed = sum(e['size'] for e, _ in pending)
        if shutil.disk_usage(root).free < needed + 512 * 1024**2:
            raise RuntimeError('Insufficient free space for restore')
        for entry, target in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.transfer-partial')
            if temporary.exists():
                raise FileExistsError('Existing partial preserved: ' + str(temporary))
            with archive.open(entry['file']) as source, temporary.open('xb') as output:
                shutil.copyfileobj(source, output, 8 * 1024**2)
            if digest(temporary) != entry['sha256']:
                raise ValueError('Restored SHA256 mismatch')
            # No existing differing file was overwritten during preflight or installation.
            try:
                if os.name == 'nt':
                    # Unlike POSIX rename(), Windows rename refuses an existing target.
                    os.rename(temporary, target)
                else:
                    os.link(temporary, target)
            except FileExistsError:
                raise FileExistsError('Destination appeared during restore; preserved: ' + str(target))
            if temporary.exists():
                temporary.unlink()
        print(f'VERIFIED {len(manifest["files"])} payload files; restored {len(pending)}.', flush=True)
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('audit', 'stage', 'pack', 'restore', 'verify'))
    parser.add_argument('archive', nargs='?', type=Path)
    parser.add_argument('--models', action='store_true')
    args = parser.parse_args()
    if args.action in ('audit', 'stage'):
        files = sources()
        print(json.dumps(audit(files), indent=2))
        if args.action == 'stage':
            names = '\0'.join(p.relative_to(ROOT).as_posix() for p in files) + '\0'
            subprocess.run(['git', 'add', '--pathspec-from-file=-', '--pathspec-file-nul'],
                           cwd=ROOT, input=names.encode(), check=True)
    elif args.action == 'pack':
        pack(models=args.models, destination=args.archive)
    else:
        if not args.archive:
            parser.error('Archive path required')
        restore(args.archive, verify_only=args.action == 'verify')


if __name__ == '__main__':
    main()
