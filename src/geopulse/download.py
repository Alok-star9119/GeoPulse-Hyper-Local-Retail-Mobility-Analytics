"""Reusable file downloader with retries; used from Day 3 for raw data."""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from geopulse.logger import get_logger

log = get_logger(__name__)


def download_file(url: str, dest: Path, retries: int = 3, timeout: int = 60,
                  overwrite: bool = False, chunk_size: int = 1 << 20) -> Path:
    """Stream `url` to `dest`. Skips if dest exists. Writes via a .part file."""
    dest = Path(dest)
    if dest.exists() and not overwrite:
        log.info("Skipping %s (already exists)", dest.name)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "geopulse-intern-project"})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:
                while chunk := resp.read(chunk_size):
                    out.write(chunk)
            part.replace(dest)
            log.info("Downloaded %s (%d bytes)", dest.name, dest.stat().st_size)
            return dest
        except Exception as err:  # network errors vary widely
            last_err = err
            log.warning("Attempt %d/%d failed for %s: %s", attempt, retries, url, err)
            time.sleep(min(2 ** attempt, 10))
    if part.exists():
        part.unlink()
    raise RuntimeError(f"Failed to download {url}") from last_err
