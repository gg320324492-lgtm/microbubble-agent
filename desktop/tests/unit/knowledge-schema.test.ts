// Phase 7-A0 Knowledge Schema tests.
//
// Coverage (>= 30 cases, no database):
//   - Paper entity (5)
//   - Experiment entity (4)
//   - Equipment entity (3)
//   - Dataset entity (3)
//   - Figure entity (3)
//   - ResearchProject entity (3)
//   - Parameter metadata (3)
//   - Measurement metadata (3)
//   - Citation metadata (3)
//   - Relationship validity (4)
//   - Extension compatibility (2)
//   - Security / no-secret (4)

import { describe, it, expect } from 'vitest'

import {
  isValidPaper,
  isValidExperiment,
  isValidEquipment,
  isValidDataset,
  isValidFigure,
  isValidResearchProject,
  isValidParameter,
  isValidMeasurement,
  isValidCitation,
  isValidRelationship,
  isExtensionFieldsSafe
} from '../../src/shared/knowledge/schemas'

// ============ Paper ============

describe('Phase 7-A0 Paper validator', () => {
  it('accepts a minimal Paper', () => {
    expect(isValidPaper({
      id: 'paper:abc123',
      title: 'Ozone degradation of tetracycline',
      authors: ['Wang, T.', 'Li, M.'],
      journal: 'Water Research',
      year: 2024,
      keywords: ['ozone', 'microbubble', 'TC'],
      researchField: 'water treatment',
      abstract: 'A study of TC removal using ozone micro-nano bubbles.'
    })).toBe(true)
  })
  it('rejects Paper missing required fields', () => {
    expect(isValidPaper({ id: 'paper:abc', title: 'X' })).toBe(false)
  })
  it('rejects Paper with year out of range', () => {
    expect(isValidPaper({
      id: 'paper:abc', title: 'X', authors: ['A'], journal: 'J',
      year: 1500, keywords: [], researchField: 'f', abstract: 'a'
    })).toBe(false)
  })
  it('rejects Paper with invalid id (special chars)', () => {
    expect(isValidPaper({
      id: 'paper with spaces', title: 'X', authors: ['A'], journal: 'J',
      year: 2024, keywords: [], researchField: 'f', abstract: 'a'
    })).toBe(false)
  })
  it('accepts Paper with optional fields', () => {
    expect(isValidPaper({
      id: 'paper:abc', title: 'X', authors: ['A'], journal: 'J',
      year: 2024, doi: '10.1234/abc', keywords: ['k'],
      researchField: 'f', abstract: 'a', methods: 'method', results: 'r',
      conclusions: 'c', relatedExperiments: ['exp:1'],
      parameters: [{ name: 'pH', value: 7.0 }]
    })).toBe(true)
  })
})

// ============ Experiment ============

describe('Phase 7-A0 Experiment validator', () => {
  it('accepts an O3-MNB-TC degradation Experiment', () => {
    expect(isValidExperiment({
      id: 'exp:o3-mnb-tc-001',
      name: 'O3-MNB-TC degradation',
      researchTopic: 'ozone micro-nano bubble degradation of tetracycline',
      objective: 'quantify TC removal rate under varying ozone dose',
      system: 'semi-batch bubble column',
      equipment: ['eq:mnb-generator-001'],
      parameters: [
        { name: 'ozone_concentration', value: 5.0, unit: 'mg/L' },
        { name: 'gas_flow', value: 1.0, unit: 'L/min' },
        { name: 'pressure', value: 0.3, unit: 'MPa' },
        { name: 'bubble_size', value: 50, unit: 'um' },
        { name: 'ph', value: 7.2 },
        { name: 'tc_concentration', value: 50, unit: 'mg/L' }
      ]
    })).toBe(true)
  })
  it('rejects Experiment with empty parameters array', () => {
    expect(isValidExperiment({
      id: 'exp:1', name: 'X', researchTopic: 't', objective: 'o',
      system: 's', equipment: [], parameters: []
    })).toBe(false)
  })
  it('rejects Experiment with invalid parameter', () => {
    expect(isValidExperiment({
      id: 'exp:1', name: 'X', researchTopic: 't', objective: 'o',
      system: 's', equipment: [],
      parameters: [{ name: '', value: 1 }]
    })).toBe(false)
  })
  it('accepts Experiment with measurements', () => {
    expect(isValidExperiment({
      id: 'exp:1', name: 'X', researchTopic: 't', objective: 'o',
      system: 's', equipment: [],
      parameters: [{ name: 'p', value: 1 }],
      measurements: [
        { metric: 'tc_removal', value: 87.3, method: 'HPLC', instrument: 'Agilent' }
      ]
    })).toBe(true)
  })
})

