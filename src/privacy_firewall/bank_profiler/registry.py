"""Registry for bank-statement profilers."""
from __future__ import annotations

from privacy_firewall.bank_profiler.models import BankProfile
from privacy_firewall.bank_profiler.provider import BankProfiler
from privacy_firewall.models.document import Document


class BankProfilerRegistry:
    """Holds registered bank profilers and auto-selects the best match.

    Usage::

        registry = BankProfilerRegistry()
        registry.register(SBIProfiler)
        profile = registry.profile(document)
    """

    def __init__(self) -> None:
        self._profilers: dict[str, type[BankProfiler]] = {}

    def register(self, profiler: type[BankProfiler]) -> None:
        """Register a profiler class.

        Args:
            profiler: A ``BankProfiler`` subclass.
        """
        self._profilers[profiler.name] = profiler

    def profile(self, document: Document) -> BankProfile:
        """Run all registered profilers and return the best match.

        The profiler with the highest confidence wins.  If nothing is
        registered, a generic fallback with ``confidence=0`` is returned.

        Args:
            document: The parsed document to profile.

        Returns:
            A ``BankProfile`` from the best-matching profiler.
        """
        if not self._profilers:
            from privacy_firewall.bank_profiler.models import BankName

            return BankProfile(
                bank_name=BankName.GENERIC,
                confidence=0.0,
                page_count=len(document.pages),
            )

        best: BankProfile | None = None
        for cls in self._profilers.values():
            profile = cls().profile(document)
            if best is None or profile.confidence > best.confidence:
                best = profile

        return best  # type: ignore[return-value]  # guaranteed non-None by check above

    @property
    def names(self) -> list[str]:
        """Names of all registered profilers."""
        return list(self._profilers.keys())
