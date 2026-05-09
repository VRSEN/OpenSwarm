# BMAD Implementation Gap Analysis

## Premessa

La prima integrazione BMAD nello swarm aggiungeva principalmente i ruoli agente e il routing base. Questo non era sufficiente a riprodurre la forza del framework BMAD, che dipende da:
- output contracts rigidi
- template standardizzati
- workflow espliciti
- gating tra fasi
- metadata e stato degli artefatti

## Gap individuati

### 1. Mancanza di workflow espliciti
Prima mancava un workflow macchina-legibile che codificasse:
- fasi
- owner
- input richiesti
- output previsti
- transizioni consentite

### 2. Mancanza di template rigidi
Gli agenti avevano istruzioni generiche ma non template persistenti e riusabili nel repo.

### 3. Mancanza di schema artefatti
Non esisteva un contratto formale per metadata, status e next step.

### 4. Mancanza di allineamento con `_bmad/custom/`
L'installazione BMAD locale prevede override durevoli in `_bmad/custom/`. Senza questi override, la personalizzazione viveva solo nei prompt degli agenti dello swarm.

## Raffinamento implementato

Sono stati aggiunti:

### Workflow
- `_bmad/custom/workflows/bmad-software-delivery-workflow.yaml`

### Schemi
- `_bmad/custom/schemas/artifact-metadata.schema.json`

### Template
- `_bmad/custom/templates/product-brief-template.md`
- `_bmad/custom/templates/prd-template.md`
- `_bmad/custom/templates/architecture-template.md`
- `_bmad/custom/templates/story-template.md`
- `_bmad/custom/templates/readiness-report-template.md`

### Guide/contratti
- `_bmad/custom/guides/artifact-contracts.md`

### Override config BMAD
- `_bmad/custom/config.toml`

## Stato dopo il raffinamento

Ora l'integrazione BMAD nello swarm non si basa più solo su agenti aggiunti, ma anche su:
- un workflow esplicito
- template persistenti
- un contratto per gli artefatti
- override BMAD in posizione nativa prevista dal framework

## Limite residuo

Restano ancora possibili miglioramenti:
1. creare tool locali che instanzino automaticamente i template nei percorsi corretti;
2. aggiungere validazione automatica dei documenti rispetto allo schema;
3. integrare anche i workflow core BMAD non ancora esposti nello swarm, come party mode, distillator, editorial review, adversarial review;
4. aggiungere un BMAD QA agent dedicato o modellare meglio le attività QA nel developer flow.

## Conclusione

L'integrazione è ora molto più fedele alla filosofia BMAD: non solo ruoli, ma struttura, contratti e workflow.
