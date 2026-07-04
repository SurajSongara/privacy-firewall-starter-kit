"""OCR provider abstraction layer."""

from privacy_firewall.ocr.adapters import PaddleOCRAdapter
from privacy_firewall.ocr.provider import OCRProvider
from privacy_firewall.ocr.registry import OCRProviderRegistry

__all__ = [
    "OCRProvider",
    "OCRProviderRegistry",
    "PaddleOCRAdapter",
]
