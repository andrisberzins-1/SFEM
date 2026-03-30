# Homework Checking Workflow Proposal
## Būvmehānikas ievadkurss — Truss Analysis (Topics 2 & 3)

### The Core Dilemma

> Students must submit handwritten work to prove they worked through the problem.
> But handwritten answers are hard to check automatically.

The trick is: **don't eliminate handwriting — supplement it with a structured answer sheet**.

---

## Vision/OCR Options for Reading Handwriting Directly

### Live Test Results (this session)

I extracted all member forces from Jodzonaite's 5 pages using Claude Opus vision:

| Value | Claude Read | Excel Answer Key | Match? |
|-------|------------|------------------|--------|
| V₁ | 36.67 | 36.67 | ✓ exact |
| V₁₃ | 13.33 | 13.33 | ✓ exact |
| N₁₋₄ | 63.34 | 63.3 | ✓ (0.1%) |
| N₄₋₅ | 63.34 | 63.3 | ✓ (0.1%) |
| N₅₋₈ | 90.02 | 90.0 | ✓ (0.0%) |
| N₈₋₉ | 90.02 | 90.0 | ✓ (0.0%) |
| N₃₋₅ | 48.46 | 48.4 | ✓ (0.1%) |
| N₅₋₇ | 18.63 | 18.6 | ✓ (0.2%) |
| N₁₋₃ | -70.82 | (not in Excel) | — |
| N₃₋₆ | -106.68 | (not in Excel) | — |
| Tension/Compression labels | all correct | — | ✓ |

**100% accuracy on Jodzonaite's digital handwriting (tablet).** Every value matched.

### AI Vision Providers Comparison

| Provider | Handwriting Quality | Speed | Cost | Best For |
|----------|-------------------|-------|------|----------|
| **Claude Opus 4.6** | Excellent — captures nuance, strict schema output | ~3-5s/page | ~$0.02/page | Structured extraction with reasoning |
| **Gemini 2.5/3 Pro** | Best-in-class — #1-2 on LMArena Vision | ~2-3s/page | ~$0.01/page | High accuracy, spatial reasoning |
| **Gemini 3 Flash** | Very good — #4 overall | <0.2s/page | ~$0.001/page | High volume, speed priority |
| **Mathpix API** | Purpose-built for math/STEM | <1s/image | $0.002/image | LaTeX output, equation-native |
| **GPT-5.2 Vision** | Excellent — #1 ELO overall | ~2-3s/page | ~$0.02/page | General document understanding |
| **Google Cloud Vision** | Good for printed, weaker for handwriting | <1s/page | $0.0015/page | Printed text, barcodes |

### Recommendation by Architecture

**Option 1: Claude-only (simplest, current session)**
- Use Claude Code / Cowork sessions
- Teacher uploads PDF, Claude reads each page and checks answers
- No API setup needed
- Cost: included in Claude subscription
- **Limitation:** manual per-student, ~2-3 min each

**Option 2: Gemini Flash batch pipeline (cheapest at scale)**
- Script sends each page to Gemini Flash API
- Structured JSON output: {member: force, ...}
- Compare programmatically to reference
- Cost: ~$0.01 per student (10 pages × $0.001)
- **Best for 50+ students** — runs all homeworks in minutes

**Option 3: Mathpix for equation extraction**
- Purpose-built for handwritten math → LaTeX
- Could parse entire calculation chain, not just final answers
- Cost: $0.002/image × ~10 pages = $0.02/student
- **Best if you want to check methodology**, not just answers

**Option 4: Hybrid — Gemini Flash + Claude spot-check**
- Gemini Flash reads all numerical answers (cheap, fast)
- Claude Opus reviews flagged pages where values don't match (deep reasoning)
- Best accuracy-to-cost ratio

### Key Insight from Testing

The **main challenge is NOT reading the numbers** — all modern vision models handle that well for clean handwriting like Jodzonaite's. The real challenges are:

1. **Member identification** — which force belongs to which member? Students use their own node/member labeling
2. **Messy handwriting** — Treikale's pen-on-grid-paper is harder than Jodzonaite's tablet writing
3. **Crossed-out work** — students sometimes cross out wrong calculations
4. **Inconsistent formatting** — every student lays out their work differently

