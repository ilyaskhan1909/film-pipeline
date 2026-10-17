"""Isolated CPU tests; no real checkpoints, credentials, GPU or network used."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import project_transfer as t


class TransferTests(unittest.TestCase):
    def setUp(self):
        scratch = t.ROOT / '.runtime/test-temp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, name='outputs/graphic-novel-v8/characters/test.png', data=b'dummy', corrupt=False):
        path = self.root / 'example.zip'
        manifest = {'format': 'film-transfer-v1', 'kind': 'assets',
                    'files': [{'file': name, 'size': len(data),
                               'sha256': '0' * 64 if corrupt else hashlib.sha256(data).hexdigest()}]}
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr(name, data)
            z.writestr('TRANSFER-MANIFEST.json', json.dumps(manifest))
        return path, manifest

    def test_traversal_is_rejected(self):
        for name in ('../oops', '/tmp/oops', 'C:/oops', 'a\\b', 'a/../b', 'a//b', 'CON.png', 'a./x'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                t.safe_target(self.root, name)

    def test_secret_detection_does_not_print_value(self):
        path = self.root / 'probe.py'
        secret = 'ghp' + '_' + 'a' * 36
        path.write_text('TOKEN = ' + repr(secret))
        with self.assertRaises(RuntimeError) as error:
            t.audit([path], self.root)
        self.assertNotIn(secret, str(error.exception))

    def test_notebook_outputs_rejected(self):
        path = self.root / 'probe.ipynb'
        path.write_text(json.dumps({'cells': [{'outputs': [{'text': 'private output'}]}]}))
        with self.assertRaises(RuntimeError):
            t.audit([path], self.root)

    def test_restore_and_verify_idempotent(self):
        archive, manifest = self.archive()
        with contextlib.redirect_stdout(io.StringIO()):
            t.restore(archive, self.root)
            t.restore(archive, self.root)
            t.restore(archive, self.root, verify_only=True)
        self.assertEqual((self.root / manifest['files'][0]['file']).read_bytes(), b'dummy')

    def test_existing_different_file_not_overwritten(self):
        archive, manifest = self.archive()
        target = self.root / manifest['files'][0]['file']
        target.parent.mkdir(parents=True)
        target.write_bytes(b'user changes')
        with self.assertRaises(FileExistsError):
            t.restore(archive, self.root)
        self.assertEqual(target.read_bytes(), b'user changes')

    def test_corrupt_content_not_restored(self):
        archive, manifest = self.archive(corrupt=True)
        with self.assertRaises(ValueError):
            t.restore(archive, self.root)
        self.assertFalse((self.root / manifest['files'][0]['file']).exists())

    def test_archive_outside_asset_scope_rejected(self):
        archive, _ = self.archive(name='tools/attacker.py')
        with self.assertRaises(ValueError):
            t.restore(archive, self.root)

    def test_case_duplicate_rejected(self):
        archive, _ = self.archive()
        with zipfile.ZipFile(archive, 'a') as z:
            z.writestr('OUTPUTS/GRAPHIC-NOVEL-V8/CHARACTERS/TEST.PNG', b'dummy')
        with self.assertRaises(ValueError):
            t.restore(archive, self.root)

    def test_missing_file_verify_fails(self):
        archive, _ = self.archive()
        with self.assertRaises(FileNotFoundError):
            t.restore(archive, self.root, verify_only=True)

    def test_credential_payload_name_rejected(self):
        for name in ('local-comfy/data/input/.env', 'local-comfy/data/input/kaggle.json',
                     'outputs/graphic-novel-v8/.git/config'):
            self.assertFalse(t.allowed(name, 'assets'))

    def test_model_scope_is_separate(self):
        self.assertTrue(t.allowed('local-comfy/data/models/vae/model.safetensors', 'models'))
        self.assertFalse(t.allowed('local-comfy/data/models/vae/model.safetensors', 'assets'))

    def test_sources_exclude_heavy_files_and_junctions(self):
        files = t.sources()
        self.assertTrue(files)
        self.assertFalse(any('node_modules' in p.parts or p.suffix in ('.wav', '.exe', '.mp4') for p in files))


if __name__ == '__main__':
    unittest.main()
