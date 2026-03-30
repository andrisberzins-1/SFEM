# Homework Checker — System Design

## Goal
Teachers download student PDFs from Ortus → drop into a folder → ask Claude to check → get reports. Minimum technical skill required.

## Target Users
- University teachers using **Claude Desktop app** (not CLI)
- Most are not programmers
- Need to see it work to be convinced

---

## Option Comparison

| Approach | User experience | Setup effort | Shareable? | Best for |
|----------|----------------|-------------|------------|----------|
| **A: Claude Project + folder** | Upload PDFs to Claude conversation, ask "check this" | Zero setup | Share project template | 1-5 students, quick check |
| **B: Claude Desktop + MCP server** | Local folder watcher, automatic processing | Medium setup (install once) | Share MCP config | 10-50 students, batch |
| **C: Streamlit web app** | Browser UI, drag-drop, visual reports | Build + host | URL link | Department-wide, 100+ students |
| **D: Claude Code skill** | Type `/check-homework` in terminal | Install Claude Code | Share skill file | Technical teachers |

### Recommended: Start with A, grow to B or C

**Phase 1 (now):** Claude Project — zero infrastructure, proves the concept
**Phase 2 (if adopted):** MCP server or Streamlit app for batch processing

---

## Phase 1: Claude Project Approach

### How it works

1. Teacher creates a **Claude Project** called "BM Homework Checker 2026"
2. Project has **system instructions** that explain:
   - The assignment structure
   - Correct answers for each variant (pre-computed)
   - How to read student work and diagnose errors
3. Teacher uploads student PDF → asks "Check this homework"
4. Claude reads the PDF, identifies the variant, traces calculations, produces a report

### What goes INTO the project

```
Project: "BM Homework Checker 2026"
│
├── System Instructions (project prompt):
│   "You are a structural mechanics homework checker for BBM169.
│    When given a student PDF, do the following:
│    1. Identify student name and ID
│    2. Determine variant from last digit of ID (see table)
│    3. Check reactions against reference
│    4. Trace member forces joint by joint
│    5. Find root cause of any errors
│    6. Produce grading report"
│
├── Knowledge files (uploaded once):
│   ├── assignment.pdf          — the task description
│   ├── answer_key.json         — all 10 variants' correct answers
│   ├── variant_table.md        — student ID → variant mapping
│   └── checking_guide.md       — what to check, tolerances, common errors
│
└── Each conversation:
    └── Teacher uploads 1-3 student PDFs → gets reports
```

### Limitations of Phase 1
- Manual — one conversation per batch of students
- Claude Desktop has file size limits (~10 pages per PDF works fine)
- No permanent storage of results
- Teacher needs to copy/save the report themselves

### But it proves the concept with ZERO setup

---

## Phase 2: Folder-Based Batch Workflow

### Folder Structure

```
homework_checking/
│
├── courses/
│   └── BBM169_2026/
│       ├── course.yaml                    ← course config
│       │
│       ├── tasks/
│       │   ├── MD2_truss/
│       │   │   ├── task.yaml              ← task definition
│       │   │   ├── assignment.pdf         ← printed task (for reference)
│       │   │   ├── variants/
│       │   │   │   ├── kopne_1.yaml       ← variant 1 definition + answers
│       │   │   │   ├── kopne_2.yaml
│       │   │   │   └── ...kopne_10.yaml
│       │   │   └── variant_map.yaml       ← student ID last digit → variant
│       │   │
│       │   └── MD3_beam/                  ← another task (future)
│       │       ├── task.yaml
│       │       └── variants/...
│       │
│       ├── submissions/
│       │   └── MD2_truss/
│       │       ├── Jodzonaite_251RBC080.pdf
│       │       ├── Treikale_ROC004.pdf
│       │       ├── Baiks_251RBC059.pdf
│       │       └── ...
│       │
│       └── reports/
│           └── MD2_truss/
│               ├── Jodzonaite_251RBC080_report.md
│               ├── Treikale_ROC004_report.md
│               ├── Baiks_251RBC059_report.md
│               └── summary.md             ← class overview
```

### File Formats

