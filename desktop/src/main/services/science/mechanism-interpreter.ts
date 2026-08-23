// Mechanism Interpreter (Phase 8-H1: Experiment Optimization Agent).
//
// Phase 8-H1: deterministic interpretation of optimization issues into
// scientific explanations using domain knowledge. No hallucinated values.

import type {
  OptimizationIssue
} from '../../../shared/science/experiment-optimization-schema'
import type { ExperimentPlan } from '../../../shared/science/research-design-schema'

// ============ Domain knowledge base ============

interface MechanismEntry {
  keywords: readonly string[]
  explanation: string
}

const ENVIRONMENT_KB: readonly MechanismEntry[] = [
  { keywords: ['ozone', 'o3', 'degradation', 'oxidation'],
    explanation: 'Ozone degradation involves direct molecular oxidation and indirect radical pathways (OH, O). Mass transfer of O3 from gas to liquid phase is often rate-limiting — smaller bubbles increase interfacial area and improve dissolution.' },
  { keywords: ['bubble', 'microbubble', 'nanobubble', 'size', 'diameter'],
    explanation: 'Bubble size directly governs gas-liquid interfacial area per unit volume. Smaller bubbles (micro/nano) provide higher surface-area-to-volume ratio, enhancing mass transfer coefficients (kLa) and extending bubble residence time.' },
  { keywords: ['mass transfer', 'dissolution', 'klA', 'interfacial'],
    explanation: 'Mass transfer at gas-liquid interfaces follows two-film theory. The transfer coefficient depends on turbulence, bubble size, and contact time. Insufficient mass transfer limits overall reaction rate in gas-liquid systems.' },
  { keywords: ['removal', 'efficiency', 'pollutant', 'degradation'],
    explanation: 'Pollutant removal efficiency depends on the balance between mass transfer rate, reaction kinetics, and contact time. Insufficient removal may indicate mass transfer limitation or inadequate oxidant dosage.' },
  { keywords: ['radical', 'hydroxyl', 'oh', 'reactive'],
    explanation: 'Hydroxyl radical generation during bubble collapse (cavitation) provides additional oxidation pathways. Radical yield depends on bubble dynamics, energy input, and solution chemistry.' },
  { keywords: ['pressure', 'gas flow', 'dosage'],
    explanation: 'Operating pressure and gas flow rate determine bubble formation dynamics and gas holdup. Higher pressure produces smaller bubbles but may reduce gas throughput. Optimal conditions balance bubble size with gas availability.' }
]

const MATERIAL_KB: readonly MechanismEntry[] = [
  { keywords: ['surface', 'morphology', ' roughness'],
    explanation: 'Surface properties (roughness, wettability, functional groups) govern interfacial interactions. Surface modification can enhance or inhibit adhesion, reaction, and transport processes.' },
  { keywords: ['crystal', 'crystallization', 'nucleation', 'phase'],
    explanation: 'Crystallization kinetics depend on supersaturation, temperature, and nucleation rate. Controlled crystallization produces desired phase, size, and morphology. Rapid nucleation yields many small crystals; slow growth yields fewer large ones.' },
  { keywords: ['nanoparticle', 'synthesis', 'size control'],
    explanation: 'Nanoparticle synthesis involves nucleation and growth stages. Size control requires balancing nucleation rate (burst nucleation) with growth rate (Ostwald ripening, aggregation).' }
]

const CHEMICAL_KB: readonly MechanismEntry[] = [
  { keywords: ['catalyst', 'catalytic', 'active site', 'turnover'],
    explanation: 'Catalytic activity depends on active site density, accessibility, and electronic structure. Catalyst deactivation may occur through poisoning, sintering, or leaching. Activity scales with accessible surface area.' },
  { keywords: ['kinetic', 'rate', 'activation', 'arrhenius'],
    explanation: 'Reaction kinetics follow Arrhenius behavior: rate increases exponentially with temperature. Activation energy determines temperature sensitivity. Higher activation energy means stronger temperature dependence.' },
  { keywords: ['selectivity', 'yield', 'product distribution'],
    explanation: 'Product selectivity depends on relative reaction rates of competing pathways. Thermodynamic vs kinetic control determines product distribution. Temperature, catalyst, and residence time are key selectivity controls.' }
]

const ALL_KBS = [
  { domain: 'environment', entries: ENVIRONMENT_KB },
  { domain: 'material', entries: MATERIAL_KB },
  { domain: 'chemical', entries: CHEMICAL_KB }
]

// ============ Explanation lookup ============

function findExplanations(
  issue: OptimizationIssue,
  plan: ExperimentPlan
): string[] {
  const allText = (issue.description + ' ' + issue.evidence + ' ' +
    plan.hypothesis + ' ' + plan.expectedOutcome).toLowerCase()
  const explanations: string[] = []

  for (const kb of ALL_KBS) {
    for (const entry of kb.entries) {
      const matches = entry.keywords.filter(kw => allText.includes(kw))
      if (matches.length > 0) {
        explanations.push(entry.explanation)
        break // one explanation per domain KB
      }
    }
  }

  if (explanations.length === 0) {
    explanations.push(`The observed ${issue.type} may indicate a systematic measurement issue or environmental variability that warrants further investigation.`)
  }

  return explanations
}

// ============ Public API ============

/**
 * Phase 8-H1: interpret optimization issues into scientific explanations.
 * Deterministic — knowledge base lookup, no hallucinated values.
 */
export function interpretMechanism(
  issues: OptimizationIssue[],
  plan: ExperimentPlan
): string[] {
  const explanations: string[] = []
  for (const issue of issues) {
    const found = findExplanations(issue, plan)
    for (const exp of found) {
      if (!explanations.includes(exp)) {
        explanations.push(exp)
      }
    }
  }
  return explanations
}
