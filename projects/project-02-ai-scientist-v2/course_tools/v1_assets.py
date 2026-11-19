"""Pinned, reviewed CIFAR model assets for the course V1 benchmark.

No torch.hub repository entrypoint is executed. Only the three reviewed model
definitions are imported after checking their full source SHA256. The cached
upstream files retain their copyright notices and accompanying BSD license.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import urllib.request

import torch
from torch import nn
from torchvision.datasets import CIFAR10
from torchvision.transforms import ToTensor


MODEL_REPO = "https://github.com/chenyaofo/pytorch-cifar-models"
MODEL_COMMIT = "786c16252c0fc58ee9adac063f8337cc4a7a497a"
PREPROCESSING_COMMIT = "610e6523ab462351700aaf629e6c739a9a30e903"
PREPROCESSING_URL = (
    "https://raw.githubusercontent.com/chenyaofo/image-classification-codebase/"
    f"{PREPROCESSING_COMMIT}/conf/cifar10.conf"
)
PREPROCESSING_SHA256 = "31fe87685702e3939c9df52975925e50bae013fad196d2fd523347c41e220686"
MEAN = (0.4914, 0.4822, 0.4465)
STD = (0.2023, 0.1994, 0.2010)
SOURCE_HASHES = {
    "LICENSE": "0eab51837bca1227951f45df5d2c4e07c5fc9926862d758ab3fe629ff31b04bc",
    "pytorch_cifar_models/resnet.py": "885b8fd2ccfb8ee27c02d3a382e2951622fdcbc2af2bbca375aaf71d40f5f246",
    "pytorch_cifar_models/mobilenetv2.py": "8d78f491e55286754c0faad9f70fac8e329f7073c930d7aa68962cb2aae69938",
    "pytorch_cifar_models/vgg.py": "5562540e312da9184ff2e4ebc290dc68a9aec1e2a3f5b1e395b9cab4d7e8c3e5",
}
MODEL_SPECS = {
    "cifar10_resnet20": {
        "source": "pytorch_cifar_models/resnet.py",
        "weight_url": f"{MODEL_REPO}/releases/download/resnet/cifar10_resnet20-4118986f.pt",
        "published_sha256_prefix": "4118986f",
        "expected_weight_sha256": "4118986f0df73003d572b0e397f0ac7b3f60af1f31aff3d2da164536e36f6ec8",
        "author_test_top1_percent": 92.60,
    },
    "cifar10_mobilenetv2_x1_0": {
        "source": "pytorch_cifar_models/mobilenetv2.py",
        "weight_url": f"{MODEL_REPO}/releases/download/mobilenetv2/cifar10_mobilenetv2_x1_0-fe6a5b48.pt",
        "published_sha256_prefix": "fe6a5b48",
        "expected_weight_sha256": "fe6a5b4808c9b1b7a440c02fa19a10dc3d8ea5c63e38381b2f60b1937958735e",
        "author_test_top1_percent": 93.79,
    },
    "cifar10_vgg11_bn": {
        "source": "pytorch_cifar_models/vgg.py",
        "weight_url": f"{MODEL_REPO}/releases/download/vgg/cifar10_vgg11_bn-eaeebf42.pt",
        "published_sha256_prefix": "eaeebf42",
        "expected_weight_sha256": "eaeebf42370c92fdfbb5dbe8eba7c27d4eb7366a1dca0b5be435364ccdf54378",
        "author_test_top1_percent": 92.79,
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch_checked(url: str, destination: Path, expected: str, download: bool) -> str:
    """Check full source hashes or the weight prefix published in its filename."""
    if not destination.is_file():
        if not download:
            raise FileNotFoundError(f"Missing V1 asset: {destination}. Run the prepare command first.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".part")
        request = urllib.request.Request(url, headers={"User-Agent": "course-v1-assets/1.0"})
        with urllib.request.urlopen(request, timeout=90) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        digest = sha256_file(partial)
        if not digest.startswith(expected):
            raise ValueError(f"SHA256 mismatch for downloaded asset {destination.name}: {digest}")
        partial.replace(destination)
    digest = sha256_file(destination)
    if not digest.startswith(expected):
        raise ValueError(f"SHA256 mismatch for cached asset {destination.name}: {digest}")
    return digest


def _cache(root: Path) -> Path:
    return Path(root).resolve() / "cache" / "v1"


def _source_directory(root: Path) -> Path:
    return _cache(root) / f"pytorch-cifar-models-{MODEL_COMMIT}"


def _asset_metadata(name: str, root: Path) -> dict:
    spec = MODEL_SPECS[name]
    weight_path = _cache(root) / "weights" / spec["weight_url"].rsplit("/", 1)[1]
    source_path = _source_directory(root) / spec["source"]
    return {
        "name": name,
        **spec,
        "weight_relative_path": str(weight_path.relative_to(Path(root).resolve())),
        "weight_sha256": _fetch_checked(spec["weight_url"], weight_path, spec["expected_weight_sha256"], False),
        "source_sha256": _fetch_checked("", source_path, SOURCE_HASHES[spec["source"]], False),
        "code_repository": MODEL_REPO,
        "code_commit": MODEL_COMMIT,
        "license": "BSD-3-Clause; upstream source retains its notices",
        "input_space": "RGB float32 [0,1], BCHW, 32x32",
        "normalization": {"mean": list(MEAN), "std": list(STD), "source": PREPROCESSING_URL, "config_sha256": PREPROCESSING_SHA256},
    }


def prepare_assets(root: Path, download: bool = True) -> dict:
    """Fetch/check model definitions, weights and the official CIFAR-10 dataset."""
    root = Path(root).resolve()
    source_dir = _source_directory(root)
    sources = {}
    for relative, expected in SOURCE_HASHES.items():
        url = f"https://raw.githubusercontent.com/chenyaofo/pytorch-cifar-models/{MODEL_COMMIT}/{relative}"
        digest = _fetch_checked(url, source_dir / relative, expected, download)
        sources[relative] = {"url": url, "sha256": digest}
        print(f"Checked model source: {relative}", flush=True)
    for name, spec in MODEL_SPECS.items():
        path = _cache(root) / "weights" / spec["weight_url"].rsplit("/", 1)[1]
        _fetch_checked(spec["weight_url"], path, spec["expected_weight_sha256"], download)
        print(f"Checked model weights: {name}", flush=True)
    _fetch_checked(PREPROCESSING_URL, _cache(root) / "cifar10.conf", PREPROCESSING_SHA256, download)

    # torchvision checks the official archive/file MD5 values before loading.
    load_cifar(root, train=True, download=download)
    load_cifar(root, train=False, download=False)
    data_dir = root / "data" / CIFAR10.base_folder
    dataset_hashes = {
        path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(data_dir.iterdir()) if path.is_file()
    }
    acquisition_path = _cache(root) / "download-provenance.json"
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8")) if acquisition_path.is_file() else {}
    manifest = {
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_repository": MODEL_REPO,
        "model_commit": MODEL_COMMIT,
        "sources": sources,
        "acquisition": acquisition,
        "models": {name: _asset_metadata(name, root) for name in MODEL_SPECS},
        "dataset": {
            "name": "CIFAR-10",
            "url": CIFAR10.url,
            "official_archive_md5": CIFAR10.tgz_md5,
            "archive_sha256": sha256_file(root / "data" / CIFAR10.filename),
            "relative_path": "data/" + CIFAR10.base_folder,
            "files": dataset_hashes,
            "loader": "torchvision.datasets.CIFAR10; ToTensor only",
        },
    }
    manifest_path = _cache(root) / "assets-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


class PixelSpaceModel(nn.Module):
    """Keep the attack and its epsilon in raw pixel coordinates."""

    def __init__(self, model: nn.Module, metadata: dict):
        super().__init__()
        self.model = model
        self.register_buffer("mean", torch.tensor(MEAN).reshape(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(STD).reshape(1, 3, 1, 1))
        self.asset_metadata = metadata

    def forward(self, pixels: torch.Tensor) -> torch.Tensor:
        return self.model((pixels - self.mean) / self.std)


def load_model(name: str, root: Path, device: str | torch.device = "cpu") -> nn.Module:
    """Return a frozen eval model, normalized inside its differentiable wrapper."""
    if name not in MODEL_SPECS:
        raise ValueError(f"Unknown V1 model {name!r}; available: {sorted(MODEL_SPECS)}")
    root = Path(root).resolve()
    metadata = _asset_metadata(name, root)
    source_path = _source_directory(root) / MODEL_SPECS[name]["source"]
    module_name = f"course_v1_{source_path.stem}_{MODEL_COMMIT}"
    if module_name not in sys.modules:
        module_spec = importlib.util.spec_from_file_location(module_name, source_path)
        if module_spec is None or module_spec.loader is None:
            raise ImportError(f"Cannot load checked model definition {source_path}")
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)
    module = sys.modules[module_name]
    constructor = getattr(module, name)
    model = constructor(pretrained=False)
    weights = root / metadata["weight_relative_path"]
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    wrapped = PixelSpaceModel(model, metadata).to(device).eval()
    wrapped.requires_grad_(False)
    return wrapped


def load_cifar(root: Path, train: bool, download: bool = False) -> CIFAR10:
    return CIFAR10(root=str(Path(root).resolve() / "data"), train=train, transform=ToTensor(), download=download)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare pinned assets for the course V1 benchmark")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--offline", action="store_true", help="Only verify already downloaded assets")
    args = parser.parse_args()
    result = prepare_assets(args.root, download=not args.offline)
    print(json.dumps(result, indent=2))
