"""CPU-only workflow/provenance checks; not substitutes for GPU/visual review."""
import copy
import unittest
from assets import graph
from select_assets import validate


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.job={'id':'shot-038','size':[1536,864],'seed':42,'prompt':'ONE Jess',
                  'prompt_revision':3,'references':[
                      {'image':'scene.png','size':[1536,864]},
                      {'image':'jess.png','size':[768,768]}]}
        self.selection={'decision':'select_for_workprint','id':'shot-038',
                        'sha256':'abc','review_notes':'Reviewed count and hands.',
                        'user_approved':False}
        self.report={'id':'shot-038','sha256':'abc'}

    def test_fast_steps(self):
        g=graph(self.job,'fast')
        self.assertEqual(g['9']['inputs']['steps'],4)
        self.assertEqual(g['10']['inputs']['cfg'],1)

    def test_base_is_separate(self):
        g=graph(self.job,'quality')
        self.assertEqual(g['9']['inputs']['steps'],28)
        self.assertEqual(g['10']['inputs']['cfg'],5)
        self.assertIn('base-4b',g['1']['inputs']['unet_name'])

    def test_both_conditioning_paths_have_references(self):
        g=graph(self.job,'quality')
        for slot in ('positive','negative'):
            current=g['10']['inputs'][slot][0]
            count=0
            while g[current]['class_type']=='ReferenceLatent':
                count+=1
                current=g[current]['inputs']['conditioning'][0]
            self.assertEqual(count,2)

    def test_generation_does_not_overwrite_scene(self):
        g=graph(self.job,'fast')
        self.assertEqual(g['6']['inputs']['width'],1536)
        self.assertEqual(g['6']['inputs']['height'],864)
        self.assertEqual(g['13']['inputs']['filename_prefix'],'v6/shot-038-fast-r3')

    def test_select_with_explicit_review(self):
        self.assertTrue(validate(self.selection,self.report))

    def test_reject_cannot_install(self):
        item=copy.deepcopy(self.selection);item['decision']='reject'
        with self.assertRaises(ValueError):validate(item,self.report)

    def test_hash_mismatch(self):
        item=copy.deepcopy(self.selection);item['sha256']='changed'
        with self.assertRaises(ValueError):validate(item,self.report)

    def test_cannot_invent_user_approval(self):
        item=copy.deepcopy(self.selection);item['user_approved']=True
        with self.assertRaises(ValueError):validate(item,self.report)

    def test_path_like_id_rejected(self):
        item=copy.deepcopy(self.selection);item['id']='../checkpoint'
        report=copy.deepcopy(self.report);report['id']=item['id']
        with self.assertRaises(ValueError):validate(item,report)


if __name__=='__main__':unittest.main()
