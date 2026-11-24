"""Live-server fixtures for Playwright browser tests.

Run with:  pytest -m browser
Uses the locally installed Google Chrome by default (PW_CHANNEL=chrome). Set
PW_CHANNEL="" to use Playwright's bundled Chromium (`playwright install chromium`).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("e2e") / "e2e.db"
    port = _free_port()
    env = {
        **os.environ,
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite:///{db_path}",
        "SITE_URL": f"http://127.0.0.1:{port}",
        "SECRET_KEY": "e2e-secret-key-0123456789-abcdefghijklmnop",
        "FORM_MIN_AGE_SECONDS": "0",
        "SMTP_HOST": "",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--no-access-log"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if urlopen(f"{base}/health", timeout=1).status == 200:  # noqa: S310 - local test server
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("live server did not start")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    channel = os.environ.get("PW_CHANNEL", "chrome")
    return {**browser_type_launch_args, **({"channel": channel} if channel else {})}


@pytest.fixture
def console_errors(page):
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    return errors