// ============ Equipment ============

describe('Phase 7-A0 Equipment validator', () => {
  it('accepts a microbubble generator', () => {
    expect(isValidEquipment({
      id: 'eq:mnb-generator-001',
      name: 'Microbubble generator',
      type: 'bubble-generator'
    })).toBe(true)
  })
  it('accepts Equipment with specifications map', () => {
    expect(isValidEquipment({
      id: 'eq:1', name: 'pump', type: 'pump',
      specifications: { 'flow-rate': '1 L/min' }
    })).toBe(true)
  })
  it('rejects Equipment missing type', () => {
    expect(isValidEquipment({ id: 'eq:1', name: 'X' })).toBe(false)
  })
})

// ============ Dataset ============

describe('Phase 7-A0 Dataset validator', () => {
  it('accepts a Dataset from an experiment', () => {
    expect(isValidDataset({
      id: 'ds:tcd-2024-09-15',
      name: 'TC degradation dataset',
      source: 'experiment:exp:o3-mnb-tc-001',
      variables: ['time', 'tc-concentration', 'o3-dose']
    })).toBe(true)
  })
  it('rejects Dataset with empty variables', () => {
    expect(isValidDataset({
      id: 'ds:1', name: 'X', source: 'sim', variables: []
    })).toBe(false)
  })
  it('rejects Dataset with negative samples', () => {
    expect(isValidDataset({
      id: 'ds:1', name: 'X', source: 'sim',
      variables: ['t'], samples: -5
    })).toBe(false)
  })
})

// ============ Figure ============

describe('Phase 7-A0 Figure validator', () => {
  it('accepts a SEM Figure', () => {
    expect(isValidFigure({
      id: 'fig:sem-001', type: 'SEM', source: 'data/sem/abc.png',
      caption: 'SEM image of microbubble structure'
    })).toBe(true)
  })
  it('accepts a CFD-contour Figure', () => {
    expect(isValidFigure({
      id: 'fig:cfd-001', type: 'CFD-contour', source: 'data/cfd/velocity.vtk',
      caption: 'Velocity contour at plane z=0.5'
    })).toBe(true)
  })
  it('rejects Figure with invalid type', () => {
    expect(isValidFigure({
      id: 'fig:1', type: 'unknown-type', source: 'x', caption: 'y'
    })).toBe(false)
  })
})

// ============ ResearchProject ============

describe('Phase 7-A0 ResearchProject validator', () => {
  it('accepts a ResearchProject', () => {
    expect(isValidResearchProject({
      id: 'proj:o3-mnb-2024',
      title: 'Ozone micro-nano bubble water treatment',
      members: ['Wang Tianzhi', 'Li Min'],
      topic: 'O3 MNB TC degradation',
      papers: ['paper:abc123'],
      experiments: ['exp:o3-mnb-tc-001'],
      datasets: ['ds:tcd-2024-09-15']
    })).toBe(true)
  })
  it('rejects ResearchProject missing topic', () => {
    expect(isValidResearchProject({
      id: 'proj:1', title: 'X', members: ['A'],
      papers: [], experiments: [], datasets: []
    })).toBe(false)
  })
  it('rejects ResearchProject with non-string array', () => {
    expect(isValidResearchProject({
      id: 'proj:1', title: 'X', members: [1], topic: 't',
      papers: [], experiments: [], datasets: []
    })).toBe(false)
  })
})

// ============ Parameter metadata ============

