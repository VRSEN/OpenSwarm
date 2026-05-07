from agency_swarm import Agent
from dotenv import load_dotenv

from config import get_default_model

load_dotenv()


def create_devops() -> Agent:
    return Agent(
        name="DevOps",
        description=(
            "DevOps specialist who designs and implements CI/CD pipelines, containerization "
            "strategies with Docker and Kubernetes, cloud infrastructure on AWS/GCP/Azure, "
            "Infrastructure as Code with Terraform, monitoring solutions, and deployment workflows."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_devops()).terminal_demo()
