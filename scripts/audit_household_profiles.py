#!/usr/bin/env python3
"""Redacted household Hermes profile audit.

This script inspects profile topology and safety invariants without printing secret
values. It reports config booleans, env key names, file modes, and launchd state.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception as exc:  # pragma: no cover - environment guard
    print(f"ERROR: PyYAML is required to read Hermes config.yaml files: {exc}", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = Path(os.environ.get("HERMES_ROOT", "/Users/hermes/.hermes"))
PROFILES_ROOT = HERMES_ROOT / "profiles"

PROFILES = [
    "default",
    "dev",
    "family",
    "home",
    "household-template",
    "devops",
    "research",
]

ADMIN_ONLY_ENV_PREFIXES = (
    "SUDO_",
    "KEEPASSXC_",
)
ADMIN_ONLY_ENV_KEYS = {
    "GITHUB_TOKEN",
}

HOUSEHOLD_PROFILES = {"family", "home", "household-template"}
RUNNING_LAUNCHD_PROFILES = {"family", "home"}


def profile_home(profile: str) -> Path:
    if profile == "default":
        return HERMES_ROOT
    return PROFILES_ROOT / profile


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        return {}
    return data


def nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def env_keys(path: Path) -> list[str]:
    if not path.exists():
        return []
    keys: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.append(key)
    return sorted(set(keys))


def mode(path: Path) -> str | None:
    if not path.exists():
        return None
    return oct(stat.S_IMODE(path.stat().st_mode))


def launchd_state(profile: str) -> dict[str, Any]:
    if profile == "default":
        label = "ai.hermes.gateway"
    else:
        label = f"ai.hermes.gateway-{profile}"
    uid = os.getuid()
    proc = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/{label}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
        check=False,
    )
    output = proc.stdout or ""
    return {
        "label": label,
        "present": proc.returncode == 0,
        "running": "state = running" in output,
        "hermes_home_expected": str(profile_home(profile)) in output,
        "redacted_sample": redact_launchd_sample(output),
    }


def redact_launchd_sample(output: str) -> str:
    """Keep only non-secret diagnostic lines."""
    keep_prefixes = (
        "\tstate =",
        "\tpath =",
        "\tprogram =",
        "\tworking directory =",
        "\tpid =",
        "\tdomain =",
        "\t\tHERMES_HOME =>",
        "\t\tXPC_SERVICE_NAME =>",
    )
    lines = []
    for line in output.splitlines():
        if any(line.startswith(prefix) for prefix in keep_prefixes):
            lines.append(line.strip())
    return "\n".join(lines[:12])


def has_admin_env(keys: list[str]) -> list[str]:
    findings = []
    for key in keys:
        if key in ADMIN_ONLY_ENV_KEYS or any(key.startswith(prefix) for prefix in ADMIN_ONLY_ENV_PREFIXES):
            findings.append(key)
    return findings


def collect() -> tuple[dict[str, Any], list[dict[str, str]]]:
    report: dict[str, Any] = {"profiles": {}}
    findings: list[dict[str, str]] = []

    for profile in PROFILES:
        home = profile_home(profile)
        cfg_path = home / "config.yaml"
        env_path = home / ".env"
        cfg = read_yaml(cfg_path)
        keys = env_keys(env_path)
        launchd = launchd_state(profile) if sys.platform == "darwin" else {"present": None, "running": None}

        item = {
            "home": str(home),
            "config_exists": cfg_path.exists(),
            "env_exists": env_path.exists(),
            "env_mode": mode(env_path),
            "env_keys": keys,
            "model_provider": nested(cfg, "model", "provider"),
            "model_default": nested(cfg, "model", "default"),
            "terminal_backend": nested(cfg, "terminal", "backend"),
            "memory_enabled": nested(cfg, "memory", "memory_enabled"),
            "user_profile_enabled": nested(cfg, "memory", "user_profile_enabled"),
            "redact_secrets": nested(cfg, "security", "redact_secrets"),
            "redact_pii": nested(cfg, "privacy", "redact_pii"),
            "approvals_mode": nested(cfg, "approvals", "mode"),
            "image_input_mode": nested(cfg, "agent", "image_input_mode"),
            "disabled_toolsets": nested(cfg, "agent", "disabled_toolsets", default=[]),
            "launchd": launchd,
        }
        report["profiles"][profile] = item

        if not cfg_path.exists():
            findings.append({"severity": "FAIL", "profile": profile, "message": "config.yaml is missing"})
        if env_path.exists() and mode(env_path) != "0o600":
            findings.append({"severity": "FAIL", "profile": profile, "message": f".env mode is {mode(env_path)}, expected 0o600"})

        if profile in HOUSEHOLD_PROFILES:
            if nested(cfg, "terminal", "backend") != "docker":
                findings.append({"severity": "FAIL", "profile": profile, "message": "household profile must use terminal.backend=docker"})
            if nested(cfg, "security", "redact_secrets") is not True:
                findings.append({"severity": "FAIL", "profile": profile, "message": "security.redact_secrets must be true"})
            if nested(cfg, "privacy", "redact_pii") is not True:
                findings.append({"severity": "FAIL", "profile": profile, "message": "privacy.redact_pii must be true"})
            admin_keys = has_admin_env(keys)
            if admin_keys:
                findings.append({"severity": "FAIL", "profile": profile, "message": f"admin-only env key names present: {', '.join(admin_keys)}"})

        if profile == "home":
            disabled = set(nested(cfg, "agent", "disabled_toolsets", default=[]) or [])
            for required in ("homeassistant", "vision"):
                if required not in disabled:
                    findings.append({"severity": "FAIL", "profile": profile, "message": f"{required} toolset must remain disabled until actuation policy is accepted"})
            if nested(cfg, "agent", "image_input_mode") != "off":
                findings.append({"severity": "FAIL", "profile": profile, "message": "image_input_mode must be off until visual-input policy is accepted"})

        if profile == "household-template":
            forbidden = {"TELEGRAM_BOT_TOKEN", "TELEGRAM_HOME_CHANNEL", "TELEGRAM_ALLOWED_USERS"}.intersection(keys)
            if forbidden:
                findings.append({"severity": "FAIL", "profile": profile, "message": f"template should not carry role-specific Telegram keys: {', '.join(sorted(forbidden))}"})

        if profile in RUNNING_LAUNCHD_PROFILES and sys.platform == "darwin":
            if not launchd.get("running"):
                findings.append({"severity": "FAIL", "profile": profile, "message": "expected launchd gateway to be running"})
            if not launchd.get("hermes_home_expected"):
                findings.append({"severity": "FAIL", "profile": profile, "message": "launchd job does not show expected profile HERMES_HOME"})

        if profile in {"devops", "research"}:
            admin_keys = has_admin_env(keys)
            if admin_keys:
                findings.append({"severity": "WARN", "profile": profile, "message": f"specialist profile has admin-capable env key names; revalidate before activation: {', '.join(admin_keys)}"})

    return report, findings


def main() -> int:
    report, findings = collect()
    report["findings"] = findings
    report["summary"] = {
        "profiles_checked": len(PROFILES),
        "failures": sum(1 for f in findings if f["severity"] == "FAIL"),
        "warnings": sum(1 for f in findings if f["severity"] == "WARN"),
        "secret_values_printed": False,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["summary"]["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
