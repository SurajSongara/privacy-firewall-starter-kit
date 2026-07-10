"""Generate a realistic SBI bank statement PDF for testing."""
from __future__ import annotations

from pathlib import Path

import fitz


def generate_sbi_statement(out_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Header
    page.insert_text((50, 40), "STATE BANK OF INDIA", fontsize=16, color=(0, 0.3, 0.6))
    page.insert_text((50, 65), "Corporate Centre, Mumbai", fontsize=10, color=(0.4, 0.4, 0.4))

    # Account details box
    box = fitz.Rect(50, 85, 545, 170)
    shape = page.new_shape()
    shape.draw_rect(box)
    shape.finish(color=(0, 0, 0), fill=(0.95, 0.95, 0.97))
    shape.commit()

    page.insert_text((65, 105), "Account Statement", fontsize=13, color=(0, 0, 0))
    page.insert_text((65, 125), "Account Holder  :  John Doe", fontsize=10)
    page.insert_text((65, 140), "Account Number  :  12345678901", fontsize=10)
    page.insert_text((65, 155), "IFSC Code       :  SBIN0012345", fontsize=10)
    page.insert_text((350, 125), "Period: 01 Apr 2024 to 31 Mar 2025", fontsize=10)
    page.insert_text((350, 140), "Page: 1 of 3", fontsize=10)

    # Transactions table header
    y = 190
    cols = [50, 100, 250, 350, 450]
    headers = ["Date", "Description", "", "Debit", "Credit", "Balance"]
    # Actually let me use a simpler layout
    page.insert_text((50, y), "Date", fontsize=10, fontname="helv")
    page.insert_text((130, y), "Description", fontsize=10, fontname="helv")
    page.insert_text((370, y), "Debit", fontsize=10, fontname="helv")
    page.insert_text((440, y), "Credit", fontsize=10, fontname="helv")
    page.insert_text((510, y), "Balance", fontsize=10, fontname="helv")

    # Table separator
    page.draw_line((50, y + 5), (575, y + 5))

    # Transaction rows
    transactions = [
        ("01-Apr-2024", "Opening Balance", "", "", "25,000.00"),
        ("03-Apr-2024", "NACH DR AEPC", "", "5,000.00", "20,000.00"),
        ("10-Apr-2024", "NEFT INWARD", "15,000.00", "", "35,000.00"),
        ("15-Apr-2024", "ATM WDL 654321", "", "10,000.00", "25,000.00"),
        ("20-Apr-2024", "UPI/PAY/abc@paytm", "", "2,500.00", "22,500.00"),
        ("25-Apr-2024", "INTEREST CREDITED", "500.00", "", "23,000.00"),
        ("30-Apr-2024", "NACH DR ICICI PRU", "", "3,000.00", "20,000.00"),
        ("05-May-2024", "NEFT INWARD SALARY", "50,000.00", "", "70,000.00"),
        ("10-May-2024", "BILL PAY ELECTRICITY", "", "3,200.00", "66,800.00"),
        ("15-May-2024", "UPI/PAY/pqr@paytm", "", "1,800.00", "65,000.00"),
        ("20-May-2024", "NEFT INWARD", "12,000.00", "", "77,000.00"),
        ("25-May-2024", "ATM WDL 987654", "", "8,000.00", "69,000.00"),
        ("01-Jun-2024", "NACH DR LIC", "", "5,500.00", "63,500.00"),
    ]

    y = 205
    for row in transactions[:13]:  # Fit on one page
        page.insert_text((50, y), row[0], fontsize=8)
        page.insert_text((130, y), row[1], fontsize=8)
        if row[2]:
            page.insert_text((440, y), row[2], fontsize=8, color=(0, 0.5, 0))
        if row[3]:
            page.insert_text((370, y), row[3], fontsize=8, color=(0.8, 0, 0))
        page.insert_text((510, y), row[4], fontsize=8)
        y += 14

    # Footer
    page.insert_text((50, 820), "SBI | SBIN0012345 | Page 1 of 3", fontsize=8, color=(0.5, 0.5, 0.5))

    # Page 2
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 40), "STATE BANK OF INDIA", fontsize=14, color=(0, 0.3, 0.6))
    page2.insert_text((50, 65), "Account Statement (contd.)", fontsize=11)
    page2.insert_text((350, 65), "Page: 2 of 3", fontsize=10)

    # More transactions on page 2
    more_txns = [
        ("01-Jul-2024", "UPI/PAY/xyz@paytm", "", "2,000.00", "61,500.00"),
        ("05-Jul-2024", "NEFT INWARD", "25,000.00", "", "86,500.00"),
        ("10-Jul-2024", "ATM WDL 112233", "", "12,000.00", "74,500.00"),
        ("15-Jul-2024", "BILL PAY MOBILE RECH", "", "1,500.00", "73,000.00"),
        ("20-Jul-2024", "NACH DR HDFC LOAN", "", "8,500.00", "64,500.00"),
        ("25-Jul-2024", "INTEREST CREDITED", "520.00", "", "65,020.00"),
        ("01-Aug-2024", "UPI/PAY/food@paytm", "", "1,200.00", "63,820.00"),
    ]

    y = 95
    for row in more_txns[:7]:
        page2.insert_text((50, y), row[0], fontsize=8)
        page2.insert_text((130, y), row[1], fontsize=8)
        if row[2]:
            page2.insert_text((440, y), row[2], fontsize=8, color=(0, 0.5, 0))
        if row[3]:
            page2.insert_text((370, y), row[3], fontsize=8, color=(0.8, 0, 0))
        page2.insert_text((510, y), row[4], fontsize=8)
        y += 14

    # PII data at the bottom of page 2
    y = 250
    page2.insert_text((50, y), "Personal Information:", fontsize=10)
    y += 20
    page2.insert_text((50, y), "PAN: ABCPD1234F", fontsize=9)
    y += 15
    page2.insert_text((50, y), "Email: john.doe@example.com", fontsize=9)
    y += 15
    page2.insert_text((50, y), "Phone: +91 98765 43210", fontsize=9)
    y += 15
    page2.insert_text((50, y), "Aadhaar: 1234 5678 9012", fontsize=9)
    y += 15
    page2.insert_text((50, y), "UPI: john.doe@oksbi", fontsize=9)

    page2.insert_text((50, 820), "SBI | SBIN0012345 | Page 2 of 3", fontsize=8, color=(0.5, 0.5, 0.5))

    # Page 3
    page3 = doc.new_page(width=595, height=842)
    page3.insert_text((50, 40), "STATE BANK OF INDIA", fontsize=14, color=(0, 0.3, 0.6))
    page3.insert_text((50, 65), "Account Statement (contd.)", fontsize=11)
    page3.insert_text((350, 65), "Page: 3 of 3", fontsize=10)

    page3.insert_text((50, 120), "Summary", fontsize=12)
    page3.insert_text((50, 145), "Opening Balance: Rs. 0.00", fontsize=10)
    page3.insert_text((50, 165), "Closing Balance: Rs. 63,820.00", fontsize=10)
    page3.insert_text((50, 185), "Total Credits: Rs. 1,03,020.00", fontsize=10)
    page3.insert_text((50, 205), "Total Debits: Rs. 39,200.00", fontsize=10)

    page3.insert_text((50, 250), "Note: This is a computer-generated statement.", fontsize=9, color=(0.5, 0.5, 0.5))

    page3.insert_text((50, 820), "SBI | SBIN0012345 | Page 3 of 3", fontsize=8, color=(0.5, 0.5, 0.5))

    doc.save(str(out_path))
    doc.close()
    print(f"Generated: {out_path}")


if __name__ == "__main__":
    generate_sbi_statement(Path(__file__).parent / "sbi_statement.pdf")
