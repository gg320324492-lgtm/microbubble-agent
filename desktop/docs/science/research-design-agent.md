# Research Design Agent (Phase 8-H0)

## Architecture

```
Research Problem
        |
        v
Research Design Agent (Facade)
        |
  +-----+-----+----------------+----------------+
  |           |                |                |
  v           v                v                v
Problem    Hypothesis       Experiment      Model
Analyzer   Generator        Designer        Recommender
  |           |                |                |
  v           v                v                v
Problem    Research         Experiment       Model
Analysis   Hypotheses       Plan            Selection
  |           |                |                |
  +-----------+----------------+----------------+
                        |
                        v
              ResearchDesignResult
```

## Components

### Problem Analyzer
Analyzes a ResearchProblem into:
- **Key scientific question** — the core question to investigate
- **Possible mechanisms** — physical/chemical/biological processes involved
- **Required evidence** — data needed to test the hypothesis
- **Recommended approach** — experimental methodology suggestion

Uses domain-specific keyword matching (7 domains: environment, material, chemical, biomedical, engineering, physics, computer-science).

### Hypothesis Generator
Generates ResearchHypothesis objects from problem analysis:
- **Mechanism-based** — grounded in domain-specific physical processes
- **No hallucinated numbers** — statements are qualitative, not quantitative
- **Confidence scoring** — based on template confidence + adjustment factors
- **Multiple hypotheses** — generates 1-4 hypotheses per problem

### Experiment Designer
Creates ExperimentPlan with:
- **Design variables** — independent, dependent, and control variables with ranges
- **Experiment groups** — control group + treatment groups from evidence requirements
- **Measurements** — domain-appropriate measurement methods
- **Expected outcome** — predicted trend based on domain knowledge

### Model Recommender
Selects analysis models based on problem domain and keywords:
- **Kinetic models** — pseudo-first-order, Michaelis-Menten, Langmuir
- **Physical models** — Navier-Stokes, Beer-Lambert, Fourier
- **Statistical models** — RSM, DOE, ANOVA
- **ML models** — SVM, Random Forest, k-means
- **Confidence scoring** — based on keyword match strength

## Design Reasoning Flow

1. **Input**: ResearchProblem (title, objective, domain, constraints)
2. **Analysis**: Extract key question, mechanisms, evidence, approach
3. **Hypothesis**: Generate mechanism-based testable statements
4. **Experiment**: Design variables, groups, measurements, expected outcomes
5. **Model**: Select appropriate analysis method
6. **Output**: ResearchDesignResult (complete design package)

## Determinism

All components are deterministic:
- Same input always produces same output
- No random number generation
- No time-dependent behavior
- No external state dependencies

## Security Boundary

The design agent:
- **Never** modifies document storage
- **Never** calls LLM APIs directly
- **Never** stores API keys, tokens, or credentials
- **Only** analyzes problem descriptions and generates design recommendations
- All data flows through injected dependencies
