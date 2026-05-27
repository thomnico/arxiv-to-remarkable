"""Tests for arxiv2rm.daemon.jobs."""

import json

from arxiv2rm.daemon.jobs import Job, JobStore


def test_create_assigns_id_and_persists(tmp_path):
    store = JobStore(directory=tmp_path)
    job = store.create("https://arxiv.org/abs/1", {"font_size": 14})

    assert len(job.id) == 12
    assert job.stage == "queued"
    assert job.progress == 0
    persisted = json.loads((tmp_path / f"{job.id}.json").read_text())
    assert persisted["url"] == "https://arxiv.org/abs/1"
    assert persisted["options"]["font_size"] == 14


def test_update_changes_stage_and_bumps_updated_at(tmp_path):
    store = JobStore(directory=tmp_path)
    job = store.create("u", {})
    first_updated = job.updated_at

    updated = store.update(job.id, stage="converting", progress=40)
    assert updated.stage == "converting"
    assert updated.progress == 40
    assert updated.updated_at >= first_updated

    persisted = json.loads((tmp_path / f"{job.id}.json").read_text())
    assert persisted["stage"] == "converting"
    assert persisted["progress"] == 40


def test_update_missing_job_returns_none(tmp_path):
    store = JobStore(directory=tmp_path)
    assert store.update("nope", stage="done") is None


def test_get_unknown_returns_none(tmp_path):
    store = JobStore(directory=tmp_path)
    assert store.get("missing") is None


def test_reload_marks_inflight_as_error(tmp_path):
    store = JobStore(directory=tmp_path)
    j_inflight = store.create("u1", {})
    store.update(j_inflight.id, stage="converting", progress=40)
    j_done = store.create("u2", {})
    store.update(j_done.id, stage="done", progress=100)
    j_converted = store.create("u3", {})
    store.update(j_converted.id, stage="converted", progress=80)

    fresh = JobStore(directory=tmp_path)
    assert fresh.get(j_inflight.id).stage == "error"
    assert "restart" in fresh.get(j_inflight.id).error
    assert fresh.get(j_done.id).stage == "done"
    assert fresh.get(j_converted.id).stage == "converted"


def test_reload_skips_garbage_json(tmp_path):
    (tmp_path / "bad.json").write_text("{not valid json")
    (tmp_path / "wrong_shape.json").write_text('{"unrelated": 1}')
    store = JobStore(directory=tmp_path)
    assert store._jobs == {}


def test_job_dataclass_defaults():
    job = Job(id="abc", url="u", options={})
    assert job.stage == "queued"
    assert job.output_path is None
    assert job.error is None
