"""CPU invariants only, not an image-quality test."""
import unittest
import style_lab as lab


class StyleComparisonTests(unittest.TestCase):
    def test_controlled_matrix(self):
        self.assertEqual(len(lab.STYLES) * len(lab.SCENES), 12)

    def test_medium_is_explicit(self):
        for spec in lab.STYLES.values():
            self.assertIn('entire scene', spec['prompt'])
            self.assertIn('matte', spec['prompt'])

    def test_people_and_clue_invariants(self):
        self.assertEqual(lab.SCENES['shot-039']['people'], ['chloe', 'jess'])
        self.assertIn('cobalt-blue', lab.SCENES['shot-062']['intent'])
        self.assertIn('Exactly ONE', lab.SCENES['shot-029']['intent'])

    def test_graph_does_not_write_v6(self):
        job = {'id': 'ink-shot-029', 'size': [1536, 864], 'seed': 10,
            'prompt': 'A matte ink drawing.', 'prompt_revision': 1, 'references': []}
        nodes = lab.make_graph(job)
        self.assertEqual(nodes['13']['inputs']['filename_prefix'], 'v7/ink-shot-029-r1')
        self.assertEqual(nodes['9']['inputs']['steps'], 4)
        self.assertEqual(nodes['10']['inputs']['cfg'], 1.0)

    def test_human_style_does_not_leak_into_props(self):
        for prompt in lab.OBJECT_STYLES.values():
            self.assertNotIn('expressive faces', prompt)
            self.assertNotIn('adult anatomy', prompt)
            self.assertNotIn('natural eyes', prompt)
        self.assertIn('featureless', lab.OBJECT_INTENTS['shot-060'])


if __name__ == '__main__':
    unittest.main()