These challenges exist regardless of which AI model you use. They're solved by either:
- Standardizing the answer format (Excel summary sheet)
- Standardizing the handwritten format (answer boxes on assignment)
- Or accepting ~85-90% automation with human review for edge cases

---

## Methodology Diagnosis — Can AI Find WHERE the Error Is?

### What was tested

I attempted to trace through **three students'** calculation chains:
- **Jodzonaite** — tablet/stylus, clean digital handwriting
- **Treikale** — pen on grid paper, decent handwriting
- **Baiks** — pencil on grid paper, photographed at angle with shadows

### Results by difficulty level

**Level 1: "Is the final answer correct?"** — trivial once values are extracted
- Just compare to reference. Any AI model handles this.

**Level 2: "Are the intermediate steps internally consistent?"**
This is where it gets interesting. For Baiks' page 4 I traced:
1. Reactions: V₁ = 40 kN, V₁₃ = 20 kN, H₁ = 30 kN ← **can verify ΣF=0, ΣM=0**
2. Angle: arctan(3.2/2) = 57.99° ← **can verify numerically** ✓
3. Joint 1 equilibrium: N₁₋₃ = -35/sin(57.99°) = -41.27 kN ← **can verify** ✓
4. N₁₋₄ = 20 + 41.27·cos(57.99°) = 41.895 kN ← **can verify** ✓

**This works well** — each equation can be checked independently. If step 1 is wrong,
I can say "reactions are incorrect, all subsequent forces inherit this error."

**Level 3: "What conceptual mistake did the student make?"**
This is the hardest and most valuable for consultation prep. Examples:
- Used wrong angle (swapped sin/cos)
- Used wrong sign convention (forgot tension = positive)
- Applied load at wrong node
- Forgot a force in the equilibrium equation
- Made arithmetic error in one specific division

AI **can** detect these by:
1. Checking each equation: does ΣFy actually = 0 with their values?
2. If not, which term is wrong?
3. Is the angle calculation correct for their geometry?
4. Did they use the right loads from the assignment?

### The honest assessment for each handwriting quality

| Quality | Read values | Trace equations | Diagnose errors | Confidence |
|---------|------------|-----------------|-----------------|------------|
| Jodzonaite (tablet) | 100% | 100% | High | Can fully diagnose |
| Treikale (pen, clean) | ~90% | ~85% | Medium | Can diagnose most errors, some digit ambiguity |
| Baiks (pencil, photo) | ~60-70% | ~50% | Low | Can flag suspicious steps but uncertain on specific digits |

### Key bottleneck: It's not the AI model — it's the image quality

Baiks' homework is hard to read not because of AI limitations but because:
- **Pencil** is inherently lower contrast than pen or stylus
- **Photographed at angle** introduces perspective distortion
- **Shadows** from the phone/hand obscure parts of the page
- **Grid paper** creates visual noise that competes with the writing

**Even a human would struggle** with some of Baiks' values. The solution is image quality requirements, not better AI.

### Practical recommendations for methodology diagnosis

**What to require from students for photo submissions:**
1. Use **pen, not pencil** (or dark mechanical pencil)
2. Photograph **directly from above** (not at angle)
3. Good **lighting** (no shadows across the page)
4. Use a **scanner app** (CamScanner, Adobe Scan, Notes app) that auto-corrects perspective and enhances contrast
5. Or better: use a **flatbed scanner** if available

