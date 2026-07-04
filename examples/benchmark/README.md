# Benchmark Dataset

## Purpose

This benchmark evaluates the Privacy Firewall engine's detection accuracy.
Each dataset contains a synthetically generated PDF and a ground-truth JSON
file listing all expected PII detections.

## Datasets

| Dataset     | Description                                   | PII Types                         |
|-------------|-----------------------------------------------|-----------------------------------|
| simple-pii  | Single page, one occurrence of each PII type  | PAN, Aadhaar, Email, Phone, UPI   |
| multi-pii   | Multi-page document with repeated PII values  | PAN, Aadhaar, Email, Phone, UPI   |
| no-pii      | Clean document with no PII                    | None                              |

## Metrics

The benchmark runner (forthcoming) measures:

- **Precision**: `true_positives / (true_positives + false_positives)`
- **Recall**: `true_positives / (true_positives + false_negatives)`
- **F1 Score**: `2 * (precision * recall) / (precision + recall)`
- **Runtime**: Wall-clock time per detector

## Usage

```bash
python -m privacy_firewall benchmark examples/benchmark/
```
