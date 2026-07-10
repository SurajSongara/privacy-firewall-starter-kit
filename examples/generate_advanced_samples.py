"""Generate advanced synthetic PII test documents — Form 16, Payslips, tricky edge cases.

All data is entirely fictional. Generated for testing the privacy firewall.
"""

from __future__ import annotations

import json
import random
import string
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "synthetic"

# ─── Fictional Data ──────────────────────────────────────────────────────────

NAMES = [
    "Rajesh Kumar Sharma", "Priya Patel", "Amit Singh Rathore",
    "Sneha Agarwal", "Vikram Joshi", "Ananya Deshmukh",
    "Rohit Verma", "Kavitha Nair", "Sanjay Mishra", "Pooja Gupta",
]

EMPLOYERS = [
    ("Tata Consultancy Services Ltd", "TCS", "TIFC, Plot No. 1, Cyberabad", "Hyderabad", "500081", "TACTC0001M"),
    ("Infosys Limited", "Infosys", "Electronics City, Hosur Road", "Bengaluru", "560100", "AAAIT0001P"),
    ("Wipro Limited", "Wipro", " Doddakannelli, Sarjapur Road", "Bengaluru", "560035", "AAACW0001P"),
    ("HCL Technologies Ltd", "HCL", " 8, Civil Lines, Near Nishat Hotel", "Noida", "201301", "AABCH0001N"),
    ("Reliance Industries Ltd", "RIL", " Maker Chambers IV, 222 Nariman Point", "Mumbai", "400021", "AABCR0001A"),
]

BANKS = [
    ("State Bank of India", "SBIN0001234", "11-digit"),
    ("HDFC Bank Ltd", "HDFC0001234", "14-digit"),
    ("ICICI Bank Ltd", "ICIC0001234", "12-digit"),
    ("Axis Bank Ltd", "UTIB0001234", "15-digit"),
]


def _rand_pan() -> str:
    """Generate a valid-format PAN (5 letters, 4 digits, 1 letter).
    
    The 4th character must be a valid status code: A,B,C,F,G,H,J,L,P,T
    """
    letters = string.ascii_uppercase
    digits = string.digits
    pan_status_codes = "ABCFGHJLPT"  # Valid PAN status codes
    return (
        random.choice(letters) * 3
        + random.choice(pan_status_codes)  # 4th char = status code
        + random.choice(letters) * 1
        + "".join(random.choices(digits, k=4))
        + random.choice(letters)
    )


def _rand_aadhaar() -> str:
    """Generate a valid 12-digit Aadhaar number with Verhoeff checksum."""
    # Verhoeff algorithm tables
    D = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    ]
    P = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
    ]
    INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]
    
    # UIDAI never issues Aadhaar numbers starting with 0 or 1
    base = random.choice("23456789") + "".join(random.choices(string.digits, k=10))
    c = 0
    for i in range(len(base) - 1, -1, -1):
        digit = int(base[i])
        pos = (len(base) - i) % 8
        c = D[c][P[pos][digit]]
    return base + str(INV[c])


def _rand_phone() -> str:
    """Generate a 10-digit Indian mobile number."""
    prefixes = ["6", "7", "8", "9"]
    return random.choice(prefixes) + "".join(random.choices(string.digits, k=9))


def _rand_email(name: str) -> str:
    """Generate a realistic email from a name."""
    parts = name.lower().split()
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "company.co.in"]
    separators = [".", "_", ""]
    local = random.choice(separators).join(parts[:2])
    return f"{local}{random.randint(1, 999)}@{random.choice(domains)}"


def _rand_account(bank_type: str) -> str:
    """Generate a bank account number of appropriate length."""
    if "11" in bank_type:
        return "".join(random.choices(string.digits, k=11))
    elif "14" in bank_type:
        return "".join(random.choices(string.digits, k=14))
    elif "12" in bank_type:
        return "".join(random.choices(string.digits, k=12))
    else:
        return "".join(random.choices(string.digits, k=15))


