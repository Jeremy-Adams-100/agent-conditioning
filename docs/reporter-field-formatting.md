# Reporter Agent: Field-Specific Report Formatting

Date: 2026-03-21

## Problem

The current reporter uses a fixed output format (Overview, Work Performed,
Key Findings, Decisions Made, Open Items, Gaps in Record) regardless of the
research field. This structure reads like a project management update — not
like a research document in the field being studied.

A mathematician expects: Definitions, Lemmas, Theorems, Proofs, Remarks.
A physicist expects: Theory, Model, Results, Analysis.
An engineer expects: Introduction, Methodology, Results, Discussion.
A biologist expects: Background, Methods, Observations, Interpretation.

The codebase details (file counts, test assertions, directory structure)
currently appear as main sections. These are implementation artifacts and
should be in an appendix, not the body.

## Design Principles

1. **Soft guidance, not rigid templates.** The reporter should adapt its
   structure based on the research topic, not follow a hardcoded format.
   The field is inferred from the exploration directive and content, not
   from a user-supplied config parameter.

2. **Field detection is the reporter's job.** The reporter already reads
   the directive and all session content. It can determine whether the
   work is mathematics, physics, engineering, etc. This doesn't need a
   separate classifier — the reporter's gather phase naturally reveals
   the field.

3. **Guidance, not enforcement.** The reporter should have recommended
   section structures per field, but can deviate when the content warrants
   it. A physics exploration that proves a theorem should use proof
   formatting for that section, even though "Proof" isn't in the default
   physics template.

4. **Appendix for implementation details.** File structure, test counts,
   library inventories, code organization — these go in an appendix.
   The main body is about the research, not the codebase.

## Field-Specific Section Recommendations

### Mathematics
Core sections (in order):
- **Introduction** — problem statement, motivation, context
- **Definitions** — key terms, notation, conventions
- **Results** — theorems, lemmas, propositions (each with proof or
  computational verification)
- **Examples** — worked examples demonstrating the results
- **Remarks** — observations, connections to other areas, asides
- **Open Questions** — unresolved problems, conjectures

Conventions:
- Number theorems/lemmas sequentially (Theorem 1, Lemma 2, ...)
- Proofs follow their statement immediately
- Use \begin{equation} for key results
- "Q.E.D." or similar end-of-proof markers

### Physics
Core sections (in order):
- **Introduction** — physical system, motivation, scope
- **Theory** — governing equations, assumptions, derivations
- **Model** — computational approach, discretization, parameters
- **Results** — numerical/analytical results with figures
- **Analysis** — interpretation, comparison to known results, limits
- **Conclusions** — summary of findings

Conventions:
- Equations are central — display key equations with numbers
- Figures are expected (plots, phase diagrams, field visualizations)
- SI units or natural units stated explicitly
- Compare to established results where possible

### Chemistry
Core sections (in order):
- **Introduction** — system, motivation, relevant literature
- **Theory** — quantum chemistry methods, approximations used
- **Computational Details** — basis sets, software, convergence criteria
- **Results and Discussion** — combined, organized by property/system
- **Conclusions** — summary, comparison to experiment if available

Conventions:
- Report energies in consistent units (eV, Hartree, kcal/mol)
- Tabulate numerical results
- Compare to experimental data where available

### Biology / Biophysics
Core sections (in order):
- **Introduction** — biological context, research question
- **Methods** — computational approach, models, parameters
- **Observations** — results organized by biological question
- **Interpretation** — what the results mean biologically
- **Implications** — broader significance, predictions

Conventions:
- Biological context first, math/computation second
- Figures should illustrate biological structures/processes
- Statistical measures where applicable

### Engineering / Applied Computation
Core sections (in order):
- **Introduction** — engineering problem, requirements, constraints
- **Methodology** — approach, algorithms, implementation choices
- **Results** — performance data, validation, convergence studies
- **Discussion** — trade-offs, limitations, comparison to alternatives
- **Conclusions and Recommendations** — actionable outcomes

Conventions:
- Quantitative validation against benchmarks
- Error analysis and convergence studies
- Practical recommendations, not just findings

### General / Interdisciplinary
Fallback for topics that don't clearly fit one field:
- **Overview** — what was investigated and why
- **Approach** — how the investigation was structured
- **Findings** — key results, organized by sub-topic
- **Discussion** — interpretation, connections, limitations
- **Open Questions** — what remains

## Appendix (All Fields)

Every report, regardless of field, should end with an appendix:

**Appendix: Implementation Details**
- Code organization (directory structure, file counts)
- Libraries and functions created
- Test suite results (assertions, pass/fail)
- Tool versions (Wolfram Engine version, etc.)
- Session references (cycle range, session IDs)

This separates the research narrative from the engineering bookkeeping.

## Implementation Approach

**Where to inject:** The reporter's role definition in `exploration-score.yaml`,
specifically the OUTPUT FORMAT section. Replace the current fixed format with
field-adaptive guidance.

**How to inject:** Replace the hardcoded section list with:
1. A brief instruction to detect the field from the directive and content
2. The field-specific section recommendations (concise, not the full detail
   above — the reporter is an LLM, it knows what math/physics papers look like)
3. The appendix requirement

**What to keep fixed:**
- Title format: `# {main_topic} — {cycle_range}`
- The appendix requirement (always present)
- The `[OUTPUT: report]` / `[END OUTPUT: report]` markers
- The pandoc compilation command

**What becomes adaptive:**
- The main body sections
- Whether to use theorem/proof formatting
- Whether equations are numbered
- The voice (mathematical precision vs engineering pragmatism)

**Token cost:** The guidance should be ~200 tokens. The reporter already has
a generous budget. The field detection adds zero tokens — it comes from
reading the content the reporter already gathers.

## Example: How the Reporter Would Handle a Math Exploration

Current output:
```
## Overview
Cycles 1-3 explored quantum mechanics postulates...

## Work Performed
The worker built qm_postulates.wls with 20 functions...

## Key Findings
The Pauli matrices satisfy σ_x σ_y σ_z = iI...
```

Improved output:
```
## Introduction
This report covers the axiomatic foundations of quantum mechanics...

## Definitions and Notation
States are represented as column vectors (kets) in a finite-dimensional
Hilbert space. We adopt ℏ = 1 throughout.

## Results
**Theorem 1 (Spectral Decomposition).** Every Hermitian operator A
admits a spectral decomposition A = Σ aₙ|aₙ⟩⟨aₙ|...

*Verification.* Computed numerically for the Pauli matrices...

## Appendix: Implementation Details
- 20 public functions in qm_postulates.wls (155 lines)
- 32 test assertions, all passing
```

The research content is the same. The presentation matches the field.
