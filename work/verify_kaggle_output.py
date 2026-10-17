"""Validate actual Kaggle deliverables, separately from synthetic smoke tests."""
import argparse
import hashlib
import json
import math
import re
import subprocess
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageStat


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--ffprobe", type=Path, required=True)
    args = parser.parse_args()
    destination = args.directory.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None, "Archive CRC failure"
        for item in archive.infolist():
            target = (destination / item.filename).resolve()
            assert target.is_relative_to(destination), "Unsafe archive path"
            assert not target.exists(), "Extraction must not overwrite existing files"
        archive.extractall(destination)
    checksums = json.loads((destination / "checksums.json").read_text(encoding="utf-8"))
    for name, expected in checksums.items():
        path = (destination / name).resolve()
        assert path.is_relative_to(destination)
        assert digest(path) == expected, "Hash mismatch: " + name
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    state = json.loads((destination / "pipeline_state.json").read_text(encoding="utf-8"))
    environment = json.loads((destination / "environment.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == state["run_id"]
    assert len(manifest["scenes"]) == manifest["selected_scene_count"]
    assert " ".join(s["text"] for s in state["scenes"]) == " ".join(
        (destination / "story.txt").read_text(encoding="utf-8").split())
    if manifest["scope"] == "full":
        assert manifest["selected_scene_count"] == manifest["source_scene_count"]
    results = []
    videos = []
    cursor = 0
    for scene in manifest["scenes"]:
        assert scene["start_frame"] == cursor
        cursor += scene["frames"]
        with wave.open(str(destination / scene["audio"]), "rb") as wav:
            assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
            duration = wav.getnframes() / wav.getframerate()
            assert abs(duration - scene["audio_duration"]) < .002
        with Image.open(destination / scene["image"]) as image:
            image.load()
            stats = ImageStat.Stat(image.convert("RGB"))
            assert max(stats.stddev) > 1, "Uniform image"
            image_size = list(image.size)
        previous = 0
        for word in scene["words"]:
            assert math.isfinite(word["start"] + word["end"])
            assert previous <= word["start"] < word["end"] <= duration + .05
            previous = word["end"]
        clean = lambda text: re.sub(r"[^\w']", "", text.casefold())
        expected_units = [clean(token) for token in scene["text"].split()]
        aligned_units = [clean(word["text"]) for word in scene["words"]]
        results.append({"index": scene["index"], "audio_duration": duration,
                        "image_size": image_size, "alignment_units": len(scene["words"]),
                        "alignment_expected_space_separated_units": len(expected_units),
                        "alignment_text_complete": expected_units == aligned_units,
                        "visual_qa": scene.get("qa"), "text": scene["text"]})
        videos.append((scene["clip"], scene["frames"]))
    assert cursor == manifest["frames"]
    for name in ("PREVIEW_raw.mp4", "RAW_review.mp4"):
        if (destination / name).exists():
            videos.append((name, cursor))
    verified = []
    for name, frames in videos:
        path = destination / name
        info = json.loads(subprocess.check_output(
            [str(args.ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            text=True))
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
        assert video["codec_name"] == "h264" and audio["codec_name"] == "aac"
        assert [video["width"], video["height"]] == [manifest["width"], manifest["height"]]
        num, den = map(int, video["avg_frame_rate"].split("/"))
        assert abs(num / den - manifest["fps"]) < 1e-6
        assert int(video["nb_frames"]) == frames
        assert abs(float(info["format"]["duration"]) - frames / manifest["fps"]) < .1
        subprocess.run([str(args.ffmpeg), "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], check=True)
        verified.append({"file": name, "frames": frames, "full_decode": "passed"})
    report = {"source": "real Kaggle GPU execution, not synthetic fixtures",
              "observed_at": datetime.now(timezone.utc).isoformat(), "status": "passed",
              "archive": str(args.archive.resolve()), "archive_sha256": digest(args.archive),
              "checksums_verified": len(checksums), "scope": manifest["scope"],
              "duration": manifest["duration"], "selected_scene_count": len(results),
              "source_scene_count": manifest["source_scene_count"], "environment": environment,
              "scenes": results, "videos": verified,
              "limitations": ["Static generated images, not generative motion",
                              "No edit or sound-design pass; listening quality is not asserted"]}
    if any(not scene["alignment_text_complete"] for scene in results):
        report["limitations"].append("Word alignment is partial in some scenes; subtitles need editorial review")
    output = destination.parent / "actual_kaggle_validation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "scope": report["scope"],
                      "scenes": len(results), "duration": report["duration"],
                      "checksums_verified": len(checksums), "report": str(output.resolve())}))


if __name__ == "__main__":
    main()
