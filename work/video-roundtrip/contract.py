"""Portable image -> video -> local-edit contract. No model imports or credentials."""
import hashlib
import json
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            hasher.update(block)
    return hasher.hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def safe_id(value):
    reserved = {'con', 'prn', 'aux', 'nul'} | {f'com{i}' for i in range(1, 10)} | {f'lpt{i}' for i in range(1, 10)}
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,63}', value) or value in reserved:
        raise ValueError('Unsafe or invalid identifier: ' + repr(value))
    return value


def safe_relative(value):
    path = PurePosixPath(value)
    if (not isinstance(value, str) or '\\' in value or ':' in value or path.is_absolute()
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('Unsafe archive path: ' + repr(value))
    return path


def validate_inputs(manifest):
    if manifest.get('schema') != 'video-inputs/v1':
        raise ValueError('Expected video-inputs/v1 manifest.')
    expected = 'video-' + identity({k: v for k, v in manifest.items() if k != 'handoff_id'})[:16]
    if manifest.get('handoff_id') != expected:
        raise ValueError('Input identity does not match content.')
    if manifest['policy']['kaggle_scope'] != 'silent_image_to_video_only':
        raise ValueError('Kaggle stage must remain video only.')
    assets, requests = manifest['assets'], manifest['requests']
    if not assets or not requests:
        raise ValueError('Empty generation batch.')
    if len({a['id'] for a in assets}) != len(assets) or len({r['id'] for r in requests}) != len(requests):
        raise ValueError('Duplicate asset/request identifiers.')
    known = {a['id'] for a in assets}
    paths = set()
    for asset in assets:
        safe_id(asset['id'])
        path = safe_relative(asset['file'])
        if path.parts[0] != 'frames' or path.suffix != '.png' or asset['file'] in paths:
            raise ValueError('Expected unique PNG keyframes in frames/.')
        paths.add(asset['file'])
        if not re.fullmatch('[0-9a-f]{64}', asset['sha256']):
            raise ValueError('Invalid source checksum.')
    for request in requests:
        safe_id(request['id'])
        if request['asset_id'] not in known or not request['prompt'].strip():
            raise ValueError('Missing source asset or motion prompt.')
        c = request['config']
        if c['WIDTH'] % 16 or c['HEIGHT'] % 16 or c['WIDTH'] * 9 != c['HEIGHT'] * 16:
            raise ValueError('Use native 16:9 dimensions divisible by 16.')
        if not 256 <= c['WIDTH'] <= 1280 or c['FRAMES'] < 9 or (c['FRAMES'] - 1) % 4:
            raise ValueError('Invalid native size or frame count.')
        if c['FPS'] != 24 or not 20 <= c['STEPS'] <= 80 or not 1 < c['GUIDANCE'] <= 10:
            raise ValueError('Invalid generation settings.')
        if not isinstance(c['SEED'], int) or c['SEED'] < 0:
            raise ValueError('Use a nonnegative integer seed.')
    return manifest


def check_zip(bundle):
    names = set()
    total = 0
    for info in bundle.infolist():
        safe_relative(info.filename.rstrip('/') if info.is_dir() else info.filename)
        if info.filename in names or stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError('Duplicate archive members or symbolic links are forbidden.')
        names.add(info.filename)
        total += info.file_size
    if total > 8 * 2**30 or len(names) > 5000:
        raise ValueError('Archive exceeds the local handoff safety limits.')


def read_json_member(bundle, name):
    if bundle.getinfo(name).file_size > 4 * 2**20:
        raise ValueError('Oversized JSON metadata.')
    return json.loads(bundle.read(name))


def load_inputs(input_root, expected_id, destination):
    """Accept either Kaggle-extracted files or an attached ZIP; bind all frames to SHA256."""
    input_root, destination = Path(input_root), Path(destination)
    validate = lambda m: validate_inputs(m) if m.get('handoff_id') == expected_id else None
    for path in input_root.rglob('video-inputs.json'):
        if path.stat().st_size > 4 * 2**20:
            continue
        manifest = validate(json.loads(path.read_text(encoding='utf-8')))
        if manifest is None:
            continue
        for asset in manifest['assets']:
            source = path.parent / asset['file']
            if not source.is_file() or digest(source) != asset['sha256']:
                raise ValueError('Missing/changed keyframe: ' + asset['id'])
        for asset in manifest['assets']:
            target = destination / asset['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or digest(target) != asset['sha256']:
                shutil.copy2(path.parent / asset['file'], target)
        save_json(destination / 'video-inputs.json', manifest)
        return manifest
    for path in input_root.rglob('*inputs.zip'):
        with zipfile.ZipFile(path) as bundle:
            check_zip(bundle)
            if 'video-inputs.json' not in bundle.namelist():
                continue
            manifest = validate(read_json_member(bundle, 'video-inputs.json'))
            if manifest is None:
                continue
            frames = []
            for asset in manifest['assets']:
                if bundle.getinfo(asset['file']).file_size > 64 * 2**20:
                    raise ValueError('Oversized image asset.')
                data = bundle.read(asset['file'])
                if hashlib.sha256(data).hexdigest() != asset['sha256']:
                    raise ValueError('Source keyframe checksum mismatch.')
                frames.append((asset['file'], data))
            for filename, data in frames:
                target = destination / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            save_json(destination / 'video-inputs.json', manifest)
            return manifest
    raise FileNotFoundError('Attach the prepared video-inputs bundle: ' + expected_id)


def validate_return_manifest(manifest, inputs, fingerprint=None):
    validate_inputs(inputs)
    if (manifest.get('schema') != 'video-results/v1' or
            manifest.get('handoff_id') != inputs['handoff_id']):
        raise ValueError('Returned clips do not belong to these inputs.')
    if fingerprint is not None and manifest.get('job_fingerprint') != fingerprint:
        raise ValueError('Worker/model fingerprint changed; old results cannot be resumed.')
    known = {r['id']: r for r in inputs['requests']}
    assets = {a['id']: a for a in inputs['assets']}
    ids = set()
    for clip in manifest['clips']:
        ident = safe_id(clip['id'])
        if ident in ids or ident not in known:
            raise ValueError('Unknown/duplicate returned clip.')
        ids.add(ident)
        request = known[ident]
        if (clip['asset_id'] != request['asset_id'] or clip['config'] != request['config']
                or clip['source_sha256'] != assets[request['asset_id']]['sha256']):
            raise ValueError('Returned clip source/settings differ from the request.')
        if clip['file'] != f'clips/{ident}.mp4' or clip['report'] != f'reports/{ident}.json':
            raise ValueError('Unexpected returned media path.')
        if not clip['technical_pass'] or not re.fullmatch('[0-9a-f]{64}', clip['sha256']):
            raise ValueError('Returned clip did not pass technical checks.')
    return manifest


def make_archive(run, target):
    run = Path(run)
    files = {p.relative_to(run).as_posix(): digest(p) for p in sorted(run.rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and '.partial' not in p.name
        and p.name != 'checksums.json' and not any(part in ('embeddings', 'frames', 'source') for part in p.relative_to(run).parts)}
    save_json(run / 'checksums.json', files)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as bundle:
        for filename in files:
            bundle.write(run / filename, filename)
        bundle.write(run / 'checksums.json', 'checksums.json')
    with zipfile.ZipFile(target) as bundle:
        if bundle.testzip():
            raise ValueError('Result archive CRC check failed.')
    return Path(target)
