# Literature Quality Evaluation (Phase 8-G0)

## Good Paper Criteria

A high-quality scientific paper should have:

### Structural Signals
- **Author information** — Clear authorship with affiliations
- **Publication year** — Recent work (within 5-10 years) preferred for fast-moving fields
- **DOI** — Digital Object Identifier for verification and citation
- **Journal/conference** — Peer-reviewed venue with impact factor
- **Abstract** — Concise summary of methods, results, and conclusions

### Content Quality
- **Methodology section** — Detailed experimental setup, materials, and procedures
- **Results with statistics** — Quantitative data with error bars, p-values, confidence intervals
- **Discussion** — Interpretation of results in context of existing literature
- **Limitations** — Honest assessment of study constraints
- **Reproducibility** — Sufficient detail for independent replication

### Citation Patterns
- **Diverse references** — Mix of recent and foundational works
- **Self-citation balance** — Moderate self-citation (10-30%) is normal
- **Cross-disciplinary** — References from related fields
- **Primary sources** — Cites original research, not just reviews

## Unreliable Paper Patterns

### Red Flags
- **No DOI or journal** — Predatory or non-peer-reviewed
- **Missing methods** — "Black box" experiments without detail
- **No error analysis** — Results without statistical validation
- **Overclaiming** — Conclusions far beyond data scope
- **Cherry-picking** — Selective reporting of favorable results
- **P-hacking** — Manipulated statistical analysis to achieve significance
- **Image manipulation** — Duplicated or doctored figures

### Methodological Issues
- **Small sample size** — Insufficient statistical power
- **No controls** — Missing baseline comparisons
- **Confounding variables** — Uncontrolled factors affecting results
- **Measurement bias** — Unblinded or subjective assessments
- **Selective reporting** — Only positive results shown

## Reproducibility Checks

### Essential Elements
1. **Materials and methods** — Complete experimental protocol
2. **Raw data availability** — Accessible datasets (dryad, zenodo, etc.)
3. **Code availability** — Analysis scripts (github, zenodo)
4. **Statistical analysis** — Full pipeline from raw to results
5. **Equipment specifications** — Model numbers, calibration details

### Verification Steps
- Check if results have been independently replicated
- Look for corrigenda or retractions
- Verify statistical claims with provided data
- Assess if methods are standard for the field
- Confirm sample size is adequate for claimed effects

## Scoring Heuristic

The Literature Critic uses a weighted scoring system:

| Factor | Weight | High Score (0.8+) | Low Score (<0.3) |
|--------|--------|-------------------|------------------|
| Citation coverage | 0.3 | Multiple high-confidence citations | No or weak citations |
| Content completeness | 0.3 | Rich, diverse text content | Fragmented or minimal |
| Source credibility | 0.2 | Peer-reviewed journal | Manual or informal |
| Metadata richness | 0.2 | Author, year, DOI, keywords | Missing key metadata |

### Score Interpretation
- **0.8-1.0**: High quality — suitable for direct citation
- **0.6-0.8**: Good quality — minor concerns, cross-validate key claims
- **0.4-0.6**: Moderate quality — significant limitations, use with caution
- **0.2-0.4**: Low quality — unreliable, requires independent verification
- **0.0-0.2**: Poor quality — avoid citing, likely methodological issues
