"""Background hearings: the model calls take from seconds to minutes, so they run on a small
thread pool instead of inside the web request. The browser polls the run until it finishes.

The pool lives in the API process. If the process stops mid-hearing, the run is marked failed at
the next start (`fail_interrupted_runs`), so no run stays "running" forever.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import HearingRun
from app.db.session import get_engine
from app.hearing.agents import LLM
from app.hearing.runner import PreparedHearing, execute_hearing

log = logging.getLogger("nyayasim.hearing")

# Two hearings at a time per server: each makes several model calls in a row.
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hearing")

Submit = Callable[[Callable[[], None]], None]


def default_submit(fn: Callable[[], None]) -> None:
    _pool.submit(fn)


def hearing_job(run_id: int, prep: PreparedHearing, llm: LLM) -> Callable[[], None]:
    def job() -> None:
        with Session(get_engine()) as s:
            run = s.get(HearingRun, run_id)
            if run is None:  # deleted meanwhile (e.g. the account was deleted)
                return
            try:
                execute_hearing(s, run, prep, llm)
            except Exception:  # stored on the run by execute_hearing; logged with traceback here
                log.exception("Hearing run %s failed", run_id)
            s.commit()

    return job


def fail_interrupted_runs() -> int:
    """At startup: runs left 'running' by a stopped process can never finish."""
    with Session(get_engine()) as s:
        n = s.execute(
            update(HearingRun)
            .where(HearingRun.status == "running")
            .values(
                status="failed",
                error="Interrupted: the server restarted during the hearing. Please run it again.",
                finished_at=datetime.now(UTC),
            )
        ).rowcount
        s.commit()
    return n or 0
