from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import fitz

from privacy_firewall.models.blocks import Block, ImageBlock, TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


class PDFParser:
    def __init__(self, file_path: str | Path) -> None:
        self._path = Path(file_path)

    def parse(self) -> Document:
        doc = fitz.open(str(self._path))
        pages: list[Page] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            raw: dict[str, Any] = page.get_text("dict")
            blocks = self._extract_blocks(raw, page_num + 1)
            pages.append(
                Page(
                    page_number=page_num + 1,
                    width=page.rect.width,
                    height=page.rect.height,
                    blocks=blocks,
                )
            )

        doc.close()
        return Document(pages=pages)

    @staticmethod
    def parse_bytes(data: bytes) -> Document:
        doc = fitz.open(stream=data, filetype="pdf")
        pages: list[Page] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            raw: dict[str, Any] = page.get_text("dict")
            blocks = PDFParser._extract_blocks(raw, page_num + 1)
            pages.append(
                Page(
                    page_number=page_num + 1,
                    width=page.rect.width,
                    height=page.rect.height,
                    blocks=blocks,
                )
            )

        doc.close()
        return Document(pages=pages)

    @staticmethod
    def _extract_blocks(raw: dict[str, Any], page_number: int) -> list[Block]:
        blocks: list[Block] = []

        for item in raw.get("blocks", []):
            item_typed: dict[str, Any] = item
            bbox = BoundingBox(
                x0=item_typed["bbox"][0],
                y0=item_typed["bbox"][1],
                x1=item_typed["bbox"][2],
                y1=item_typed["bbox"][3],
            )
            block_id = str(uuid.uuid4())

            if item_typed["type"] == 0:
                text_parts: list[str] = []
                for line in item_typed.get("lines", []):
                    for span in line.get("spans", []):
                        text_parts.append(span["text"])
                text = "".join(text_parts)
                blocks.append(
                    TextBlock(
                        block_id=block_id,
                        bbox=bbox,
                        page_number=page_number,
                        confidence=1.0,
                        text=text,
                    )
                )

            elif item_typed["type"] == 1:
                image_bytes = item_typed.get("image")
                ext = item_typed.get("ext", "png")
                blocks.append(
                    ImageBlock(
                        block_id=block_id,
                        bbox=bbox,
                        page_number=page_number,
                        confidence=1.0,
                        image_data=image_bytes,
                        mime_type=f"image/{ext}",
                    )
                )

        return blocks
