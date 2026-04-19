"""Launch Edge with CDP enabled, check liveness, wait for readiness."""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request

from edge_cdp.config import Config, Profile, load_config

READY_TIMEOUT_SECONDS = 15
PROBE_TIMEOUT_SECONDS = 1.0


def _probe(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/json/version",
            timeout=PROBE_TIMEOUT_SECONDS,
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def is_alive(profile_or_port: Profile | int) -> bool:
    port = profile_or_port.port if isinstance(profile_or_port, Profile) else profile_or_port
    return _probe(port) is not None


def version_info(profile: Profile) -> dict | None:
    return _probe(profile.port)


def _spawn(profile: Profile, cfg: Config) -> None:
    browser = cfg.get_browser(profile.browser)
    bind_address = "0.0.0.0" if profile.bind_all else "127.0.0.1"
    args = [
        browser.exe,
        f"--remote-debugging-port={profile.port}",
        f"--remote-debugging-address={bind_address}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile.data_dir}",
    ]
    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def launch(profile_name: str, cfg: Config | None = None) -> Profile:
    """Launch a profile if not already alive. Idempotent."""
    if cfg is None:
        cfg = load_config()
    profile = cfg.get_profile(profile_name)
    if is_alive(profile):
        return profile
    _spawn(profile, cfg)
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if is_alive(profile):
            return profile
        time.sleep(0.5)
    raise TimeoutError(
        f"Edge did not respond on port {profile.port} within {READY_TIMEOUT_SECONDS}s.\n"
        f"If another Edge process is already using user-data-dir {profile.data_dir!r},\n"
        f"close those Edge windows and retry. Different profiles on different ports\n"
        f"can run in parallel, but the same user-data-dir cannot."
    )


def ensure_running(profile_name: str, cfg: Config | None = None) -> Profile:
    """Public alias intended for scripts: 'make sure this profile is up.'"""
    return launch(profile_name, cfg=cfg)
