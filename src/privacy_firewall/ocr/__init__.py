"""OCR provider abstraction layer."""

import os
import warnings

from privacy_firewall.ocr.provider import OCRProvider
from privacy_firewall.ocr.registry import OCRProviderRegistry

#: Env var that pins the default OCR engine (must name a registered engine).
OCR_ENGINE_ENV_VAR = "PRIVACY_FIREWALL_OCR_ENGINE"

#: Default-engine preference when the env var is unset: rapidocr first
#: (pure-wheel install, models bundled — the packaged-build backend),
#: then tesseract, then paddleocr.
_DEFAULT_PREFERENCE = ("rapidocr", "tesseract", "paddleocr")

# Module-level singleton registry — adapters register here at import time.
_registry = OCRProviderRegistry()


def get_registry() -> OCRProviderRegistry:
    """Return the global OCR provider registry."""
    return _registry


def list_engines() -> list[str]:
    """Return names of all registered OCR engines."""
    return _registry.names


def get_default_engine() -> str | None:
    """Return the name of the default OCR engine, or ``None``."""
    return _registry.default_name


# Auto-register built-in adapters (import triggers registration).
def _register_builtins() -> None:
    """Register the built-in OCR adapters if their dependencies exist."""
    try:
        from privacy_firewall.ocr.adapters.tesseract import TesseractOCRAdapter

        _registry.register(TesseractOCRAdapter)
    except ImportError:
        pass

    try:
        from privacy_firewall.ocr.adapters.paddle import PaddleOCRAdapter

        _registry.register(PaddleOCRAdapter)
    except ImportError:
        pass

    try:
        from privacy_firewall.ocr.adapters.rapid import RapidOCRAdapter

        _registry.register(RapidOCRAdapter)
    except ImportError:
        pass


def _resolve_default(registry: OCRProviderRegistry, env_value: str | None) -> None:
    """Pick the default engine deterministically.

    The env var wins if it names a registered engine (a warning is
    emitted otherwise); then the fixed preference order applies, so the
    default never depends on adapter registration order. Because the
    adapters import their backends lazily, registration alone does not
    prove an engine can run — the preference scan therefore skips
    engines whose ``is_available()`` check fails. An explicit env pin
    is honoured even if unavailable so the adapter's install-hint
    ImportError surfaces at run time instead of a silent fallback.

    Args:
        registry: The registry whose default should be set.
        env_value: The raw value of ``PRIVACY_FIREWALL_OCR_ENGINE``.
    """
    if env_value:
        name = env_value.strip().lower()
        if registry.get(name) is not None:
            registry.default_name = name
            return
        warnings.warn(
            f"{OCR_ENGINE_ENV_VAR}={env_value!r} does not match a registered "
            f"OCR engine (available: {registry.names or 'none'}); ignoring.",
            stacklevel=2,
        )
    for name in _DEFAULT_PREFERENCE:
        provider = registry.get(name)
        if provider is not None and provider.is_available():
            registry.default_name = name
            return


_register_builtins()
_resolve_default(_registry, os.environ.get(OCR_ENGINE_ENV_VAR))

__all__ = [
    "OCR_ENGINE_ENV_VAR",
    "OCRProvider",
    "OCRProviderRegistry",
    "get_default_engine",
    "get_registry",
    "list_engines",
]
