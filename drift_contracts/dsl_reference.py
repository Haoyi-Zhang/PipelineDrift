"""Independent reference semantics for the bounded declaration language.

This module does not import the compiler's private expression evaluator, state
enumerators, or transition builders.  It reconstructs every extensional cell
from a JSON declaration and compares it with the compiled PortfolioProblem.
It is intentionally simple and used only as an assurance oracle.
"""
from __future__ import annotations

from itertools import product
import math
from typing import Any

from .portfolio_model import PortfolioProblem


def _freeze(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(x) for x in value)
    if isinstance(value, dict):
        return tuple(sorted((str(k), _freeze(v)) for k, v in value.items()))
    if value is None or type(value) in (bool, int, str):
        return value
    raise ValueError(f"unsupported value {value!r}")


def _key(value: Any) -> tuple[str, str]:
    value = _freeze(value)
    return type(value).__name__, repr(value)


def _eval(expr: Any, record: dict[str, Any]) -> Any:
    if expr is None or type(expr) in (bool, int, str) or isinstance(expr, list):
        return _freeze(expr)
    if not isinstance(expr, dict):
        raise ValueError("expression must be JSON-compatible")
    if set(expr) == {"field"}:
        return record[expr["field"]]
    if set(expr) == {"const"}:
        return _freeze(expr["const"])
    op = expr["op"]
    values = [_eval(arg, record) for arg in expr["args"]]
    if op == "not":
        return not bool(values[0])
    if op == "and":
        return all(bool(x) for x in values)
    if op == "or":
        return any(bool(x) for x in values)
    if op == "tuple":
        return tuple(values)
    if op == "in":
        return values[0] in values[1]
    left, right = values
    if op == "eq": return _key(left) == _key(right)
    if op == "ne": return _key(left) != _key(right)
    if op == "lt": return left < right
    if op == "le": return left <= right
    if op == "gt": return left > right
    if op == "ge": return left >= right
    raise ValueError(f"unsupported operator {op!r}")


