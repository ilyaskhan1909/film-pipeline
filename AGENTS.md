# Project handoff

Read docs/HANDOFF.md before generation or editing. Keep replies concise, in Russian.

- v6 is a full 11:38 film. v8 is an 88.625-second ink-style pilot, not a full restyle.
- Preserve original, v6, v7 and v8 assets and evidence. New production belongs in v9.
- Current goal: full dark-ink horror film, then a demonstrable audio improvement.
- Existing narration has unresolved identity/intonation variation. LUFS/ASR do not prove listening quality.
- Local Docker/ComfyUI creates assets; Kaggle is the optional silent-video stage. Editing/audio stay local.
- No paid API, automatic uploads, publishing, new cloud costs, or credential commits.
- Do not rerun legacy build/delivery scripts against checkpoints. Review write targets first.
- Absolute paths in checkpoint JSON are historical evidence, not portable runtime paths. Do not rewrite the evidence.
- Install fresh dependencies after cloning. Never copy/junction node_modules from the old computer.
- Transfer assets with tools/project_transfer.py, check hashes, then run tools/bootstrap.py doctor.
- Do not claim validation on new GPU/OS until it was actually tested there.
