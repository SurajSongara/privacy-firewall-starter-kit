# P008_PAGE_IMAGE_RENDERER

Engine utility for the review UI: render each PDF page to PNG via PyMuPDF pixmap at a given DPI, and expose the coordinate transform (PDF points → rendered-image pixels) so ReviewPlan bboxes can be drawn as overlays client-side. `(pdf_path, page_number, dpi) → PageImage {png_bytes, width, height, scale}`. No UI code here — pure engine. Tests assert bbox transform round-trips against known fixtures.
