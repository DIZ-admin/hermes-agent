import json
from pathlib import Path


def _with_cron_store(cron_jobs, cron_dir: Path):
    class _Store:
        def __enter__(self):
            self.old_cron_dir = cron_jobs.CRON_DIR
            self.old_jobs_file = cron_jobs.JOBS_FILE
            self.old_output_dir = cron_jobs.OUTPUT_DIR
            cron_jobs.CRON_DIR = cron_dir
            cron_jobs.JOBS_FILE = cron_dir / "jobs.json"
            cron_jobs.OUTPUT_DIR = cron_dir / "output"
            return cron_jobs

        def __exit__(self, exc_type, exc, tb):
            cron_jobs.CRON_DIR = self.old_cron_dir
            cron_jobs.JOBS_FILE = self.old_jobs_file
            cron_jobs.OUTPUT_DIR = self.old_output_dir

    return _Store()


def test_cronjob_list_uses_active_profile_store(tmp_path, monkeypatch):
    import cron.jobs as cron_jobs
    import tools.cronjob_tools as tool_mod

    root_home = tmp_path / ".hermes"
    profile_home = root_home / "profiles" / "worker"
    profile_cron = profile_home / "cron"
    profile_cron.mkdir(parents=True)

    with _with_cron_store(cron_jobs, profile_cron):
        cron_jobs.create_job(prompt="worker heartbeat", schedule="every 1h", name="worker-heartbeat")

    monkeypatch.setattr(tool_mod, "get_hermes_home", lambda: profile_home)
    monkeypatch.setattr(tool_mod, "get_default_hermes_root", lambda: root_home)

    result = json.loads(tool_mod.cronjob(action="list"))
    assert result["success"] is True
    assert result["count"] == 1
    assert result["jobs"][0]["name"] == "worker-heartbeat"


def test_cronjob_create_persists_into_active_profile_store(tmp_path, monkeypatch):
    import cron.jobs as cron_jobs
    import tools.cronjob_tools as tool_mod

    root_home = tmp_path / ".hermes"
    root_cron = root_home / "cron"
    root_cron.mkdir(parents=True)
    profile_home = root_home / "profiles" / "worker"
    profile_cron = profile_home / "cron"
    profile_cron.mkdir(parents=True)

    monkeypatch.setattr(tool_mod, "get_hermes_home", lambda: profile_home)
    monkeypatch.setattr(tool_mod, "get_default_hermes_root", lambda: root_home)

    result = json.loads(
        tool_mod.cronjob(
            action="create",
            schedule="every 1h",
            prompt="worker heartbeat",
            name="worker-heartbeat",
        )
    )
    assert result["success"] is True

    with _with_cron_store(cron_jobs, profile_cron):
        profile_jobs = cron_jobs.load_jobs()
    with _with_cron_store(cron_jobs, root_cron):
        root_jobs = cron_jobs.load_jobs()

    assert any(j.get("name") == "worker-heartbeat" for j in profile_jobs)
    assert not any(j.get("name") == "worker-heartbeat" for j in root_jobs)