def _rand_ifsc(bank_code: str = None) -> str:
    """Generate IFSC code.
    
    IFSC format: 4 letters (bank) + 0 + 6 alphanumeric (branch) = 11 chars
    
    Args:
        bank_code: 4-letter bank code. If None, uses a random known code.
    """
    if bank_code is None:
        bank_codes = ["SBIN", "HDFC", "ICIC", "UTIB", "KKBK", "CNRB"]
        bank_code = random.choice(bank_codes)
    # Branch code is 6 characters (alphanumeric)
    branch_code = "".join(random.choices(string.digits + string.ascii_uppercase, k=6))
    return bank_code + "0" + branch_code


def _rand_upi(name: str) -> str:
    """Generate a UPI ID."""
    handles = ["okaxis", "okhdfcbank", "okicicibank", "ybl", "paytm", "ibl", "sbi"]
    parts = name.lower().split()
    username = ".".join(parts[:2]) + str(random.randint(1, 99))
    return f"{username}@{random.choice(handles)}"


# ─── Document Generators ─────────────────────────────────────────────────────


class SyntheticDocumentGenerator:
    """Base class for generating synthetic PDF documents."""

    def __init__(self):
        self.pii_data = {}  # Track all PII for ground truth

    def _add_pii(self, det_type: str, text: str, page: int, label: str = ""):
        """Record PII for ground truth."""
        key = f"{det_type}:{text}"
        if key not in self.pii_data:
            self.pii_data[key] = {
                "detection_type": det_type,
                "text": text,
                "page_number": page,
                "label": label,
            }

    def _draw_header(self, page: fitz.Page, title: str, subtitle: str = ""):
        """Draw a professional header."""
        # Title
        page.insert_text(
            fitz.Point(50, 60), title,
            fontsize=16, fontname="helv", color=(0, 0, 0.5)
        )
        # Subtitle
        if subtitle:
            page.insert_text(
                fitz.Point(50, 80), subtitle,
                fontsize=10, fontname="helv", color=(0.3, 0.3, 0.3)
            )
        # Line
        page.draw_line(fitz.Point(50, 90), fitz.Point(545, 90),
                       color=(0, 0, 0.5), width=1.5)

    def _draw_field(self, page: fitz.Page, x: float, y: float,
                    label: str, value: str, pii_type: str = None):
        """Draw a label: value field."""
        page.insert_text(fitz.Point(x, y), label, fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(x + 120, y), str(value), fontsize=10, fontname="helv")
        # Only add to ground truth if it's a detectable PII type
        detectable_types = {"PAN", "AADHAAR", "EMAIL", "PHONE", "UPI", "ACCOUNT", "IFSC"}
        if pii_type and pii_type in detectable_types:
            self._add_pii(pii_type, str(value), page.number + 1, label)

    def _draw_table(self, page: fitz.Page, start_y: float,
                    headers: list[str], rows: list[list[str]],
                    col_widths: list[float] = None):
        """Draw a simple table."""
        if not col_widths:
            col_widths = [540 / len(headers)] * len(headers)

        x_start = 55
        y = start_y

        # Header row
        x = x_start
        for i, header in enumerate(headers):
            page.draw_rect(fitz.Rect(x, y - 12, x + col_widths[i], y + 2),
                           color=(0, 0, 0.5), fill=(0.9, 0.9, 1.0))
            page.insert_text(fitz.Point(x + 3, y - 2), header,
                             fontsize=8, fontname="helv", color=(0, 0, 0.5))
            x += col_widths[i]

        y += 15

        # Data rows
        for row in rows:
            x = x_start
            for i, cell in enumerate(row):
                page.draw_rect(fitz.Rect(x, y - 12, x + col_widths[i], y + 2),
                               color=(0.6, 0.6, 0.6))
                page.insert_text(fitz.Point(x + 3, y - 2), str(cell),
                                 fontsize=8, fontname="helv")
                x += col_widths[i]
            y += 15

        return y


