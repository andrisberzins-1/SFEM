# buckling_app -- Member Capacity Check

Strength and buckling check for steel members per Eurocode EC3 / EN 1993-1-1.
Educational tool showing step-by-step calculations with all intermediate values.

## Critical Rules

- **`buckling_solver.py` is the single source of truth** for all math -- `app.py` does NOT implement any calculations.
- All calculations MUST produce step-by-step intermediate values (StrengthResult, BucklingAxisResult) -- never just a final number.
- Formulas shown to students must match Eurocode EC3 / EN 1993-1-1 notation.

## Scope

Two checks combined in one module:
1. **Strength check** (EN 1993-1-1 cl. 6.2.3/6.2.4) -- 3 equivalent methods (force, stress, area comparison)
2. **Buckling check** (EN 1993-1-1 cl. 6.3.1) -- both y and z axes independently, using imperfection-based chi reduction factor

## Units

- Forces: kN (input/output), N (internal conversion where needed)
- Stresses: MPa (N/mm2)
- Lengths: m (member length), mm (section properties)
- Area: mm2
- Moment of inertia: mm4
- Elastic modulus: MPa (default E = 200,000 MPa)

## Sign Convention

- N_Ed > 0: tension (strength check only)
- N_Ed < 0: compression (strength + buckling checks)

## Key Constants

- `E_STEEL_MPA = 200_000.0`
- `GAMMA_M0_DEFAULT = 1.0`, `GAMMA_M1_DEFAULT = 1.0`
- `SLENDERNESS_THRESHOLD = 0.2` (below this, buckling check may be skipped)
- `IMPERFECTION_FACTORS = {"a0": 0.13, "a": 0.21, "b": 0.34, "c": 0.49, "d": 0.76}`
- `MU_VALUES = {"cantilever": 2.0, "pinned_pinned": 1.0, "fixed_pinned": 0.7, "fixed_fixed": 0.5}`

## Buckling Check Algorithm (per axis)

1. Effective length: Lcr = mu * L
2. Radius of gyration: i = sqrt(I / A)
3. Characteristic resistance: NRk = A * fy
4. Euler critical force: Ncr = pi^2 * E * I / Lcr^2
5. Relative slenderness: lambda_bar = sqrt(NRk / Ncr)
6. Imperfection factor alpha from buckling curve table
7. Phi = 0.5 * [1 + alpha * (lambda_bar - 0.2) + lambda_bar^2]
8. chi = 1 / (Phi + sqrt(Phi^2 - lambda_bar^2)), capped at 1.0
9. Nb,Rd = chi * A * fy / gamma_M1
10. Check: |NEd| <= Nb,Rd

## Exchange Integration

- **Import from section_app**: Reads `exchange/sections/*.section_result.json` for A, Iy, Iz
- **Import from fem_app**: Reads `exchange/fem_results/*.fem_result.json` for member forces (future)

## File Structure

```
buckling_app/
├── app.py                  # Streamlit frontend (port 8504)
├── buckling_solver.py      # Strength + buckling calculations
├── file_io.py              # SFEM envelope file I/O (templates, saves, exchange)
├── module.json             # Hub discovery
├── requirements.txt
├── templates/              # .buckling.json template files (auto-discovered)
├── saves/                  # User case saves (auto-created)
├── tests/
│   ├── __init__.py
│   └── test_buckling.py    # Analytical verification
└── CLAUDE.md               # This file
```

## Testing

```bash
pytest buckling_app/tests/ -v
```

- 38 tests verify against algorithm document example (SHS 100x100x6, S235)
- Covers: strength methods, Euler force, slenderness, chi, Nb,Rd, utilization
- Tests for: tension, stocky members, asymmetric sections, boundary conditions, edge cases

## Port

- Streamlit: 8504
