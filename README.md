<div align="center">

# CodeSwarm

![CodeSwarm](assets/new-framework.jpg)

</div>

**A multi-agent coding team that works on your codebase together.**

Get architecture advice, frontend and backend implementation, code reviews, tests, and DevOps configurations — all from a single prompt. A full dev team of AI specialists working in your terminal.

**6 specialized coding agents working together**
**Full-stack web: React, Vue, Node.js, Python, and more**
**Install in 30 seconds, running in 60**
**100% customizable and forkable**

Built on [Agency Swarm](https://github.com/VRSEN/agency-swarm) — the framework powering real AI agencies.

---

## What Makes This Different?

Instead of one agent trying to do everything poorly, you get **specialized developers coordinated by an architect**.

### Real Examples

Paste these into your terminal and watch magic happen:

- **"Build a user authentication system with JWT"** → Architecture plan + backend API + frontend login form + tests
- **"Review this PR for security issues"** → Security audit + best practices review + fix suggestions
- **"Add CI/CD pipeline for this Node.js project"** → GitHub Actions workflow + Docker config + deployment scripts
- **"Refactor this module to use TypeScript"** → Type definitions + refactored code + updated tests
- **"Build a REST API for managing todos"** → Database schema + API endpoints + validation + unit tests

---

## Meet Your AI Dev Team

| Agent | What it does |
|---|---|
| **Architect** | Plans system architecture and routes tasks to the right specialist(s). Never codes directly — pure coordination. |
| **Frontend Dev** | Builds UI with React, Vue, Angular, Svelte. TypeScript, CSS, component architecture, state management. |
| **Backend Dev** | Builds APIs and server logic with Node.js, Python, Go. Database design, authentication, microservices. |
| **Code Reviewer** | Reviews code for quality, security, performance. Enforces best practices and suggests refactoring. |
| **QA Tester** | Writes unit tests, integration tests, E2E tests. Finds bugs and edge cases. |
| **DevOps** | Sets up CI/CD pipelines, Docker, Kubernetes, cloud deployments, monitoring. |

---

## Get Started in 30 Seconds

**Quick start:**

```bash
git clone https://github.com/yourusername/codeswarm.git
cd codeswarm
pip install -r requirements.txt
python swarm.py
```

**Requirements:** Python 3.10+

## API Keys & Setup

You'll need at least one of these:

**Required (choose one):**

- `OPENAI_API_KEY` - For GPT models
- `ANTHROPIC_API_KEY` - For Claude models

Create a `.env` file:

```bash
cp .env.example .env
# Add your API keys
```

---

## For Developers

**Local development:**

```bash
git clone https://github.com/yourusername/codeswarm.git
cd codeswarm
python swarm.py
```

**Docker deployment:**

```bash
cp .env.example .env        # Add your API keys
docker-compose up --build
```

**API server:**

```bash
python server.py           # Runs on localhost:8080
```

---

## Customize Your Team

Fork this repo and modify agents for your specific needs:

- Change `instructions.md` in each agent folder to adjust behavior
- Add tools in each agent's `tools/` folder
- Update `swarm.py` to add/remove agents or change communication flows

**Example customizations:**

- **Mobile Dev Team:** Replace Frontend Dev with iOS/Android specialists
- **Data Engineering Team:** Add data pipeline and ML specialists
- **Security Team:** Add penetration testing and compliance agents

---

## Learn More

- **Multi-agent framework:** [Agency Swarm](https://github.com/VRSEN/agency-swarm)

---

## License

MIT — see [LICENSE](LICENSE).

**Built with Agency Swarm**
