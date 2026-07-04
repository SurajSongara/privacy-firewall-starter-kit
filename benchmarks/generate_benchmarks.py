"""Generate synthetic benchmark PDFs for regression testing."""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def _out_dir() -> Path:
    return Path(__file__).parent


def _native_pdf() -> None:
    """Create a PDF with extractable text (native PDF)."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "State Bank of India\n"
        "Account Statement\n"
        "Account Holder: John Doe\n"
        "IFSC: SBIN0012345\n"
        "Account Number: 12345678901\n"
        "Period: 01 Apr 2024 to 31 Mar 2025\n\n"
        "PAN: ABCPD1234F\n"
        "Email: john.doe@example.com\n"
        "Phone: +91 98765 43210\n"
        "Aadhaar: 1234 5678 9012\n"
        "UPI: john@oksbi\n"
    )
    page.insert_text((50, 50), text, fontsize=11)
    out = _out_dir() / "native" / "sbi_statement_native.pdf"
    doc.save(str(out))
    doc.close()


def _scanned_pdf() -> None:
    """Create a PDF with only images (simulated scan)."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Draw some colored rectangles to simulate a scan (no text layer)
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(50, 50, 545, 792))
    shape.finish(color=(0, 0, 0), fill=(0.95, 0.95, 0.95))
    shape.commit()
    # Insert a small image to simulate a scanned document
    # Create a tiny 1x1 pixel PNG and embed it
    img_doc = fitz.open()
    img_page = img_doc.new_page(width=100, height=100)
    img_shape = img_page.new_shape()
    img_shape.draw_rect(fitz.Rect(0, 0, 100, 100))
    img_shape.finish(color=(0, 0, 0), fill=(0.8, 0.8, 0.8))
    img_shape.commit()
    # Use a simple pixmap instead (no alpha channel)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), 0)
    pix.set_rect(pix.irect, (180, 180, 180))
    img_bytes = pix.tobytes(output="png")
    page.insert_image(fitz.Rect(50, 50, 545, 792), stream=img_bytes)
    out = _out_dir() / "scanned" / "scanned_doc.pdf"
    doc.save(str(out))
    doc.close()


def _hybrid_pdf() -> None:
    """Create a PDF with both text and images."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "HDFC Bank\nAccount Statement", fontsize=14)
    # Add an image below
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 100), 0)
    pix.set_rect(pix.irect, (200, 200, 200))
    img_bytes = pix.tobytes(output="png")
    page.insert_image(fitz.Rect(50, 200, 250, 300), stream=img_bytes)
    out = _out_dir() / "hybrid" / "hdfc_hybrid.pdf"
    doc.save(str(out))
    doc.close()


def _broken_pdf() -> None:
    """Create a minimal broken PDF."""
    doc = fitz.open()
    # Create a page with no text (empty page)
    doc.new_page(width=595, height=842)
    out = _out_dir() / "broken" / "empty.pdf"
    doc.save(str(out))
    doc.close()

    # Corrupted PDF (invalid bytes)
    broken_path = _out_dir() / "broken" / "corrupted.pdf"
    broken_path.write_bytes(b"%PDF-1.4 invalid garbage data here")


def generate_all() -> None:
    """Generate all benchmark PDFs."""
    _native_pdf()
    _scanned_pdf()
    _hybrid_pdf()
    _broken_pdf()
    print("Benchmark PDFs generated.")


if __name__ == "__main__":
    generate_all()
