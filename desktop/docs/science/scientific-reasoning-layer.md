# Scientific Reasoning Layer (Phase 8-G0)

## Architecture

```
Research Workspace
        |
        v
Scientific Reasoner (Facade)
        |
  +-----+-----+----------------+
  |           |                |
  v           v                v
Literature  Claim         Method
Critic      Extractor     Selector
  |           |                |
  v           v                v
Paper       Scientific    Method
Assessment  Claims        Recommendation
                    |
                    v
              Conflict
              Analyzer
                    |
                    v
              Research
              Conflict
```

## Components

### Literature Critic
Evaluates paper quality based on:
- Citation coverage (confidence scores, count)
- Content completeness (chunk count, average length, metadata)
- Source credibility (journal vs preprint vs manual)
- Metadata richness (author, year, DOI, keywords)

### Claim Extractor
Extracts `ScientificClaim` objects from document chunks:
- Category detection via keyword signals (mechanism/observation/correlation/causation/prediction)
- Evidence type classification (experiment/simulation/theory/statistical/review)
- Confidence estimation from retrieval scores + quantitative content signals

### Conflict Analyzer
Compares two claims for conflicts using:
- Scale difference (orders of magnitude in numeric claims)
- Method difference (simulation vs experiment)
- Parameter difference (different categories, overlapping terms)
- Measurement error (low-confidence observations)
- Insufficient data (few evidence items, low confidence)

### Method Selector
Recommend scientific methods based on research problem domain:
- Kinetics: pseudo-first-order, Langmuir/Freundlich, two-film theory
- CFD: Euler-Euler, VOF, DPM, k-epsilon
- Optimization: RSM, DOE, NSGA-II
- Statistics: ANOVA, regression, Mann-Whitney
- Characterization: DLS, electron microscopy, zeta potential

## Data Flow

1. User submits research question
2. Planner creates ResearchPlan with steps
3. Knowledge retrieval finds relevant documents
4. **Scientific Reasoner** analyzes each document:
   - Literature Critic scores quality
   - Claim Extractor extracts claims + evidence
5. Claims are compared across documents:
   - Conflict Analyzer identifies disagreements
   - Resolution suggestions generated
6. Method Selector recommends analysis approaches
7. Results assembled into response with citations

## Security Boundary

The reasoning layer:
- **Never** modifies document storage
- **Never** calls LLM APIs directly
- **Never** stores API keys, tokens, or credentials
- **Only** analyzes text content and structural metadata
- All data flows through injected dependencies

## Confidence Model

Confidence is computed from:
- Retrieval score (0.3-1.0 weight)
- Quantitative content density (+0.1 for numbers)
- Statistical significance mentions (+0.05)
- Hedging language penalty (-0.05 per hedge word)

## Determinism

All functions are deterministic:
- Same input always produces same output
- No random number generation
- No time-dependent behavior
- No external state dependencies
