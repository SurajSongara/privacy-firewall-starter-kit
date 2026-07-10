from privacy_firewall.detectors.email_detector import EmailDetector
from privacy_firewall.models.blocks import TextBlock
from privacy_firewall.models.document import Document, Page
from privacy_firewall.models.geometry import BoundingBox


def _page(text: str) -> Page:
    bbox = BoundingBox(x0=0.0, y0=0.0, x1=300.0, y1=50.0)
    block = TextBlock(
        block_id="b1", bbox=bbox, page_number=1, confidence=1.0, text=text
    )
    return Page(
        page_number=1, width=612.0, height=792.0, blocks=[block]
    )


class TestEmailDetector:
    def setup_method(self) -> None:
        self.detector = EmailDetector()

    def test_name(self) -> None:
        assert self.detector.name == "email"

    def test_detect_simple_email(self) -> None:
        doc = Document(pages=[_page("Contact: user@example.com")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "user@example.com"
        assert result[0].detection_type == "EMAIL"
        assert result[0].confidence == 0.9

    def test_detect_email_with_plus(self) -> None:
        doc = Document(pages=[_page("Email: user+tag@example.co.uk")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "user+tag@example.co.uk"

    def test_detect_email_with_dots(self) -> None:
        doc = Document(pages=[_page("Email: first.last@domain.com")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "first.last@domain.com"

    def test_detect_email_with_underscores(self) -> None:
        doc = Document(pages=[_page("Email: user_name@domain.com")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "user_name@domain.com"

    def test_detect_email_with_hyphen(self) -> None:
        doc = Document(pages=[_page("Email: user-name@my-domain.com")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "user-name@my-domain.com"

    def test_detect_email_percent_encoded(self) -> None:
        doc = Document(pages=[_page("Email: user%test@domain.com")])
        result = self.detector.scan(doc)
        assert len(result) == 1

    def test_multiple_emails(self) -> None:
        doc = Document(pages=[_page("a@b.com, c@d.org, e@f.net")])
        result = self.detector.scan(doc)
        assert len(result) == 3

    def test_no_false_positive_without_at(self) -> None:
        doc = Document(pages=[_page("This is just text without an email.")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_no_false_positive_bare_domain(self) -> None:
        doc = Document(pages=[_page("Visit example.com for more info")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_rejects_double_dot_in_domain(self) -> None:
        doc = Document(pages=[_page("Email: user@example..com")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_rejects_no_local_part(self) -> None:
        doc = Document(pages=[_page("Email: @example.com")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_email_at_start(self) -> None:
        doc = Document(pages=[_page("user@example.com is my email")])
        result = self.detector.scan(doc)
        assert len(result) == 1

    def test_email_at_end(self) -> None:
        doc = Document(pages=[_page("My email is user@example.com")])
        result = self.detector.scan(doc)
        assert len(result) == 1

    def test_email_in_parentheses(self) -> None:
        doc = Document(pages=[_page("Email: (user@example.com)")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "user@example.com"

    def test_email_subdomain(self) -> None:
        doc = Document(pages=[_page("Email: user@sub.domain.com")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "user@sub.domain.com"

    def test_long_local_part_rejected(self) -> None:
        local = "a" * 65
        doc = Document(pages=[_page(f"{local}@example.com")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_total_email_too_long_rejected(self) -> None:
        local = "a" * 200
        doc = Document(pages=[_page(f"{local}@b.com")])
        result = self.detector.scan(doc)
        assert len(result) == 0

    def test_bbox_populated(self) -> None:
        bbox = BoundingBox(x0=10.0, y0=20.0, x1=300.0, y1=50.0)
        block = TextBlock(
            block_id="b1", bbox=bbox, page_number=1, confidence=1.0, text="user@example.com"
        )
        page = Page(page_number=1, width=612.0, height=792.0, blocks=[block])
        doc = Document(pages=[page])
        result = self.detector.scan(doc)
        assert result[0].bbox == bbox

    def test_unknown_tld_rejected(self) -> None:
        # OCR artifact from a mangled "sbi.co.in" — "coin" is not a real TLD.
        doc = Document(pages=[_page("Branch Code: 30524@sbi.coin")])
        result = self.detector.scan(doc)
        assert result == []

    def test_internal_system_id_rejected(self) -> None:
        doc = Document(pages=[_page("System ID: admin@internal.ledger")])
        result = self.detector.scan(doc)
        assert result == []

    def test_country_tld_accepted(self) -> None:
        doc = Document(pages=[_page("Contact: support@bank.co.in")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "support@bank.co.in"

    def test_glued_next_token_trimmed(self) -> None:
        # Fragmented PDF extraction glues the next label onto the email.
        doc = Document(pages=[_page("pooja569@hotmail.comPhone: 9876543210")])
        result = self.detector.scan(doc)
        assert len(result) == 1
        assert result[0].text == "pooja569@hotmail.com"

    def test_lowercase_glued_residue_still_rejected(self) -> None:
        # "coin" starts with the known TLD "co" but the residue "in" is
        # lowercase — a genuine artifact, not a glued token.
        doc = Document(pages=[_page("Branch: 30524@sbi.coin")])
        result = self.detector.scan(doc)
        assert result == []
