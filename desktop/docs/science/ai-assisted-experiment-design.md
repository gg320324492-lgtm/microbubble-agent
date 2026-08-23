# AI-Assisted Experiment Design (Phase 8-H0)

## Overview

The Research Design Agent helps scientists plan experiments by analyzing research problems and generating structured design recommendations. This document walks through a concrete example.

## Case Study: Microbubble Ozone Degradation Optimization

### Input Problem

```typescript
const problem: ResearchProblem = {
  problemId: 'mb-ozone-001',
  title: 'Optimize microbubble-enhanced ozone degradation',
  objective: 'Improve ozone mass transfer efficiency for pollutant removal using microbubble technology',
  domain: 'environment',
  constraints: ['lab-scale reactor', 'budget < 50k RMB', '3-month timeline']
}
```

### Step 1: Problem Analysis

**Output:**
```typescript
{
  keyScientificQuestion: 'How does bubble size affect ozone transfer efficiency in pollutant removal?',
  possibleMechanisms: ['mass transfer', 'radical generation', 'oxidation'],
  requiredEvidence: ['pollutant concentration', 'removal efficiency', 'reaction kinetics', 'byproduct formation'],
  recommendedApproach: 'batch experiment'
}
```

**Reasoning:**
- The domain is `environment`, which activates environment-specific knowledge
- Keywords "ozone", "degradation", "mass transfer" match environment mechanisms
- The approach "batch experiment" is standard for initial parameter screening

### Step 2: Hypothesis Generation

**Output:**
```typescript
[
  {
    hypothesisId: 'mb-ozone-001-h1',
    statement: 'Enhanced mass transfer through increased interfacial area improves pollutant removal efficiency',
    mechanism: 'mass transfer',
    confidence: 0.80
  },
  {
    hypothesisId: 'mb-ozone-001-h2',
    statement: 'Reactive radical generation during bubble collapse accelerates chemical oxidation of target compounds',
    mechanism: 'radical generation',
    confidence: 0.73
  }
]
```

**Reasoning:**
- Two hypotheses match the "mass transfer" and "radical" mechanisms
- Confidence decreases slightly for the second hypothesis (diminishing confidence)

### Step 3: Experiment Design

**Output:**
```typescript
{
  planId: 'mb-ozone-001-plan',
  variables: [
    { name: 'bubble_diameter', type: 'independent', range: '50-500 nm', unit: 'nm', importance: 0.90 },
    { name: 'removal_efficiency', type: 'dependent', range: '0-100%', unit: '%', importance: 0.75 },
    { name: 'temperature', type: 'control', range: '20-25', unit: '°C', importance: 0.60 },
    { name: 'initial_concentration', type: 'independent', range: '10-100 mg/L', unit: 'mg/L', importance: 0.45 }
  ],
  groups: [
    { groupId: 'mb-ozone-001-g-control', condition: 'conventional aeration (no microbubbles)', purpose: 'Establish baseline performance' },
    { groupId: 'mb-ozone-001-g1', condition: 'varied pollutant concentration', purpose: 'Investigate concentration effect' }
  ],
  measurements: [
    { name: 'particle_size_distribution', method: 'dynamic light scattering', reason: 'Characterize bubble size distribution' },
    { name: 'pollutant_concentration', method: 'UV-Vis spectroscopy', reason: 'Quantify removal efficiency' },
    { name: 'dissolved_oxygen', method: 'DO meter', reason: 'Measure oxygen transfer performance' }
  ],
  expectedOutcome: 'Decreasing bubble diameter increases removal efficiency up to optimal size'
}
```

### Step 4: Model Selection

**Output:**
```typescript
{
  model: 'pseudo-first-order kinetic model',
  purpose: 'Quantify degradation kinetics and rate constants',
  justification: 'Standard model for dilute pollutant removal processes',
  confidence: 0.82
}
```

## Benefits

1. **Structured approach** — ensures all key aspects are considered
2. **Domain expertise** — leverages established experimental methodologies
3. **Reproducibility** — generates documented, systematic designs
4. **Time savings** — automates initial design phase, freeing researcher time for analysis
5. **Consistency** — applies same rigorous standards to every problem

## Limitations

- **Qualitative, not quantitative** — does not predict specific numerical outcomes
- **Template-based** — may miss novel approaches outside knowledge base
- **No validation** — recommendations should be reviewed by domain experts
- **No literature integration** — does not check if similar experiments already exist

## Integration with Phase 8-G0

The Research Design Agent can be combined with the Scientific Reasoning Layer:
1. Use Phase 8-G0 to analyze existing literature and extract claims
2. Use Phase 8-H0 to design experiments that test those claims
3. Use Phase 8-G0's conflict analyzer to compare results with existing claims
