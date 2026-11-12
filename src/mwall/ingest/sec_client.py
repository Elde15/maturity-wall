"""Polite EDGAR HTTP client (SOP section 7, step 1).

* The contact string comes from the SEC_CONTACT environment variable and is sent
  as the User-Agent. It is never logged, printed or written to disk. On Windows,
  if the variable was set after this shell started, it is read from the user
  environment in the registry.
* One process-wide token bucket keeps us under SEC's 10 requests/second limit.
* 403 and 429 (and 5xx) back off exponentially.
* Every request is appended to a JSONL log with url, status, bytes and timing.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from mwall.common import paths

DEFAULT_RATE = 6.0  # requests per second, shared by all threads; SEC's cap is 10
RETRY_STATUS = {403, 429, 500, 502, 503, 504}


def sec_contact() -> str:
    value = os.environ.get("SEC_CONTACT", "").strip()
    if not value and sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value = str(winreg.QueryValueEx(key, "SEC_CONTACT")[0]).strip()
        except OSError:
            value = ""
    if not value or "@" not in value:
        raise RuntimeError(
            "SEC_CONTACT is not set. SEC requires a declared User-Agent such as "
            "'Your Name you@example.com'. Set it as an environment variable; never commit it."
        )
    return value


class RateLimiter:
    """Thread-safe token bucket."""

    def __init__(self, rate: float, burst: int = 1):
        self.rate = rate
        self.capacity = max(1, burst)
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            time.sleep(wait)


@dataclass
class FetchResult:
    url: str
    status: int
    content: bytes
    elapsed_s: float


class SecClient:
    def __init__(self, rate: float = DEFAULT_RATE, log_path: Path | None = None, max_retries: int = 6):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": sec_contact(), "Accept-Encoding": "gzip, deflate"}
        )
        self.limiter = RateLimiter(rate)
        self.max_retries = max_retries
        paths.ensure_dirs()
        self.log_path = log_path or (paths.STATE_DIR / "requests.jsonl")
        self._log_lock = threading.Lock()

    # -- logging -----------------------------------------------------------
    def _log(self, url: str, status: int, nbytes: int, elapsed: float, attempt: int, note: str = "") -> None:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "url": url,
            "status": status,
            "bytes": nbytes,
            "elapsed_s": round(elapsed, 3),
            "attempt": attempt,
        }
        if note:
            rec["note"] = note
        with self._log_lock, open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    # -- requests ----------------------------------------------------------
    def get(self, url: str, timeout: float = 60.0, allow_404: bool = True) -> FetchResult:
        """GET with throttle and backoff. Returns status 404 results instead of raising when allowed."""
        attempt = 0
        while True:
            attempt += 1
            self.limiter.acquire()
            t0 = time.monotonic()
            try:
                resp = self.session.get(url, timeout=timeout)
                status, body = resp.status_code, resp.content
            except requests.RequestException as exc:  # network hiccup
                status, body = -1, b""
                note = type(exc).__name__
            else:
                note = ""
            elapsed = time.monotonic() - t0
            self._log(url, status, len(body), elapsed, attempt, note)
            if status == 200 or (status == 404 and allow_404):
                return FetchResult(url, status, body, elapsed)
            if (status in RETRY_STATUS or status == -1) and attempt <= self.max_retries:
                time.sleep(min(120.0, 2.0 ** attempt))
                continue
            raise RuntimeError(f"GET {url} failed with status {status} after {attempt} attempts")

    def head_bytes(self, url: str, nbytes: int = 4096, timeout: float = 60.0) -> FetchResult:
        """Read only the first nbytes of a file by streaming and closing early.

        EDGAR ignores HTTP Range headers, so this is how we check an XML root
        namespace without downloading a 100 MB auto-loan exhibit.
        """
        attempt = 0
        while True:
            attempt += 1
            self.limiter.acquire()
            t0 = time.monotonic()
            note = "head"
            try:
                with self.session.get(url, timeout=timeout, stream=True) as resp:
                    status = resp.status_code
                    body = b""
                    if status == 200:
                        for chunk in resp.iter_content(chunk_size=nbytes, decode_unicode=False):
                            body += chunk
                            if len(body) >= nbytes:
                                break
            except requests.RequestException as exc:
                status, body, note = -1, b"", "head:" + type(exc).__name__
            elapsed = time.monotonic() - t0
            self._log(url, status, len(body), elapsed, attempt, note)
            if status in (200, 404):
                return FetchResult(url, status, body, elapsed)
            if (status in RETRY_STATUS or status == -1) and attempt <= self.max_retries:
                time.sleep(min(120.0, 2.0 ** attempt))
                continue
            raise RuntimeError(f"GET {url} failed with status {status} after {attempt} attempts")

    def download_gz(self, url: str, dest: Path, timeout: float = 300.0) -> tuple[int, str, int]:
        """Stream a file to dest as gzip. Returns (status, sha256 of the uncompressed bytes, raw size).

        Writes to a temp name and renames, so a killed process never leaves a
        truncated file under the final name.
        """
        attempt = 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        while True:
            attempt += 1
            self.limiter.acquire()
            t0 = time.monotonic()
            note = "download"
            sha = hashlib.sha256()
            size = 0
            try:
                with self.session.get(url, timeout=timeout, stream=True) as resp:
                    status = resp.status_code
                    if status == 200:
                        with gzip.open(tmp, "wb", compresslevel=6) as out:
                            for chunk in resp.iter_content(chunk_size=1 << 16):
                                if chunk:
                                    out.write(chunk)
                                    sha.update(chunk)
                                    size += len(chunk)
            except requests.RequestException as exc:
                status, note = -1, "download:" + type(exc).__name__
            elapsed = time.monotonic() - t0
            self._log(url, status, size, elapsed, attempt, note)
            if status == 200:
                os.replace(tmp, dest)
                return status, sha.hexdigest(), size
            if tmp.exists():
                tmp.unlink()
            if status == 404:
                return status, "", 0
            if (status in RETRY_STATUS or status == -1) and attempt <= self.max_retries:
                time.sleep(min(120.0, 2.0 ** attempt))
                continue
            raise RuntimeError(f"download {url} failed with status {status} after {attempt} attempts")
