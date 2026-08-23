# Experiment Optimization Agent (Phase 8-H1)

## Architecture

```
Experiment Plan + Observations
              |
              v
Experiment Optimization Agent (Facade)
              |
  +-----------+-----------+--------------+--------------+
  |           |           |              |              |
  v           v           v              v              v
Experiment  Variable    Mechanism     Optimization   Next
Analyzer   Importance  Interpreter   Advisor        Experiment
  |           |           |              |              |
  v           v           v              v              v
Issues     Importance  Explanations  Suggestions    Recommendations
  |           |           |              |              |
  +-----------+-----------+--------------+--------------+
                        |
                        v
          ExperimentOptimizationResult
```

## Components

### Experiment Analyzer
Detects anomalies in observations:
- **Outlier detection** — z-score > 2.0 identifies abnormal values
- **Contradiction detection** — checks if independent variable increase consistently improves dependent variable
- **Missing data detection** — identifies planned metrics absent from observations
- **Unexpected trend detection** — high coefficient of variation (CV > 30%) flags unreliable trends

### Variable Importance Analyzer
Calculates variable importance using range-sensitivity analysis:
- **Range sensitivity** — metric change / variable change ratio
- **Monotonicity** — checks if trend is consistent across data points
- **Confidence** — based on data coverage and monotonicity
- **Sorting** — results sorted by importance descending

### Mechanism Interpreter
Translates issues into scientific explanations using domain knowledge:
- **Environment** — ozone degradation, bubble dynamics, mass transfer, radical generation
- **Material** — surface properties, crystallization, nanoparticle synthesis
- **Chemical** — catalysis, kinetics, selectivity
- No hallucinated values — explanations from knowledge base only

### Optimization Advisor
Generates suggestions from issues and variable importance:
- **Rule-based** — matches issue type + keywords to suggestion rules
- **Importance-driven** — focuses optimization on highest-impact variables
- **Confidence scoring** — reflects reliability of each suggestion

### Next Experiment Generator
Recommends follow-up experiments based on:
- **Variable importance** — prioritizes high-impact variables
- **Data coverage** — prioritizes variables with fewer observations
- **Range extension** — suggests 20% range expansion for exploration
- **Purpose-driven** — each recommendation explains what it tests

## Optimization Workflow

1. **Input**: ExperimentPlan + ExperimentObservation[]
2. **Anomaly detection**: Find outliers, contradictions, missing data, unexpected trends
3. **Variable importance**: Calculate range sensitivity for each independent variable
4. **Mechanism interpretation**: Explain why anomalies occur using domain knowledge
5. **Optimization suggestions**: Generate actionable improvement recommendations
6. **Next experiments**: Recommend follow-up experiments with specific variable changes
7. **Output**: ExperimentOptimizationResult (complete optimization package)

## Determinism

All components are deterministic:
- Same input always produces same output
- No random number generation
- No time-dependent behavior
- No external state dependencies

## Security Boundary

The optimization agent:
- **Never** modifies experiment data
- **Never** calls LLM APIs directly
- **Never** stores API keys, tokens, or credentials
- **Only** analyzes observations and generates recommendations