class Form16Generator(SyntheticDocumentGenerator):
    """Generate realistic Form 16 (Tax Deducted at Source Certificate)."""

    def generate(self, output_path: Path) -> dict:
        name = random.choice(NAMES)
        pan = _rand_pan()
        aadhaar = _rand_aadhaar()
        email = _rand_email(name)
        phone = _rand_phone()
        employer = random.choice(EMPLOYERS)
        account = _rand_account("11-digit")
        ifsc = _rand_ifsc("SBIN")
        upi = _rand_upi(name)

        doc = fitz.open()

        # ─── Page 1: Certificate ─────────────────────────────────────────
        page = doc.new_page(width=595, height=842)
        self._draw_header(page, "FORM 16", "[See Rule 31(1)(a)]")
        page.insert_text(
            fitz.Point(50, 110),
            "CERTIFICATE UNDER SECTION 203 OF THE INCOME-TAX ACT, 1961",
            fontsize=11, fontname="helv", color=(0, 0, 0.5)
        )

        y = 140
        page.insert_text(fitz.Point(50, y), "Name of Employer:", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(170, y), employer[0], fontsize=10, fontname="helv")
        y += 20
        page.insert_text(fitz.Point(50, y), "TAN:", fontsize=9, fontname="helv")
        page.insert_text(fitz.Point(170, y), employer[3], fontsize=10, fontname="helv")

        y += 30
        self._draw_field(page, 50, y, "Name of Employee:", name)
        self._draw_field(page, 300, y, "PAN:", pan, "PAN")
        y += 25
        self._draw_field(page, 50, y, "Aadhaar:", aadhaar, "AADHAAR")
        self._draw_field(page, 300, y, "Designation:", "Senior Software Engineer")
        y += 25
        self._draw_field(page, 50, y, "Email:", email, "EMAIL")
        self._draw_field(page, 300, y, "Phone:", phone, "PHONE")

        y += 35
        page.insert_text(fitz.Point(50, y), "Summary of TDS Deducted",
                         fontsize=11, fontname="helv", color=(0, 0, 0.5))

        y += 15
        headers = ["Quarter", "Period", "Gross Salary", "TDS Deducted", "Date of Payment"]
        rows = [
            ["Q1", "Apr-Jun 2025", "₹ 4,50,000", "₹ 45,000", "30/06/2025"],
            ["Q2", "Jul-Sep 2025", "₹ 4,50,000", "₹ 45,000", "30/09/2025"],
            ["Q3", "Oct-Dec 2025", "₹ 4,50,000", "₹ 45,000", "31/12/2025"],
            ["Q4", "Jan-Mar 2026", "₹ 4,50,000", "₹ 45,000", "31/03/2026"],
        ]
        y = self._draw_table(page, y, headers, rows)

        y += 20
        page.insert_text(fitz.Point(50, y), f"Total Salary: ₹ 18,00,000", fontsize=10, fontname="helv")
        page.insert_text(fitz.Point(300, y), f"Total TDS: ₹ 1,80,000", fontsize=10, fontname="helv")

        # ─── Page 2: Bank Details & Verification ─────────────────────────
        page2 = doc.new_page(width=595, height=842)
        self._draw_header(page2, "FORM 16 — Bank & Verification Details")

        y = 120
        self._draw_field(page2, 50, y, "Bank Account:", account, "ACCOUNT")
        y += 25
        self._draw_field(page2, 50, y, "IFSC Code:", ifsc, "IFSC")
        y += 25
        self._draw_field(page2, 50, y, "UPI ID:", upi, "UPI")

        y += 40
        page2.insert_text(fitz.Point(50, y), "Verification:", fontsize=10, fontname="helv")
        y += 20
        verification_text = (
            f"I, {name}, son/daughter of ..., working as Senior Software Engineer "
            f"at {employer[0]}, do hereby certify that the information given above "
            f"is correct and complete to the best of my knowledge and belief."
        )
        # Word wrap
        words = verification_text.split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > 80:
                page2.insert_text(fitz.Point(50, y), line, fontsize=9, fontname="helv")
                y += 15
                line = word
            else:
                line = f"{line} {word}" if line else word
        if line:
            page2.insert_text(fitz.Point(50, y), line, fontsize=9, fontname="helv")

        y += 40
        page2.insert_text(fitz.Point(350, y), "Authorized Signatory", fontsize=9, fontname="helv")
        page2.draw_line(fitz.Point(350, y + 5), fitz.Point(500, y + 5),
                        color=(0, 0, 0), width=0.5)
        page2.insert_text(fitz.Point(350, y + 15), employer[0], fontsize=8, fontname="helv")

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        doc.close()

        return self.pii_data


