from privacy_firewall.detectors.pan_detector import PANDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _page(text: str) -> Page:
    bbox = BoundingBox(x0=0.0, y0=0.0, x1=200.0, y1=50.0)
    block = TextBlock(
        block_id="b1", bbox=bbox, page_number=1, confidence=1.0, text=text
    )
    return Page(
        page_number=1, width=612.0, height=792.0, blocks=[block]
    )


VALID_PAN = "AAAAA1111A"  # status=A (AOP), first letter=A, seq=1111, check=A


class TestPANDetector:
    def setup_method(self) -> None:
        self.detector = PANDetector()

    def test_name(self) -> None:
        assert self.detector.name == "pan"

    def test_detect_valid_pan(self) -> None:
        doc = Document(pages=[_page(f"My PAN is {VALID_PAN}")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == VALID_PAN
        assert result[0].detection_type == "PAN"
        assert result[0].confidence == 0.95

    def test_detect_individual_pan_status_p(self) -> None:
        doc = Document(pages=[_page("PAN: AAAAA1111P")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "AAAAA1111P"

    def test_detect_company_pan_status_c(self) -> None:
        doc = Document(pages=[_page("PAN: AAAAA1111C")])
        result = self.detector.scan(doc)
        assert len(result) == 1

    def test_multiple_pans(self) -> None:
        doc = Document(pages=[_page(f"First: {VALID_PAN}, Second: PPPPP1111P")])
        result = self.detector.scan(doc)
        assert len(result) == 2

    def test_no_false_positive_short(self) -> None:
        doc = Document(pages=[_page("ABCD1234E is too short")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_no_false_positive_invalid_status(self) -> None:
        doc = Document(pages=[_page("AAADP1111P has invalid status code")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_no_false_positive_lowercase(self) -> None:
        doc = Document(pages=[_page("aaaaa1111a is lowercase")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_no_match_when_no_pan(self) -> None:
        doc = Document(pages=[_page("This is a normal sentence with no PAN.")])
        result = self.detector.scan(doc)
        assert result == []

    def test_pan_at_start_of_text(self) -> None:
        doc = Document(pages=[_page(f"{VALID_PAN} is at the start")])
        result = self.detector.scan(doc)
        assert len(result) == 1

    def test_pan_at_end_of_text(self) -> None:
        doc = Document(pages=[_page(f"End has {VALID_PAN}")])
        result = self.detector.scan(doc)
        assert len(result) == 1

    def test_pan_with_surrounding_punctuation(self) -> None:
        doc = Document(pages=[_page(f"({VALID_PAN})")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == VALID_PAN

    def test_rejects_sequential_digits_only(self) -> None:
        doc = Document(pages=[_page("1234567890")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_rejects_sequential_letters_only(self) -> None:
        doc = Document(pages=[_page("ABCDEFGHIJ")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_validate_format_all_known_status_codes(self) -> None:
        valid_codes = ["P", "C", "H", "F", "A", "T", "B", "L", "J", "G"]
        for code in valid_codes:
            pan = f"AAAAA1111{code}"
            doc = Document(pages=[_page(pan)])
            result = self.detector.scan(doc)
            assert len(result) == 1, f"Failed for code {code}"

    def test_rejects_invalid_status_code(self) -> None:
        for code in ["D", "E", "I", "K", "M", "N", "O", "Q", "R", "S", "U", "V", "W", "Y", "Z"]:
            pan = f"AAA{code}P1111P"
            doc = Document(pages=[_page(pan)])
            result = self.detector.scan(doc)
            assert len(result) == 0, f"Should reject code {code}"

    def test_bbox_populated(self) -> None:
        bbox = BoundingBox(x0=10.0, y0=20.0, x1=200.0, y1=50.0)
        block = TextBlock(
            block_id="b1", bbox=bbox, page_number=1, confidence=1.0, text=VALID_PAN
        )
        page = Page(page_number=1, width=612.0, height=792.0, blocks=[block])
        doc = Document(pages=[page])
        result = self.detector.scan(doc)
        assert result[0].bbox == bbox
