"""Fixed, reviewed MI-FGSM and BSR attacks for the course V1 benchmark.

Inputs and perturbation bounds are always in raw [0, 1] pixel space. The caller
supplies a source model whose wrapper performs the model's normalization. No
target model is accepted by this module.

The BSR mechanism follows the authors' linked PyTorch reference:
https://github.com/Trustworthy-AI-Group/TransferAttack/blob/main/transferattack/input_transformation/bsr.py
This independently implemented CIFAR adaptation enforces nonempty strips and
uses its own CPU generator. Transform parameters are shared within a batch.
"""

from dataclasses import dataclass
import math
from typing import Callable

import torch
from torch import Tensor, nn
import torch.nn.functional as F
from torchvision.transforms import InterpolationMode
from torchvision.transforms.functional import rotate


@dataclass(frozen=True)
class AttackConfig:
    name: str
    method: str
    steps: int
    views: int
    epsilon: float
    alpha: float
    decay: float = 1.0
    blocks: int = 2
    rotation_degrees: float = 10.0

    def __post_init__(self):
        if not self.name or self.method not in {"mi", "bsr"}:
            raise ValueError("An attack needs a name and method 'mi' or 'bsr'.")
        for key in ("steps", "views", "blocks"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{key} must be a positive integer.")
        for key in ("epsilon", "alpha", "decay", "rotation_degrees"):
            if not math.isfinite(getattr(self, key)):
                raise ValueError(f"{key} must be finite.")
        if not 0 <= self.epsilon <= 1 or self.alpha <= 0 or self.decay < 0:
            raise ValueError("Require epsilon in [0, 1], alpha > 0, decay >= 0.")
        if not 0 <= self.rotation_degrees <= 180:
            raise ValueError("rotation_degrees must be in [0, 180].")
        if self.method == "mi" and self.views != 1:
            raise ValueError("MI-FGSM uses one untransformed view per step.")


def _positive_lengths(length: int, blocks: int, generator: torch.Generator):
    """Random nonuniform partition, with at least one pixel per strip.

    Reserve one pixel per strip, then apportion the remainder by random
    proportions and largest fractional remainders. This differs from the
    reference's rounding specifically to prevent empty CIFAR-size strips.
    """
    if blocks > length:
        raise ValueError("blocks cannot exceed the image's spatial dimensions.")
    weights = torch.rand(blocks, generator=generator, device="cpu", dtype=torch.float64)
    weights = weights + torch.finfo(weights.dtype).eps
    shares = weights / weights.sum() * (length - blocks)
    extras = shares.floor().to(torch.int64)
    remaining = length - blocks - int(extras.sum().item())
    if remaining:
        indices = torch.argsort(shares - extras, descending=True)[:remaining]
        extras[indices] += 1
    return (extras + 1).tolist()


def _shuffled_strips(x: Tensor, axis: int, blocks: int, generator: torch.Generator):
    pieces = x.split(_positive_lengths(x.shape[axis], blocks, generator), dim=axis)
    order = torch.randperm(blocks, generator=generator, device="cpu").tolist()
    return [pieces[index] for index in order]


def bsr_transform(
    x: Tensor,
    generator: torch.Generator,
    blocks: int = 2,
    rotation_degrees: float = 10.0,
) -> Tensor:
    """Shuffle strips, rotate each strip, shuffle its other axis, and rejoin.

    Bilinear rotation keeps each strip's canvas (expand=False), has zero fill,
    and remains differentiable with respect to x. The returned image has the
    original shape. All randomness is drawn from the provided CPU generator;
    every image in a batch receives the same sampled geometry.
    """
    if x.ndim != 4 or not x.is_floating_point():
        raise ValueError("BSR needs a floating NCHW tensor.")
    if not isinstance(blocks, int) or isinstance(blocks, bool) or blocks < 1:
        raise ValueError("blocks must be a positive integer.")
    if min(x.shape[-2:]) < blocks:
        raise ValueError("blocks cannot exceed the image's spatial dimensions.")
    if not math.isfinite(rotation_degrees) or not 0 <= rotation_degrees <= 180:
        raise ValueError("rotation_degrees must be finite and in [0, 180].")
    if generator.device.type != "cpu":
        raise ValueError("BSR uses an independent CPU random generator.")
    axes = [2 + index for index in torch.randperm(2, generator=generator).tolist()]
    transformed = []
    for strip in _shuffled_strips(x, axes[0], blocks, generator):
        angle = (2 * torch.rand((), generator=generator).item() - 1) * rotation_degrees
        if rotation_degrees:
            strip = rotate(
                strip, angle, interpolation=InterpolationMode.BILINEAR,
                expand=False, fill=0.0,
            )
        transformed.append(torch.cat(_shuffled_strips(strip, axes[1], blocks, generator), dim=axes[1]))
    return torch.cat(transformed, dim=axes[0])


def _require_finite(value: Tensor, description: str):
    if not torch.isfinite(value).all().item():
        raise FloatingPointError(f"Nonfinite {description} in V1 attack.")


@torch.enable_grad()
def run_attack(
    model: nn.Module,
    x: Tensor,
    y: Tensor,
    config: AttackConfig,
    seed: int,
    *,
    transform: Callable[[Tensor, torch.Generator], Tensor] | None = None,
):
    """Generate untargeted examples, returning ``(adversarial_pixels, metrics)``.

    ``transform`` is an optional BSR view function for correctness diagnostics,
    such as testing an identity transform. Production BSR uses bsr_transform.
    Each view has its own forward/autograd.grad call. Losses sum over images,
    and view gradients are averaged *before* per-image normalization and sign.
    Model parameters are neither updated nor assigned gradients.
    """
    if x.ndim != 4 or x.shape[0] < 1 or not x.is_floating_point():
        raise ValueError("x must be a nonempty floating NCHW batch.")
    if y.shape != (x.shape[0],) or y.dtype != torch.int64 or y.device != x.device:
        raise ValueError("y must contain one int64 label per image on x's device.")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**63:
        raise ValueError("seed must be an integer in [0, 2**63).")
    if transform is not None and config.method != "bsr":
        raise ValueError("A custom view transform is only valid for BSR diagnostics.")
    _require_finite(x, "input")
    if x.min().item() < 0 or x.max().item() > 1:
        raise ValueError("x must be in raw [0, 1] pixel space.")

    model.eval()
    original = x.detach().clone()
    adversarial = original.clone()
    momentum = torch.zeros_like(original)
    generator = torch.Generator(device="cpu").manual_seed(seed)
    gradient_evaluations = 0
    backward_calls = 0

    for _ in range(config.steps):
        current = adversarial.detach().requires_grad_(True)
        average_gradient = torch.zeros_like(current)
        for _ in range(config.views):
            if config.method == "mi":
                view = current
            elif transform is not None:
                view = transform(current, generator)
            else:
                view = bsr_transform(current, generator, config.blocks, config.rotation_degrees)
            if view.shape != current.shape:
                raise ValueError("The view transform must preserve the NCHW shape.")
            _require_finite(view, "transformed input")
            logits = model(view)
            _require_finite(logits, "model logits")
            loss = F.cross_entropy(logits, y, reduction="sum")
            _require_finite(loss, "loss")
            gradient, = torch.autograd.grad(loss, current)
            backward_calls += 1
            gradient_evaluations += 1
            _require_finite(gradient, "input gradient")
            average_gradient.add_(gradient.detach() / config.views)

        _require_finite(average_gradient, "mean input gradient")
        scale = average_gradient.abs().mean(dim=(1, 2, 3), keepdim=True)
        _require_finite(scale, "gradient normalization scale")
        normalized = average_gradient / scale.clamp_min(torch.finfo(current.dtype).tiny)
        momentum = config.decay * momentum + normalized
        _require_finite(momentum, "momentum")
        candidate = current.detach() + config.alpha * momentum.sign()
        delta = (candidate - original).clamp(-config.epsilon, config.epsilon)
        adversarial = (original + delta).clamp(0, 1).detach()

    _require_finite(adversarial, "adversarial pixels")
    per_image_linf = (adversarial - original).abs().flatten(1).amax(1)
    tolerance = 8 * torch.finfo(adversarial.dtype).eps
    if (per_image_linf > config.epsilon + tolerance).any().item():
        raise RuntimeError("Generated pixels exceed the Linf perturbation budget.")
    metrics = {
        "name": config.name,
        "method": config.method,
        "steps": config.steps,
        "views_per_step": config.views,
        "seed": seed,
        "batch_size": x.shape[0],
        "gradient_evaluations_per_image": gradient_evaluations,
        "sample_view_gradient_evaluations": gradient_evaluations * x.shape[0],
        "backward_calls": backward_calls,
        "max_linf": per_image_linf.max().item(),
        "per_image_linf": per_image_linf.cpu().tolist(),
        "pixel_min": adversarial.min().item(),
        "pixel_max": adversarial.max().item(),
        "transform_randomness": "batch_shared_independent_cpu_generator" if config.method == "bsr" else "none",
    }
    return adversarial, metrics
