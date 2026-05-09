# OpenSwarm — Customization Guide

This file gives coding agents (Cursor, Claude Code, Codex, etc.) everything they need to understand and customize this swarm. Read it before making any changes.

---

## What is OpenSwarm?

OpenSwarm is a multi-agent AI team you can fork and reshape into any kind of swarm you need — SEO, sales, research, finance, customer support, or anything else. Each agent is a specialist. They collaborate through a shared orchestrator.

---

## Folder Structure

```
swarm.py                  ← main config: imports all agents, defines how they connect
shared_instructions.md    ← context shared across every agent
run.py                    ← CLI entry point (terminal demo)
server.py                 ← API entry point (FastAPI server)

orchestrator/
  orchestrator.py         ← agent definition
  instructions.md         ← system prompt

data_analyst_agent/
  data_analyst_agent.py
  instructions.md
  tools/                  ← custom tools for this agent

docs_agent/
  docs_agent.py
  instructions.md
  tools/

slides_agent/
  slides_agent.py
  instructions.md
  tools/

image_generation_agent/
  image_generation_agent.py
  instructions.md
  tools/

video_generation_agent/
  video_generation_agent.py
  instructions.md
  tools/

deep_research/
  deep_research.py
  instructions.md
  tools/

virtual_assistant/
  virtual_assistant.py
  instructions.md
  tools/

shared_tools/             ← tools available to all agents (Composio integrations, etc.)
```

---

## How Agents Connect (`swarm.py`)

`swarm.py` is the only file you need to edit when adding, removing, or rewiring agents. It:

1. Imports a `create_*` factory function from each agent folder
2. Instantiates all agents
3. Defines communication flows — who can talk to whom

The default pattern is **orchestrator-to-all**: the orchestrator can send messages to every specialist, and all agents can hand off to each other.

---

## How to Customize

To build your own swarm from this repo:

1. **Fork and rename** the repo (e.g., `seo-swarm`)
2. **Decide which agents to keep, rename, or replace**
   - Rename the folder and its files to match the new agent's purpose
   - Update `instructions.md` with the new system prompt
   - Update `swarm.py` to import and register the renamed agent
3. **Add or remove tools** inside each agent's `tools/` folder
4. **Update `shared_instructions.md`** with any context all agents should share
5. **Run** with `python run.py`

### Example prompt to give your coding agent

> "Turn this into an SEO optimization swarm. The Research Agent becomes an SEO Keyword Planner, the Docs Agent becomes a Blog Post Writer, the Data Analyst becomes an SEO Analytics Agent (Google Search Console + GA4), and the General Agent handles technical SEO like schema markup and site audits. Keep the orchestrator and shared tools as-is."

The coding agent will read this file, understand the structure, and make the right changes automatically.

### BMAD integration note

This repository also contains a BMAD installation scaffold under `_bmad/` and `_bmad-output/`. If you are customizing the swarm for software delivery, prefer extending the BMAD-specific agents and keeping planning artifacts under `_bmad-output/planning-artifacts/` and implementation artifacts under `_bmad-output/implementation-artifacts/`.

The BMAD integration is not only agent-based. The authoritative customization layer now also lives in `_bmad/custom/` and includes:
- workflow definitions
- templates
- artifact contracts
- metadata schema

When refining software-delivery behavior, update those assets first and then align agent instructions and routing.

---

## Current Agents

| Agent | Purpose |
|---|---|
| `orchestrator` | Routes tasks to the right specialist |
| `virtual_assistant` | Email, calendar, Slack, file management |
| `deep_research` | Web research and synthesis |
| `data_analyst_agent` | Data analysis, visualization, statistical modeling |
| `docs_agent` | Document creation and editing |
| `slides_agent` | PowerPoint / HTML slide generation |
| `image_generation_agent` | AI image generation and editing |
| `video_generation_agent` | AI video generation and editing |
| `bmad_business_analyst` | BMAD software discovery, briefs, and project framing |
| `bmad_product_manager` | BMAD PRD, requirements, and validation workflows |
| `bmad_architect` | BMAD architecture, epics/stories, and readiness workflows |
| `bmad_developer` | BMAD development execution and review workflows |
| `bmad_technical_writer` | BMAD technical documentation and summaries |

---

## Key Conventions

- Each agent folder has one `<name>.py` file and one `instructions.md`
- `instructions.md` is the agent's system prompt — edit it to change behavior
- Tools live in `tools/` and are auto-loaded by the agent definition
- `shared_tools/` contains Composio-powered integrations (Gmail, Slack, GitHub, etc.) available to all agents
- Models are configured via `DEFAULT_MODEL` in `.env` — never hardcoded

Before proceeding with agent creation, please read the following instructions carefully:

- `.cursor/rules/agency-swarm-workflow.mdc` - your primary guide for creating agents and agencies

The following files can be read on demand, depending on the task at hand:

- `.cursor/commands/add-mcp.md` - how to add MCP servers to an agent
- `.cursor/commands/mcp-code-exec.md` - how to convert an MCP server into the Code Execution Pattern (progressive tool disclosure, 98% token reduction)
- `.cursor/commands/write-instructions.md` - how to write effective instructions for AI agents
- `.cursor/commands/create-prd.md` - how to create a PRD for an agent (use for complex multi agent systems)
