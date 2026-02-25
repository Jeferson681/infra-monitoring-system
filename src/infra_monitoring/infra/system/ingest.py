"""Resilient readers for JSONL (newline-delimited JSON) files.

Utilities to iterate JSONL files with optional gzip support and strategies
to handle partially-written records (for producers that append lines).
The reader is resilient to empty lines and malformed JSON and supports a
``follow`` mode similar to ``tail -f`` with lightweight retries/backoff.

Public API:
- ``iter_jsonl(path, follow=False, max_retries=3, retry_delay=0.1)``
    -> yields decoded dict objects for each valid JSON line.
"""

from __future__ import annotations

import gzip
import io
import json
import time
from pathlib import Path
from typing import Generator


def _open_maybe_gzip(path: Path):
    """Open a file supporting gzip when extension is .gz.

    Returns a text-mode file-like object. Caller must close the object.
    """
    if str(path).endswith(".gz"):
        # gzip.open yields bytes; open in text mode to simplify line reading
        return gzip.open(path, mode="rt", encoding="utf-8", errors="replace")
    return open(path, mode="r", encoding="utf-8", errors="replace")


def iter_jsonl(
    path: str | Path,
    follow: bool = False,
    max_retries: int = 3,
    retry_delay: float = 0.1,
) -> Generator[dict, None, None]:
    """Iterate over a JSONL file and yield Python objects.

    Args:
        path: path to a .jsonl or .jsonl.gz file
        follow: if True, wait for new lines (similar to tail -f)
        max_retries: attempts before giving up when follow=False
        retry_delay: delay between attempts (seconds)

    Yields:
        dicts decoded from each valid JSON line.

    Notes:
        - Empty lines or lines that do not decode as JSON are ignored.
        - For files being written, a partial line may appear; the reader
          will wait briefly when follow=True to allow completion.

    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    retries = 0
    with _open_maybe_gzip(p) as fh:
        while True:
            line = fh.readline()
            if not line:
                # EOF reached
                if follow:
                    # wait and retry
                    time.sleep(retry_delay)
                    retries = 0
                    continue
                if retries < max_retries:
                    retries += 1
                    time.sleep(retry_delay)
                    continue
                break

            retries = 0
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Possibly a partial line; if in follow mode, wait for the
                # rest to be written. Otherwise ignore the line.
                if follow:
                    # rewind the cursor for the current line to attempt
                    # reading again after a short delay. Note: only possible
                    # when the file object supports seek().
                    try:
                        pos = fh.tell()
                        # wait a little to allow completion
                        time.sleep(retry_delay)
                        fh.seek(pos)
                        continue
                    except (OSError, io.UnsupportedOperation):
                        # If seeking is unsupported (e.g. stream), just wait
                        time.sleep(retry_delay)
                        continue
                # Outside follow mode, ignore the invalid line
                continue
            yield obj


__all__ = ["iter_jsonl"]