class PayslipGenerator(SyntheticDocumentGenerator):
    """Generate realistic monthly payslip."""

    def generate(self, output_path: Path) -> dict:
        name = random.choice(NAMES)
        pan = _rand_pan()
        aadhaar = _rand_aadhaar()
        email = _rand_email(name)
        phone = _rand_phone()
        employer = random.choice(EMPLOYERS)
        bank = random.choice(BANKS)
        account = _rand_account(bank[2])
        upi = _rand_upi(name)

        employee_id = f"EMP{random.randint(10000, 99999)}"
        month = random.choice(["January", "February", "March", "April", "May", "June"])
        year = "2026"

        # Salary components
        basic = random.randint(30000, 80000)
        hra = int(basic * 0.4)
        da = int(basic * 0.1)
        special = int(basic * 0.2)
        conveyance = 1600
        medical = 1250
        pf = int(basic * 0.12)
        esi = int((basic + hra) * 0.0075) if (basic + hra) < 21000 else 0
        pt = 200
        tds = int(basic * 0.1)

        gross = basic + hra + da + special + conveyance + medical
        deductions = pf + esi + pt + tds
        net = gross - deductions

        doc = fitz.open()
        page = doc.new_page(width=595, height=842)

        # Header
        self._draw_header(page, f"PAYSLIP — {month} {year}",
                          f"{employer[0]} | {employer[1]}")

        y = 110
        # Employee details
        self._draw_field(page, 50, y, "Employee Name:", name)
        self._draw_field(page, 320, y, "Employee ID:", employee_id)
        y += 20
        self._draw_field(page, 50, y, "PAN:", pan, "PAN")
        self._draw_field(page, 320, y, "Aadhaar:", aadhaar, "AADHAAR")
        y += 20
        self._draw_field(page, 50, y, "Email:", email, "EMAIL")
        self._draw_field(page, 320, y, "Phone:", phone, "PHONE")
        y += 20
        self._draw_field(page, 50, y, "Designation:", "Software Engineer")
        self._draw_field(page, 320, y, "Department:", "Engineering")

        y += 35
        # Earnings table
        page.insert_text(fitz.Point(50, y), "Earnings", fontsize=11, fontname="helv",
                         color=(0, 0.5, 0))
        y += 15
        headers = ["Component", "Amount (₹)"]
        rows = [
            ["Basic Salary", f"{basic:,}"],
            ["House Rent Allowance (HRA)", f"{hra:,}"],
            ["Dearness Allowance (DA)", f"{da:,}"],
            ["Special Allowance", f"{special:,}"],
            ["Conveyance Allowance", f"{conveyance:,}"],
            ["Medical Allowance", f"{medical:,}"],
            ["GROSS EARNINGS", f"{gross:,}"],
        ]
        y = self._draw_table(page, y, headers, rows, col_widths=[350, 190])

        y += 15
        # Deductions table
        page.insert_text(fitz.Point(50, y), "Deductions", fontsize=11, fontname="helv",
                         color=(0.5, 0, 0))
        y += 15
        rows = [
            ["Provident Fund (PF)", f"{pf:,}"],
            ["Employee State Insurance (ESI)", f"{esi:,}"],
            ["Professional Tax (PT)", f"{pt:,}"],
            ["Tax Deducted at Source (TDS)", f"{tds:,}"],
            ["TOTAL DEDUCTIONS", f"{deductions:,}"],
        ]
        y = self._draw_table(page, y, headers, rows, col_widths=[350, 190])

        y += 15
        # Net pay
        page.draw_rect(fitz.Rect(50, y - 5, 540, y + 20),
                       color=(0, 0.5, 0), fill=(0.9, 1.0, 0.9))
        page.insert_text(fitz.Point(55, y + 10), f"NET PAY: ₹ {net:,}",
                         fontsize=12, fontname="helv", color=(0, 0.3, 0))

        y += 35
        # Bank details
        self._draw_field(page, 50, y, "Bank:", bank[0])
        y += 20
        self._draw_field(page, 50, y, "Account No:", account, "ACCOUNT")
        self._draw_field(page, 320, y, "IFSC:", _rand_ifsc(bank[1][:4]), "IFSC")
        y += 20
        self._draw_field(page, 50, y, "UPI:", upi, "UPI")

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        doc.close()

        return self.pii_data


