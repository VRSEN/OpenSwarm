# BMAD Artifact Contracts for OpenSwarm

Questo documento definisce i contratti minimi degli artefatti BMAD nello swarm.

## Regole generali

Ogni artefatto BMAD deve contenere nell'ordine:
1. blocco `# Metadata`
2. blocco YAML racchiuso in code fence
3. sezione `# Status`
4. corpo del documento
5. sezione finale `# Next Step`

## Campi metadata obbligatori

- `artifact_type`
- `artifact_id`
- `status`
- `owner_agent`
- `stage`
- `project`
- `last_updated`
- `source_inputs`
- `recommended_next_agent`

## Regole per status

Valori ammessi:
- `draft`
- `in_review`
- `ready`
- `blocked`
- `superseded`

Regole operative:
- `blocked` richiede almeno un elemento in `blocking_issues`
- tutti gli status richiedono una sezione `# Next Step` valorizzata
- `superseded` dovrebbe indicare nell'handoff o nel next step quale artefatto sostituisce il corrente

## Regole di handoff

- `BMAD Business Analyst` -> `BMAD Product Manager`
- `BMAD Product Manager` -> `BMAD Architect`
- `BMAD Architect` -> `BMAD Developer` o `BMAD Technical Writer`
- `BMAD Developer` -> `BMAD Developer`, `BMAD Architect` o `BMAD Technical Writer`
- `BMAD Technical Writer` -> `Docs Agent` o stakeholder finali

## Coerenza artifact_type / owner / stage

Regole attuali applicate dal validator:
- `product-brief` -> owner `BMAD Business Analyst`, stage `analysis`
- `prd` -> owner `BMAD Product Manager`, stage `planning`
- `architecture` -> owner `BMAD Architect`, stage `solutioning`
- `story` -> owner `BMAD Developer`, stage `implementation`
- `readiness-report` -> owner `BMAD Architect`, stage `planning`

## Heading minimi per template

- `product-brief`: Executive Summary, Problem Statement, Target Users and Stakeholders, Goals, Non-Goals, Constraints, Assumptions, Risks, Open Questions, Evidence and Inputs Used, Next Step
- `prd`: Executive Summary, Product Vision, Problem and Opportunity, Target Users, User Journeys, Functional Requirements, Non-Functional Requirements, Success Metrics, Constraints and Dependencies, Out of Scope, Risks, Open Questions, Readiness Verdict, Next Step
- `architecture`: Executive Summary, System Context, Architectural Drivers, Proposed Architecture, Components and Responsibilities, Data and Integration Flows, Technology Choices, Risks and Trade-Offs, Open Questions, Next Step
- `story`: Context, Description, Acceptance Criteria, Dependencies, Implementation Notes, Test Notes, Validation Notes, Next Step
- `readiness-report`: Scope Reviewed, Findings, Gaps, Risks, Recommendations, Next Step

## Brownfield workflows supportati

Strumenti dedicati:
- `document-project`
- `generate-project-context`
- `quick-dev`
- `correct-course`

Questi workflow possono usare l'analisi dell'albero progetto e il riepilogo degli artefatti BMAD esistenti per guidare discovery, project context, quick development e correzione rotta.

## QA workflow minimo

1. Validare ogni artefatto con il validator singolo o di directory.
2. Eseguire un pass QA con il tool BMAD QA.
3. Correggere tutti gli errori prima di dichiarare un flusso `ready`.
4. Riesaminare i warning per drift fra ownership, handoff e completezza.
5. Pubblicare un readiness report o un QA report quando serve visibilità verso stakeholder.

## Regole di qualità

Un agente BMAD non deve dichiarare un deliverable `ready` se:
- mancano campi metadata obbligatori
- manca `# Next Step`
- manca il passaggio di stato esplicito
- il documento non contiene gli heading minimi richiesti dal suo template
- owner, stage o handoff non sono coerenti con l'`artifact_type`
