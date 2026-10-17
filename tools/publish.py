"""Publish this source-only project to a new PRIVATE GitHub repository after login."""
import argparse
from pathlib import Path
import subprocess
import sys

import project_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='film-pipeline')
    args = parser.parse_args()
    if not args.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.name):
        parser.error('Repository name must contain letters, digits, hyphens or underscores.')
    transfer.audit(transfer.sources())
    auth = subprocess.run(['gh', 'auth', 'status'], cwd=ROOT, capture_output=True)
    if auth.returncode:
        sys.exit('GitHub login required. Run: gh auth login --hostname github.com\nDo not send tokens in chat.')
    remotes = subprocess.check_output(['git', 'remote'], cwd=ROOT, text=True).splitlines()
    if 'origin' in remotes:
        sys.exit('origin already exists. Inspect git remote -v; nothing changed.')
    status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    if status.strip():
        sys.exit('Uncommitted source changes found. Review and commit them before publishing.')
    # No public fallback, no --force, no credential arguments.
    subprocess.run(['gh', 'repo', 'create', args.name, '--private', '--source=.',
                    '--remote=origin', '--push'], cwd=ROOT, check=True)
    subprocess.run(['gh', 'repo', 'view', '--json', 'url,sshUrl'], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