#### course.yaml
```yaml
course: BBM169
name: "Būvmehānikas ievadkurss"
year: 2026
semester: spring
teachers:
  - Šliseris
  - (others)
```

#### task.yaml
```yaml
task_id: MD2_truss
name: "2 un 3 tēmas pastāvīgie darba uzdevumi"
type: truss_analysis
checks:
  - reactions          # ΣF=0, ΣM=0
  - member_forces      # all member axial forces
  - cross_sections     # A and d for tension members
  - deformations       # ε, Δl, Δd
tolerances:
  reactions_kN: 0.5%
  forces_kN: 1%
  area_mm2: 1%
  diameter_mm: 1%
  deformation: 2%
material:
  sigma_allow_task1_MPa: 300
  sigma_allow_task2_MPa: 450
  E_GPa: 210
  nu: 0.3
```

#### variant file (e.g. kopne_1.yaml)
```yaml
variant_id: 1
name: "Kopne 1"
geometry:
  nodes:
    1: [0, 0]
    2: [0, 1]
    3: [2, 1]
    # ... (from .struct file)
  members:
    1: [1, 2]
    2: [2, 3]
    # ...
  supports:
    1: pinned
    13: roller_x
loads:
  2: {Fy: -5}
  3: {Fy: -10}
  6: {Fy: -30}
  7: {Fy: -10}
  12: {Fy: 10}
  14: {Fy: -5}

# Pre-computed correct answers
answers:
  reactions:
    V1: 36.67
    V13: 13.33
    H1: 0
  member_forces:
    1-2: -5.0
    2-3: 0.0
    1-3: -70.82
    1-4: 63.34
    # ... all 25 members
  tension_members_task1:  # σ = 300 MPa
    1-4: {N: 63.34, A_mm2: 211.1, d_mm: 16.39}
    4-5: {N: 63.34, A_mm2: 211.1, d_mm: 16.39}
    # ...
```

#### variant_map.yaml
```yaml
# Student ID last digit → variant number
# Task 1
task1:
  0: 1
  1: 2
  2: 3
  3: 4
  4: 5
  5: 1
  6: 2
  7: 3
  8: 4
  9: 5
# Task 2
task2:
  0: 6
  1: 7
  2: 8
  3: 9
  4: 10
  5: 6
  6: 7
  7: 8
  8: 9
  9: 10
```

### Report Format

Each student gets a markdown report:

```markdown
# Homework Report: Krista Jodzonaite (251RBC080)
## Task: MD2 — Truss Analysis
## Date checked: 2026-03-27

### Variant: Kopne 1 (student ID last digit: 0)

### Task 1 (σ = 300 MPa)

#### Reactions
| Value | Student | Reference | Status |
|-------|---------|-----------|--------|
| V₁    | 36.67   | 36.67     | ✓      |
| V₁₃   | 13.33   | 13.33     | ✓      |
| H₁    | 0       | 0         | ✓      |

#### Member Forces
| Member | Student (kN) | Reference (kN) | Status |
|--------|-------------|-----------------|--------|
| 1-2    | -5.00       | -5.00           | ✓      |
| 1-3    | -70.82      | -70.82          | ✓      |
| 1-4    | +63.34      | +63.34          | ✓      |
| ...    | ...         | ...             | ...    |

#### Cross-sections (tension members)
| Member | N (kN) | A (mm²) | d (mm) | Status |
|--------|--------|---------|--------|--------|
| 1-4    | 63.34  | 211.1   | 16.39  | ✓      |
| ...    | ...    | ...     | ...    | ...    |

### Error Diagnosis
No errors found. All values match reference within tolerance.

### Score: 22/22 (100%)

---
*Checked by AI assistant. Teacher should verify flagged items.*
```

For a student WITH errors:

