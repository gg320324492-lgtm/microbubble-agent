# Scientific Data Analysis Agent (Phase 8-H2)

## Architecture

```
Scientific Dataset
        |
        v
Scientific Data Analyst (Facade)
        |
  +-----+-----+-----------+--------------+-----------+
  |           |           |              |           |
  v           v           v              v           v
Data       Statistical  Model        Visualization  Scientific
Quality    Analyzer     Fitting      Planner        Interpretation
Analyzer                Engine
  |           |           |              |           |
  v           v           v              v           v
Quality    Statistical  ModelFit      Figure       Scientific
Report     Results      Results       Recommendations Conclusions
  |           |           |              |           |
  +-----------+-----------+--------------+-----------+
                        |
                        v
              AnalysisReport
```

## Components

### Data Quality Analyzer
Evaluates dataset quality:
- **Completeness** — percentage of non-empty cells
- **Missing values** — per-variable null/empty counts
- **Outliers** — IQR method (1.5×IQR beyond Q1/Q3)
- **Invalid values** — type mismatches (string in number column)
- **Duplicate rows** — exact match detection

### Statistical Analyzer
Computes descriptive statistics:
- **Mean, Median** — central tendency
- **Std, Variance** — dispersion
- **CV (Coefficient of Variation)** — normalized variability
- **Correlation** — pairwise Pearson r for numeric variable pairs

### Model Fitting Engine
Fits multiple models and ranks by R²:
- **Kinetic models**: zero-order, first-order, second-order
- **Regression**: linear (least squares)
- **Polynomial**: quadratic (least squares)
- Returns all fits sorted by R² descending

### Visualization Planner
Recommends figures based on variable types:
- **Time-series** → line chart (date × numeric)
- **Distribution** → histogram (numeric)
- **Comparison** → bar chart (string × numeric)
- **Correlation** → scatter plot (numeric × numeric)
- **Model** → scatter + fitting curve

### Scientific Interpretation
Generates conclusions from analysis results:
- **Quality interpretation** — data sufficiency assessment
- **Statistical interpretation** — correlation strength, variability
- **Model interpretation** — best-fit model, kinetic behavior
- No hallucinated values — conclusions from data only

## Data Pipeline

1. **Input**: ScientificDataset (variables + rows + metadata)
2. **Quality**: Assess completeness, detect issues
3. **Statistics**: Compute descriptive stats + correlations
4. **Model**: Fit kinetic/regression models, rank by R²
5. **Visualization**: Recommend figures for data exploration
6. **Interpretation**: Generate scientific conclusions
7. **Output**: AnalysisReport (quality + statistics + models + figures + conclusions)

## Determinism

All components are deterministic:
- Same input always produces same output
- No random number generation
- No time-dependent behavior
- No external state dependencies

## Security Boundary

The data analyst:
- **Never** modifies datasets
- **Never** calls LLM APIs directly
- **Never** stores API keys, tokens, or credentials
- **Only** analyzes data and generates reports
