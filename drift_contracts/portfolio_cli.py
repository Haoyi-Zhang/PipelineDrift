"""Command-line analysis for declarative retention portfolios."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .portfolio import (build_conflict_analysis, make_optimal_certificate,
                        make_unsafe_certificate, optimize_portfolio, shortest_failure)
from .portfolio_dsl import load_declaration
from .portfolio_verify import verify_optimal, verify_unsafe


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("declaration", type=Path)
    parser.add_argument("--selected", type=int,
                        help="also check this numeric atom mask")
    args = parser.parse_args(argv)
    try:
        problem = load_declaration(args.declaration)
        analysis = build_conflict_analysis(problem)
        optimum = optimize_portfolio(problem, analysis)
        result = {
            "problem": problem.name,
            "atoms": [{"name": atom.name, "cost": atom.cost,
                       "states": len(atom.transition)} for atom in problem.atoms],
            "updates": [{"name": update.name, "states": len(update.history)}
                        for update in problem.updates],
            "obstruction_basis": list(analysis.obligations),
            "feasible": optimum["feasible"],
            "optimal_mask": optimum["selected_mask"],
            "optimal_atoms": [] if optimum["selected_mask"] is None else
                             problem.selected_names(int(optimum["selected_mask"])),
            "optimal_cost": optimum["cost"],
        }
        if optimum["feasible"]:
            certificate = make_optimal_certificate(
                problem, analysis, int(optimum["selected_mask"]))
            result["certificate"] = certificate
            result["certificate_valid"] = verify_optimal(problem, certificate)
        else:
            witness = shortest_failure(problem.all_mask, analysis)
            certificate = (make_unsafe_certificate(problem, problem.all_mask, witness)
                           if witness is not None else None)
            result["certificate"] = certificate
            result["certificate_valid"] = bool(certificate and verify_unsafe(
                problem, certificate))
        if args.selected is not None:
            witness = shortest_failure(args.selected, analysis)
            selected = {"mask": args.selected,
                        "atoms": problem.selected_names(args.selected),
                        "cost": problem.cost(args.selected),
                        "safe": witness is None and analysis.feasible}
            if witness is not None:
                cert = make_unsafe_certificate(problem, args.selected, witness)
                selected["certificate"] = cert
                selected["certificate_valid"] = verify_unsafe(problem, cert)
            result["selected"] = selected
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
