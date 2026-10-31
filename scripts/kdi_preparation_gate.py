"""KDI-P02: isolated async-preparation admission gate (no tool execution).

A producer owns each concurrent.futures.Future. This gate only admits completed
preparation results. Cancellation is effective until claim_ready() atomically
hands a result to its consumer; it cannot stop work already claimed/executing.

The source and tests have no dependency on DeepInfer or external runtimes.
"""

from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
from threading import Lock


class AdmissionError(ValueError):
    """Invalid or exhausted preparation admission boundary."""


@dataclass
class _Record:
    future: Future
    status: str = "PENDING"
    result: object = None


class PreparationGate:
    """Single-owner admission queue with cancellation tombstones.

    The gate keeps all IDs for its bounded lifetime to forbid accidental reuse
    after cancellation. Construct a fresh gate for a new batch.
    """

    def __init__(self, max_tasks=64):
        if type(max_tasks) is not int or not 1 <= max_tasks <= 1024:
            raise AdmissionError("max_tasks must be an integer in [1, 1024]")
        self._max_tasks = max_tasks
        self._records = {}
        self._ready = deque()
        self._lock = Lock()

    def register(self, task_id, future):
        """Register a preparation Future; never schedule or execute a tool."""
        if (not isinstance(task_id, str) or not 1 <= len(task_id) <= 128
                or any(ord(c) < 32 or ord(c) == 127 for c in task_id)):
            raise AdmissionError("invalid task_id")
        if not isinstance(future, Future):
            raise AdmissionError("expected concurrent.futures.Future")
        with self._lock:
            if task_id in self._records:
                raise AdmissionError("duplicate task_id, including cancelled IDs")
            if len(self._records) >= self._max_tasks:
                raise AdmissionError("preparation capacity exhausted")
            self._records[task_id] = _Record(future)

    def cancel(self, task_id):
        """Return True only if the task was not yet claimed for dispatch.

        Cancelling a running producer is best-effort: the tombstone is the
        authoritative guard against its later result entering the ready queue.
        """
        with self._lock:
            record = self._records.get(task_id)
            if record is None or record.status in ("CLAIMED", "FAILED"):
                return False
            if record.status == "CANCELLED":
                return True
            record.status = "CANCELLED"
            record.result = None
            pending_future = record.future
        pending_future.cancel()  # May return False when a producer is already running.
        return True

    def pump(self):
        """Poll completed work and admit only records still PENDING.

        No callbacks can push directly into the ready queue. A cancelled task
        remains cancelled even if its worker completes after cancellation.
        """
        admitted = 0
        with self._lock:
            for task_id, record in self._records.items():
                if record.status != "PENDING" or not record.future.done():
                    continue
                try:
                    result = record.future.result(timeout=0)
                except Exception:
                    record.status = "FAILED"
                    continue
                record.result = result
                record.status = "READY"
                self._ready.append(task_id)
                admitted += 1
        return admitted

    def claim_ready(self):
        """Atomically remove one admitted result, or return None.

        A successful claim is a point-of-no-return for *this gate*: subsequent
        cancellation returns False. Actual authorization must still be checked
        at the execution boundary by DSHA's existing Gate.
        """
        with self._lock:
            while self._ready:
                task_id = self._ready.popleft()
                record = self._records[task_id]
                if record.status != "READY":
                    continue
                record.status = "CLAIMED"
                result = record.result
                record.result = None
                return task_id, result
        return None

    def status(self, task_id):
        with self._lock:
            record = self._records.get(task_id)
            return record.status if record is not None else None
