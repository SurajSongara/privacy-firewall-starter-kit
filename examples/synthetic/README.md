# Synthetic Test Documents

This directory contains synthetic test documents for benchmarking the Privacy Firewall.

## Generated Documents

| File | Description | PII Items |
|------|-------------|-----------|
| 01-form16.pdf | Form 16 (Employer Certificate) | 7 (PAN, Aadhaar, Email, Phone, Account, IFSC, UPI) |
| 02-payslip.pdf | Payslip with bank details | 7 (PAN, Aadhaar, Email, Phone, Account, IFSC, UPI) |
| 03-tricky-edge-cases.pdf | False positive testing | 0 (designed to trigger false positives) |
| 04-aadhaar-checksum.pdf | Aadhaar checksum validation | 5 (4 valid, 1 invalid) |
| 05-payslip-batch-2.pdf | Additional payslip variant | 7 |
| 06-payslip-batch-3.pdf | Additional payslip variant | 7 |
| 07-form16-batch-2.pdf | Additional Form 16 variant | 7 |

## Running the Benchmark

```bash
cd examples
python benchmark_synthetic.py
```

## Regenerating Documents

```bash
cd examples
python generate_advanced_samples.py
```

## PII Types Detected

- **PAN**: Indian Permanent Account Number (10 chars, format: XXXXX1234X)
- **AADHAAR**: Indian Aadhaar number (12 digits, Verhoeff checksum validated)
- **EMAIL**: Email addresses
- **PHONE**: Indian phone numbers (10 digits, starts with 6-9)
- **UPI**: UPI IDs (format: name@provider)
- **IFSC**: Indian Financial System Code (11 chars, format: XXXX0YYYYYY)
- **ACCOUNT**: Bank account numbers (9-18 digits, context-aware, supports leading zeros)