class TrickyEdgeCaseGenerator(SyntheticDocumentGenerator):
    """Generate tricky documents with false-positive-prone patterns."""

    def generate(self, output_path: Path) -> dict:
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)

        self._draw_header(page, "BANK TRANSACTION STATEMENT",
                          "Account Statement — Tricky Edge Cases")

        y = 120

        # These are designed to test false positive reduction
        tricky_items = [
            # 12-digit numbers that look like Aadhaar but are transaction refs
            ("Transaction Ref: /DR/387696619190/", "FALSE_AADHAAR"),
            ("NEFT Ref: /NFB/247730907120/", "FALSE_AADHAAR"),
            ("IMPS Ref: /P2A/100224490779/", "FALSE_AADHAAR"),

            # 10-digit numbers that look like phone but are bank refs
            ("Challan No: /CNRB/9179083184/", "FALSE_PHONE"),
            ("UTR: 7987465071", "FALSE_PHONE"),
            ("Ref ID: 8223027920", "FALSE_PHONE"),

            # Email-like patterns that are not real emails
            ("Branch Code: 30524@sbi.coin", "FALSE_EMAIL"),
            ("System ID: admin@internal.ledger", "FALSE_EMAIL"),

            # Real PII mixed in (226251716424 is Verhoeff-valid, starts 2-9)
            ("Account Holder: Rajesh Kumar Sharma", "REAL_NAME"),
            ("PAN: ABCPA5678J", "REAL_PAN"),
            ("Phone: +91-9876543210", "REAL_PHONE"),
            ("Email: rajesh.sharma@gmail.com", "REAL_EMAIL"),
            ("Aadhaar: 226251716424", "REAL_AADHAAR"),
            ("UPI: rajesh@okhdfcbank", "REAL_UPI"),
        ]

        for item, item_type in tricky_items:
            page.insert_text(fitz.Point(50, y), item, fontsize=10, fontname="helv")
            y += 18

        # Ground truth for the deterministic real PII on page 1
        self._add_pii("PAN", "ABCPA5678J", 1, "PAN:")
        self._add_pii("PHONE", "+91-9876543210", 1, "Phone:")
        self._add_pii("EMAIL", "rajesh.sharma@gmail.com", 1, "Email:")
        self._add_pii("AADHAAR", "226251716424", 1, "Aadhaar:")
        self._add_pii("UPI", "rajesh@okhdfcbank", 1, "UPI:")

        # Page 2: Multi-column layout with PII in headers/footers
        page2 = doc.new_page(width=595, height=842)
        self._draw_header(page2, "MULTI-COLUMN STATEMENT")

        # Header with PII
        page2.insert_text(fitz.Point(50, 50), f"PAN: XYZAB1234C", fontsize=8,
                          fontname="helv", color=(0.5, 0.5, 0.5))

        # Footer with PII
        page2.insert_text(fitz.Point(50, 800), f"Contact: support@bank.co.in",
                          fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))
        page2.insert_text(fitz.Point(300, 800), f"Helpline: 1800-11-2233",
                          fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))

        # Main content with mixed PII
        y = 120
        lines = [
            "Date         Description                    Debit      Credit     Balance",
            "─────────────────────────────────────────────────────────────────────────",
            "01/01/2026   Opening Balance                            ₹50,000",
            "02/01/2026   Salary Credit - ABCPA5678J                ₹85,000   ₹1,35,000",
            "03/01/2026   NEFT to Priya Patel (UPI: priya@ybl)     ₹10,000   ₹1,25,000",
            "05/01/2026   IMPS Ref: 7987465071                      ₹5,000    ₹1,20,000",
            "10/01/2026   Electricity Bill                           ₹2,500    ₹1,17,500",
            "15/01/2026   Mobile: 9876543210                        ₹599      ₹1,16,901",
            "20/01/2026   UPI: rajesh@okhdfcbank                    ₹15,000   ₹1,01,901",
            "25/01/2026   Credit Card Bill                          ₹8,500    ₹93,401",
        ]

        for line in lines:
            page2.insert_text(fitz.Point(50, y), line, fontsize=9, fontname="cour")
            y += 15

        # Ground truth for the deterministic real PII on page 2
        self._add_pii("PAN", "XYZAB1234C", 2, "PAN:")
        self._add_pii("EMAIL", "support@bank.co.in", 2, "Contact:")
        self._add_pii("PAN", "ABCPA5678J", 2, "Salary Credit")
        self._add_pii("UPI", "priya@ybl", 2, "UPI:")
        self._add_pii("PHONE", "9876543210", 2, "Mobile:")
        self._add_pii("UPI", "rajesh@okhdfcbank", 2, "UPI:")

        # Page 3: OCR stress test - rotated text, small text, overlapping
        page3 = doc.new_page(width=595, height=842)
        self._draw_header(page3, "OCR STRESS TEST")

        y = 120
        page3.insert_text(fitz.Point(50, y), "Small text: PAN: MNPQR5678S", fontsize=7, fontname="helv")
        y += 20
        page3.insert_text(fitz.Point(50, y), "Tight spacing: Aadhaar:555566667771 Email:user@test.com", fontsize=9, fontname="helv")
        y += 20
        page3.insert_text(fitz.Point(50, y), "Mixed case: pAn: AbCdE1234F  aAdHaAr: 234512341239", fontsize=9, fontname="helv")
        y += 20
        page3.insert_text(fitz.Point(50, y), "With symbols: Phone: (91) 98765-43210  UPI: user@paytm", fontsize=9, fontname="helv")
        y += 20
        page3.insert_text(fitz.Point(50, y), "Dotted: A.C. No. 1234.5678.9012  IFSC: SBIN.0001.234", fontsize=9, fontname="helv")

        # Ground truth for the deterministic real PII on page 3
        self._add_pii("PAN", "MNPQR5678S", 3, "Small text:")
        self._add_pii("AADHAAR", "555566667771", 3, "Tight spacing")
        self._add_pii("EMAIL", "user@test.com", 3, "Tight spacing")
        self._add_pii("AADHAAR", "234512341239", 3, "Mixed case")
        self._add_pii("PHONE", "98765-43210", 3, "With symbols")
        self._add_pii("UPI", "user@paytm", 3, "With symbols")

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        doc.close()

        return self.pii_data


