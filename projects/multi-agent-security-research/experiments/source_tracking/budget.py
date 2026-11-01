"""Conservative call reservations survive interrupted model requests."""

import os
from pathlib import Path


class CallBudget:
    def __init__(self, path: Path, limit: int):
        self.path = path
        self.limit = limit
        self.used = 0
        if path.exists():
            data = path.read_bytes()
            if any(line != b"reserved" for line in data.splitlines()):
                raise ValueError("Invalid call ledger; preserve it and use a new run directory")
            self.used = len(data.splitlines())
        if self.used > limit:
            raise ValueError("Recorded reservations exceed the configured request budget")

    def reserve(self) -> bool:
        if self.used >= self.limit:
            return False
        # Reserve and flush before sending: a crashed request still consumes budget.
        with self.path.open("ab") as handle:
            handle.write(b"reserved\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.used += 1
        return True


class RunLock:
    """Do not let two processes share a budget or append to the same output."""

    def __init__(self, directory: Path):
        self.path = directory / ".running.lock"

    def __enter__(self):
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ValueError("Output is locked; after a crash confirm the old process stopped before removing .running.lock") from None
        with os.fdopen(descriptor, "w") as handle:
            handle.write(str(os.getpid()))
        return self

    def __exit__(self, *args):
        self.path.unlink()
