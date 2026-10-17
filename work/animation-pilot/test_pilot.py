"""Static and deterministic tests are not a substitute for an actual T4 generation."""
import json
import tempfile
import unittest
from pathlib import Path

import nbformat
import numpy as np
import torch
from PIL import Image

from common import bilinear, control_frames, encode_frames, inspect_video, validate_config
from driver import import_sources
from worker import install_chunked_attention
from comparison import compare

ROOT = Path(__file__).resolve().parents[2]
FFMPEG = ROOT/'work/ffmpeg-full/ffmpeg.exe'
FFPROBE = ROOT/'work/smoke-scratch/node/remotion-c57941070451/node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe'


class PilotTests(unittest.TestCase):
    def test_standalone_notebook(self):
        nb = nbformat.read(ROOT/'outputs/animation-pilot/videogenerator-v4.2-kaggle-animation-pilot.ipynb', as_version=4)
        nbformat.validate(nb)
        self.assertEqual(sum(c.cell_type == 'markdown' for c in nb.cells), 1)
        self.assertNotIn('Wan2GP', nb.cells[2].source)
        for index, cell in enumerate(nb.cells):
            if cell.cell_type == 'code':
                compile(cell.source, f'cell-{index}', 'exec')

    def test_query_chunking_matches_full_attention(self):
        q, k, v = [torch.randn(2, 3, 17, 8) for _ in range(3)]
        mask = torch.randn(17, 17)
        original = torch.nn.functional.scaled_dot_product_attention
        expected = original(q, k, v, attn_mask=mask)
        install_chunked_attention(5)
        try:
            actual = torch.nn.functional.scaled_dot_product_attention(q, k, v, attn_mask=mask)
            torch.testing.assert_close(actual, expected, rtol=2e-5, atol=2e-5)
        finally:
            torch.nn.functional.scaled_dot_product_attention = original

    def test_identity_backward_sampling(self):
        array = np.random.default_rng(5).integers(0, 255, (32, 64, 3), dtype=np.uint8)
        y, x = np.mgrid[:32, :64].astype(np.float32)
        np.testing.assert_array_equal(bilinear(array, x, y)[:-1, :-1], array[:-1, :-1])

    def test_wrong_source_hash_cannot_be_imported(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work/animation-pilot') as temporary:
            base = Path(temporary)
            (base/'source').mkdir()
            with self.assertRaises(FileNotFoundError):
                import_sources(base, [{'id':'shot-001', 'sha256':'0'*64}], ROOT/'outputs/first-film/curated/assets/images')

    def test_exact_native_shape_and_fps(self):
        config = {'WIDTH':512, 'HEIGHT':288, 'FRAMES':9, 'FPS':24, 'SEEDS':[1,2],
                  'MAX_GPU_WORKERS':2, 'STEPS':40}
        validate_config(config)
        with self.assertRaises(ValueError):
            validate_config(dict(config, HEIGHT=290))
        with tempfile.TemporaryDirectory(dir=ROOT/'work/animation-pilot') as temporary:
            file = Path(temporary)/'control.mp4'
            image = Image.open(ROOT/'outputs/first-film/curated/assets/images/shot-001.png').resize((512,288))
            depth = np.tile(np.linspace(0,1,512,dtype=np.float32), (288,1))
            encode_frames(control_frames(image,9,depth),file,ffmpeg=FFMPEG)
            report, samples = inspect_video(file,config,image,ffmpeg=FFMPEG,ffprobe=FFPROBE)
            self.assertEqual(report['decoded_frames'],9)
            self.assertFalse(report['editorial_approved'])
            self.assertGreater(report['frame_difference_mean'],0)
            self.assertEqual(len(samples),5)

    def test_comparison_labels_absent_second_seed(self):
        config = {'WIDTH':512,'HEIGHT':288,'FRAMES':9,'FPS':24,'SEEDS':[1,2]}
        with tempfile.TemporaryDirectory(dir=ROOT/'work/animation-pilot') as temporary:
            run = Path(temporary)
            for folder in ('controls','clips','review'):
                (run/folder).mkdir()
            image = Image.open(ROOT/'outputs/first-film/curated/assets/images/shot-001.png').resize((512,288))
            for name in ('controls/shot-001-static.mp4','controls/shot-001-depth.mp4','clips/shot-001-seed-1.mp4'):
                encode_frames(control_frames(image,9),run/name,ffmpeg=FFMPEG)
            compare({'run':str(run),'config':config,'shots':[{'id':'shot-001'}]},FFMPEG,FFPROBE)
            report = json.loads((run/'review/shot-001-comparison.json').read_text())
            self.assertIsNone(report['panels'][3])
            self.assertEqual(report['native_size'],[1024,640])
            self.assertEqual(report['decoded_frames'],9)


if __name__ == '__main__':
    unittest.main()
