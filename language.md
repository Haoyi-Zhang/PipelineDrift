# Declarative finite contract language

A declaration is a JSON object with `history_schema`, `future_schema`,
`retention_atoms`, and `monitor_updates`.  Schemas contain named finite fields;
the compiler enumerates their Cartesian products in declaration order.  The
language is intentionally bounded so every semantic obligation is decidable by
finite analysis.

## Expressions

An expression is a scalar/list constant, `{ "field": NAME }`,
`{ "const": VALUE }`, or `{ "op": OP, "args": [...] }`.  Supported operators
are `eq`, `ne`, `lt`, `le`, `gt`, `ge`, `and`, `or`, `not`, `in`, and `tuple`.
Predicates must evaluate to JSON Booleans on every record.  Field references are
checked separately against the historical and future schemas.

## Retention atoms

- `seen`: one bit recording whether a predicate has occurred.
- `count`: a predicate count saturated at a positive `cap`.
- `run`: the current consecutive predicate run, saturated at `cap`.
- `last`: an unset state plus the last value from an explicit finite domain.
- `bitset`: the set of observed values from an explicit domain of at most 12.
- `histogram`: one saturated counter per declared value.
- `window`: the Boolean predicate suffix up to a width in 1..10.

The default cost is the minimum fixed-width bits for the atom state count.
Declarations may instead supply a positive integer cost when a different
storage/accounting policy is part of the contract.  Costs are additive across
selected atoms.

## Monitor updates

`seen`, `count_threshold`, `run_threshold`, `last_equals`, `bitset_any`,
`bitset_all`, and `window_pattern` use the corresponding finite state.  An
update can supply `history_predicate`/`future_predicate` or
`history_value`/`future_value` to express a field rename, deletion, or changed
record representation while preserving one temporal obligation.  The output is
binary; multiple updates express a planned evolution family.

## Bounds and non-claims

A schema may enumerate at most 4,096 records and a primitive at most 4,096
states.  These are implementation guards.  The language has no unbounded
integer, timestamp, probabilistic, learned-model, or external-service semantics.
Compilation does not infer that two business fields mean the same thing; that
mapping is a declaration supplied by the engineer and remains a modeling
assumption.
