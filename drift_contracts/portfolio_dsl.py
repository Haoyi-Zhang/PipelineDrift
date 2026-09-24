"""Compiler for a bounded declarative monitoring and retention language.

The surface language is JSON data.  It describes finite categorical record
schemas, retention atoms, and monitor updates whose historical and future
predicates may use different schemas.  Compilation enumerates the finite record
alphabets and emits the extensional tables consumed by the exact portfolio
analysis.  No expression evaluation occurs in the analysis core.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable

from .portfolio_model import MonitorUpdate, PortfolioProblem, RetentionAtom

MAX_MACHINE_STATES = 4096
MAX_RECORDS = 4096


Json = Any
Record = dict[str, Any]


def _freeze(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if value is None or type(value) in (bool, int, str):
        return value
    raise ValueError(f"unsupported JSON value {value!r}")


def _typed_key(value: Any) -> tuple[str, str]:
    frozen = _freeze(value)
    return (type(frozen).__name__, repr(frozen))


def _expect_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _expect_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _enumerate_schema(value: Any, name: str) -> tuple[tuple[str, ...], tuple[Record, ...]]:
    schema = _expect_mapping(value, name)
    fields_obj = _expect_mapping(schema.get("fields"), f"{name}.fields")
    if not fields_obj:
        raise ValueError(f"{name}.fields must be nonempty")
    fields = tuple(fields_obj)
    if any(not isinstance(field, str) or not field for field in fields):
        raise ValueError(f"{name} field names must be nonempty strings")
    domains: list[tuple[Any, ...]] = []
    count = 1
    for field in fields:
        values = _expect_list(fields_obj[field], f"{name}.fields.{field}")
        if not values:
            raise ValueError(f"domain for {field} must be nonempty")
        frozen = tuple(_freeze(item) for item in values)
        if len({_typed_key(item) for item in frozen}) != len(frozen):
            raise ValueError(f"domain for {field} contains duplicate values")
        domains.append(frozen)
        count *= len(frozen)
        if count > MAX_RECORDS:
            raise ValueError(f"{name} expands above {MAX_RECORDS} records")
    records = tuple(dict(zip(fields, values)) for values in product(*domains))
    return fields, records


def _eval(expr: Any, record: Record) -> Any:
    if expr is None or type(expr) in (bool, int, str) or isinstance(expr, list):
        return _freeze(expr)
    obj = _expect_mapping(expr, "expression")
    if set(obj) == {"field"}:
        field = obj["field"]
        if not isinstance(field, str) or field not in record:
            raise ValueError(f"unknown field {field!r}")
        return record[field]
    if set(obj) == {"const"}:
        return _freeze(obj["const"])
    op = obj.get("op")
    args = obj.get("args")
    if not isinstance(op, str) or not isinstance(args, list):
        raise ValueError("operator expression requires string op and array args")
    values = [_eval(arg, record) for arg in args]
    if op == "not" and len(values) == 1:
        return not bool(values[0])
    if op == "and" and values:
        return all(bool(value) for value in values)
    if op == "or" and values:
        return any(bool(value) for value in values)
    if op == "tuple":
        return tuple(values)
    if op == "in" and len(values) == 2 and isinstance(values[1], tuple):
        return values[0] in values[1]
    if len(values) != 2:
        raise ValueError(f"operator {op!r} expects two arguments")
    left, right = values
    if op == "eq":
        return _typed_key(left) == _typed_key(right)
    if op == "ne":
        return _typed_key(left) != _typed_key(right)
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    raise ValueError(f"unsupported operator {op!r}")


def _bools(expr: Any, records: tuple[Record, ...], name: str) -> tuple[bool, ...]:
    values: list[bool] = []
    for record in records:
        value = _eval(expr, record)
        if type(value) is not bool:
            raise ValueError(f"{name} must evaluate to a Boolean")
        values.append(value)
    return tuple(values)


def _values(expr: Any, records: tuple[Record, ...]) -> tuple[Any, ...]:
    return tuple(_eval(expr, record) for record in records)


def _bits_for_states(count: int) -> int:
    return max(1, math.ceil(math.log2(count)))


def _cost(spec: dict[str, Any], states: int) -> int:
    value = spec.get("cost")
    if value is None or value == "state_bits":
        return _bits_for_states(states)
    if type(value) is not int or value <= 0:
        raise ValueError("cost must be a positive integer or 'state_bits'")
    return value


def _table(states: tuple[Any, ...], records: tuple[Record, ...],
           step: Callable[[Any, Record], Any], name: str) -> tuple[tuple[int, ...], ...]:
    if not states or len(states) > MAX_MACHINE_STATES:
        raise ValueError(f"{name} must have 1..{MAX_MACHINE_STATES} states")
    index = {_typed_key(state): i for i, state in enumerate(states)}
    if len(index) != len(states):
        raise ValueError(f"{name} has duplicate states")
    rows: list[tuple[int, ...]] = []
    for state in states:
        row: list[int] = []
        for record in records:
            nxt = step(state, record)
            key = _typed_key(nxt)
            if key not in index:
                raise ValueError(f"{name} transition escaped its state space: {nxt!r}")
            row.append(index[key])
        rows.append(tuple(row))
    return tuple(rows)


def _window_states(width: int) -> tuple[tuple[bool, ...], ...]:
    if type(width) is not int or not 1 <= width <= 10:
        raise ValueError("window width must be in 1..10")
    states: list[tuple[bool, ...]] = [()]
    for length in range(1, width + 1):
        states.extend(tuple(bits) for bits in product((False, True), repeat=length))
    return tuple(states)


def _value_domain(spec: dict[str, Any], key: str = "values") -> tuple[Any, ...]:
    values = tuple(_freeze(item) for item in _expect_list(spec.get(key), key))
    if not values or len({_typed_key(item) for item in values}) != len(values):
        raise ValueError(f"{key} must be a nonempty duplicate-free array")
    return values


def _compile_atom(spec_value: Any, records: tuple[Record, ...]) -> RetentionAtom:
    spec = _expect_mapping(spec_value, "retention atom")
    name = spec.get("name")
    kind = spec.get("kind")
    if not isinstance(name, str) or not name or not isinstance(kind, str):
        raise ValueError("retention atom requires nonempty name and kind")
    description = spec.get("description", "")
    if not isinstance(description, str):
        raise ValueError("description must be a string")

    if kind in {"seen", "count", "run"}:
        cap = 1 if kind == "seen" else spec.get("cap")
        if type(cap) is not int or cap < 1:
            raise ValueError(f"{kind} cap must be a positive integer")
        truth = _bools(spec.get("predicate"), records, f"atom {name} predicate")
        states = tuple(range(cap + 1))
        if kind in {"seen", "count"}:
            table = tuple(tuple(min(cap, state + int(truth[x])) for x in range(len(records)))
                          for state in states)
        else:
            table = tuple(tuple(min(cap, state + 1) if truth[x] else 0
                                for x in range(len(records))) for state in states)
    elif kind == "last":
        values = _value_domain(spec)
        observed = _values(spec.get("value"), records)
        lookup = {_typed_key(value): i + 1 for i, value in enumerate(values)}
        if any(_typed_key(value) not in lookup for value in observed):
            raise ValueError(f"atom {name} observes a value outside values")
        states = tuple(range(len(values) + 1))
        table = tuple(tuple(lookup[_typed_key(observed[x])] for x in range(len(records)))
                      for _ in states)
    elif kind == "bitset":
        values = _value_domain(spec)
        if len(values) > 12:
            raise ValueError("bitset supports at most 12 declared values")
        observed = _values(spec.get("value"), records)
        lookup = {_typed_key(value): i for i, value in enumerate(values)}
        if any(_typed_key(value) not in lookup for value in observed):
            raise ValueError(f"atom {name} observes a value outside values")
        states = tuple(range(1 << len(values)))
        table = tuple(tuple(state | (1 << lookup[_typed_key(observed[x])])
                            for x in range(len(records))) for state in states)
    elif kind == "histogram":
        values = _value_domain(spec)
        cap = spec.get("cap")
        if type(cap) is not int or not 1 <= cap <= 15:
            raise ValueError("histogram cap must be in 1..15")
        observed = _values(spec.get("value"), records)
        lookup = {_typed_key(value): i for i, value in enumerate(values)}
        if any(_typed_key(value) not in lookup for value in observed):
            raise ValueError(f"atom {name} observes a value outside values")
        states = tuple(product(range(cap + 1), repeat=len(values)))
        def hist_step(state: tuple[int, ...], record: Record) -> tuple[int, ...]:
            idx = lookup[_typed_key(_eval(spec.get("value"), record))]
            result = list(state)
            result[idx] = min(cap, result[idx] + 1)
            return tuple(result)
        table = _table(states, records, hist_step, f"atom {name}")
    elif kind == "window":
        width = spec.get("width")
        states = _window_states(width)
        predicate = spec.get("predicate")
        def window_step(state: tuple[bool, ...], record: Record) -> tuple[bool, ...]:
            value = _eval(predicate, record)
            if type(value) is not bool:
                raise ValueError(f"atom {name} predicate must evaluate to a Boolean")
            return (state + (value,))[-width:]
        table = _table(states, records, window_step, f"atom {name}")
    else:
        raise ValueError(f"unsupported retention kind {kind!r}")
    return RetentionAtom(name=name, cost=_cost(spec, len(states)), transition=table,
                         description=description)


@dataclass(frozen=True)
class _MonitorMachine:
    states: tuple[Any, ...]
    history: tuple[tuple[int, ...], ...]
    future: tuple[tuple[int, ...], ...]
    output: tuple[int, ...]


def _compile_monitor_machine(spec: dict[str, Any], history_records: tuple[Record, ...],
                             future_records: tuple[Record, ...], name: str) -> _MonitorMachine:
    kind = spec.get("kind")
    if not isinstance(kind, str):
        raise ValueError(f"update {name} requires a kind")
    hp = spec.get("history_predicate", spec.get("predicate"))
    fp = spec.get("future_predicate", spec.get("predicate"))
    hv = spec.get("history_value", spec.get("value"))
    fv = spec.get("future_value", spec.get("value"))

    if kind in {"seen", "count_threshold", "run_threshold"}:
        threshold = 1 if kind == "seen" else spec.get("threshold")
        if type(threshold) is not int or threshold < 1:
            raise ValueError(f"update {name} threshold must be positive")
        states = tuple(range(threshold + 1))
        hb = _bools(hp, history_records, f"update {name} historical predicate")
        fb = _bools(fp, future_records, f"update {name} future predicate")
        if kind in {"seen", "count_threshold"}:
            history = tuple(tuple(min(threshold, state + int(hb[x]))
                                  for x in range(len(history_records))) for state in states)
            future = tuple(tuple(min(threshold, state + int(fb[x]))
                                 for x in range(len(future_records))) for state in states)
        else:
            history = tuple(tuple(min(threshold, state + 1) if hb[x] else 0
                                  for x in range(len(history_records))) for state in states)
            future = tuple(tuple(min(threshold, state + 1) if fb[x] else 0
                                 for x in range(len(future_records))) for state in states)
        output = tuple(int(state >= threshold) for state in states)
    elif kind == "last_equals":
        values = _value_domain(spec)
        target = _freeze(spec.get("target"))
        lookup = {_typed_key(value): i + 1 for i, value in enumerate(values)}
        if _typed_key(target) not in lookup:
            raise ValueError(f"update {name} target is outside values")
        hvalues = _values(hv, history_records)
        fvalues = _values(fv, future_records)
        if any(_typed_key(value) not in lookup for value in hvalues + fvalues):
            raise ValueError(f"update {name} observes a value outside values")
        states = tuple(range(len(values) + 1))
        history = tuple(tuple(lookup[_typed_key(hvalues[x])]
                              for x in range(len(history_records))) for _ in states)
        future = tuple(tuple(lookup[_typed_key(fvalues[x])]
                             for x in range(len(future_records))) for _ in states)
        output = tuple(int(state == lookup[_typed_key(target)]) for state in states)
    elif kind in {"bitset_any", "bitset_all"}:
        values = _value_domain(spec)
        required = tuple(_freeze(item) for item in _expect_list(spec.get("required"), "required"))
        lookup = {_typed_key(value): i for i, value in enumerate(values)}
        if not required or any(_typed_key(value) not in lookup for value in required):
            raise ValueError(f"update {name} required values must be in values")
        hvalues = _values(hv, history_records)
        fvalues = _values(fv, future_records)
        if any(_typed_key(value) not in lookup for value in hvalues + fvalues):
            raise ValueError(f"update {name} observes a value outside values")
        states = tuple(range(1 << len(values)))
        history = tuple(tuple(state | (1 << lookup[_typed_key(hvalues[x])])
                              for x in range(len(history_records))) for state in states)
        future = tuple(tuple(state | (1 << lookup[_typed_key(fvalues[x])])
                             for x in range(len(future_records))) for state in states)
        required_mask = sum(1 << lookup[_typed_key(value)] for value in required)
        if kind == "bitset_any":
            output = tuple(int(bool(state & required_mask)) for state in states)
        else:
            output = tuple(int((state & required_mask) == required_mask) for state in states)
    elif kind == "window_pattern":
        pattern_raw = _expect_list(spec.get("pattern"), "pattern")
        if not pattern_raw or any(type(value) is not bool for value in pattern_raw):
            raise ValueError("window pattern must be a nonempty Boolean array")
        pattern = tuple(pattern_raw)
        width = len(pattern)
        states = _window_states(width)
        def make_step(expr: Any) -> Callable[[tuple[bool, ...], Record], tuple[bool, ...]]:
            def step(state: tuple[bool, ...], record: Record) -> tuple[bool, ...]:
                value = _eval(expr, record)
                if type(value) is not bool:
                    raise ValueError(f"update {name} predicate must be Boolean")
                return (state + (value,))[-width:]
            return step
        history = _table(states, history_records, make_step(hp), f"update {name} history")
        future = _table(states, future_records, make_step(fp), f"update {name} future")
        output = tuple(int(state == pattern) for state in states)
    else:
        raise ValueError(f"unsupported monitor kind {kind!r}")
    if len(states) > MAX_MACHINE_STATES:
        raise ValueError(f"update {name} expands above {MAX_MACHINE_STATES} states")
    return _MonitorMachine(states, history, future, output)


def _symbol(prefix: str, index: int, fields: tuple[str, ...], record: Record) -> str:
    values = ",".join(f"{field}={json.dumps(record[field], separators=(',', ':'))}"
                      for field in fields)
    return f"{prefix}{index}:{values}"


def compile_declaration(value: Any) -> PortfolioProblem:
    """Compile one JSON-compatible declaration to an extensional problem."""
    doc = _expect_mapping(value, "declaration")
    name = doc.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("declaration requires a nonempty name")
    hfields, history_records = _enumerate_schema(doc.get("history_schema"), "history_schema")
    ffields, future_records = _enumerate_schema(doc.get("future_schema"), "future_schema")
    atom_specs = _expect_list(doc.get("retention_atoms"), "retention_atoms")
    update_specs = _expect_list(doc.get("monitor_updates"), "monitor_updates")
    if not atom_specs or not update_specs:
        raise ValueError("declaration requires retention_atoms and monitor_updates")
    atoms = tuple(_compile_atom(spec, history_records) for spec in atom_specs)
    updates: list[MonitorUpdate] = []
    for value in update_specs:
        spec = _expect_mapping(value, "monitor update")
        update_name = spec.get("name")
        if not isinstance(update_name, str) or not update_name:
            raise ValueError("monitor update requires a nonempty name")
        machine = _compile_monitor_machine(spec, history_records, future_records, update_name)
        description = spec.get("description", "")
        if not isinstance(description, str):
            raise ValueError("description must be a string")
        updates.append(MonitorUpdate(update_name, machine.history, machine.future,
                                     machine.output, description=description))
    history_symbols = tuple(_symbol("h", i, hfields, record)
                            for i, record in enumerate(history_records))
    future_symbols = tuple(_symbol("f", i, ffields, record)
                           for i, record in enumerate(future_records))
    metadata = dict(doc.get("metadata") or {})
    metadata.update({
        "language": "declarative-drift-contracts",
        "history_fields": list(hfields),
        "future_fields": list(ffields),
        "history_records": history_records,
        "future_records": future_records,
        "source_declaration": doc,
    })
    return PortfolioProblem(name, history_symbols, future_symbols, atoms,
                            tuple(updates), metadata)


def load_declaration(path: str | Path) -> PortfolioProblem:
    with Path(path).open("r", encoding="utf-8") as handle:
        return compile_declaration(json.load(handle))


def declaration_fingerprint(value: Any) -> str:
    """Stable semantic text for result records (not a cryptographic manifest)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
