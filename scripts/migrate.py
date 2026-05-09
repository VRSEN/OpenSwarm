import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enterprise.database import create_all


if __name__ == "__main__":
    create_all()
    print("Enterprise database schema is ready.")
