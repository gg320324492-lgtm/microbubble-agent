# Scientific Writing Workflow (Phase 8-H3)

## Overview

The Scientific Paper Generation Agent automates the transformation of research results into SCI-style manuscripts through a deterministic pipeline.

## Workflow

### Step 1: Input Collection

**Required inputs:**
- `ResearchDesignResult` — problem analysis, hypotheses, experiment plan, model selection
- `AnalysisReport` — quality, statistics, model fits, figures, conclusions

### Step 2: Structure Planning

The Paper Structure Planner generates a ManuscriptOutline:
- **IMRaD format**: Introduction, Methods, Results, Discussion, Conclusion
- **Key points**: extracted from research design and analysis
- **Figure count**: based on visualization recommendations
- **Reference count**: based on statistics and model fits

### Step 3: Section Writing

The Scientific Writer generates SectionDrafts:
- **Introduction**: problem → gap → objective (from design)
- **Methods**: variables → procedure → measurements (from experiment plan)
- **Results**: statistics → model fits (from analysis, observation-first)
- **Discussion**: mechanism → literature comparison (from conclusions)
- **Conclusion**: 4-point summary (from key findings)

### Step 4: Figure Captioning

The Figure Caption Generator creates FigureCaptions:
- **Line chart**: temporal evolution description
- **Histogram**: distribution shape description
- **Bar chart**: comparison description
- **Scatter**: relationship description
- **Scatter+fit**: model fit description with R²

### Step 5: Language Review

The SCI Language Reviewer detects issues:
- **Overstatement**: words like "proves", "definitely", "undoubtedly"
- **Unsupported claims**: claims without numerical evidence
- **Repeated sentences**: duplicate text across paragraphs
- **Missing hedging**: results without uncertainty qualifiers

### Step 6: Assembly

The Manuscript Generator assembles the final Manuscript:
- Sections with content
- Figure captions
- Highlights from conclusions
- Abstract from key conclusions

## Example: O3-Microbubble Degradation

### Input
- Design: optimize ozone microbubble degradation
- Analysis: first-order kinetics (R²=0.998), strong negative correlation

### Output Manuscript
```
Title: "First-Order Kinetics of Ozone Microbubble Degradation"
Abstract: "Ozone concentration decay follows first-order kinetics..."
Introduction: Research problem, mechanisms, objective
Methods: Variables, procedure, measurements
Results: Statistics, model fits
Discussion: Mechanism interpretation, literature comparison
Conclusion: Key contributions
Figures: "O3 concentration over time" with first-order fit
```

## Benefits

1. **Consistency** — same data always produces same manuscript structure
2. **Completeness** — IMRaD format ensures all sections are addressed
3. **Objectivity** — no hallucinated values, only data-driven content
4. **Efficiency** — automated first draft frees researcher time for refinement
5. **Quality** — language review catches common writing issues
