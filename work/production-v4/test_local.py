"""Static/unit checks do not replace the authenticated Kaggle GPU run."""
import ast
import hashlib
import json
import unittest
import sys
from pathlib import Path

import nbformat
from prepare_edit import script_timing, at_phrase, readable_subtitles
from mix_sound import normalise, loudness
from make_repair import make

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'work'))
from resume_assets import resume


class ProductionTests(unittest.TestCase):
    def test_verified_curated_notebook_selection(self):
        nb=nbformat.read(ROOT/'outputs/videogenerator-v4.1-kaggle-assets.ipynb',as_version=4)
        nbformat.validate(nb)
        for i,cell in enumerate(nb.cells):
            if cell.cell_type=='code':compile(cell.source,f'curated-cell-{i}','exec')
        values={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(nb.cells[1].source).body
                if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
                and n.targets[0].id in ('CONFIG','PLAN')}
        self.assertFalse(values['CONFIG']['QUICK_TEST'])
        self.assertEqual(set(values['PLAN']['export_shots']),set(range(71))-{2,21,26,31,55,61,65,67})
        self.assertEqual(len(values['PLAN']['segments']),26)
        self.assertEqual(len([c for c in nb.cells if c.cell_type=='markdown']),1)

    def test_standalone_notebook_and_cache_identity(self):
        nb = nbformat.read(ROOT/'outputs/videogenerator-v4-production-FULL.ipynb',as_version=4)
        nbformat.validate(nb)
        for i,cell in enumerate(nb.cells):
            if cell.cell_type=='code':
                compile(cell.source,f'cell-{i}','exec')
        literal = {}
        for node in ast.parse(nb.cells[1].source).body:
            if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name):
                key = node.targets[0].id
                if key in ('CONFIG','PLAN','PINS','REVISIONS','IMPLEMENTATION_SHA'):
                    literal[key]=ast.literal_eval(node.value)
        def fingerprint(config):
            filtered={k:v for k,v in config.items() if k not in ('QUICK_TEST','TEST_SCENES','COMPARE_BASE','PILOT_AUDIO_INDICES')}
            return hashlib.sha256(json.dumps({'config':filtered,'plan':literal['PLAN'],
                'implementation':literal['IMPLEMENTATION_SHA'],'revisions':literal['REVISIONS'],
                'pins':literal['PINS']},sort_keys=True).encode()).hexdigest()[:16]
        config = literal['CONFIG']
        self.assertEqual(fingerprint(config),nb.metadata.videogenerator.run_id)
        self.assertEqual(fingerprint(dict(config,QUICK_TEST=True)),fingerprint(config))
        self.assertNotEqual(fingerprint(dict(config,GEN_W=1280)),fingerprint(config))
        self.assertNotEqual(fingerprint(dict(config,SPEAKER='Aiden')),fingerprint(config))
        self.assertEqual(len(literal['PLAN']['segments']),26)
        self.assertEqual(len(literal['PLAN']['shots']),71)
        self.assertFalse(config['LLM_ENABLED'])
        self.assertEqual(config['TTS_TAKES'],{'19':1})

    def test_caption_preserves_script(self):
        heard=[{'text':'My','start':0,'end':.2},{'text':'flashlight','start':.3,'end':.7},
               {'text':'being','start':.8,'end':1},{'text':'shaking.','start':1.1,'end':1.6}]
        source='My flashlight beam shaking.'
        timed=script_timing(source,heard)
        self.assertEqual(' '.join(w['text'] for w in timed),source)
        self.assertEqual(timed[2]['start'],.8)
        self.assertEqual(at_phrase(timed,'flashlight beam'),.3)

    def test_subtitle_reading_and_paragraph_boundary(self):
        cues=[(0,2,'The exact source',0),(2,2.3,'story.',0),
              (3,3.4,'Next.',1),(4,5,'Paragraph.',1)]
        result=readable_subtitles(cues,6)
        self.assertEqual(' '.join(t.replace('\n',' ') for _,_,t in result),
                         'The exact source story. Next. Paragraph.')
        self.assertEqual(len(result),3)
        self.assertEqual(result[1][0],3)
        self.assertGreaterEqual(result[1][1]-result[1][0],.89)

    def test_repairs_are_explicit_and_do_not_mutate_original(self):
        nb = nbformat.read(ROOT/'outputs/videogenerator-v4-production-FULL.ipynb',as_version=4)
        original = nb.cells[1].source
        repair = make(nb, {'shots':{'shot-054':{'prompt':'Test close-up of loose blue fabric.','refs':[]}},
                           'audio_takes':{'19':2}})
        self.assertEqual(nb.cells[1].source, original)
        self.assertNotEqual(repair.metadata.videogenerator.run_id, nb.metadata.videogenerator.run_id)
        self.assertIn("'PILOT_AUDIO_INDICES': [19]", repair.cells[1].source)
        self.assertIn("'pilot_shots': [54]", repair.cells[1].source)
        for bad in ({'shots':{'shot-054':{'lens':'macro'}}}, {'audio_takes':{'19':1}}, {'unknown':1}):
            with self.assertRaises(AssertionError):
                make(nb, bad)

    def test_measured_audio_processing(self):
        scratch = ROOT/'work/production-v4/local-test'
        scratch.mkdir(exist_ok=True)
        target = scratch/'normalized-test.wav'
        source = ROOT/'outputs/first-film/pilot/assets/audio/s0000.wav'
        normalise(source,target,-18)
        actual = loudness(target,-18)
        self.assertLessEqual(float(actual['input_tp']),-1.3)
        self.assertLess(abs(float(actual['input_i'])+18),.5)

    def test_voice_change_preserves_independent_image_cache(self):
        nb=nbformat.read(ROOT/'outputs/videogenerator-v4.1-kaggle-assets.ipynb',as_version=4)
        values={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(nb.cells[1].source).body
            if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
            and n.targets[0].id in ('CONFIG','PLAN','PINS','REVISIONS')}
        config=dict(values['CONFIG'],SPEAKER='Aiden')
        directory=ROOT/'work/production-v4/local-test'/('voice-change-'+nb.metadata.videogenerator.run_id)
        directory.mkdir(exist_ok=True)
        resume(directory,config,values['PLAN'],values['PINS'],values['REVISIONS'],
               input_root=ROOT/'outputs/first-film/full')
        state=json.loads((directory/'pipeline_state.json').read_text(encoding='utf-8'))
        self.assertFalse(any(s.get('audio') for s in state['scenes']))
        source=json.loads((ROOT/'outputs/first-film/full/assets/production_manifest.json').read_text(encoding='utf-8'))
        eligible=sum(s['index'] in values['PLAN']['export_shots'] and
            s['generation']['prompt']==values['PLAN']['shots'][s['index']]['prompt'] for s in source['shots'])
        self.assertEqual(len(list((directory/'images').glob('*.png'))),eligible)


if __name__=='__main__':
    unittest.main(verbosity=2)
