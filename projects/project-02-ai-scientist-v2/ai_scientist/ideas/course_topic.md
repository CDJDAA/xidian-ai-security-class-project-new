# Title: When Do Lightweight Tabular Classifiers Resist Feature Perturbation Attacks?

## Keywords
adversarial robustness, tabular data, feature perturbation, lightweight models, CPU-efficient evaluation

## TL;DR
Small tabular classifiers can be trained on a CPU in minutes, but how much robustness do they actually retain under simple feature-perturbation attacks, and does model capacity change the picture?

## Abstract
Feature-perturbation attacks against tabular classifiers are usually evaluated with large ensembles, exhaustive search, or gradient-based optimizers that assume substantial compute. This leaves an open practical question for resource-constrained deployment: when a tabular model is small enough to train on a single CPU core in minutes, how robust is it under inexpensive attacks, and does added capacity actually buy robustness?

We propose a controlled, low-compute study on small tabular datasets (at most 10000 rows, at most 50 features). The study compares at least three model families of increasing capacity — regularized logistic regression, random forest, and gradient boosting — plus one small multilayer perceptron. Each model is attacked with three perturbation strategies of increasing attacker knowledge: (1) uniform random feature noise, (2) greedy single-feature flips ranked by local sensitivity, and (3) a gradient-based perturbation on the differentiable models. Robustness is measured by attack success rate and clean-accuracy drop as a function of an explicit perturbation budget, and we additionally test whether adversarial training at low compute reduces success rate without collapsing clean accuracy.

The key questions are: (a) does the ranking of model families by robustness match their ranking by clean accuracy, (b) is the cheapest attack already sufficient to break high-capacity models, and (c) does low-compute adversarial training help or merely trade accuracy for a false sense of security. All experiments must run within a strict budget: single-process CPU execution, no GPU, no model larger than a few million parameters, and each full run under ten minutes. We will report per-dataset and averaged metrics, and explicitly note where the reduced budget (small models, few seeds, limited attack iterations) limits the strength of the conclusions.

## Constraints for the executing agent
- CPU only, no CUDA; do not attempt to use a GPU or download large pretrained models.
- Total runtime per experiment must stay under 10 minutes on a single process.
- Prefer scikit-learn and small PyTorch MLPs; avoid training deep convolutional networks.
- Use publicly available small tabular datasets or synthetic data generated locally; do not depend on large downloads.
