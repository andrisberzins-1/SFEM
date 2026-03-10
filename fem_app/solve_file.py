"""
solve_file.py — CLI file-based solver for 2D FEM analysis.

Usage:
    python solve_file.py input.json output.json
    python solve_file.py model.fem.yaml output.json

Reads a model definition from a JSON or YAML file, solves it,
and writes results to a JSON file.

Exit code 0 on success, 1 on error.
Prints a human-readable summary to stdout.
"""

import json
import sys
from pathlib import Path

import yaml

from solver import (
    ModelDefinition,
    dict_to_model,
    yaml_to_model,
    solve,
    result_to_dict,
)


def load_model(input_path: Path) -> ModelDefinition:
    """
    Load a model from a JSON or YAML file.

    Args:
        input_path: Path to .json or .fem.yaml file.

    Returns:
        A ModelDefinition ready for solving.

    Raises:
        ValueError: If the file format is unsupported or contents invalid.
    """
    text = input_path.read_text(encoding="utf-8")

    if input_path.suffix == ".json":
        data = json.loads(text)
        return dict_to_model(data)
    elif input_path.name.endswith(".fem.yaml") or input_path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
        return yaml_to_model(data)
    else:
        raise ValueError(
            f"Unsupported file format: {input_path.suffix}. "
            f"Use .json or .fem.yaml"
        )


def print_summary(result_dict: dict) -> None:
    """Print a human-readable summary of the solve results to stdout."""
    status = result_dict["status"]
    print(f"\n{'='*50}")
    print(f"  FEM Analysis Result: {status.upper()}")
    print(f"{'='*50}")

    if status == "error":
        print(f"\n  Error: {result_dict['error']}")
        print()
        return

    # Reactions
    reactions = result_dict.get("reactions", [])
    if reactions:
        print(f"\n  Reaction Forces:")
        print(f"  {'Node':>6}  {'Rx (kN)':>10}  {'Ry (kN)':>10}  {'Mz (kNm)':>10}")
        print(f"  {'-'*6}  {'-'*10}  {'-'*10}  {'-'*10}")
        sum_rx, sum_ry, sum_mz = 0.0, 0.0, 0.0
        for r in reactions:
            print(f"  {r['node_id']:>6}  {r['Rx_kN']:>10.3f}  {r['Ry_kN']:>10.3f}  {r['Mz_kNm']:>10.3f}")
            sum_rx += r["Rx_kN"]
            sum_ry += r["Ry_kN"]
            sum_mz += r["Mz_kNm"]
        print(f"  {'-'*6}  {'-'*10}  {'-'*10}  {'-'*10}")
        print(f"  {'Sum':>6}  {sum_rx:>10.3f}  {sum_ry:>10.3f}  {sum_mz:>10.3f}")

    # Member results
    members = result_dict.get("member_results", [])
    if members:
        print(f"\n  Element Results:")
        print(f"  {'Mem':>5}  {'N_max':>8}  {'V_max':>8}  {'M_max':>8}  {'Disp':>8}")
        print(f"  {'':>5}  {'(kN)':>8}  {'(kN)':>8}  {'(kNm)':>8}  {'(mm)':>8}")
        print(f"  {'-'*5}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}")
        for m in members:
            print(
                f"  {m['member_id']:>5}  {m['N_max_kN']:>8.3f}  "
                f"{m['V_max_kN']:>8.3f}  {m['M_max_kNm']:>8.3f}  "
                f"{m['max_displacement_mm']:>8.3f}"
            )

    # Node displacements
    nodes = result_dict.get("nodes_displaced", [])
    if nodes:
        print(f"\n  Node Displacements:")
        print(f"  {'Node':>6}  {'dx (mm)':>10}  {'dy (mm)':>10}  {'rz (mrad)':>10}")
        print(f"  {'-'*6}  {'-'*10}  {'-'*10}  {'-'*10}")
        for n in nodes:
            print(f"  {n['node_id']:>6}  {n['dx_mm']:>10.4f}  {n['dy_mm']:>10.4f}  {n['rz_mrad']:>10.4f}")

    print()


def main() -> int:
    """Main entry point. Returns exit code 0 or 1."""
    if len(sys.argv) < 3:
        print("Usage: python solve_file.py <input.json|input.fem.yaml> <output.json>")
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1

    # Load model
    try:
        model = load_model(input_path)
    except Exception as e:
        print(f"Error reading input file: {e}")
        return 1

    # Solve
    result = solve(model)
    result_dict = result_to_dict(result)

    # Print summary
    print_summary(result_dict)

    # Write output
    try:
        output_path.write_text(
            json.dumps(result_dict, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Results written to: {output_path}")
    except Exception as e:
        print(f"Error writing output file: {e}")
        return 1

    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
