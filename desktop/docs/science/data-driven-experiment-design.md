# Data-Driven Experiment Design (Phase 8-H1)

## Overview

The Experiment Optimization Agent transforms raw experimental data into actionable scientific insights. This document demonstrates the workflow with a concrete example.

## Case Study: O3-Microbubble Degradation Optimization

### Experiment Setup

**Problem**: Optimize ozone microbubble-enhanced degradation of organic pollutants

**Variables**:
- Independent: bubble_diameter (nm), ozone_dosage (mg/L), pressure (MPa)
- Dependent: removal_efficiency (%), reaction_rate (mg/L·min)
- Control: temperature (25°C), pH (7.0)

**Observations** (5 experiments):

| Obs | Bubble Diameter | Ozone Dosage | Pressure | Removal Efficiency | Reaction Rate |
|-----|----------------|--------------|----------|-------------------|---------------|
| 1   | 200            | 5            | 0.2      | 85%               | 2.1           |
| 2   | 300            | 5            | 0.2      | 78%               | 1.8           |
| 3   | 200            | 10           | 0.2      | 92%               | 3.2           |
| 4   | 200            | 5            | 0.4      | 88%               | 2.5           |
| 5   | 200            | 15           | 0.2      | 95%               | 3.8           |

### Step 1: Anomaly Detection

**Output**:
```typescript
issues: [
  {
    type: 'outlier',
    description: 'Observation 2 has removal_efficiency=78% which deviates from mean',
    severity: 0.45,
    evidence: 'metric=removal_efficiency, value=78, mean=87.6, std=6.2'
  }
]
```

**Reasoning**: Observation 2 (300nm bubbles) shows lower removal efficiency than expected — flagged as potential outlier.

### Step 2: Variable Importance

**Output**:
```typescript
importantVariables: [
  { variable: 'ozone_dosage', importance: 0.82, contribution: 'ozone_dosage has strong positive effect on removal_efficiency', confidence: 0.75 },
  { variable: 'bubble_diameter', importance: 0.68, contribution: 'bubble_diameter has moderate negative effect on removal_efficiency', confidence: 0.65 },
  { variable: 'pressure', importance: 0.35, contribution: 'pressure has weak positive effect on removal_efficiency', confidence: 0.45 }
]
```

**Reasoning**: Ozone dosage has the strongest influence, followed by bubble diameter. Pressure has moderate effect.

### Step 3: Mechanism Interpretation

**Output**:
```typescript
explanations: [
  'Ozone degradation involves direct molecular oxidation and indirect radical pathways. Mass transfer of O3 from gas to liquid phase is often rate-limiting — smaller bubbles increase interfacial area and improve dissolution.',
  'Bubble size directly governs gas-liquid interfacial area per unit volume. Smaller bubbles provide higher surface-area-to-volume ratio, enhancing mass transfer coefficients.'
]
```

### Step 4: Optimization Suggestions

**Output**:
```typescript
suggestions: [
  {
    suggestion: 'Repeat measurement at outlier condition to verify reproducibility',
    reason: 'Outliers may indicate measurement error or genuine process variability',
    expectedEffect: 'Improved data reliability and confidence in trend analysis',
    confidence: 0.75
  },
  {
    suggestion: 'Focus optimization efforts on ozone_dosage — highest impact variable',
    reason: 'ozone_dosage has strong positive effect on removal_efficiency',
    expectedEffect: 'Optimizing ozone_dosage should produce the largest improvement',
    confidence: 0.75
  }
]
```

### Step 5: Next Experiment

**Output**:
```typescript
nextExperiments: [
  {
    changeVariable: 'ozone_dosage',
    currentValue: 10,
    suggestedRange: '12-18',
    purpose: 'Investigate ozone_dosage influence with expanded range'
  },
  {
    changeVariable: 'bubble_diameter',
    currentValue: 250,
    suggestedRange: '120-280',
    purpose: 'Investigate bubble_diameter influence with expanded range'
  }
]
```

## Benefits

1. **Objective analysis** — data-driven anomaly detection replaces subjective judgment
2. **Prioritized optimization** — variable importance guides resource allocation
3. **Scientific grounding** — mechanism interpretation provides physical understanding
4. **Iterative improvement** — next experiment recommendations enable systematic optimization
5. **Reproducibility** — deterministic analysis ensures consistent results

## Integration with Phase 8-H0

The Experiment Optimization Agent completes the research cycle:
1. **Phase 8-H0**: Design the initial experiment
2. **Phase 8-H1**: Analyze results and recommend improvements
3. **Repeat**: Use recommendations to design next experiment

This creates a closed-loop optimization cycle that progressively improves experimental outcomes.