```markdown
### Error Diagnosis

⚠ **3 errors found. Root cause: incorrect moment equation.**

**Error chain:**
1. REACTIONS (page 2, line 2):
   Student wrote: ΣM₁ = 100·2 + 200·4 + 100·6 ...
   But load at node 6 is 30 kN, not 100 kN.
   → V₁₃ = 200 kN (should be 13.33 kN)
   → V₁ = 300 kN (should be 36.67 kN)

2. This causes ALL subsequent member forces to be wrong.
   However, the student's METHOD is correct —
   all equilibrium equations are properly set up.

3. CROSS-SECTIONS: Wrong because forces are wrong.
   Method is correct (A = N/σ, d = 2√(A/π)).

**Recommendation:** Student understands the method well.
Ask them to recheck the load values from the assignment diagram.

### Score: 4/22 (reactions wrong → cascade failure)
### Adjusted score (method): 19/22 (method correct, one input error)
```

### Summary Report (class overview)

```markdown
# MD2 Truss — Class Summary
## BBM169 Spring 2026, checked 2026-03-27

| Student | Variant | Reactions | Forces | Sections | Deform. | Score | Notes |
|---------|---------|-----------|--------|----------|---------|-------|-------|
| Jodzonaite | K1 | ✓ | ✓ | ✓ | ✓ | 22/22 | Perfect |
| Treikale | K4 | ✓ | 18/25 | ✓ | ✓ | 19/22 | 2 force errors |
| Baiks | K5 | ⚠ | ⚠ | ⚠ | — | 8/22 | Wrong reactions |
| ... | | | | | | | |

### Common errors this batch:
1. Wrong load value in moment equation (3 students)
2. Sin/cos swap in diagonal member (2 students)
3. Sign convention error at joint 4 (1 student)

### Students needing consultation:
- Baiks — fundamental reaction error, needs review of moment method
- (student X) — systematic sign error, needs review of FBD conventions
```

---

## Implementation Options for Phase 2

### Option B1: Claude Code Skill (for teachers who use Claude Code)

A skill file at `~/.claude/skills/check-homework.md` that:
1. Reads the folder structure above
2. For each student PDF in `submissions/`:
   - Uses vision to read the homework
   - Compares to variant answers
   - Traces error chains
   - Writes report to `reports/`
3. Generates class summary

**Usage:** `claude "check all homework in courses/BBM169_2026/submissions/MD2_truss/"`

### Option B2: MCP Server (for Claude Desktop)

A small Python MCP server that:
1. Exposes tools: `list_submissions`, `check_student`, `generate_summary`
2. Claude Desktop connects to it
3. Teacher says: "Check all MD2 submissions"
4. Claude calls the tools, reads PDFs, produces reports

**Advantage:** Works in Claude Desktop app — teacher just types in chat.
**Setup:** Install Python + run `pip install homework-checker` + add MCP config.

### Option C: Streamlit Web App

A new SFEM module: `homework_app/`
- Teacher uploads student PDFs
- Selects course + task
- App calls AI API (Gemini Flash for speed, Claude for diagnosis)
- Shows visual report with pass/fail per answer
- Export as PDF/Excel

**Advantage:** Zero installation for teachers — just a URL.
**Disadvantage:** Needs hosting + API keys + development time.

---

## What to Build First (Proof of Concept)

### Fastest path to a demo for colleagues:

1. **Create a Claude Project** with the system prompt + answer keys (1 hour)
2. **Process 3 student homeworks** live in front of colleagues (15 min)
3. **Show the diagnostic report** — "here's where student X made their error"

This requires ZERO code, ZERO infrastructure. Just a Claude Pro subscription.

### If they're convinced:

4. Build the folder structure + variant YAML files (half day)
5. Create a Claude Code skill or MCP server for batch processing (1-2 days)
6. Or build a Streamlit homework module (1 week)

---

## Pre-requisites (regardless of approach)

Before any of this works, we need:

1. **Reference answers for all variants** — solve all 10 kopnes correctly
   (currently blocked by fem_app solver bug — can compute manually or use
   the original external solver that created the .struct files)

2. **Standardized member numbering** — a diagram with numbered members
   that students must use (currently students invent their own labeling)

3. **Image quality guidelines** — pen not pencil, scan app, good lighting

4. **For future tasks beyond trusses** — each new task type needs:
   - Task definition (what to check)
   - Variant definitions (geometry, loads, correct answers)
   - Checking logic (what error patterns to look for)
