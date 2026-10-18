<div align="center">

# 🚀 OpenSwarm

![OpenSwarm](assets/new-framework.jpg)

</div>

**The fully open-source multi-agent system that does everything Claude Code can't.**

Create polished slide decks, research reports, data visualizations, documents, images, and videos — all from a single prompt in your terminal. No platform, no UI, no setup hassles.

✨ **One prompt → Complete deliverables**<br>
🎯 **8 specialized agents working together**<br>
⚡ **Install in 30 seconds, running in 60**<br>
🔧 **100% customizable and forkable**<br>

Built on [Agency Swarm](https://github.com/VRSEN/agency-swarm) — the framework powering real AI swarms.<br>

---

> 💼 **Investor or looking to integrate AI agents into your SaaS?**
> We're the team behind OpenSwarm and Agency Swarm, building the future of multi-agent systems.
> **[Partner with us →](https://vrsen-ai.notion.site/fee2d391a8d74b24baa04a0b648af83c?pvs=105)**

---

## 💡 What Makes This Different?

Instead of one agent trying to do everything poorly, you get **specialists coordinated by an orchestrator**.

### 🎯 Real Examples

Paste these into your terminal and watch magic happen:

- **"Create a complete investor pitch for OpenSwarm"** → Full deck + executive summary + market research
- **"Research my top 5 competitors and write 3 SEO-optimized blog posts"** → Competitive analysis + keyword research + publish-ready content
- **"Analyze this data and create a quarterly report with charts"** → Data insights + visualizations + formatted document
- **"Generate a product launch video with animations"** → Professional video with graphics and transitions
- **"Build me a marketing campaign for Q2"** → Strategy doc + creative assets + implementation timeline

Connect to 10,000+ external services (Gmail, Slack, GitHub, HubSpot) via Composio for even more power.

---

## 🤖 Meet Your AI Team

| Agent                      | What it does                                                                                                                                                                                 |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Orchestrator**           | Routes every user request to the right specialist(s). Never answers directly — pure coordination.                                                                                            |
| **Virtual Assistant**      | Handles everyday tasks: writing, scheduling, messaging, task management. Gains 10,000+ external integrations via [Composio](https://composio.dev) (Gmail, Slack, GitHub, HubSpot, and more). |
| **Deep Research**          | Conducts comprehensive, evidence-based web research with citations and balanced analysis.                                                                                                    |
| **Data Analyst**           | Analyses structured data, builds charts, runs statistical models — all inside an isolated IPython kernel.                                                                                    |
| **Slides Agent**           | Generates complete, visually polished HTML slide decks, then exports them to PPTX.                                                                                                           |
| **Docs Agent**             | Creates formatted Word documents and PDFs from outlines or raw content.                                                                                                                      |
| **Image Generation Agent** | Generates and edits images using Gemini 2.5 Flash Image / Gemini 3 Pro Image and fal.ai.                                                                                                     |
| **Video Generation Agent** | Produces videos via Sora (OpenAI), Veo (Google), and Seedance (fal.ai); also edits and combines clips.                                                                                       |

---

## 📦 Get Started in 30 Seconds

```bash
npx @vrsen/openswarm
```

That's it! The setup wizard handles everything: authentication, dependencies, and configuration.

**Requirements:** Node.js 20+ and Python 3.12+. OpenSwarm creates or repairs an isolated project `.venv`.

Telemetry opt-out: set `ENABLE_TELEMETRY=0`, `OPEN_SWARM_TELEMETRY=0`, `AGENTSWARM_TELEMETRY=0`, or pass `--no-telemetry`.

## 🔧 Build Your Own Swarm

Fork this repo and create your own specialized AI team in minutes:

```bash
git clone https://github.com/VRSEN/openswarm.git
cd openswarm
```

Then tell **Claude Code**, **Cursor**, or **Codex**:

> _"Turn this into an SEO optimization swarm"_

They'll automatically customize all agents for your use case.

**Popular custom swarms:**

- **SEO Swarm:** Keyword research + competitor analysis + blog writing
- **Sales Swarm:** Lead research + outreach + proposal generation
- **Marketing Swarm:** Campaign planning + creative assets + analytics
- **Product Swarm:** Market research + feature specs + launch materials

## ⚙️ API Keys & Setup

The setup wizard walks you through everything, but you'll need at least one of these:

**Required (choose one):**

- `OPENAI_API_KEY` - For GPT 5.5 and Sora video generation
- `ANTHROPIC_API_KEY` - For Claude models

**Optional superpowers:**

- `COMPOSIO_API_KEY` - Unlock 10,000+ integrations (Gmail, Slack, GitHub, etc.)
- `GOOGLE_API_KEY` - Gemini image generation + Veo video
- `FAL_KEY` - Advanced video editing and effects
- `SEARCH_API_KEY` - Web search for research agent

Tools gracefully degrade when keys are missing — you'll get clear instructions on what to add.

---

## 🚀 Coming Soon

- **Agent Builder Agent** - Create custom swarms from a single prompt
- **OpenClaw + Claude Code integration** - All agents in one place

⭐ **Star us on GitHub** to stay updated and help us prioritize features!

## 🏗️ For Developers

**Local development:**

```bash
git clone https://github.com/VRSEN/openswarm.git
cd openswarm
python swarm.py
```

**Docker deployment:**

```bash
git clone https://github.com/VRSEN/openswarm.git
cd openswarm
cp .env.example .env        # Add your API keys
docker-compose up --build
```

**API server:**

```bash
python server.py           # Runs on localhost:8080
```

---

## 📺 Learn More

- **Watch the full demo:** [YouTube video →](https://youtu.be/c5DdXzqaeVU?si=rM2CNaZ8qVwMvqmz)
- **Multi-agent framework:** [Agency Swarm](https://github.com/VRSEN/agency-swarm)
- **Terminal UI for Agency Swarm:** [AgentSwarm](https://github.com/VRSEN/agentswarm-cli) (OpenCode-based TUI)
- **External integrations:** [Composio](https://composio.dev)

---

## 👥 Team

- **Artemii Shatokhin** — Built the core OpenSwarm agent team: the specialist agents, orchestration layer, shared tools, and runtime integrations. ([GitHub](https://github.com/ArtemShatokhin))
- **Nick Bobrowski** — Built the foundation OpenSwarm builds on: Agency Swarm and the AgentSwarm CLI/TUI, an OpenCode-based terminal experience customized for Agency Swarm. ([GitHub](https://github.com/nicko-ai))

---

## 📄 License

MIT — see [LICENSE](LICENSE).

**Built with ❤️ by the team behind [Agency Swarm](https://github.com/VRSEN/agency-swarm)**
