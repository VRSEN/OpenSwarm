# BMAD Next Steps

## Priorità alta

1. **Template instantiation tools**
   - creare utility/tool che generino automaticamente artefatti BMAD da template
   - scrivere direttamente nei percorsi `_bmad-output/planning-artifacts/` e `_bmad-output/implementation-artifacts/`

2. **Validation tools**
   - controllare presenza di metadata block
   - controllare heading minimi
   - controllare coerenza tra status e next step

3. **Workflow-aware orchestrator refinement**
   - insegnare all'orchestratore a riconoscere esplicitamente la fase BMAD corrente
   - bloccare salti impropri tra fasi

## Priorità media

4. **Core BMAD exposure**
   - integrare anche skill core utili come:
     - bmad-party-mode
     - bmad-review-adversarial-general
     - bmad-review-edge-case-hunter
     - bmad-distillator
     - bmad-customize

5. **QA specialization**
   - creare un agente QA BMAD oppure un workflow QA più forte

6. **Brownfield support**
   - implementare in modo più forte:
     - bmad-document-project
     - bmad-generate-project-context

## Priorità bassa

7. **Packaging polish**
   - verificare inclusione completa degli asset `_bmad/custom/` nel package distributivo
   - documentare la procedura di aggiornamento rispetto all'upstream BMAD