class AadhaarChecksumGenerator(SyntheticDocumentGenerator):
    """Generate documents specifically for Aadhaar Verhoeff checksum testing."""

    # Verhoeff algorithm tables
    _D = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    ]
    _P = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
    ]
    _INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]

    def _verhoeff_checksum(self, num: str) -> str:
        """Compute Verhoeff check digit for a number.
        
        The check digit is computed such that when appended to num,
        the full number validates to 0.
        """
        # First, compute what the check digit should be
        # by simulating the validation with check digit = 0
        c = 0
        for i in range(len(num) - 1, -1, -1):
            digit = int(num[i])
            pos = (len(num) - i) % 8
            c = self._D[c][self._P[pos][digit]]
        # The check digit is the inverse that makes c become 0
        return str(self._INV[c])

    def _valid_aadhaar(self) -> str:
        """Generate a valid Aadhaar number with Verhoeff check digit."""
        base = "".join(random.choices("0123456789", k=11))
        check = self._verhoeff_checksum(base)
        return base + check

    def _invalid_aadhaar(self) -> str:
        """Generate an invalid Aadhaar number (wrong check digit)."""
        base = "".join(random.choices("0123456789", k=11))
        check = self._verhoeff_checksum(base)
        # Flip the check digit
        invalid_check = str((int(check) + 1) % 10)
        return base + invalid_check

    def generate(self, output_path: Path) -> dict:
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)

        self._draw_header(page, "AADHAAR CHECKSUM TEST DOCUMENT")

        y = 120
        page.insert_text(fitz.Point(50, y), "Valid Aadhaar numbers (should detect):",
                         fontsize=10, fontname="helv", color=(0, 0.5, 0))
        y += 20

        valid_aadhaars = []
        for _ in range(5):
            aadhaar = self._valid_aadhaar()
            valid_aadhaars.append(aadhaar)
            page.insert_text(fitz.Point(70, y), f"• {aadhaar}", fontsize=10, fontname="helv")
            self._add_pii("AADHAAR", aadhaar, 1, "Valid Aadhaar")
            y += 18

        y += 20
        page.insert_text(fitz.Point(50, y), "Invalid Aadhaar numbers (should NOT detect as Aadhaar):",
                         fontsize=10, fontname="helv", color=(0.5, 0, 0))
        y += 20

        for _ in range(5):
            aadhaar = self._invalid_aadhaar()
            page.insert_text(fitz.Point(70, y), f"• {aadhaar}", fontsize=10, fontname="helv")
            y += 18

        y += 30
        page.insert_text(fitz.Point(50, y), "Formatted Aadhaar numbers:",
                         fontsize=10, fontname="helv", color=(0, 0, 0.5))
        y += 20

        for aadhaar in valid_aadhaars[:3]:
            formatted = f"{aadhaar[:4]} {aadhaar[4:8]} {aadhaar[8:]}"
            page.insert_text(fitz.Point(70, y), f"• {formatted}", fontsize=10, fontname="helv")
            y += 18

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
        doc.close()

        return self.pii_data


