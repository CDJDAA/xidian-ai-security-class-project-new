# Title: Compute-Matched Diversity Allocation for Transferable Adversarial Examples

## Keywords
adversarial transferability, surrogate checkpoints, block shuffle and rotation, gradient budget, reproducibility, negative results

## TL;DR
Under the same input-gradient evaluation budget, are training-trajectory diversity and spatial input diversity complementary or redundant? Propose a small, falsifiable CIFAR-10 study suitable for one GTX 1660 Ti with 6 GB of VRAM.

## Abstract
Existing attacks introduce diversity through spatial transformations (BSR), training checkpoints, local perturbation augmentation (LPAA), random parameter pruning (RaPA), or ViT patch restructuring (PR). These interventions change both the surrogate distribution and the computation performed. We will investigate budget allocation rather than claim that simply combining existing attacks is novel. With a single surrogate training trajectory, compare checkpoint-only, BSR-only, and mixed allocations at fixed update count and a fixed number of surrogate-view input-gradient evaluations. Include a longer-step MI-FGSM baseline matched on that budget. Use only source training/validation data to select checkpoints and hyperparameters; keep final target models and test IDs fixed and unavailable for selection. Report per-target clean-conditioned untargeted ASR, denominators, robust accuracy, actual gradient counts, wall-clock time, memory, and training/selection costs. A failure of mixed allocation to outperform either endpoint is a valid result. Existing Checkpoints work already includes vertical checkpoint ensembles; do not claim their invention. Do not conflate RaPA's targeted setting with untargeted ASR. Do not treat MNIST or a toy CUDA smoke check as an ImageNet reproduction.

## Fixed course constraints

- Source: CIFAR-adapted ResNet-18; source split 45,000 training / 5,000 validation. Preserve split hashes.
- Final targets: independently trained, predeclared CIFAR-adapted ResNet-34 and MobileNetV2; no target-based tuning.
- Main matrix: T=10, (K,M)=(4,1),(1,4),(2,2), all G=T*K*M=40 evaluations per input. Original views for checkpoint-only, BSR views where applicable.
- Budget curve: G=20/40/80 uses T=5/10/20 respectively, always four surrogate-view evaluations per step and the same allocations (K,M)=(4,1),(1,4),(2,2).
- Baselines at every budget G: final-model MI-FGSM T=G for equal compute and T=G/4 as a separate equal-iteration reference. Use alpha=epsilon/T and projection.
- Debug the protocol only on source validation data. Freeze all selection and evaluation rules before viewing any final-target predictions or metrics. The first 500 fixed test IDs are the first formal evaluation after freezing, never a hyperparameter-tuning pilot; any predeclared larger evaluation keeps the same rules.
- Pixel range [0,1], L-infinity epsilon 8/255 and a separately reported 16/255 sensitivity condition. Fixed IDs and shared origin policy.
- Batched views still count as K*M evaluations; include initialization and diagnostic gradients separately.
- Three attack seeds do not constitute three independent training trajectories. Use paired per-image analysis and disclose training repetitions.
- Sequential GPU gradients, one worker, small batches. No simultaneous training of large models; no downloads beyond approved public datasets and declared model weights.
- No target queries during attack construction, no tuning on final target results, no fabricated outcomes or citations.
- Only local, authorized benchmark classifiers. No external production systems.

## References

See `docs/research/transfer-attack-budget.md` for PDF page references and three candidate directions. The local corpus is `../paper/`: BSR, Checkpoints, LPAA, RaPA, and PR. PR_2026 is a Discover Computing article; infer bibliographic information from the paper, not the filename.
