import time

from .database import SessionLocal, create_all
from .models import RunState, SwarmRun
from .orchestration import execute_run_once


def main() -> None:
    create_all()
    while True:
        db = SessionLocal()
        try:
            run = db.query(SwarmRun).filter(SwarmRun.state == RunState.queued).order_by(SwarmRun.created_at).first()
            if run:
                execute_run_once(db, run.id)
        finally:
            db.close()
        time.sleep(2)


if __name__ == "__main__":
    main()

