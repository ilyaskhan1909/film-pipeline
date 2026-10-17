"""Offline independent ASR check using an already-cached local Whisper model."""
import argparse
import json
import re
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio


def words(text):
    # Preserve numbers; normalize only equivalent English ordinal spellings.
    ordinals = {"1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth",
                "5th": "fifth", "6th": "sixth", "7th": "seventh", "8th": "eighth",
                "9th": "ninth", "10th": "tenth"}
    tokens = re.findall(r"[a-z]+(?:'[a-z]+)?|\d+(?:st|nd|rd|th)?", text.casefold())
    return [ordinals.get(token, token) for token in tokens]


def distance(left, right):
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        next_row = [i]
        for j, b in enumerate(right, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (a != b)))
        row = next_row
    return row[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.directory / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        state = json.loads((args.directory / "pipeline_state.json").read_text(encoding="utf-8"))
        manifest = {"scope": "partial run audio only",
                    "scenes": [s for s in state["scenes"] if s.get("audio") and
                               (args.directory / s["audio"]).is_file()]}
    assert manifest["scenes"], "No audio available"
    model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=8,
                         download_root=str(args.cache), local_files_only=True)
    results = []
    for scene in manifest["scenes"]:
        audio = decode_audio(str(args.directory / scene["audio"]), sampling_rate=16000)
        segments, _ = model.transcribe(audio, language="en", beam_size=5,
                                       condition_on_previous_text=False, vad_filter=False)
        transcript = " ".join(segment.text.strip() for segment in segments)
        expected, observed = words(scene["text"]), words(transcript)
        errors = distance(expected, observed)
        result = {"index": scene["index"], "expected": scene["text"], "transcript": transcript,
                  "word_error_rate": errors / max(len(expected), 1), "word_errors": errors,
                  "expected_words": len(expected), "duration": len(audio) / 16000,
                  "rms_dbfs": float(20 * np.log10(np.sqrt(np.mean(audio ** 2)) + 1e-10)),
                  "peak": float(np.max(np.abs(audio)))}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    report = {"model": "faster-whisper large-v3-turbo, cached, CPU int8, offline",
              "normalization": "case and punctuation; equivalent English ordinals; numbers preserved",
              "scope": manifest["scope"], "scenes": results,
              "word_error_rate": sum(r["word_errors"] for r in results) /
                                 max(sum(r["expected_words"] for r in results), 1),
              "limitations": ["ASR measures intelligibility, not acting quality or listening approval"]}
    output = args.directory.parent / "independent_asr.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output.resolve()), "word_error_rate": report["word_error_rate"]}))


if __name__ == "__main__":
    main()
