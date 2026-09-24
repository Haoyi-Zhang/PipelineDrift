# Benchmark overfitting and generalization boundary

## Scope

The artifact trains no predictive model and estimates no parameters from a training set. Conventional model overfitting, test accuracy, calibration, and train/test leakage are therefore not applicable evaluation concepts. The relevant validity risks are instead (1) hand-crafted benchmark bias, (2) reusing the same implementation in the producer and oracle, (3) tuning examples to a desired conclusion, and (4) extrapolating finite-state results to unrestricted production systems.

## Controls in the release

- Randomized finite problems and differential oracles present: **True**.
- Mutation or adversarial certificate checks present: **True**.
- Cost sensitivity analysis present: **True**.
- Exact-versus-baseline evidence present: **True**.
- Scalability/resource-bound evidence present: **True**.
- Externally sourced pipeline projection present: **True**.
- Negative or infeasible controls present: **True**.

These flags are an inventory, not a substitute for results. The release checker recomputes the corresponding records, and the paper limits every conclusion to the finite, deterministic model actually checked.

## Non-adaptive holdout principle

The random differential checks use fixed, disclosed seeds and independently generated problems. A seed is not treated as statistical evidence by itself. The intended role is fault detection: a candidate implementation must agree with an independently written oracle on every generated instance. Any disagreement is a failing counterexample, not a data point averaged away.

## External validity

The TFX/TFDV projections demonstrate that public schema constraints can be mapped into the finite contract language with provenance. They do not establish full compatibility with arbitrary TFX pipelines, protobuf semantics, streaming engines, or industrial retention costs. No production throughput, incident-reduction, or storage-savings claim is made.

## Reproduction

Run `python tools/release_check.py --output <new-directory>` from the artifact root. The command rejects a pre-existing output directory, executes the complete deterministic suite, and writes machine-readable records for review.
