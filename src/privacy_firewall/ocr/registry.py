"""Registry that manages available OCR provider implementations."""
from __future__ import annotations

from privacy_firewall.ocr.provider import OCRProvider


class OCRProviderRegistry:
    """Registry of OCR provider classes (not instances).

    Providers are registered by their ``.name`` property.  A default
    provider can be set so that pipeline code does not need to specify
    a name when one provider is sufficient.
    """

    def __init__(self) -> None:
        """Initialise an empty registry."""
        self._providers: dict[str, type[OCRProvider]] = {}
        self._default: str | None = None

    def register(self, provider: type[OCRProvider], *, default: bool = False) -> None:
        """Register an OCR provider class.

        If a provider with the same ``.name`` already exists it is
        overwritten.

        Args:
            provider: The provider class (not an instance) to register.
            default: If ``True``, set this provider as the default.
        """
        self._providers[provider.name] = provider
        if default or self._default is None:
            self._default = provider.name

    def get(self, name: str) -> type[OCRProvider] | None:
        """Look up a provider class by name.

        Args:
            name: The provider name.

        Returns:
            The provider class, or ``None`` if not registered.
        """
        return self._providers.get(name)

    def get_default(self) -> type[OCRProvider] | None:
        """Return the default provider class, or ``None``.

        Returns:
            The default provider class, or ``None`` if none registered.
        """
        if self._default is None:
            return None
        return self._providers.get(self._default)

    @property
    def names(self) -> list[str]:
        """List of all registered provider names."""
        return list(self._providers)

    @property
    def default_name(self) -> str | None:
        """Name of the default provider, or ``None``."""
        return self._default

    @default_name.setter
    def default_name(self, name: str) -> None:
        if name not in self._providers:
            msg = f"Unknown OCR provider: {name!r}"
            raise KeyError(msg)
        self._default = name
