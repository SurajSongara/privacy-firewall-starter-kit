"""OCR provider abstraction layer."""

from privacy_firewall.ocr.provider import OCRProvider
from privacy_firewall.ocr.registry import OCRProviderRegistry

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

        _registry.register(TesseractOCRAdapter, default=True)
    except ImportError:
        pass

    try:
        from privacy_firewall.ocr.adapters.paddle import PaddleOCRAdapter

        _registry.register(PaddleOCRAdapter)
    except ImportError:
        pass

    try:
        from privacy_firewall.ocr.adapters.rapid import RapidOCRAdapter

        # Register as default if no other default is set
        _registry.register(RapidOCRAdapter, default=not _registry.default_name)
    except ImportError:
        pass


_register_builtins()

__all__ = [
    "OCRProvider",
    "OCRProviderRegistry",
    "get_default_engine",
    "get_registry",
    "list_engines",
]
