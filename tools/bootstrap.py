"""Portable, opt-in setup; no GPU jobs, dependency installs or servers in doctor."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = {'ink': ROOT / 'outputs/graphic-novel-v8/edit/remotion',
            'full': ROOT / 'outputs/local-production-v6/edit/remotion'}
MASTERS = {'ink': 'pilot-master-pcm24.wav', 'full': 'master.wav'}


def run(command, cwd=ROOT):
    print('RUN', ' '.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=cwd, check=True)


def executable(name):
    found = shutil.which(name + '.cmd') if os.name == 'nt' else None
    found = found or shutil.which(name)
    if not found:
        raise RuntimeError(f'{name} not found in PATH')
    return found


def env_python():
    return ROOT / '.venv-local' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def doctor():
    report = {'python': sys.version.split()[0], 'python_compatible': (3, 11) <= sys.version_info[:2] <= (3, 12),
              'root': str(ROOT), 'free_gib': round(shutil.disk_usage(ROOT).free / 1024**3, 1)}
    for name in ('git', 'node', 'npm', 'docker', 'ffmpeg', 'nvidia-smi'):
        try:
            binary = executable(name)
            cmd = [binary, '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'] if name == 'nvidia-smi' else [binary, '--version' if name != 'ffmpeg' else '-version']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            report[name] = {'available': result.returncode == 0,
                            'version': (result.stdout or result.stderr).splitlines()[:2]}
        except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
            report[name] = {'available': False, 'reason': type(exc).__name__}
    report['assets'] = {name: (project / 'public/sound' / MASTERS[name]).is_file()
                        for name, project in PROJECTS.items()}
    report['legacy_ffmpeg'] = (ROOT / 'work/ffmpeg-full/ffmpeg.exe').is_file()
    report['ink_images'] = len(list((PROJECTS['ink'] / 'public/assets').glob('*.png')))
    print(json.dumps(report, indent=2, ensure_ascii=False))


def install(project):
    if not (3, 11) <= sys.version_info[:2] <= (3, 12):
        raise RuntimeError('Use Python 3.11/3.12 for the pinned CPU requirements.')
    target = ROOT / '.venv-local'
    if not target.exists():
        venv.EnvBuilder(with_pip=True).create(target)
    run([env_python(), '-m', 'pip', 'install', '-r', ROOT / 'requirements-local.txt'])
    # Never npm ci through a checkpoint's old junction/symlink.
    modules = project / 'node_modules'
    if modules.exists():
        raise RuntimeError('node_modules already exists; preserved. Install only in a fresh clone.')
    npm = executable('npm')
    if not (project / 'package-lock.json').is_file():
        locked = ROOT / 'tools/locks/ink-package-lock.json'
        if project != PROJECTS['ink'] or not locked.is_file():
            raise RuntimeError('Missing dependency lockfile; do not silently select new versions.')
        shutil.copy2(locked, project / 'package-lock.json')
    run([npm, 'ci', '--no-audit', '--no-fund'], project)


def preview(project, port):
    name = next(name for name, path in PROJECTS.items() if path == project)
    if not (project / 'public/sound' / MASTERS[name]).is_file():
        raise RuntimeError('Restore film-assets.zip before preview.')
    cli = project / 'node_modules/@remotion/cli/remotion-cli.js'
    if not cli.is_file():
        raise RuntimeError('Install project dependencies first.')
    # require() must resolve renderer from the selected project's fresh install,
    # even if only the full-film project was installed on this machine.
    binding = project / 'scripts/loopback-only.cjs'
    if not binding.is_file():
        source = ROOT / 'outputs/graphic-novel-v8/edit/remotion/scripts/loopback-only.cjs'
        binding.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, binding)
    run([executable('node'), '--require', binding, cli, 'studio', 'src/index.tsx',
         '--no-open', f'--port={port}'], project)


def models():
    # Reuse the checked downloader without its manifest() mutating historical evidence.
    sys.path.insert(0, str(ROOT / 'work/local-production-v6'))
    from download_models import download, digest
    lock = json.loads((ROOT / 'outputs/graphic-novel-v8/model-lock.json').read_text())
    for item in lock:
        target = ROOT / 'local-comfy/data/models' / item['file']
        if target.is_file() and target.stat().st_size == item['size'] and digest(target) == item['sha256']:
            print('VERIFIED', item['file'], flush=True)
            continue
        # The legacy download writes license copies only after successful weight download;
        # route those copies to a new runtime folder, preserving research checkpoints.
        import download_models
        download_models.RESEARCH = ROOT / '.runtime/model-licenses'
        download_models.RESEARCH.mkdir(parents=True, exist_ok=True)
        needed = item['size'] + 2 * 1024**3
        if shutil.disk_usage(ROOT).free < needed:
            raise RuntimeError('Insufficient space for weight plus 2 GiB reserve.')
        download(item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('doctor', 'install', 'preview', 'models', 'comfy-start'))
    parser.add_argument('--project', choices=PROJECTS, default='ink')
    parser.add_argument('--port', type=int, default=3018)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Port must be 1024..65535')
    project = PROJECTS[args.project]
    if args.action == 'doctor':
        doctor()
    elif args.action == 'install':
        install(project)
    elif args.action == 'preview':
        preview(project, args.port)
    elif args.action == 'models':
        if not (ROOT / 'outputs/graphic-novel-v8/model-lock.json').is_file():
            raise RuntimeError('Restore film-assets.zip for the pinned model lock.')
        models()
    else:
        for folder in ('models', 'input', 'output', 'user', 'cache'):
            (ROOT / 'local-comfy/data' / folder).mkdir(parents=True, exist_ok=True)
        run([executable('docker'), 'compose', '-f', ROOT / 'local-comfy/compose.yaml', 'up', '-d', '--build'])


if __name__ == '__main__':
    main()
