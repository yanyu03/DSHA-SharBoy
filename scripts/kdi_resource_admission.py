"""KDI-P03 isolated resource admission (no execution, OS locks, or Gate changes).

An atomic, in-memory reservation prototype for one scheduler owner. assess() is
advisory; acquire() is authoritative. LATER requires an explicit caller retry;
NEVER means the request cannot fit the declared budget, not a policy decision.
"""

from dataclasses import dataclass
from threading import Lock


class ResourceAdmissionError(ValueError):
    """Malformed or out-of-range resource configuration/request."""


@dataclass(frozen=True)
class Decision:
    state: str  # OK, LATER, NEVER
    reason: str  # ready, busy, lease_limit, unknown_resource, exceeds_capacity


class ResourceAdmission:
    """Bounded per-owner quotas with atomic reservations and opaque lease tokens.

    This is not a replacement for DSHA's authorization Gate, host OS quotas,
    or a cross-process lock. No fairness, persistence, or timeout is provided.
    """

    def __init__(self, capacities, max_leases=64):
        self._validate_map(capacities, "capacities")
        if type(max_leases) is not int or not 1 <= max_leases <= 1024:
            raise ResourceAdmissionError("max_leases must be an integer in [1, 1024]")
        self._capacities = dict(capacities)
        self._used = {name: 0 for name in capacities}
        self._max_leases = max_leases
        self._leases = {}
        self._lock = Lock()

    @staticmethod
    def _validate_map(values, label):
        if type(values) is not dict or not 1 <= len(values) <= 16:
            raise ResourceAdmissionError(f"{label} must contain 1..16 resources")
        for name, amount in values.items():
            if (type(name) is not str or not 1 <= len(name) <= 32
                    or not name[0].isascii() or not ('a' <= name[0] <= 'z')
                    or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in name)):
                raise ResourceAdmissionError(f"invalid resource name in {label}")
            if type(amount) is not int or not 1 <= amount <= 1024:
                raise ResourceAdmissionError(f"{label} values must be integers in [1, 1024]")

    def _decide_locked(self, demand):
        # Permanent incompatibilities take precedence over temporary pressure.
        for name in sorted(demand):
            if name not in self._capacities:
                return Decision("NEVER", "unknown_resource")
            if demand[name] > self._capacities[name]:
                return Decision("NEVER", "exceeds_capacity")
        if len(self._leases) >= self._max_leases:
            return Decision("LATER", "lease_limit")
        if any(self._used[name] + amount > self._capacities[name]
               for name, amount in demand.items()):
            return Decision("LATER", "busy")
        return Decision("OK", "ready")

    def assess(self, demand):
        """Non-reserving observation; never rely on it to authorize execution."""
        self._validate_map(demand, "demand")
        with self._lock:
            return self._decide_locked(demand)

    def acquire(self, demand):
        """Return (decision, opaque_token_or_None) under one lock.

        An OK token reserves the full demand until release(token). The caller
        must separately enforce DSHA Gate policy at the execution boundary.
        """
        self._validate_map(demand, "demand")
        with self._lock:
            decision = self._decide_locked(demand)
            if decision.state != "OK":
                return decision, None
            token = object()  # identity-scoped to this instance, not guessable by ID
            self._leases[token] = dict(demand)
            for name, amount in demand.items():
                self._used[name] += amount
            return decision, token

    def release(self, token):
        """Return True exactly once for an owned lease; foreign tokens fail closed."""
        with self._lock:
            try:
                demand = self._leases.pop(token, None)
            except TypeError:  # unhashable foreign token
                return False
            if demand is None:
                return False
            for name, amount in demand.items():
                self._used[name] -= amount
            return True

    def usage(self):
        """Read-only snapshot for diagnostics; not an admission decision."""
        with self._lock:
            return dict(self._used)
