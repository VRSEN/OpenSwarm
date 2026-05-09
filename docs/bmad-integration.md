# Integrazione BMAD in OpenSwarm

Questo repository contiene ora un'integrazione BMAD orientata allo sviluppo applicativo.

## Stato attuale

È stata rilevata una installazione BMAD locale in:
- `_bmad/`
- `_bmad-output/`

Configurazione rilevata:
- BMAD version: `6.6.0`
- output planning: `_bmad-output/planning-artifacts`
- output implementation: `_bmad-output/implementation-artifacts`
- lingua configurata: italiano

## Agenti aggiunti

Sono stati aggiunti i seguenti specialisti BMAD:
- `BMAD Business Analyst`
- `BMAD Product Manager`
- `BMAD Architect`
- `BMAD Developer`
- `BMAD Technical Writer`

## Integrazione effettuata

Sono stati aggiornati:
- `swarm.py`
- `shared_instructions.md`
- `orchestrator/instructions.md`
- `README.md`
- `AGENTS.md`

Sono stati creati i nuovi moduli agente:
- `bmad_business_analyst/`
- `bmad_product_manager/`
- `bmad_architect/`
- `bmad_developer/`
- `bmad_technical_writer/`

## Workflow consigliato

Per richieste di sviluppo software, l'orchestratore dovrebbe seguire questa pipeline:

1. **BMAD Business Analyst**
   - idea discovery
   - product brief
   - PRFAQ

2. **BMAD Product Manager**
   - PRD
   - requisiti
   - validazione scope

3. **BMAD Architect**
   - architettura
   - epiche e storie
   - implementation readiness

4. **BMAD Developer**
   - story pronte allo sviluppo
   - supporto implementativo
   - code review

5. **BMAD Technical Writer**
   - documentazione tecnica
   - summary strutturati

## Limite importante

Il manifest locale BMAD (`_bmad/_config/files-manifest.csv`) elenca numerosi file, workflow e template, ma nella copia locale non tutti risultano materializzati sul filesystem. Per questo l'integrazione attuale è:
- **funzionale e nativa nello swarm**;
- **allineata alla struttura BMAD**;
- ma **non ancora un mirror completo di tutti gli asset sorgente BMAD**.

## Passi successivi consigliati

Per completare l'integrazione in modo ancora più profondo, i prossimi step sono:

1. materializzare o importare tutti i workflow/template BMAD mancanti;
2. aggiungere strumenti locali dedicati per creare automaticamente artefatti in `_bmad-output/`;
3. aggiungere un agente QA BMAD o integrare il flow QA nei ruoli esistenti;
4. testare il routing con richieste reali come:
   - "crea il PRD di una app SaaS"
   - "progetta l'architettura di una piattaforma multi-tenant"
   - "scomponi il progetto in epiche e storie"
   - "prepara una story pronta per implementazione"

## Esempi di prompt ora supportati

- "Voglio sviluppare una app per prenotazioni mediche, crea il brief BMAD"
- "Trasforma questa idea in un PRD completo"
- "Genera architettura, epiche e storie per questa piattaforma"
- "Crea una user story pronta per sviluppo per il login con ruoli"
