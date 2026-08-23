# Paper Generation Agent (Phase 8-H3)

## Architecture

```
Research Data (Design + Analysis)
              |
              v
    Manuscript Generator (Facade)
              |
  +-----------+-----------+--------------+-----------+
  |           |           |              |           |
  v           v           v              v           v
Paper       Scientific  Figure        SCI Language  Manuscript
Structure   Writer      Caption       Reviewer      Output
Planner                 Generator
  |           |           |              |           |
  v           v           v              v           v
Outline     Section     Figure        Writing      Manuscript
            Drafts      Captions      Issues
```

## Components

### Paper Structure Planner
Generates IMRaD outline from research data:
- **Introduction**: problem → gap → objective
- **Methods**: materials → procedure → analysis
- **Results**: observation → statistics → model fits
- **Discussion**: interpretation → literature comparison → limitations
- **Conclusion**: key contributions → implications → future work

### Scientific Writer
Generates section drafts from outline key points:
- Template-based scientific writing
- No hallucinated values — uses only provided data
- Observation-first in results section
- Mechanism interpretation in discussion

### Figure Caption Generator
Creates figure captions from visualization recommendations:
- Describes what the figure shows (no invented values)
- References model fits (R² values) when applicable
- Follows SCI figure caption conventions

### SCI Language Reviewer
Detects writing issues:
- **Overstatement**: "proves", "definitely", "undoubtedly"
- **Unsupported claims**: claims without numerical evidence
- **Repeated sentences**: duplicate text across paragraphs
- **Missing hedging**: results without uncertainty qualifiers

## Manuscript Pipeline

1. **Structure**: Plan IMRaD outline from research design + analysis
2. **Write**: Generate section drafts from outline key points
3. **Figures**: Create captions for each visualization
4. **Review**: Detect writing issues (overstatement, repetition)
5. **Assemble**: Combine sections, figures, highlights into Manuscript

## SCI Writing Rules

- **Introduction**: problem statement → knowledge gap → study objective
- **Methods**: materials → procedure → analysis method
- **Results**: observation first, no mechanism interpretation
- **Discussion**: result → mechanism → literature comparison
- **Conclusion**: 4-point summary, no new data

## Determinism

All components are deterministic:
- Same input always produces same output
- No random number generation
- No time-dependent behavior
- No external state dependencies

## Security Boundary

The manuscript generator:
- **Never** modifies research data
- **Never** calls LLM APIs directly
- **Never** stores API keys, tokens, or credentials
- **Only** generates manuscript text from provided data
