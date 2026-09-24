# Resource accounting

## Fixed limits

The project was constrained to four CPU cores, 4 GiB RAM, no swap, GPU, external
compute, model API, private dataset, real service/device, or new human study.
Each scientific run had to remain below 45 minutes; the full campaign ceiling
was eight CPU-hours with at least one quarter reserved for repair and clean
reproduction.  The final archives must remain below 128 MiB.

All recorded experiments used one worker and the Python standard library.
Resource guards in the clean runner attempt one-CPU affinity, a 3 GiB virtual
address-space limit, and a 60-second child CPU limit.  Platform enforcement of
these guards is checked where supported and is not presented as a sandbox
security claim.

## Portfolio campaign

The complete portfolio campaign (`results/portfolio/summary.json`) recorded:

- 20,480 finite problems and 98,304 portfolio masks;
- 4.071191058 CPU seconds and 4.077175123 wall seconds in the final recorded campaign;
- maximum recorded process peak RSS 96,300 KiB;
- no timeout, safety disagreement, optimizer disagreement, invalid certificate,
  or minimum-witness mismatch.

The language checker covers 1,117 extensional compiler cells.  The declaration
and mutation portions cover 12 declarations and 571 one-cell mutations.  Their
counts, rather than timing, support the correctness claims.

## Preserved legacy campaign

The eight single-summary chunks cover 46,932 cases.  Their inner timed regions
sum to 2.577352622 CPU seconds and 2.596182846 wall seconds, with maximum process
peak RSS 93,992 KiB.  The 48-point counter grid recorded 0.000910101 CPU seconds.
These values exclude interpreter startup, editing, web acquisition, TeX build,
and packaging; they are not retroactively treated as whole-project CPU use.

## Working clean reproduction

`results/reproduction.json` records the full sequential runner used before final
packaging:

- 46 unit and CLI tests;
- 1,117 language cells;
- 46,932 legacy cases;
- 20,480 portfolio problems and 98,304 masks;
- 12 declarations and 571 mutations;
- 18 deterministic scientific-record comparisons;
- 15.055686564 seconds elapsed;
- 0.341461705 parent CPU seconds and 14.699353 child CPU seconds;
- 100,908 KiB parent and 98,140 KiB maximum child peak RSS.

Fresh package-extraction runs may report different timing/RSS values.  The
scientific records, not timing equality, are the reproducibility criterion.
This accounting establishes ample closure under the stated budget; it does not
support a scalability or throughput claim.
