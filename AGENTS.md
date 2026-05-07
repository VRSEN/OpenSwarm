# CodeSwarm — Customization Guide

This file gives coding agents (Cursor, Claude Code, Codex, etc.) everything they need to understand and customize this swarm. Read it before making any changes.

---

## What is CodeSwarm?

CodeSwarm is a multi-agent AI development team you can fork and reshape for any coding workflow. Each agent is a specialist — architect, frontend dev, backend dev, code reviewer, QA tester, and DevOps. They collaborate through a shared architect (orchestrator).

---

## Folder Structure

```
swarm.py                  <- main config: imports all agents, defines how they connect
shared_instructions.md    <- context shared across every agent
server.py                 <- API entry point (FastAPI server)

architect/
  architect.py            <- agent definition
  instructions.md         <- system prompt

frontend_dev/
  frontend_dev.py
  instructions.md
  tools/                  <- custom tools for this agent

backend_dev/
  backend_dev.py
  instructions.md
  tools/

code_reviewer/
  code_reviewer.py
  instructions.md
  tools/

qa_tester/
  qa_tester.py
  instructions.md
  tools/

devops/
  devops.py
  instructions.md
  tools/

shared_tools/             <- tools available to all agents
```

---

## How Agents Connect (`swarm.py`)

`swarm.py` is the only file you need to edit when adding, removing, or rewiring agents. It:

1. Imports a `create_*` factory function from each agent folder
2. Instantiates all agents
3. Defines communication flows — who can talk to whom

The default pattern is **architect-to-all**: the architect can send messages to every specialist, and all agents can hand off to each other.

---

## How to Customize

To build your own coding swarm from this repo:

1. **Fork and rename** the repo (e.g., `mobile-dev-swarm`)
2. **Decide which agents to keep, rename, or replace**
   - Rename the folder and its files to match the new agent's purpose
   - Update `instructions.md` with the new system prompt
   - Update `swarm.py` to import and register the renamed agent
3. **Add or remove tools** inside each agent's `tools/` folder
4. **Update `shared_instructions.md`** with any context all agents should share
5. **Run** with `python swarm.py`

### Example prompt to give your coding agent

> "Turn this into a mobile development swarm. Replace Frontend Dev with an iOS Developer and an Android Developer, keep Backend Dev for API work, and add a Mobile QA specialist. The Architect should understand mobile app architecture patterns."

The coding agent will read this file, understand the structure, and make the right changes automatically.

---

## Current Agents

| Agent | Purpose | Specialties |
|---|---|---|
| `architect` | Plans architecture and routes tasks | System design, component breakdown, task delegation |
| `frontend_dev` | Frontend implementation | React, Vue, Angular, TypeScript, CSS, UI/UX |
| `backend_dev` | Backend implementation | Node.js, Python, APIs, databases, auth |
| `code_reviewer` | Code quality assurance | Reviews, security, best practices, refactoring |
| `qa_tester` | Testing and QA | Unit tests, integration tests, E2E, bug hunting |
| `devops` | Infrastructure and deployment | CI/CD, Docker, Kubernetes, cloud, monitoring |

---

## Key Conventions

- Each agent folder has one `<name>.py` file and one `instructions.md`
- `instructions.md` is the agent's system prompt — edit it to change behavior
- Tools live in `tools/` and are auto-loaded by the agent definition
- `shared_tools/` contains utilities available to all agents
- Models are configured via `DEFAULT_MODEL` in `.env` — never hardcoded

---

## Additional Resources

Before proceeding with agent creation, please read the following instructions carefully:

- `.cursor/rules/agency-swarm-workflow.mdc` - your primary guide for creating agents and agencies

The following files can be read on demand, depending on the task at hand:

- `.cursor/commands/add-mcp.md` - how to add MCP servers to an agent
- `.cursor/commands/mcp-code-exec.md` - how to convert an MCP server into the Code Execution Pattern
- `.cursor/commands/write-instructions.md` - how to write effective instructions for AI agents
- `.cursor/commands/create-prd.md` - how to create a PRD for an agent
