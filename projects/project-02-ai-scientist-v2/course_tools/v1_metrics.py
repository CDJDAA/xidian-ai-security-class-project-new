"""Metrics for a fixed transfer-attack evaluation set; no model access.

Predictions are integer class IDs. Adversarial predictions may have shape (N,)
or (S, N), where S denotes attack seeds. Seeds are averaged within each image;
they are not independent observations and are never combined as a best-of-S
attack. All bootstrap samples keep methods and seeds paired by image.
"""

import operator

import numpy as np


def _class_ids(values, name, dimensions):
    array = np.asarray(values)
    if array.ndim not in dimensions or array.size == 0:
        raise ValueError(f"{name} must be nonempty with dimension in {dimensions}")
    if array.dtype.kind not in "iuf":
        raise ValueError(f"{name} must contain numeric integer class IDs")
    if not np.isfinite(array).all() or (array < 0).any():
        raise ValueError(f"{name} must contain finite nonnegative class IDs")
    if array.dtype.kind == "f" and (array != np.floor(array)).any():
        raise ValueError(f"{name} must contain integer class IDs")
    # No cast is needed: equality works across numeric integer representations,
    # and avoiding int64 conversion also avoids overflow for large uint64 IDs.
    return array


def _inputs(labels, clean_predictions, adv_predictions):
    labels = _class_ids(labels, "labels", (1,))
    clean = _class_ids(clean_predictions, "clean_predictions", (1,))
    adv = _class_ids(adv_predictions, "adv_predictions", (1, 2))
    if adv.ndim == 1:
        adv = adv[np.newaxis, :]
    if clean.shape != labels.shape or adv.shape[1] != len(labels):
        raise ValueError("All predictions must match the number of labels")
    return labels, clean, adv


def _per_image_success(labels, clean, adv):
    clean_correct = clean == labels
    success = (adv != labels[np.newaxis, :]) & clean_correct[np.newaxis, :]
    return clean_correct, success


def summarise_predictions(labels, clean_predictions, adv_predictions):
    """Return clean/attacked accuracy and clean-correct conditional ASR.

    For S attack seeds, asr_numerator is the mean successful-image count across
    seeds (possibly fractional), not the union of successful attacks. The
    denominator is the same clean-correct image count for every method/seed.
    """
    labels, clean, adv = _inputs(labels, clean_predictions, adv_predictions)
    clean_correct, success = _per_image_success(labels, clean, adv)
    count = len(labels)
    denominator = int(clean_correct.sum())
    numerators = success.sum(axis=1)
    correct_adv = adv == labels[np.newaxis, :]
    numerator = float(numerators.mean())
    if len(adv) == 1:
        numerator = int(numerators[0])
    return {
        "sample_count": count,
        "attack_seed_count": len(adv),
        "clean_accuracy": float(clean_correct.mean()),
        "robust_accuracy": float(correct_adv.mean()),
        "asr_numerator": numerator,
        "asr_denominator": denominator,
        "asr": float(numerator / denominator) if denominator else None,
        "per_seed": [
            {
                "seed_index": index,
                "robust_accuracy": float(correct_adv[index].mean()),
                "asr_numerator": int(value),
                "asr_denominator": denominator,
                "asr": float(value / denominator) if denominator else None,
            }
            for index, value in enumerate(numerators)
        ],
    }


def _nonnegative_integer(value, name, minimum=0):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    try:
        integer = operator.index(value)
    except TypeError as error:
        raise ValueError(f"{name} must be an integer >= {minimum}") from error
    if integer < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return integer


def paired_bootstrap(
    labels, clean_predictions, adv_a, adv_b, *, seed=20261117, n_bootstrap=2000
):
    """Percentile 95% CI for ASR(a)-ASR(b), clustering by input image.

    Both methods use the same resampled image indices, with all attack seeds
    attached to each selected image. Clean-incorrect images stay in the sampling
    set, while each replicate recomputes the clean-correct denominator. A
    replicate with no clean-correct images is skipped and explicitly counted.
    This CI measures image-sampling uncertainty, conditional on the supplied
    models and attack seeds; it does not measure training-run uncertainty.
    """
    labels, clean, adv_a = _inputs(labels, clean_predictions, adv_a)
    _, _, adv_b = _inputs(labels, clean, adv_b)
    seed = _nonnegative_integer(seed, "seed")
    n_bootstrap = _nonnegative_integer(n_bootstrap, "n_bootstrap", minimum=1)
    clean_correct, success_a = _per_image_success(labels, clean, adv_a)
    _, success_b = _per_image_success(labels, clean, adv_b)
    denominator = int(clean_correct.sum())
    per_image_a = success_a.mean(axis=0)
    per_image_b = success_b.mean(axis=0)
    asr_a = float(per_image_a.sum() / denominator) if denominator else None
    asr_b = float(per_image_b.sum() / denominator) if denominator else None
    result = {
        "sample_count": len(labels),
        "asr_denominator": denominator,
        "attack_seed_count_a": len(adv_a),
        "attack_seed_count_b": len(adv_b),
        "asr_a": asr_a,
        "asr_b": asr_b,
        "difference_a_minus_b": asr_a - asr_b if denominator else None,
        "ci95": None,
        "bootstrap_seed": seed,
        "bootstrap_requested": n_bootstrap,
        "bootstrap_valid": 0,
        "bootstrap_skipped_zero_denominator": n_bootstrap,
        "resampling_unit": "image_with_all_attack_seeds_and_methods",
    }
    if not denominator:
        return result

    generator = np.random.default_rng(seed)
    differences = []
    # Bound the temporary index-array size for larger evaluation sets.
    for start in range(0, n_bootstrap, 128):
        indices = generator.integers(
            0, len(labels), size=(min(128, n_bootstrap - start), len(labels))
        )
        denominators = clean_correct[indices].sum(axis=1)
        valid = denominators != 0
        paired_difference = (per_image_a - per_image_b)[indices].sum(axis=1)
        differences.extend((paired_difference[valid] / denominators[valid]).tolist())
    if differences:
        result["ci95"] = np.percentile(differences, [2.5, 97.5]).tolist()
    result["bootstrap_valid"] = len(differences)
    result["bootstrap_skipped_zero_denominator"] = n_bootstrap - len(differences)
    return result