def _records(schema: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    fields = tuple(schema["fields"])
    domains = [tuple(_freeze(v) for v in schema["fields"][field]) for field in fields]
    return tuple(dict(zip(fields, values)) for values in product(*domains))


def _window_states(width: int) -> tuple[tuple[bool, ...], ...]:
    result: list[tuple[bool, ...]] = [()]
    for length in range(1, width + 1):
        result.extend(tuple(bits) for bits in product((False, True), repeat=length))
    return tuple(result)


def _table(states: tuple[Any, ...], records: tuple[dict[str, Any], ...], step) -> tuple[tuple[int, ...], ...]:
    indices = {_key(state): i for i, state in enumerate(states)}
    return tuple(tuple(indices[_key(step(state, record))] for record in records)
                 for state in states)


def _atom(spec: dict[str, Any], records: tuple[dict[str, Any], ...]) -> tuple[tuple[tuple[int, ...], ...], int]:
    kind = spec["kind"]
    if kind in {"seen", "count", "run"}:
        cap = 1 if kind == "seen" else spec["cap"]
        states = tuple(range(cap + 1))
        truth = tuple(_eval(spec["predicate"], r) for r in records)
        if kind in {"seen", "count"}:
            table = tuple(tuple(min(cap, s + int(truth[x])) for x in range(len(records))) for s in states)
        else:
            table = tuple(tuple(min(cap, s + 1) if truth[x] else 0 for x in range(len(records))) for s in states)
    elif kind == "last":
        values = tuple(_freeze(v) for v in spec["values"])
        lookup = {_key(v): i + 1 for i, v in enumerate(values)}
        states = tuple(range(len(values) + 1))
        observed = tuple(_eval(spec["value"], r) for r in records)
        table = tuple(tuple(lookup[_key(observed[x])] for x in range(len(records))) for _ in states)
    elif kind == "bitset":
        values = tuple(_freeze(v) for v in spec["values"])
        lookup = {_key(v): i for i, v in enumerate(values)}
        states = tuple(range(1 << len(values)))
        observed = tuple(_eval(spec["value"], r) for r in records)
        table = tuple(tuple(s | (1 << lookup[_key(observed[x])]) for x in range(len(records))) for s in states)
    elif kind == "histogram":
        values = tuple(_freeze(v) for v in spec["values"])
        lookup = {_key(v): i for i, v in enumerate(values)}
        cap = spec["cap"]
        states = tuple(product(range(cap + 1), repeat=len(values)))
        def step(state, record):
            nxt = list(state)
            i = lookup[_key(_eval(spec["value"], record))]
            nxt[i] = min(cap, nxt[i] + 1)
            return tuple(nxt)
        table = _table(states, records, step)
    elif kind == "window":
        width = spec["width"]
        states = _window_states(width)
        table = _table(states, records,
                       lambda s, r: (s + (bool(_eval(spec["predicate"], r)),))[-width:])
    else:
        raise ValueError(f"unsupported retention kind {kind!r}")
    default_cost = max(1, math.ceil(math.log2(len(states))))
    expected_cost = default_cost if spec.get("cost") in (None, "state_bits") else spec["cost"]
    return table, expected_cost


def _monitor(spec: dict[str, Any], history_records, future_records):
    kind = spec["kind"]
    hp = spec.get("history_predicate", spec.get("predicate"))
    fp = spec.get("future_predicate", spec.get("predicate"))
    hv = spec.get("history_value", spec.get("value"))
    fv = spec.get("future_value", spec.get("value"))
    if kind in {"seen", "count_threshold", "run_threshold"}:
        threshold = 1 if kind == "seen" else spec["threshold"]
        states = tuple(range(threshold + 1))
        hb = tuple(bool(_eval(hp, r)) for r in history_records)
        fb = tuple(bool(_eval(fp, r)) for r in future_records)
        if kind in {"seen", "count_threshold"}:
            history = tuple(tuple(min(threshold, s + int(hb[x])) for x in range(len(history_records))) for s in states)
            future = tuple(tuple(min(threshold, s + int(fb[x])) for x in range(len(future_records))) for s in states)
        else:
            history = tuple(tuple(min(threshold, s + 1) if hb[x] else 0 for x in range(len(history_records))) for s in states)
            future = tuple(tuple(min(threshold, s + 1) if fb[x] else 0 for x in range(len(future_records))) for s in states)
        output = tuple(int(s >= threshold) for s in states)
    elif kind == "last_equals":
        values = tuple(_freeze(v) for v in spec["values"])
        lookup = {_key(v): i + 1 for i, v in enumerate(values)}
        states = tuple(range(len(values) + 1))
        hvals = tuple(_eval(hv, r) for r in history_records)
        fvals = tuple(_eval(fv, r) for r in future_records)
        history = tuple(tuple(lookup[_key(hvals[x])] for x in range(len(history_records))) for _ in states)
        future = tuple(tuple(lookup[_key(fvals[x])] for x in range(len(future_records))) for _ in states)
        target = lookup[_key(_freeze(spec["target"]))]
        output = tuple(int(s == target) for s in states)
    elif kind in {"bitset_any", "bitset_all"}:
        values = tuple(_freeze(v) for v in spec["values"])
        lookup = {_key(v): i for i, v in enumerate(values)}
        states = tuple(range(1 << len(values)))
        hvals = tuple(_eval(hv, r) for r in history_records)
        fvals = tuple(_eval(fv, r) for r in future_records)
        history = tuple(tuple(s | (1 << lookup[_key(hvals[x])]) for x in range(len(history_records))) for s in states)
        future = tuple(tuple(s | (1 << lookup[_key(fvals[x])]) for x in range(len(future_records))) for s in states)
        required = sum(1 << lookup[_key(_freeze(v))] for v in spec["required"])
        if kind == "bitset_any":
            output = tuple(int(bool(s & required)) for s in states)
        else:
            output = tuple(int((s & required) == required) for s in states)
    elif kind == "window_pattern":
        pattern = tuple(spec["pattern"])
        width = len(pattern)
        states = _window_states(width)
        history = _table(states, history_records,
                         lambda s, r: (s + (bool(_eval(hp, r)),))[-width:])
        future = _table(states, future_records,
                        lambda s, r: (s + (bool(_eval(fp, r)),))[-width:])
        output = tuple(int(s == pattern) for s in states)
    else:
        raise ValueError(f"unsupported monitor kind {kind!r}")
    return history, future, output


def check_compilation(document: dict[str, Any], problem: PortfolioProblem) -> dict[str, int]:
    """Recompute and compare every emitted transition and output cell."""
    history_records = _records(document["history_schema"])
    future_records = _records(document["future_schema"])
    if tuple(problem.metadata["history_records"]) != history_records:
        raise AssertionError("history record enumeration mismatch")
    if tuple(problem.metadata["future_records"]) != future_records:
        raise AssertionError("future record enumeration mismatch")
    if len(document["retention_atoms"]) != len(problem.atoms):
        raise AssertionError("retention atom count mismatch")
    if len(document["monitor_updates"]) != len(problem.updates):
        raise AssertionError("monitor update count mismatch")
    atom_cells = monitor_cells = output_cells = 0
    for spec, atom in zip(document["retention_atoms"], problem.atoms):
        expected, cost = _atom(spec, history_records)
        if expected != atom.transition or cost != atom.cost or spec["name"] != atom.name:
            raise AssertionError(f"retention semantics mismatch for {spec['name']}")
        atom_cells += sum(len(row) for row in expected)
    for spec, update in zip(document["monitor_updates"], problem.updates):
        history, future, output = _monitor(spec, history_records, future_records)
        if history != update.history or future != update.future or output != update.output or spec["name"] != update.name:
            raise AssertionError(f"monitor semantics mismatch for {spec['name']}")
        monitor_cells += sum(len(row) for row in history) + sum(len(row) for row in future)
        output_cells += len(output)
    return {
        "history_records": len(history_records),
        "future_records": len(future_records),
        "retention_atoms": len(problem.atoms),
        "monitor_updates": len(problem.updates),
        "retention_transition_cells": atom_cells,
        "monitor_transition_cells": monitor_cells,
        "monitor_output_cells": output_cells,
    }