# ─── Main Generator ──────────────────────────────────────────────────────────

def generate_all():
    """Generate all synthetic documents."""
    print("Generating synthetic test documents...\n")

    generators = [
        ("01-form16", Form16Generator()),
        ("02-payslip", PayslipGenerator()),
        ("03-tricky-edge-cases", TrickyEdgeCaseGenerator()),
        ("04-aadhaar-checksum", AadhaarChecksumGenerator()),
        # Generate multiple payslips for variety
        ("05-payslip-batch-2", PayslipGenerator()),
        ("06-payslip-batch-3", PayslipGenerator()),
        # Generate multiple Form 16s
        ("07-form16-batch-2", Form16Generator()),
    ]

    all_ground_truth = {}

    for name, generator in generators:
        output_path = OUTPUT_DIR / f"{name}.pdf"
        pii_data = generator.generate(output_path)

        # Create ground truth
        ground_truth = {
            "document": f"synthetic/{name}.pdf",
            "description": f"Synthetic {name.replace('-', ' ').title()}",
            "expectations": list(pii_data.values()),
        }

        gt_path = output_path.with_suffix(".json")
        gt_path.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")

        all_ground_truth[name] = ground_truth
        print(f"  [OK] {name}.pdf - {len(pii_data)} PII items")

    # Summary
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(all_ground_truth, indent=2), encoding="utf-8")
    print(f"\n  [OK] Summary: {summary_path}")
    print(f"\n  Total documents: {len(generators)}")
    print(f"  Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    generate_all()
