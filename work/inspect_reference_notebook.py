"""Read notebook source without executing it; redact potential credentials."""
import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("notebook", type=Path)
parser.add_argument("--first", type=int, default=0)
parser.add_argument("--last", type=int, default=99)
args = parser.parse_args()
nb = json.loads(args.notebook.read_text(encoding="utf-8"))
for i, cell in enumerate(nb["cells"]):
    if not args.first <= i <= args.last:
        continue
    source = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
    source = re.sub(r"\b(?:hf_[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|KGAT_[A-Za-z0-9_-]+)\b", "[REDACTED]", source)
    source = re.sub(r'''(?mi)(\b\w*(?:API_KEY|TOKEN|PASSWORD|SECRET)\w*\s*=\s*)(["'])([^\n]*?)\2''',
                    lambda m: m[1] + m[2] + "[REDACTED]" + m[2], source)
    print(f"\nCELL {i}: {cell['cell_type']}\n{source}")
