"""Local tests with SYNTHETIC fixtures. These do not test Kaggle/model quality."""
import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from contract import digest, identity, load_inputs, make_archive, save_json, validate_inputs
from ingest import FFMPEG, FFPROBE, ingest
from transfer import duration_seconds, quota_remaining

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def fixture(folder):
    (folder / 'frames').mkdir()
    Image.new('RGB', (256,144), (40,80,120)).save(folder / 'frames/shot-001.png')
    manifest = {'schema':'video-inputs/v1','assets':[{'id':'shot-001',
        'file':'frames/shot-001.png','sha256':digest(folder / 'frames/shot-001.png')}],
        'requests':[{'id':'lake-test-01','asset_id':'shot-001','prompt':'Still camera, gentle ripples.',
            'config':{'WIDTH':256,'HEIGHT':144,'FRAMES':9,'FPS':24,'STEPS':20,'GUIDANCE':3.5,'SEED':5}}],
        'policy':{'kaggle_scope':'silent_image_to_video_only'}}
    manifest['handoff_id'] = 'video-' + identity(manifest)[:16]
    save_json(folder / 'video-inputs.json', manifest)
    return manifest


class RoundtripTests(unittest.TestCase):
    def setUp(self):
        scratch = HERE / 'test-scratch'
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='fixture-', dir=scratch)
        self.folder = Path(self.temporary.name).resolve()
        if not self.folder.is_relative_to(scratch.resolve()):
            raise RuntimeError('Temporary fixture must stay within the test workspace.')
        self.inputs = self.folder / 'inputs'
        self.inputs.mkdir()
        self.manifest = fixture(self.inputs)

    def tearDown(self):
        self.temporary.cleanup()

    def test_direct_input_loading(self):
        result = load_inputs(self.inputs, self.manifest['handoff_id'], self.folder / 'loaded')
        self.assertEqual(result, self.manifest)
        self.assertEqual(digest(self.folder / 'loaded/frames/shot-001.png'), self.manifest['assets'][0]['sha256'])

    def test_zip_input_loading(self):
        folder = self.folder / 'attached'
        folder.mkdir()
        with zipfile.ZipFile(folder / 'test-inputs.zip','w') as bundle:
            for path in self.inputs.rglob('*'):
                if path.is_file():
                    bundle.write(path,path.relative_to(self.inputs).as_posix())
        self.assertEqual(load_inputs(folder,self.manifest['handoff_id'],self.folder / 'loaded'),self.manifest)

    def test_changed_input_refused_before_copy(self):
        (self.inputs / 'frames/shot-001.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            load_inputs(self.inputs,self.manifest['handoff_id'],self.folder / 'loaded')
        self.assertFalse((self.folder / 'loaded').exists())

    def test_manifest_edit_invalidates_identity(self):
        bad = copy.deepcopy(self.manifest)
        bad['requests'][0]['config']['SEED'] = 6
        with self.assertRaises(ValueError):
            validate_inputs(bad)

    def test_traversal_refused(self):
        attached = self.folder / 'attached'
        attached.mkdir()
        with zipfile.ZipFile(attached / 'test-inputs.zip','w') as bundle:
            bundle.writestr('../escape.txt','unsafe')
            bundle.writestr('video-inputs.json',json.dumps(self.manifest))
        with self.assertRaises(ValueError):
            load_inputs(attached,self.manifest['handoff_id'],self.folder / 'loaded')
        self.assertFalse((self.folder / 'escape.txt').exists())

    def test_duration_and_quota_guard(self):
        self.assertAlmostEqual(duration_seconds('32620.601623.0s'),32620.601623)
        response = {'gpuQuota':{'timeUsed':'32620.601623.0s','timeReserved':'0s',
            'totalTimeAllowed':'21600s','isPayToScaleEnabled':False}}
        self.assertEqual(quota_remaining(response),0)
        response['gpuQuota']['isPayToScaleEnabled'] = True
        with self.assertRaises(RuntimeError):
            quota_remaining(response)

    def test_native_video_return_and_tampered_archive(self):
        import sys
        sys.path.insert(0,str(ROOT / 'work/animation-pilot'))
        from common import encode_frames
        result = self.folder / 'result'
        (result / 'clips').mkdir(parents=True)
        (result / 'reports').mkdir()
        config = self.manifest['requests'][0]['config']
        ident = 'lake-test-01'
        video = result / 'clips' / f'{ident}.mp4'
        frames = [np.full((144,256,3),40+i*3,dtype=np.uint8) for i in range(9)]
        encode_frames(frames,video,24,ffmpeg=FFMPEG)
        report = {'sha256':digest(video),'config':config,
            'source_sha256':self.manifest['assets'][0]['sha256'],
            'job_fingerprint':'synthetic-contract-fixture','technical_pass':True}
        save_json(result / 'reports' / f'{ident}.json',report)
        returned = {'schema':'video-results/v1','handoff_id':self.manifest['handoff_id'],
            'job_fingerprint':'synthetic-contract-fixture','clips':[{
                'id':ident,'asset_id':'shot-001','config':config,
                'file':f'clips/{ident}.mp4','report':f'reports/{ident}.json',
                'sha256':digest(video),'source_sha256':report['source_sha256'],
                'technical_pass':True,'production_approved':False}]}
        save_json(result / 'video-results.json',returned)
        archive = make_archive(result,self.folder / 'test-results.zip')
        destination = ingest(archive,self.inputs / 'video-inputs.json',self.folder / 'returned',FFMPEG,FFPROBE)
        catalogue = json.loads((destination / 'edit-assets.json').read_text())
        self.assertEqual(catalogue['clips'][0]['frames'],9)
        self.assertFalse(catalogue['clips'][0]['editorial_approved'])
        corrupt = self.folder / 'bad-results.zip'
        with zipfile.ZipFile(archive) as original, zipfile.ZipFile(corrupt,'w') as edited:
            for info in original.infolist():
                data = original.read(info.filename)
                if info.filename == f'clips/{ident}.mp4':
                    data += b'CORRUPTED'
                edited.writestr(info.filename,data)
        with self.assertRaises(ValueError):
            ingest(corrupt,self.inputs / 'video-inputs.json',self.folder / 'bad-return',FFMPEG,FFPROBE)
        self.assertFalse((self.folder / 'bad-return').exists())


if __name__ == '__main__':
    unittest.main()