**What the AI checking pipeline can realistically diagnose:**
1. ✓ Wrong reactions (most common error — verifiable independently)
2. ✓ Wrong angle calculations (verifiable from geometry)
3. ✓ Sign errors in equilibrium (check if ΣF actually = 0)
4. ✓ Arithmetic errors (verify each calculation step)
5. ✓ Missing forces in FBD (compare number of terms to expected)
6. ~ Wrong FBD cut (harder — requires understanding which members connect to which joint)
7. ✗ Conceptual misunderstanding of method (would need to understand student's reasoning narrative)

**Error propagation analysis — the most useful feature:**
When the final answer is wrong, the AI can trace backward:
- "Final force N₅₋₈ = 49.76 kN is wrong (expected: 53.21 kN)"
- "Tracing back: this value depends on N₃₋₅ from Joint 3"
- "N₃₋₅ = 12.63 kN — this is also wrong (expected: 15.41 kN)"
- "N₃₋₅ depends on reaction V₁ = 40 kN"
- "→ ROOT CAUSE: V₁ is incorrect. Check moment equation."

This is exactly what saves consultation time — instead of "your answer is wrong",
the student gets "your error is in the moment equation for reactions, line 2 of page 4."

---

## Proposed Workflow

### Student Side

Students submit **two things**:

#### 1. Handwritten calculation pages (PDF scan, as today)
- Full method of joints / sections work
- Free body diagrams at each node
- Equilibrium equations
- Cross-section and deformation calculations
- **This proves they did the work** — AI can generate correct answers but cannot fake handwritten process

#### 2. Answer summary sheet (structured, typed)

A **single-page form** where they transcribe their final answers into a table.
This is the part that gets auto-checked.

**Format options (easiest → most powerful):**

| Option | Format | Effort to create | Auto-checkable |
|--------|--------|-------------------|----------------|
| A | Word/PDF table template | 5 min | 90% — parse table from docx |
| B | Excel template | 10 min | 99% — read cells directly |
| C | Web form (Streamlit) | 2-3 hours | 100% — structured data |
| D | Paper form with fixed boxes | 10 min | 80% — OCR fixed positions |

**Recommended: Option B (Excel template)** — minimal effort, students already know Excel, trivially parseable.

### Answer Sheet Template (Excel)

```
Sheet: "Uzdevums 1"
──────────────────────────────────────────────────────
Row 1:  Studenta vārds: [           ]  Apliecības nr: [        ]
Row 2:  Kopnes shēma nr: [  ]  (auto-filled from last digit)
Row 3:
Row 4:  BALSTA REAKCIJAS
Row 5:  V₁ (kN) | H₁ (kN) | V₁₃ (kN)
Row 6:  [      ] | [      ] | [       ]
Row 7:
Row 8:  PIEPŪLES STIEŅOS
Row 9:  Stieņa Nr | Mezgli | N (kN) | Stiepe(+)/Spiede(-)
Row 10: 1          | 1-2    | [     ] | [                  ]
Row 11: 2          | 2-3    | [     ] | [                  ]
...     (pre-filled member numbering from truss diagram)
Row 35:
Row 36: STIEPTO STIEŅU ŠĶĒRSGRIEZUMI (σ = 300 MPa)
Row 37: Stieņa Nr | N (kN) | A (mm²) | d (mm)
Row 38: [        ] | [     ] | [      ] | [     ]
...
Row 48:
Row 49: DEFORMĀCIJAS (E = 210 GPa, ν = 0.3)
Row 50: Stieņa Nr | ε       | Δl (mm) | Δd (mm)
Row 51: [        ] | [      ] | [      ] | [      ]
...

Sheet: "Uzdevums 2"
(same structure, σ = 450 MPa)
```

**Key design decisions:**
- Member numbering is **pre-printed** on the truss diagram and in the template → forces students to use consistent labeling
- Student fills in yellow cells only
- Template has **conditional formatting**: negative N values auto-highlight as compression
- One template file for all variants (student enters their scheme number)

### Why This Catches AI-Assisted Cheating

1. **Handwritten pages prove process** — AI can give answers, but cannot produce handwritten equilibrium work page by page. Copy-pasting AI output looks obvious.

2. **Cross-referencing** — Claude can spot-check that handwritten intermediate values on the pages match the typed final answers. If the Excel says N₁₋₂ = -50 kN but the handwritten page shows a different calculation leading to -50, that's consistent. If the handwritten work shows N₁₋₂ = -30 but the typed answer says -50 (correct), that's suspicious.

3. **Method checking** — Claude can verify that the student used the correct free body diagrams, correct sign convention, correct angles. Even if the answer is right, the method tells the story.

### Teacher Side (Checking Workflow)

```
┌─────────────────────────────────────┐
│  Teacher runs: "Check homework"     │
│  (Claude Code session or Cowork)    │
└──────────────┬──────────────────────┘
               │
    ┌──────────▼──────────┐
    │  1. Load student's  │
    │     Excel answer     │
    │     sheet            │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  2. Identify variant│
    │     from student ID │
    │     → load .struct  │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  3. Solve truss     │
    │     (reference       │
    │     answers)         │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  4. Compare student │
    │     answers to       │
    │     reference        │
    │     (tolerance ±2%)  │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  5. Generate grading│
    │     report (Excel    │
    │     with ✓/✗ marks)  │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │  6. OPTIONAL:        │
    │     Spot-check       │
    │     handwritten PDF  │
    │     for methodology  │
    │     (Claude vision)  │
    └──────────────────────┘
```

### Grading Output

The checking script produces an annotated copy of the student's Excel:

| Check | Student | Reference | Status |
|-------|---------|-----------|--------|
| V₁    | 36.67   | 36.67     | ✓      |
| V₁₃   | 13.33   | 13.33     | ✓      |
| N₁₋₂  | -5.00   | -5.00     | ✓      |
| N₃₋₅  | 48.40   | 48.38     | ✓ (Δ=0.04%) |
| A₃₋₅  | 162.00  | 161.27    | ✓ (Δ=0.5%)  |
| d₃₋₅  | 14.40   | 14.33     | ✗ (Δ=0.5%, but exceeds 0.3% for diameters) |
| ...   |         |           |        |
| **Score: 18/22 correct** | | | |

Plus a flag for any suspiciously perfect answers (all exactly matching reference to 4 decimal places → likely copied from solver, not hand-calculated).

---

## Implementation Phases

### Phase 1: Template + Checking Script (this semester, ~1 day work)

1. Create Excel answer template with pre-filled member numbering for all 10 schemes
2. Fix the fem_app solver bug (separate task)
3. Write a Python checking script that:
   - Reads student Excel
   - Solves reference truss
   - Compares and produces grading report
4. Can be run as a Claude Code command or standalone script

### Phase 2: Handwriting Spot-Check (next semester, ~2 days)

1. Add Claude vision cross-referencing:
   - Extract key values from handwritten pages
   - Compare to typed answers for consistency
   - Flag discrepancies
2. Optional: annotate handwritten PDF with marks in margins

### Phase 3: SFEM Homework Module (future, ~1-2 weeks)

1. Web-based homework submission:
   - Student enters ID → auto-loads correct truss variant
   - Shows the truss diagram
   - Student fills in answers in web form
   - Instant feedback on correctness (self-checking mode)
   - Export results for teacher review
2. Still requires handwritten scan upload for methodology verification

---

## Member Numbering Convention

For the checking to work, students and the reference must use the **same member numbering**. Current .struct files number members 1-25 by connectivity order.

**Recommendation:** Add a numbered truss diagram to the homework assignment showing member numbers explicitly. Each scheme gets its own diagram. This eliminates ambiguity about which member is "Member 3-5" vs "Member 5-3".

The numbered diagrams can be generated from the .struct files automatically using Plotly or matplotlib.

---

## Tolerance Strategy

| Quantity | Tolerance | Rationale |
|----------|-----------|-----------|
| Reactions (kN) | ±0.5% or ±0.01 kN | Hand calculation rounding |
| Member forces (kN) | ±1% or ±0.1 kN | Accumulated rounding |
| Cross-section area (mm²) | ±1% | One division step |
| Diameter (mm) | ±1% | Square root rounding |
| Deformations (mm) | ±2% | Multiple calculation steps |

Values within tolerance → ✓
Values outside tolerance but correct method shown in handwriting → partial credit (teacher decision)
Values wildly wrong → ✗

---

## Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| Student submission | Handwritten PDF only | Handwritten PDF + Excel answer sheet |
| Checking method | Manual, page by page | Auto-check Excel, spot-check handwriting |
| Time per student | ~15-20 min | ~2-3 min (review report + spot-check) |
| Accuracy of grading | Human judgment | Computational verification |
| Catches AI cheating? | Somewhat (handwriting) | Better (cross-reference handwriting vs typed) |
| Student effort | Same calculations | Same + 5 min to fill Excel |
| Setup effort | None | ~1 day (template + script) |
