"""Portable, non-destructive animation pilot contracts and media checks."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, path)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate_config(config):
    width, height = config['WIDTH'], config['HEIGHT']
    if width % 32 or height % 32 or width * 9 != height * 16:
        raise ValueError('Use exact 16:9 dimensions divisible by 32, e.g. 512x288 or 1024x576.')
    if config['FRAMES'] < 9 or (config['FRAMES'] - 1) % 4:
        raise ValueError('Wan frame count must be 4n+1.')
    if config['FPS'] != 24 or len(config['SEEDS']) != 2:
        raise ValueError('This controlled pilot uses 24 fps and exactly two seeds.')
    if not 1 <= config['MAX_GPU_WORKERS'] <= 2:
        raise ValueError('At most two independent GPU workers are allowed.')
    if not 10 <= config['STEPS'] <= 80:
        raise ValueError('Use 10..80 denoising steps; the pilot default is 40.')


def encode_frames(frames, target, fps=24, ffmpeg='ffmpeg'):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    frames = iter(frames)
    first = np.asarray(next(frames), dtype=np.uint8)
    height, width = first.shape[:2]
    temporary = target.with_name(target.stem + '.partial.mp4')
    command = [str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}', '-r', str(fps),
               '-i', 'pipe:0', '-an', '-vf', 'scale=in_range=full:out_range=tv:out_color_matrix=bt709',
               '-c:v', 'libx264', '-preset', 'medium', '-crf', '16',
               '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709',
               '-colorspace', 'bt709', '-movflags', '+faststart', str(temporary)]
    error_path = target.with_suffix('.encoder.log')
    with error_path.open('wb') as errors:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
        try:
            process.stdin.write(first.tobytes())
            for frame in frames:
                array = np.asarray(frame, dtype=np.uint8)
                if array.shape != first.shape:
                    raise ValueError('Frame dimensions changed.')
                process.stdin.write(array.tobytes())
            process.stdin.close()
            if process.wait(timeout=300):
                raise RuntimeError(error_path.read_text(encoding='utf-8', errors='replace')[-1500:])
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
    os.replace(temporary, target)


def bilinear(image, x, y):
    """Backward sampling: no synthesized disocclusions or hidden inpainting."""
    height, width = image.shape[:2]
    x = np.clip(x, 0, width - 1.001)
    y = np.clip(y, 0, height - 1.001)
    left, top = x.astype(np.int32), y.astype(np.int32)
    fx, fy = (x - left)[..., None], (y - top)[..., None]
    a = image[top, left].astype(np.float32)
    b = image[top, left + 1].astype(np.float32)
    c = image[top + 1, left].astype(np.float32)
    d = image[top + 1, left + 1].astype(np.float32)
    return np.clip((a * (1 - fx) + b * fx) * (1 - fy) +
                   (c * (1 - fx) + d * fx) * fy, 0, 255).round().astype(np.uint8)


def control_frames(image, frames, depth=None):
    """Static-camera and modest depth-guided warp controls, not true layered 3D."""
    image = np.asarray(image.convert('RGB'))
    height, width = image.shape[:2]
    y, x = np.mgrid[:height, :width].astype(np.float32)
    if depth is None:
        for _ in range(frames):
            yield image
        return
    # A 3% safety crop contains the translation. Warp amplitude stays below 2 px at 512w.
    for index in range(frames):
        t = index / max(1, frames - 1)
        progress = t * t * (3 - 2 * t)
        shift = (progress - .5) * width * .006 * (.2 + .8 * depth)
        sample_x = (x - width / 2) / 1.03 + width / 2 - shift
        sample_y = (y - height / 2) / 1.03 + height / 2
        yield bilinear(image, sample_x, sample_y)


def inspect_video(path, config, reference=None, ffmpeg='ffmpeg', ffprobe='ffprobe'):
    raw = subprocess.check_output([str(ffprobe), '-v', 'error', '-count_frames',
        '-show_streams', '-show_format', '-of', 'json', str(path)], text=True)
    info = json.loads(raw)
    videos = [s for s in info['streams'] if s['codec_type'] == 'video']
    if len(videos) != 1 or any(s['codec_type'] == 'audio' for s in info['streams']):
        raise ValueError('Asset must contain one silent video stream.')
    video = videos[0]
    if (video['width'], video['height']) != (config['WIDTH'], config['HEIGHT']):
        raise ValueError('Wrong native video resolution.')
    if video['avg_frame_rate'] != '24/1' or int(video['nb_read_frames']) != config['FRAMES']:
        raise ValueError('Wrong frame rate or count.')
    if abs(float(info['format']['duration']) - config['FRAMES'] / config['FPS']) > .06:
        raise ValueError('Wrong clip duration.')
    process = subprocess.Popen([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-i', str(path),
        '-vf', 'scale=256:144', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    size = 256 * 144 * 3
    means, differences, reference_differences, sampled = [], [], [], []
    previous = None
    base = None if reference is None else np.asarray(reference.resize((256, 144)), dtype=np.float32)
    while True:
        data = process.stdout.read(size)
        if not data:
            break
        if len(data) != size:
            raise ValueError('Truncated decoded frame.')
        frame = np.frombuffer(data, np.uint8).reshape(144, 256, 3).astype(np.float32)
        means.append(float(frame.mean()))
        if previous is not None:
            differences.append(float(np.abs(frame - previous).mean()))
        if base is not None:
            reference_differences.append(float(np.abs(frame - base).mean()))
        if len(means) - 1 in {0, config['FRAMES']//4, config['FRAMES']//2,
                              3*config['FRAMES']//4, config['FRAMES']-1}:
            sampled.append(frame.astype(np.uint8))
        previous = frame
    errors = process.stderr.read().decode('utf-8', errors='replace')
    process.stdout.close()
    process.stderr.close()
    if process.wait(timeout=60) or errors.strip() or len(means) != config['FRAMES']:
        raise ValueError('Full decode failed: ' + errors[-1000:])
    report = {'sha256': sha256(path), 'decoded_frames': len(means),
        'native_size': [video['width'], video['height']], 'fps': 24,
        'duration_seconds': float(info['format']['duration']), 'silent': True,
        'mean_rgb_range': [min(means), max(means)],
        'frame_difference_mean': float(np.mean(differences)),
        'frame_difference_max': max(differences),
        'reference_rgb_difference_range': None if base is None else
            [min(reference_differences), max(reference_differences)],
        'technical_pass': True, 'editorial_approved': False,
        'warning': 'Pixel differences are advisory, not identity or animation-quality verification.'}
    if min(means) < .4:
        report['warning_black_frames'] = True
    return report, sampled
