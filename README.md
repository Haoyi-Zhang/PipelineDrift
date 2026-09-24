# Declarative Drift Contracts

This standalone artifact implements **cost-aware retention-portfolio synthesis**
for bounded, deterministic monitor evolution.  A declaration provides finite
historical/future record schemas, candidate summary atoms with positive costs,
and a planned family of monitor updates.  The analyzer either:

1. returns a minimum-cost portfolio whose retained states are sufficient to
   reproduce every update exactly as if the complete history had been replayed;
2. returns a paired-history and common-future certificate showing why a proposed
   portfolio is unsafe; or
3. proves the candidate catalogue infeasible by exhibiting a target-relevant
   history pair separated by no candidate atom.

The implementation uses only the Python standard library.  It does not train or
run a model, call an external API, access private data, or require a GPU.

## Quick start

From the extracted `declarative-drift-contracts/` directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python -m drift_contracts.portfolio_cli \
  declarations/threshold-family.json
PYTHONDONTWRITEBYTECODE=1 python -m drift_contracts.portfolio_cli \
  declarations/marginals-only-infeasible.json
```

The first declaration demonstrates cross-update sharing: exact joint retention
costs 2 while the union of independently optimized update portfolios costs 5.
The second has a zero separator, so no subset of its marginal summaries can
recover a later disagreement monitor.

## Complete reproduction

The output directory must not already exist:

```sh
PYTHONDONTWRITEBYTECODE=1 python tools/reproduce.py \
  --output ../drift-reproduction
```

The runner is sequential.  It executes the complete unit/CLI suite (46 tests in the shipped artifact), independently checks the
surface-language compilation, reruns the legacy single-summary pilot and all
46,932 legacy finite specifications, reruns a 48-point counter family, and
reruns the portfolio campaign.  It then byte-compares 18 claim-critical
scientific records against the shipped records while intentionally excluding
fresh timing and memory fields.  A successful command demonstrates deterministic
re-execution of the bounded checks; it is not a proof assistant result,
production validation, or independent peer review.

## Reported finite evidence

- 20,480 complete bounded portfolio problems and 98,304 candidate masks;
- zero safety-equivalence, optimizer, certificate, or minimum-witness mismatch;
- 12 pipeline-evolution declarations, of which 11 are feasible and one remains
  infeasible even with all candidate atoms;
- three declarations where the union of per-update optima is more expensive
  than the joint optimum;
- one weighted declaration where greedy costs 11 and exact synthesis costs 10;
- 571 valid one-cell monitor mutations: 188 invalidate the old optimum, 172 make
  the catalogue infeasible, 15 increase and 41 decrease optimum cost, with no
  certificate-verification failure;
- 1,117 compiler cells independently recomputed across 12 declarations;
- the preserved 46,932-case legacy regression, with no oracle discrepancy.

These counts describe the shipped finite spaces and declarations.  They do not
measure production prevalence, throughput, human usefulness, or learned-model
accuracy.

## Repository map

- `drift_contracts/portfolio_dsl.py` — parser and finite compiler;
- `drift_contracts/dsl_reference.py` — independent direct interpreter used for
  cell-by-cell compiler checks;
- `drift_contracts/portfolio.py` — product reachability, obstruction extraction,
  exact optimization, and shortest certificate search;
- `drift_contracts/portfolio_verify.py` — independent safety, optimality, and
  certificate validators, including exact obstruction-basis and migration-map
  checking;
- `declarations/` — 12 bounded pipeline-evolution declarations;
- `proofs/portfolio.md` — complete written proof arguments;
- `language.md` — declaration syntax and guarded semantics;
- `protocol.md` — frozen evaluation and mutation protocol;
- `results/` — claim-critical raw and aggregate records;
- `claim_evidence_ledger.csv` — claim-to-proof/check/result mapping;
- `calibration-matrix.csv` — 12 TSE, five influential/foundational, and five
  adjacent-paper writing/novelty calibration record;
- `bibliography-verification.csv` — metadata-verification record for every
  cited work in the paper package;
- `drift_contracts/bibliography.py` and `tools/check_references.py` — offline
  consistency checks for citations, DOI syntax/uniqueness, verification-ledger
  coverage, and calibration counts (publisher/source inspection remains a
  separate human evidence obligation);
- `external_resources.csv` — source, license/access, and integration inventory;
- `tools/reproduce.py` — clean deterministic reproduction entry point.

## Trust boundary

Theorems are conventional written mathematics, not machine-checked proofs.  The
compiler check deliberately uses a separate interpreter, and the finite
catalogues compare the optimizer against exhaustive enumeration, but all code
was produced and audited within one project.  Human authors must independently
review the mathematical argument, source characterization, implementation, and
policy disclosures before any external use.

## License and scholarly inputs

Project code and original documentation are under the MIT License in `LICENSE`.
Scholarly papers are cited and linked but not redistributed.  Publisher/template
assets belong in the separate paper package, not this standalone repository.
Substantive generative-AI assistance affected the research formulation, proofs,
implementation, experiments, and manuscript; the paper contains a corresponding
truthful disclosure.
