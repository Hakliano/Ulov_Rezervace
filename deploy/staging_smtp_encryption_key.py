#!/usr/bin/env python3
"""Staging SMTP_ENCRYPTION_KEY: persistent sidecar, never taken from LIVE.

Never prints key material. LIVE .env is not opened; the already-copied
.env.staging is stripped, and .smtp_encryption_key.live is read only to
abort when staging would match LIVE.
"""
from __future__ import annotations

import base64
import os
import sys
from pathlib import Path


def _root() -> Path:
    return Path(os.environ.get("STAGING_SMTP_KEY_ROOT", ".")).resolve()


def _read_sidecar(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _strip_smtp_key(text: str) -> tuple[str, str]:
    live_val = ""
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("SMTP_ENCRYPTION_KEY="):
            if not live_val:
                live_val = line.split("=", 1)[1].strip()
            continue
        lines.append(line)
    body = "\n".join(lines)
    if body:
        body += "\n"
    return body, live_val


def _set_smtp_key(text: str, key: str) -> str:
    lines: list[str] = []
    found = False
    for line in text.splitlines():
        if line.startswith("SMTP_ENCRYPTION_KEY="):
            lines.append(f"SMTP_ENCRYPTION_KEY={key}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"SMTP_ENCRYPTION_KEY={key}")
    return "\n".join(lines) + "\n"


def _generate_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def main() -> int:
    root = _root()
    env_path = root / ".env.staging"
    sidecar = root / ".smtp_encryption_key"
    live_sidecar = root / ".smtp_encryption_key.live"

    if not env_path.is_file():
        print("FAIL: missing .env.staging", file=sys.stderr)
        return 1

    text, live_from_copy = _strip_smtp_key(env_path.read_text(encoding="utf-8"))
    # Drop the LIVE secret from staging env before any further work.
    env_path.write_text(text, encoding="utf-8")

    live_sidecar_val = _read_sidecar(live_sidecar)
    live_refs = [v for v in (live_sidecar_val, live_from_copy) if v]
    if not live_refs:
        print(
            "FAIL: cannot verify staging SMTP encryption key is isolated from LIVE.",
            file=sys.stderr,
        )
        return 1

    staging_key = _read_sidecar(sidecar)
    generated = False
    if not staging_key:
        staging_key = _generate_key()
        generated = True

    if any(staging_key == v for v in live_refs):
        print(
            "FAIL: staging SMTP encryption key matches LIVE. Deploy aborted.",
            file=sys.stderr,
        )
        return 1

    sidecar.write_text(staging_key + "\n", encoding="utf-8")
    os.chmod(sidecar, 0o600)
    env_path.write_text(_set_smtp_key(env_path.read_text(encoding="utf-8"), staging_key), encoding="utf-8")

    print(
        "SMTP_ENCRYPTION_KEY staging generated"
        if generated
        else "SMTP_ENCRYPTION_KEY staging reused from sidecar"
    )
    print("SMTP_ENCRYPTION_KEY staging isolated from LIVE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
