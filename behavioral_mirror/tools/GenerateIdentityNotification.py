import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class GenerateIdentityNotification(BaseTool):
    """Produces identity-based (not goal-based) notification text."""

    architect_identity: str = Field(default="architect who protects their future")
    recent_behavior: str = Field(...)
    stage: str = Field(default="Stability")

    def run(self) -> str:
        notification = (
            f"You are an {self.architect_identity}. "
            f"At the {self.stage} stage, your recent pattern shows: {self.recent_behavior}. "
            f"The machine holds the line when motivation fades—execute the next mechanical step."
        )
        return json.dumps(
            {
                "notification_type": "identity",
                "notification": notification,
                "avoid": "Do not use goal-based alerts like 'You saved $X'.",
            },
            indent=2,
        )


if __name__ == "__main__":
    tool = GenerateIdentityNotification(
        recent_behavior="you initiated a 72-hour pause instead of impulse buying",
        stage="Stability",
    )
    print(tool.run())
