"""Concrete OCR adapter implementations."""

from privacy_firewall.ocr.adapters.paddle import PaddleOCRAdapter
from privacy_firewall.ocr.adapters.rapid import RapidOCRAdapter
from privacy_firewall.ocr.adapters.tesseract import TesseractOCRAdapter

__all__ = [
    "PaddleOCRAdapter",
    "RapidOCRAdapter",
    "TesseractOCRAdapter",
]
