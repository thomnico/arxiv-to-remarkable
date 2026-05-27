"""In-memory job registry with JSON spill for restart-safety."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

JOBS_DIR = Path.home() / ".arxiv2rm" / "jobs"


Stage = str  # "queued" | "downloading" | "converting" | "converted" | "pushing" | "done" | "error"


@dataclass
class Job:
    id: str
    url: str
    options: dict
    stage: Stage = "queued"
    progress: int = 0
    output_path: Optional[str] = None
    remote_path: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class JobStore:
    def __init__(self, directory: Path = JOBS_DIR):
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._reload_from_disk()

    def _reload_from_disk(self) -> None:
        """Rehydrate jobs from JSON spill. In-flight jobs become ``error``."""
        terminal = {"done", "error", "converted"}
        for path in self.dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            try:
                job = Job(**data)
            except TypeError:
                continue
            if job.stage not in terminal:
                job.stage = "error"
                job.error = (job.error or "") + " [daemon restart]"
            self._jobs[job.id] = job

    def create(self, url: str, options: dict) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], url=url, options=options)
        with self._lock:
            self._jobs[job.id] = job
        self._persist(job)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = time.time()
        self._persist(job)
        return job

    def _persist(self, job: Job) -> None:
        path = self.dir / f"{job.id}.json"
        path.write_text(json.dumps(asdict(job), indent=2))
