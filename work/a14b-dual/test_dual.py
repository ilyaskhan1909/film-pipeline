"""CPU tests only: scheduler continuity, CFG, attention equivalence, GPU map."""
import contextlib
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'animation-pilot'))
spec = importlib.util.spec_from_file_location('a14b_worker', HERE / 'worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class FakeExpert:
    def __init__(self, stage):
        self.stage = stage

    def cache_context(self, name):
        return contextlib.nullcontext()

    def __call__(self, hidden_states, timestep, encoder_hidden_states, return_dict):
        # Nonconstant prediction exercises CFG and the unchanged latents.
        scale = 2 if self.stage == 'high' else 1
        return (hidden_states[:, :1] * .1 + encoder_hidden_states.mean() * scale,)


class FakeScheduler:
    config = SimpleNamespace(num_train_timesteps=1000)

    def __init__(self):
        self.set_count = 0
        self.step_count = 0

    def set_timesteps(self, steps, device):
        self.set_count += 1
        self.timesteps = torch.tensor([1000., 950., 850., 0.], device=device)

    def step(self, prediction, timestep, latents, return_dict):
        self.step_count += 1
        # Stateful update catches a restarted multistep schedule.
        return (latents - prediction * (self.step_count / 100),)


class DualTests(unittest.TestCase):
    def test_scheduler_and_cfg_match_reference(self):
        initial = torch.ones(1, 1, 2, 2, 2)
        condition = torch.zeros_like(initial)
        positive, negative = torch.ones(1, 4, 4), torch.zeros(1, 4, 4)
        loads, releases, steps = [], [], []
        scheduler = FakeScheduler()
        def load(stage):
            loads.append(stage)
            return FakeExpert(stage)
        actual = worker.denoise(scheduler, initial.clone(), condition, positive, negative,
            4, 3.5, .9, load, lambda model, stage: releases.append(stage),
            lambda index, timestep, stage, values: steps.append(stage))
        reference_scheduler = FakeScheduler()
        reference_scheduler.set_timesteps(4, 'cpu')
        expected = initial.clone()
        for timestep in reference_scheduler.timesteps:
            stage = 'high' if timestep >= 900 else 'low'
            model = FakeExpert(stage)
            inputs = torch.cat([expected, condition], dim=1)
            conditional = model(inputs, timestep, positive, False)[0]
            unconditional = model(inputs, timestep, negative, False)[0]
            expected = reference_scheduler.step(unconditional + 3.5 *
                (conditional - unconditional), timestep, expected, False)[0]
        self.assertTrue(torch.equal(actual, expected))
        self.assertEqual(scheduler.set_count, 1)
        self.assertEqual(scheduler.step_count, 4)
        self.assertEqual(loads, ['high', 'low'])
        self.assertEqual(releases, ['high', 'low'])
        self.assertEqual(steps, ['high', 'high', 'low', 'low'])

    def test_exact_boundary(self):
        self.assertEqual(worker.stage_for(900, 900), 'high')
        self.assertEqual(worker.stage_for(899.99, 900), 'low')

    def test_map_covers_two_gpus_without_cpu_blocks(self):
        mapping = worker.device_map_for()
        self.assertEqual({mapping[f'blocks.{i}'] for i in range(40)}, {0, 1})
        self.assertEqual(sum(mapping[f'blocks.{i}'] == 0 for i in range(40)), 20)
        self.assertEqual(mapping[''], 0)
        self.assertEqual(mapping['proj_out'], 1)

    def test_attention_matches_dense_with_mask(self):
        original = torch.nn.functional.scaled_dot_product_attention
        torch.manual_seed(8)
        q, k, v = [torch.randn(1, 2, 17, 8) for _ in range(3)]
        mask = torch.randn(17, 17) * .1
        expected = original(q, k, v, attn_mask=mask)
        worker.install_chunked_attention(4)
        try:
            actual = torch.nn.functional.scaled_dot_product_attention(q, k, v, attn_mask=mask)
        finally:
            torch.nn.functional.scaled_dot_product_attention = original
        self.assertTrue(torch.allclose(actual, expected, atol=1e-6, rtol=1e-5))

    def test_failure_releases_model(self):
        released = []
        class BadExpert(FakeExpert):
            def __call__(self, hidden_states, *args, **kwargs):
                return (hidden_states[:, :1] * float('nan'),)
        with self.assertRaises(ValueError):
            worker.denoise(FakeScheduler(), torch.ones(1, 1, 2, 2, 2),
                torch.zeros(1, 1, 2, 2, 2), torch.ones(1, 2, 2), torch.zeros(1, 2, 2),
                4, 3.5, .9, lambda stage: BadExpert(stage),
                lambda model, stage: released.append(stage), lambda *args: None)
        self.assertEqual(released, ['high'])


if __name__ == '__main__':
    unittest.main()
