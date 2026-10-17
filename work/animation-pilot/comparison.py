"""Silent, native-resolution controlled comparisons; absent candidates stay labelled absent."""
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from common import atomic_json, encode_frames, inspect_video


def decoded_frames(path, width, height, ffmpeg='ffmpeg'):
    process = subprocess.Popen([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-i', str(path),
        '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    size = width*height*3
    try:
        while True:
            data = process.stdout.read(size)
            if not data:
                break
            if len(data) != size:
                raise ValueError('Truncated comparison input.')
            yield np.frombuffer(data, np.uint8).reshape(height, width, 3)
        error = process.stderr.read().decode('utf-8', errors='replace')
        if process.wait(timeout=60) or error.strip():
            raise ValueError('Comparison input decode failed: '+error[-1000:])
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def compare(job, ffmpeg='ffmpeg', ffprobe='ffprobe'):
    run, config = Path(job['run']), job['config']
    width, height = config['WIDTH'], config['HEIGHT']
    label_height = 32
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
    except OSError:
        font = ImageFont.load_default()
    for shot in job['shots']:
        ident = shot['id']
        candidates = [run/'clips'/f'{ident}-seed-{seed}.mp4' for seed in config['SEEDS']]
        if not any(path.exists() for path in candidates):
            continue
        paths = [run/'controls'/f'{ident}-static.mp4', run/'controls'/f'{ident}-depth.mp4', *candidates]
        labels = ['STATIC REFERENCE', 'DEPTH WARP | 3% SAFETY CROP'] + [
            f'WAN I2V | SEED {seed}' for seed in config['SEEDS']]
        readers = [decoded_frames(path,width,height,ffmpeg) if path.exists() else None for path in paths]

        def grid():
            for frame in range(config['FRAMES']):
                canvas = Image.new('RGB', (width*2, (height+label_height)*2), '#151515')
                draw = ImageDraw.Draw(canvas)
                for index, reader in enumerate(readers):
                    x, y = (index % 2)*width, (index // 2)*(height+label_height)
                    label = labels[index]
                    if reader is None:
                        label += ' | NOT GENERATED'
                    else:
                        array = next(reader)
                        canvas.paste(Image.fromarray(array), (x,y+label_height))
                    draw.text((x+7,y+7),label,font=font,fill='white')
                yield np.asarray(canvas)
        target = run/'review'/f'{ident}-comparison.mp4'
        try:
            encode_frames(grid(),target,config['FPS'],ffmpeg)
        finally:
            for reader in readers:
                if reader is not None:
                    reader.close()
        check_config = dict(config,WIDTH=width*2,HEIGHT=(height+label_height)*2)
        report, _ = inspect_video(target,check_config,ffmpeg=ffmpeg,ffprobe=ffprobe)
        report['kind'] = 'silent_native_resolution_comparison_not_final_edit'
        report['panels'] = [str(path.relative_to(run)) if path.exists() else None for path in paths]
        atomic_json(target.with_suffix('.json'),report)
        print(f'COMPARISON {target.name}',flush=True)
