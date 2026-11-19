"""Check trust boundaries and differentiable pixel normalization, offline."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch
from torch import nn

from course_tools import v1_assets as assets


def digest(value):
    return hashlib.sha256(value).hexdigest()


class AssetChecks(unittest.TestCase):
    def test_cached_valid_asset_is_checked_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checked.py"
            path.write_bytes(b"reviewed source\n")
            with patch.object(assets.urllib.request, "urlopen", side_effect=AssertionError("offline")) as request:
                result = assets._fetch_checked("https://example.test/source", path, digest(path.read_bytes()), False)
            self.assertEqual(result, digest(path.read_bytes()))
            request.assert_not_called()

    def test_missing_offline_asset_does_not_attempt_download(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.pt"
            with patch.object(assets.urllib.request, "urlopen", side_effect=AssertionError("offline")) as request:
                with self.assertRaises(FileNotFoundError):
                    assets._fetch_checked("https://example.test/weights", path, "0" * 64, False)
            request.assert_not_called()
            self.assertFalse(path.exists())

    def test_full_hash_is_enforced_even_if_published_prefix_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.pt"
            path.write_bytes(b"cached weights")
            actual = digest(path.read_bytes())
            wrong_full_hash = actual[:-1] + ("0" if actual[-1] != "0" else "1")
            with patch.object(assets.urllib.request, "urlopen", side_effect=AssertionError("must not replace cache")):
                with self.assertRaisesRegex(ValueError, "cached asset"):
                    assets._fetch_checked("https://example.test/weights", path, wrong_full_hash, True)
            self.assertEqual(path.read_bytes(), b"cached weights")

    def test_corrupt_download_is_never_published_as_a_valid_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weights.pt"
            with patch.object(assets.urllib.request, "urlopen", return_value=io.BytesIO(b"corrupt")):
                with self.assertRaisesRegex(ValueError, "downloaded asset"):
                    assets._fetch_checked("https://example.test/weights", path, digest(b"expected"), True)
            self.assertFalse(path.exists())

    def test_normalization_is_inside_the_differentiable_model(self):
        model = assets.PixelSpaceModel(nn.Identity(), {"name": "test"})
        mean = torch.tensor(assets.MEAN).reshape(1, 3, 1, 1)
        std = torch.tensor(assets.STD).reshape(1, 3, 1, 1)
        pixels = mean.expand(2, 3, 4, 4).clone().requires_grad_(True)
        torch.testing.assert_close(model(pixels), torch.zeros_like(pixels))
        gradient, = torch.autograd.grad(model(pixels).sum(), pixels)
        torch.testing.assert_close(gradient, (1 / std).expand_as(pixels))
        torch.testing.assert_close(model(mean + std), torch.ones_like(mean))

    def test_safe_weight_load_freezes_model_but_keeps_input_gradients(self):
        source = b"from torch import nn\ndef cifar10_asset_test(pretrained=False):\n    return nn.Sequential(nn.Conv2d(3, 10, 1), nn.AdaptiveAvgPool2d(1), nn.Flatten())\n"
        name = "cifar10_asset_test"
        source_name = "pytorch_cifar_models/offline_fixture.py"
        module_name = f"course_v1_offline_fixture_{assets.MODEL_COMMIT}"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = assets._source_directory(root) / source_name
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(source)
            weights = assets._cache(root) / "weights" / "fixture.pt"
            weights.parent.mkdir()
            torch.manual_seed(7)
            model = nn.Sequential(nn.Conv2d(3, 10, 1), nn.AdaptiveAvgPool2d(1), nn.Flatten())
            torch.save(model.state_dict(), weights)
            spec = {"source": source_name, "weight_url": "https://example.test/fixture.pt",
                    "published_sha256_prefix": assets.sha256_file(weights)[:8],
                    "expected_weight_sha256": assets.sha256_file(weights)}
            with patch.dict(assets.MODEL_SPECS, {name: spec}), patch.dict(assets.SOURCE_HASHES, {source_name: digest(source)}), \
                    patch.object(assets.urllib.request, "urlopen", side_effect=AssertionError("offline")), \
                    patch.object(torch, "load", wraps=torch.load) as loader:
                loaded = assets.load_model(name, root, "cpu")
                self.assertTrue(loader.call_args.kwargs["weights_only"])
                self.assertFalse(loaded.training)
                self.assertTrue(all(not parameter.requires_grad for parameter in loaded.parameters()))
                pixels = torch.full((2, 3, 4, 4), 0.5, requires_grad=True)
                logits = loaded(pixels)
                gradient, = torch.autograd.grad(logits.square().sum(), pixels)
                self.assertTrue(torch.isfinite(gradient).all())
                self.assertGreater(float(gradient.abs().sum()), 0)
                self.assertTrue(all(parameter.grad is None for parameter in loaded.parameters()))
            sys.modules.pop(module_name, None)


if __name__ == "__main__":
    unittest.main()
