# BUG: Truss solver gives incorrect reaction sums

## Summary
When solving kopne-type trusses (all members hinged at both ends), the sum of vertical reactions does not equal the sum of applied vertical loads. The discrepancy is consistently 10 kN regardless of load configuration.

## Severity
**High** — produces wrong structural analysis results for trusses.

## Reproduction

### Using kopne 1.struct model (14 nodes, 25 members, all pin-jointed)

```python
import sys
sys.path.insert(0, 'fem_app')
from solver import *

members_def = [
    (1,2),(2,3),(1,3),(1,4),(4,3),(4,5),(5,3),(6,3),(5,6),(5,8),
    (5,7),(6,7),(7,10),(7,9),(8,9),(7,8),(9,10),(9,12),(9,11),
    (10,11),(11,14),(11,12),(11,13),(12,13),(14,13)
]
nodes_def = [
    (1,0,0),(2,0,1),(3,2,1),(4,2,0),(5,4,0),(6,4,1),(7,6,1),
    (8,6,0),(9,8,0),(10,8,1),(11,10,1),(12,10,0),(13,12,0),(14,12,1)
]

model = ModelDefinition(
    structure_type='truss', mesh_size=2,
    materials=[MaterialDef(id=1, name='Steel', E_GPa=210.0)],
    cross_sections=[CrossSectionDef(id=1, A_cm2=28.5, Iz_cm4=19.43, material_id=1)],
    nodes=[NodeDef(id=n[0], x=n[1], y=n[2]) for n in nodes_def],
    members=[MemberDef(id=i+1, start_node=m[0], end_node=m[1], section_id=1)
             for i, m in enumerate(members_def)],
    supports=[SupportDef(node_id=1, type='pinned'),
              SupportDef(node_id=13, type='roller_x')],
    loads=[
        LoadDef(id=1, type='point_force', node_or_member_id=2,  direction='Fy', magnitude=-5.0),
        LoadDef(id=2, type='point_force', node_or_member_id=3,  direction='Fy', magnitude=-10.0),
        LoadDef(id=3, type='point_force', node_or_member_id=6,  direction='Fy', magnitude=-30.0),
        LoadDef(id=4, type='point_force', node_or_member_id=7,  direction='Fy', magnitude=-10.0),
        LoadDef(id=5, type='point_force', node_or_member_id=12, direction='Fy', magnitude=10.0),
        LoadDef(id=6, type='point_force', node_or_member_id=14, direction='Fy', magnitude=-5.0),
    ],
    hinges=[HingeDef(member_id=i, start_release=True, end_release=True)
            for i in range(1, 26)],
)

result = solve(model)
# Expected: sum Ry = 50.0 (= 5+10+30+10-10+5)
# Actual:   sum Ry = 40.0
for r in result.reactions:
    print(f'Node {r.node_id}: Ry={r.Ry_kN:.4f}')
print(f'Sum Ry = {sum(r.Ry_kN for r in result.reactions):.4f}')
```

### Results across different load combinations

All use the same kopne 1 geometry (14 nodes, 25 members, all hinged):

| Load case                              | Net Fy (kN) | Expected Sum Ry | Actual Sum Ry | Error |
|---------------------------------------|-------------|-----------------|---------------|-------|
| Full (6 loads)                        | -50         | 50.0            | **40.0**      | -10   |
| Without node 2,14 loads (4 loads)     | -40         | 40.0            | **30.0**      | -10   |
| Interior only: nodes 3,6,7 (3 loads)  | -50         | 50.0            | **40.0**      | -10   |

The error is **always exactly -10 kN** regardless of which loads are applied.

### Correct answer (verified by hand)

For the full load case, taking moments about node 1:
```
ΣM₁ = (-5)(0) + (-10)(2) + (-30)(4) + (-10)(6) + (+10)(10) + (-5)(12) = -160 kNm
V₁₃ = 160/12 = 13.33 kN
V₁ = 50 - 13.33 = 36.67 kN
```

Solver gives V₁ = 33.33, V₁₃ = 6.67 (each off by ~3.33).

Student Jodzonaite (solving same truss) correctly calculated V₁ = 36.67, V₁₃ = 13.33.

## Additional observations

1. **Member mapping is incomplete** — `an_to_model` dict from `_build_system()` only maps 14 of 25 members (members 6, 15-25 missing from mapping). This suggests some anastruct elements are being created but not tracked back to model members.

2. **N_max_kN is always positive** — The `MemberResult.N_max_kN` field stores `max(abs(Nmin), abs(Nmax))`, losing the sign. For truss checking we need signed axial forces (tension positive, compression negative). The signed values ARE available in anastruct's `element_results['Nmin']` / `['Nmax']`.

3. **Beams and frames work correctly** — The bug appears specific to the truss configuration (all members hinged at both ends) with this particular geometry.

## Suspected cause

The constant -10 kN error across all load cases suggests either:
- A load is being double-counted or dropped during the `_build_system()` mesh creation
- A hinge/constraint is incorrectly modifying the force balance
- An anastruct element is being created with wrong connectivity, absorbing 10 kN into a "phantom" reaction

The incomplete `an_to_model` mapping (only 14/25 members mapped) strongly suggests the mesh subdivision in `_build_system()` is creating orphaned elements.

## Impact

This bug affects any truss analysis done through fem_app. Member forces will also be wrong since they depend on correct reactions.

## Suggested fix direction

1. Check `_build_system()` for the member mesh creation loop — verify all model members get mapped to anastruct elements
2. Add a post-solve equilibrium check: `sum(reactions) == sum(loads)` with tolerance
3. Consider exposing signed axial force (not just absolute max) for truss applications
