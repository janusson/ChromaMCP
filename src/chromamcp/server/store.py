"""Server-side references (W8, content-derived keys W13).

A tool that would return a chromatogram or a peak table returns a **short handle**
instead: the data stays server-side, so a 100k-point trace never crosses the
context boundary (``PLAN.md`` §7 — the M2 gate).  A handle is
``ptr:chrom:<kind>:<name>``, it has a real lifecycle, and the store is **bounded**:
``release_reference`` frees a handle for real, and the store refuses to grow past
its cap rather than leaking.

Two ways to name a handle, and the difference matters for evidence:

- **Content-derived** (``put(..., key=...)``, what every tool uses): the key is a
  digest of the request and its input, so the same inputs produce the same handle
  in any process and in any order.  A response carrying it is reproducible rather
  than dependent on how many handles happened to be allocated first.
- **Allocation-ordered** (``put(...)`` with no key): a monotonically increasing
  number.  Kept for callers that hold anonymous data; no tool in this server uses
  it, because a counter in a response makes byte-identical evidence impossible.

Handles are deliberately **not** part of any provenance record — a record is
reproduced by re-running against its input file, not by replaying a handle.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from chromamcp.errors import ReferenceError

#: The stable prefix every handle carries (``PLAN.md`` §7, ``M2-BRIEF.md`` §5).
PREFIX = "ptr:chrom:"
#: The most handles the store will hold at once.  A caller that keeps loading
#: without releasing gets an explicit refusal, not unbounded memory growth.
MAX_REFERENCES = 256


@dataclass(slots=True)
class ReferenceStore:
    """A bounded, explicit-lifecycle map from a handle to server-side data."""

    max_entries: int = MAX_REFERENCES
    _items: dict[str, Any] = field(default_factory=dict)
    _counter: int = 0

    def put(self, kind: str, payload: Any, *, key: str | None = None) -> str:
        """Store *payload* and return its handle.

        With *key*, the handle is ``ptr:chrom:<kind>:<key>`` and the call is
        idempotent: the same key returns the same handle and replaces the stored
        payload.  Without it, the handle takes the next allocation number.
        """
        if key is not None:
            reference = f"{PREFIX}{kind}:{key}"
            if reference not in self._items and len(self._items) >= self.max_entries:
                raise ReferenceError(
                    f"the reference store holds {len(self._items)} handles (max "
                    f"{self.max_entries}); release one with release_reference."
                )
            self._items[reference] = payload
            return reference
        if len(self._items) >= self.max_entries:
            raise ReferenceError(
                f"the reference store holds {len(self._items)} handles (max "
                f"{self.max_entries}); release one with release_reference."
            )
        self._counter += 1
        reference = f"{PREFIX}{kind}:{self._counter}"
        self._items[reference] = payload
        return reference

    def get(self, reference: str, *, expect: str | None = None) -> Any:
        """Return the payload for *reference*, or refuse it explicitly.

        *expect* names the handle kind the caller needs.  A handle of the wrong
        kind is refused here with an actionable message, rather than surfacing a
        ``KeyError`` at the call site — whose text the SDK withholds from the
        model (``M2-BRIEF.md`` §7).
        """
        try:
            payload = self._items[reference]
        except KeyError:
            raise ReferenceError(
                f"unknown reference '{reference}'. Load a chromatogram first, "
                f"and do not reuse a handle after release_reference."
            ) from None
        if expect is not None and not reference.startswith(f"{PREFIX}{expect}:"):
            raise ReferenceError(
                f"reference '{reference}' is a handle of the wrong kind; this "
                f"call needs a '{PREFIX}{expect}:…' handle."
            )
        return payload

    def release(self, reference: str) -> None:
        """Free *reference*.  Releasing an unknown handle is refused, not ignored."""
        try:
            del self._items[reference]
        except KeyError:
            raise ReferenceError(f"unknown reference '{reference}'.") from None

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)
