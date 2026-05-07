from agency_swarm import Agent
from dotenv import load_dotenv

from config import get_default_model

load_dotenv()


def create_backend_dev() -> Agent:
    return Agent(
        name="Backend Dev",
        description=(
            "Backend development specialist who writes and implements server-side code, "
            "REST APIs, GraphQL services, database schemas, authentication systems, "
            "microservices architectures, and performance-optimized backend solutions."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_backend_dev()).terminal_demo()
