"""CPU safety and prompt invariants. No automatic artistic approval."""
import unittest
import pipeline as p


class PipelineTests(unittest.TestCase):
    def test_native_graph_is_scoped(self):
        job = {'id': 'mark-front', 'size': [1024, 1024], 'seed': 1,
            'prompt': 'Ink illustration.', 'prompt_revision': 1, 'references': []}
        graph = p.make_graph(job)
        self.assertEqual(graph['13']['inputs']['filename_prefix'], 'v8/mark-front-r1')
        self.assertEqual(graph['10']['inputs']['cfg'], 1.0)
        self.assertEqual(graph['9']['inputs']['steps'], 4)

    def test_reference_count_is_bounded(self):
        with self.assertRaises(ValueError):
            p.make_graph({'id': 'test', 'references': [None] * 5})

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            p.make_graph({'id': '../v6', 'references': []})

    def test_pilot_is_contiguous(self):
        self.assertEqual(p.PILOT_SHOTS, [f'shot-{i:03}' for i in range(37, 45)])
        self.assertEqual(set(p.PILOT_SHOTS + p.MARK_PROBES), set(p.SHOT_ACTIONS))

    def test_object_style_has_no_human_face_description(self):
        self.assertNotIn('adult eyes', p.OBJECT_INK)
        self.assertNotIn('individual faces', p.OBJECT_INK)

    def test_wardrobe_does_not_leak_between_characters(self):
        self.assertNotIn('cobalt', p.PEOPLE['chloe']['wardrobe'])
        self.assertIn('OLIVE', p.PEOPLE['jess']['wardrobe'])
        self.assertNotIn('Mark', p.SHOT_ACTIONS['shot-039'])


if __name__ == '__main__':
    unittest.main()
