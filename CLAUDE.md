# CodeSwarm

A multi-agent AI development team built on Agency Swarm. Six specialized coding agents work together to help you build, review, test, and deploy software.

## Agents

| Agent | Role | Specialization |
|---|---|---|
| **Architect** | Orchestrator | Plans architecture, routes tasks to specialists. Never writes code. |
| **Frontend Dev** | Frontend implementation | React, Vue, Angular, TypeScript, CSS, UI/UX |
| **Backend Dev** | Backend implementation | Node.js, Python, APIs, databases, auth |
| **Code Reviewer** | Quality assurance | Code review, security, best practices, refactoring |
| **QA Tester** | Testing | Unit tests, integration tests, E2E, bug hunting |
| **DevOps** | Infrastructure | CI/CD, Docker, Kubernetes, cloud, monitoring |

## Communication Pattern

The Architect is the entry point. It can send messages to all specialists in parallel or hand off to a single specialist for focused work. All agents can transfer to each other when needed.

```
         ┌─────────────┐
         │  Architect  │
         └──────┬──────┘
                │
    ┌───────┬───┴───┬───────┬───────┐
    ▼       ▼       ▼       ▼       ▼
Frontend Backend  Code    QA    DevOps
  Dev     Dev   Reviewer Tester
```

## Quick Start

```bash
pip install -r requirements.txt
python swarm.py
```

## Example Prompts

- "Build a user authentication system with JWT"
- "Review this code for security issues"
- "Add CI/CD pipeline for this project"
- "Write tests for the UserService class"
- "Refactor this module to use TypeScript"

## Customization

- Edit `instructions.md` in each agent folder to change behavior
- Add tools in each agent's `tools/` folder
- Update `swarm.py` to add/remove agents or change communication flows
- See `AGENTS.md` for detailed customization guide

## File Structure

```
swarm.py              <- Agent configuration and communication flows
shared_instructions.md <- Shared context for all agents
architect/            <- Orchestrator agent
frontend_dev/         <- Frontend specialist
backend_dev/          <- Backend specialist
code_reviewer/        <- Code review specialist
qa_tester/            <- Testing specialist
devops/               <- DevOps specialist
```
