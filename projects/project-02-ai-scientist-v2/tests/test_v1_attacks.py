"""Attack correctness checks with analytical/numerical gradients, no downloads."""

import unittest

import torch
from torch import nn

from course_tools.v1_attacks import AttackConfig, bsr_transform, run_attack


def generator(seed):
    return torch.Generator(device="cpu").manual_seed(seed)


class SumClassifier(nn.Module):
    def forward(self, x):
        score = x.flatten(1).sum(1)
        return torch.stack((score, -score), dim=1)


class AttackTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.x = torch.rand((3, 3, 6, 6), generator=generator(12)) * 0.6 + 0.2
        self.y = torch.tensor([0, 1, 2], dtype=torch.int64)
        self.model = nn.Sequential(nn.Flatten(), nn.Linear(108, 3))
        with torch.no_grad():
            self.model[1].weight.copy_(torch.randn((3, 108), generator=generator(9)) * 0.1)
            self.model[1].bias.zero_()

    def config(self, method="mi", views=1, steps=3, **kwargs):
        return AttackConfig("test", method, steps, views, 8/255, (8/255)/steps, **kwargs)

    def test_one_step_direction_and_projection_match_analytical_attack(self):
        x = torch.tensor([0.0, 0.005, 0.5, 0.999]).reshape(1, 1, 2, 2)
        config = AttackConfig("closed_form", "mi", 1, 1, 0.1, 0.2)
        adversarial, metrics = run_attack(SumClassifier(), x, torch.tensor([0]), config, 0)
        torch.testing.assert_close(adversarial, (x - 0.1).clamp(0, 1))
        self.assertEqual(metrics["gradient_evaluations_per_image"], 1)

    def test_zero_budget_preserves_pixels_even_with_positive_step(self):
        config = AttackConfig("zero", "mi", 4, 1, 0, 0.1)
        adversarial, metrics = run_attack(self.model, self.x, self.y, config, 42)
        torch.testing.assert_close(adversarial, self.x, rtol=0, atol=0)
        self.assertEqual(metrics["max_linf"], 0)

    def test_shuffle_gradient_is_mapped_back_to_original_coordinates(self):
        x = torch.arange(36, dtype=torch.float64).reshape(1, 1, 6, 6).requires_grad_(True)
        weights = torch.arange(1, 37, dtype=torch.float64).reshape_as(x)
        transformed = bsr_transform(x, generator(19), blocks=2, rotation_degrees=0)
        gradient, = torch.autograd.grad((transformed * weights).sum(), x)
        expected = torch.zeros(36, dtype=x.dtype)
        expected.scatter_(0, transformed.detach().flatten().long(), weights.flatten())
        torch.testing.assert_close(gradient.flatten(), expected, rtol=0, atol=0)
        self.assertFalse(torch.equal(gradient, weights))

    def test_rotation_gradient_matches_finite_difference(self):
        x = torch.rand((1, 1, 6, 6), dtype=torch.float64, generator=generator(4)).requires_grad_(True)
        weights = torch.randn(x.shape, dtype=torch.float64, generator=generator(2))

        def objective(value):
            return (bsr_transform(value, generator(13), blocks=2, rotation_degrees=10) * weights).sum()

        gradient, = torch.autograd.grad(objective(x), x)
        index = (0, 0, 3, 3)
        upper, lower = x.detach().clone(), x.detach().clone()
        upper[index] += 1e-5
        lower[index] -= 1e-5
        finite_difference = (objective(upper) - objective(lower)) / 2e-5
        torch.testing.assert_close(gradient[index], finite_difference, rtol=1e-6, atol=1e-7)
        self.assertGreater(gradient.abs().sum().item(), 0)

    def test_identity_bsr_one_and_multiple_views_reduce_to_mi(self):
        baseline, _ = run_attack(self.model, self.x, self.y, self.config(), 42)
        for views in (1, 4):
            with self.subTest(views=views):
                actual, metrics = run_attack(
                    self.model, self.x, self.y, self.config("bsr", views), 42,
                    transform=lambda value, rng: value,
                )
                torch.testing.assert_close(actual, baseline, rtol=0, atol=1e-7)
                self.assertEqual(metrics["gradient_evaluations_per_image"], 3 * views)
                self.assertEqual(metrics["sample_view_gradient_evaluations"], 3 * views * 3)
                self.assertEqual(metrics["backward_calls"], 3 * views)

    def test_actual_view_calls_are_counted_and_constraints_hold(self):
        calls = []

        def transformed(value, rng):
            calls.append(True)
            return value.flip(-1)

        config = self.config("bsr", views=4, steps=5)
        actual, metrics = run_attack(self.model, self.x, self.y, config, 0, transform=transformed)
        self.assertEqual(len(calls), 20)
        self.assertEqual(metrics["gradient_evaluations_per_image"], len(calls))
        self.assertEqual(metrics["sample_view_gradient_evaluations"], len(calls) * len(self.x))
        self.assertLessEqual((actual - self.x).abs().max().item(), config.epsilon + 1e-6)
        self.assertGreaterEqual(actual.min().item(), 0)
        self.assertLessEqual(actual.max().item(), 1)
        self.assertFalse(actual.requires_grad)

    def test_bsr_seed_is_repeatable_without_consuming_global_rng(self):
        config = self.config("bsr", views=2)
        before = torch.random.get_rng_state()
        actual, metrics = run_attack(self.model, self.x, self.y, config, 18)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        torch.manual_seed(928)
        repeated, repeated_metrics = run_attack(self.model, self.x, self.y, config, 18)
        torch.testing.assert_close(repeated, actual, rtol=0, atol=0)
        self.assertEqual(metrics, repeated_metrics)

    def test_bsr_geometry_is_shared_in_batch_and_preserves_shape(self):
        batch = self.x[:1].expand(2, -1, -1, -1)
        transformed = bsr_transform(batch, generator(5))
        self.assertEqual(transformed.shape, batch.shape)
        torch.testing.assert_close(transformed[0], transformed[1], rtol=0, atol=0)

    def test_weights_and_parameter_gradients_are_not_changed(self):
        original = {key: value.clone() for key, value in self.model.state_dict().items()}
        self.model.train()
        run_attack(self.model, self.x, self.y, self.config(), 0)
        self.assertFalse(self.model.training)
        for key, value in self.model.state_dict().items():
            torch.testing.assert_close(value, original[key], rtol=0, atol=0)
        self.assertTrue(all(parameter.grad is None for parameter in self.model.parameters()))

    def test_nonfinite_model_output_is_rejected(self):
        class Broken(nn.Module):
            def forward(self, x):
                return x.flatten(1)[:, :3] * float("nan")

        with self.assertRaisesRegex(FloatingPointError, "model logits"):
            run_attack(Broken(), self.x, self.y, self.config(), 0)

    def test_invalid_configurations_are_rejected(self):
        valid = dict(name="test", method="mi", steps=2, views=1, epsilon=0.1, alpha=0.05)
        for changes in (
            {"steps": 0}, {"steps": True}, {"views": 4}, {"alpha": 0},
            {"epsilon": -0.1}, {"epsilon": float("nan")}, {"method": "unknown"},
            {"rotation_degrees": float("inf")}, {"blocks": 0},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                AttackConfig(**(valid | changes))

    def test_invalid_pixels_labels_and_shapes_are_rejected(self):
        for x, y in (
            (self.x + 2, self.y), (self.x * float("nan"), self.y),
            (self.x, self.y.float()), (self.x, self.y[:1]),
            (self.x[0], self.y),
        ):
            with self.subTest(x_shape=x.shape, y_shape=y.shape), self.assertRaises((ValueError, FloatingPointError)):
                run_attack(self.model, x, y, self.config(), 0)
        with self.assertRaisesRegex(ValueError, "spatial dimensions"):
            bsr_transform(self.x, generator(0), blocks=7)
        with self.assertRaisesRegex(ValueError, "preserve"):
            run_attack(
                self.model, self.x, self.y, self.config("bsr", 1), 0,
                transform=lambda value, rng: value[..., :1],
            )


if __name__ == "__main__":
    unittest.main()