describe('Phase 7-A0 Parameter validator', () => {
  it('accepts ozone concentration parameter', () => {
    expect(isValidParameter({
      name: 'ozone_concentration', value: 5.0, unit: 'mg/L', source: 'experiment'
    })).toBe(true)
  })
  it('accepts pressure parameter with uncertainty', () => {
    expect(isValidParameter({
      name: 'pressure', value: 0.3, unit: 'MPa',
      uncertainty: 0.02, source: 'experiment'
    })).toBe(true)
  })
  it('rejects Parameter with object value', () => {
    expect(isValidParameter({ name: 'p', value: { x: 1 } })).toBe(false)
  })
})

// ============ Measurement metadata ============

describe('Phase 7-A0 Measurement validator', () => {
  it('accepts TC removal rate measurement', () => {
    expect(isValidMeasurement({
      metric: 'tc_removal_rate', value: 87.3, method: 'HPLC',
      instrument: 'Agilent 1260'
    })).toBe(true)
  })
  it('accepts qualitative observation (string value)', () => {
    expect(isValidMeasurement({ metric: 'observation', value: 'slight foam' })).toBe(true)
  })
  it('rejects Measurement with boolean value (must be observed)', () => {
    expect(isValidMeasurement({ metric: 'm', value: true })).toBe(false)
  })
})

// ============ Citation metadata ============

describe('Phase 7-A0 Citation validator', () => {
  it('accepts verified paper citation', () => {
    expect(isValidCitation({
      paperId: 'paper:abc123', source: 'paper', confidence: 'verified'
    })).toBe(true)
  })
  it('accepts inferred web citation (no confidence)', () => {
    expect(isValidCitation({
      paperId: 'paper:def456', source: 'web'
    })).toBe(true)
  })
  it('rejects Citation with invalid source', () => {
    expect(isValidCitation({
      paperId: 'paper:abc', source: 'unknown-source'
    })).toBe(false)
  })
})

// ============ Relationship validator ============

describe('Phase 7-A0 Relationship validator', () => {
  it('accepts Project -> Paper relationship', () => {
    expect(isValidRelationship({ id: 'proj:1' }, 'paper:abc', 'paper')).toBe(true)
  })
  it('accepts Experiment -> Equipment relationship', () => {
    expect(isValidRelationship({ id: 'exp:1' }, 'eq:mnb-gen', 'equipment')).toBe(true)
  })
  it('rejects self-reference', () => {
    expect(isValidRelationship({ id: 'paper:abc' }, 'paper:abc', 'paper')).toBe(false)
  })
  it('rejects invalid relationship kind', () => {
    expect(isValidRelationship({ id: 'proj:1' }, 'paper:abc', 'invalid-kind')).toBe(false)
  })
})

// ============ Extension compatibility ============

describe('Phase 7-A0 ExtensionFields', () => {
  it('accepts clean extension fields', () => {
    expect(isExtensionFieldsSafe({ phase7Tag: 'foo', notes: 'bar' })).toBe(true)
  })
  it('rejects extension fields containing secrets', () => {
    expect(() => isExtensionFieldsSafe({ apiKey: 'sk-leak' })).toThrow(/forbidden/)
  })
})

// ============ Security: no-secret enforcement ============

describe('Phase 7-A0 security — no-secret enforcement', () => {
  it('Paper validator throws when apiKey leaks in payload', () => {
    expect(() => isValidPaper({
      id: 'paper:abc', title: 'X', authors: ['A'], journal: 'J',
      year: 2024, keywords: [], researchField: 'f', abstract: 'a',
      apiKey: 'sk-supersecret'
    })).toThrow(/forbidden/)
  })
  it('Experiment validator throws when cipher leaks in payload', () => {
    expect(() => isValidExperiment({
      id: 'exp:1', name: 'X', researchTopic: 't', objective: 'o',
      system: 's', equipment: [],
      parameters: [{ name: 'note', value: 'cipher:abc' }]
    })).toThrow(/forbidden/)
  })
  it('Citation validator throws when Bearer leaks in payload', () => {
    expect(() => isValidCitation({
      paperId: 'paper:abc', source: 'paper',
      extra: 'Bearer sk-supersecret'
    })).toThrow(/forbidden/)
  })
  it('Equipment validator throws when token leaks in payload', () => {
    expect(() => isValidEquipment({
      id: 'eq:1', name: 'X', type: 'pump',
      auth: 'token=supertoken'
    })).toThrow(/forbidden/)
  })
})
