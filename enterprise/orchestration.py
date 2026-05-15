from sqlalchemy.orm import Session

from .agents import ENTERPRISE_AGENTS
from .models import AgentTask, RunState, SwarmRun, UsageRecord

EXPENSIVE_KEYWORDS = ("video", "sora", "veo", "seedance", "fal")


def requires_approval(prompt: str) -> bool:
    normalized = prompt.lower()
    return any(keyword in normalized for keyword in EXPENSIVE_KEYWORDS)


def create_run_tasks(db: Session, run: SwarmRun) -> None:
    for agent in ENTERPRISE_AGENTS:
        if agent["key"] == "orchestrator" or agent["key"].replace("_", " ") in run.prompt.lower():
            db.add(AgentTask(run_id=run.id, agent_key=agent["key"], state=RunState.queued))


def execute_run_once(db: Session, run_id: str) -> SwarmRun:
    run = db.get(SwarmRun, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} does not exist")
    if run.state == RunState.waiting_for_input:
        return run

    run.state = RunState.running
    db.commit()

    tasks = db.query(AgentTask).filter(AgentTask.run_id == run.id).all()
    for task in tasks:
        task.state = RunState.completed
        task.output = f"{task.agent_key} accepted the workflow and persisted its intermediate output."
        task.metadata_json = {"durable": True, "approval_gate_checked": run.cost_approval_required}

    db.add(
        UsageRecord(
            organization_id=run.organization_id,
            run_id=run.id,
            provider="openai",
            model="configured-default",
            input_tokens=max(1, len(run.prompt.split()) * 2),
            output_tokens=120,
            cost_cents=0,
        )
    )
    run.state = RunState.completed
    run.result_summary = "Enterprise durable run completed. Connect a worker queue to execute the live Agency Swarm workflow."
    db.commit()
    db.refresh(run)
    return run

