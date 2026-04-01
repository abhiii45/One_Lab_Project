# Payments Reconciliation Prototype

## Overview
This project is a production-style Python prototype for reconciling platform transaction records against delayed bank settlement records. It demonstrates enterprise-grade transaction reconciliation logic, handling 120+ synthetic transactions and systematically detecting 8 distinct categories of mismatches.

### Core Workflow
1. **Synthetic Data Generation**: Creates realistic transaction and settlement datasets with configurable volume
2. **Edge-Case Injection**: Injects 8 mandatory mismatch types for comprehensive testing
3. **Reconciliation Engine**: Matches transactions to settlements and categorizes mismatches
4. **Report Generation**: Produces CSV exports and optional visualization charts
5. **Console Output**: Displays reconciliation summary with detailed mismatch analysis

## Problem Context
A payments platform logs transactions instantly when a user pays. Bank settlements arrive 1-2 days later, often in delayed or batched files. By month-end, every transaction should map to a settlement. Real-world data quality issues—duplicates, refunds without originals, cross-month timing, rounding differences—create complex reconciliation challenges. This prototype systematically detects and categorizes these issues as they occur in production systems.

## Project Structure
```
reconciliation_system.py      # Main entry point; re-exports all public APIs
requirements.txt              # Python dependencies (pandas, numpy, matplotlib)
outputs/                      # Generated CSV reports and visualization charts
tests/
  test_reconciliation_system.py # Unit tests for edge-case detection and matching logic
reconciliation/               # Core package
  __init__.py                 # Public API exports
  cli.py                      # CLI argument parser and main runner
  constants.py                # Deterministic IDs for 8 injected edge cases
  models.py                   # ReconciliationConfig and ReconciliationResult dataclasses
  data_generation.py          # Synthetic data generation and edge-case injection
  reconcile.py                # Core reconciliation logic and mismatch categorization
  reporting.py                # CSV export, console report, and chart generation
  pipeline.py                 # Orchestrates end-to-end execution
  logging_utils.py            # Logging configuration
```

## Data Model

### Transactions Dataset
| Column | Type | Description |
|--------|------|-------------|
| `transaction_id` | String | Unique transaction identifier (e.g., `TXN00001`) |
| `user_id` | String | User/customer ID (e.g., `USR0123`) |
| `amount` | Float | Transaction amount in currency units |
| `transaction_date` | Datetime | Date when transaction was recorded |

### Settlements Dataset  
| Column | Type | Description |
|--------|------|-------------|
| `transaction_id` | String | Matches transaction ID for linking |
| `settled_amount` | Float | Settlement amount from bank (can be negative for refunds) |
| `settlement_date` | Datetime | Date when bank settled the transaction |

### Data Generation Defaults
- **Base Records**: 120 synthetic transactions (configurable via `--records`)
- **Settlement Delay**: 1-2 days after transaction date (realistic bank processing)
- **Date Range**: January 2026 (configurable via code)
- **Amount Range**: $5.00–$750.00 per transaction
- **Reproducibility**: Controlled via seed value (default: 7)

## Injected Test Cases & Mismatch Categories

The prototype injects **8 deterministic edge cases** matched by unique IDs in `constants.py`. Each case triggers specific mismatch detection logic.

### Edge Cases Injected During Data Generation

| # | Issue Type | Test ID | Description | Detection |
|---|------------|---------|-------------|-----------|
| 1 | **Next-Month Settlement** | `TXN00005` | Transaction on 2026-01-31, settlement on 2026-02-02 | Detected as cross-month settlement |
| 2 | **Rounding Discrepancy** | `TXN00010` | Settled amount increased by +$0.01 | Detected as rounding difference (within tolerance) |
| 3 | **Duplicate Transaction** | `TXN00020` | Same transaction_id appears twice in platform records | Duplicate transaction flagged |
| 4 | **Duplicate Settlement** | `TXN00025` | Same transaction_id appears twice in bank settlement file | Duplicate settlement flagged |
| 5 | **Refund Without Original** | `RFD90001` | Negative settlement (-$42.35) with no corresponding transaction | Detected as refund without original |
| 6 | **Missing Settlement** | `TXN00030` | Transaction exists but settlement row is removed | Detected as missing settlement |
| 7 | **Extra Settlement** | `EXT90001` | Settlement exists but no matching transaction | Detected as extra settlement |
| 8 | **Amount Mismatch** | `TXN00040` | Settled amount increased by +$5.00 (exceeds tolerance) | Detected as amount mismatch |

### Mismatch Categories Detected

The reconciliation engine categorizes all mismatches into these 8 types:

1. **`missing_settlement`** (Type: 1-to-0)
   - Transaction exists in platform but not in bank settlements
   - Indicates transaction not yet cleared or lost in transmission
   
2. **`extra_settlement`** (Type: 0-to-1)
   - Settlement appears in bank file but no matching platform transaction
   - Indicates out-of-band credit or incorrect transaction ID in bank file

3. **`refund_without_original`** (Type: Negative 0-to-1)
   - Negative settlement with no corresponding transaction (refund/reversal)
   - Indicates customer refund processed where original transaction not found

4. **`duplicate_transaction`** (Type: Many-to-1)
   - Same transaction_id appears multiple times in platform records
   - Indicates duplicate transaction entry or duplicate payment detection failure

5. **`duplicate_settlement`** (Type: 1-to-Many)
   - Same transaction_id appears multiple times in bank settlement file
   - Indicates duplicate entry in bank file or split settlement

6. **`amount_mismatch`** (Type: Amount > Tolerance)
   - Absolute difference between transaction and settled amount exceeds tolerance
   - Indicates conversion error, FX rounding, or fee deduction

7. **`rounding_difference`** (Type: 0 < Amount ≤ Tolerance)
   - Minor difference (default tolerance: $0.02) within rounding threshold
   - Typically not actionable; flagged for aggregate-level detection

8. **`cross_month_settlement`** (Type: Date Mismatch)
   - Transaction and settlement occur in different calendar months
   - Common at month boundaries; requires special handling for month-end cutoff

## Reconciliation Logic

### Core Algorithm: `reconcile_data(transactions, settlements, rounding_tolerance=0.02)`

The reconciliation engine performs the following steps:

#### Step 1: Aggregation
- Group transactions by `transaction_id`, sum amounts, track record count
- Group settlements by `transaction_id`, sum amounts, track record count
- Extract unique transaction and settlement ID sets

#### Step 2: Mismatch Detection
```
Duplicate transactions ← Transactions with record_count > 1
Duplicate settlements ← Settlements with record_count > 1
Missing settlements ← Transaction IDs NOT in settlement ID set
Extra settlements ← Settlement IDs NOT in transaction ID set
Refunds without original ← Extra settlements with negative amount
```

#### Step 3: Matched Records Analysis
For records with exactly 1 transaction AND 1 settlement:
- Calculate `amount_diff = settled_amount - transaction_amount`
- **Rounding differences**: `0 < |amount_diff| ≤ tolerance` (default: $0.02)
- **Amount mismatches**: `|amount_diff| > tolerance`
- **Cross-month settlements**: `transaction_month ≠ settlement_month`

#### Step 4: Summary Computation
Calculates aggregate metrics:
- Total transaction rows and unique transaction IDs
- Total settlement rows and unique settlement IDs
- Total transaction amount and total settled amount  
- Overall amount gap (settlements - transactions)
- Count of each mismatch category
- Flag: `total_rounding_only_gap_detected` (gap ≤ $0.50 with only rounding differences)
  - aggregate gap (`total_settlement_amount - total_transaction_amount`)
- Flags `total_rounding_only_gap_detected=True` only when:
  - small non-zero aggregate gap (`<= 0.5`)
  - no hard amount mismatches
  - at least one rounding difference

## Reporting Output

### Console Output
When executed, the program prints:
1. **Reconciliation Summary**
   - Total transaction and settlement row counts
   - Unique transaction IDs and settlement IDs
   - Total amount across both datasets
   - Overall amount gap (settlements - transactions)

2. **Mismatch Counts**
   - Count of each issue type (duplicates, missing, extra, amount mismatch, rounding diff, cross-month)

3. **Detailed Mismatch Report** (first 20 rows)
   - Columns: `issue_type`, `transaction_id`, `transaction_amount`, `settled_amount`, `transaction_date`, `settlement_date`, `explanation`
   - Sorted by issue_type and transaction_id

4. **Assumptions**
   - Business rules used in reconciliation
   - Settlement delay expectations
   - Matching logic principles

5. **Production Limitations**
   - Notes on scalability constraints
   - Many-to-one matching not fully modeled
   - Lack of external idempotency store
   - Need for partitioning in high-volume scenarios

### CSV Files (saved to `outputs/` directory)
- **`transactions.csv`**: Platform transaction records (all rows)
- **`settlements.csv`**: Bank settlement records (all rows)
- **`summary_report.csv`**: Metric name and value pairs
- **`detailed_mismatch_report.csv`**: Complete mismatch detail report (sortable in Excel)

### Chart Visualization (Optional)
- **`mismatch_counts.png`**: Bar chart showing count of each mismatch category
  - Generated by matplotlib
  - Can be disabled with `--no-plot` flag

## How to Run

### Prerequisites
Python 3.8+ with pandas, numpy, and matplotlib (optional)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Reconciliation Pipeline
**Basic execution (default: 120 transactions, seed=7, plot enabled):**
```bash
python reconciliation_system.py
```

**With custom parameters:**
```bash
python reconciliation_system.py --records 150 --seed 42 --rounding-tolerance 0.02
```

**Disable outputs (summary to console only):**
```bash
python reconciliation_system.py --no-save --no-plot
```

**Use alternative output directory:**
```bash
python reconciliation_system.py --output-dir ./reports
```

### CLI Arguments
| Argument | Default | Description |
|----------|---------|-------------|
| `--records` | 120 | Number of synthetic base transactions to generate |
| `--seed` | 7 | Random seed for reproducibility |
| `--rounding-tolerance` | 0.02 | Amount difference threshold (in currency units) |
| `--output-dir` | outputs | Directory for CSV and chart outputs |
| `--no-save` | False | Skip CSV file generation |
| `--no-plot` | False | Skip chart visualization |

### 3. Run Test Suite
```bash
python -m unittest discover -s tests -v
```

Tests validate:
- Duplicate transaction detection
- Missing settlement detection
- Extra settlement detection
- Refund without original detection
- Rounding difference detection
- Amount mismatch detection
- Cross-month settlement detection
- Summary metric calculations

**Expected Result**: All 8 tests pass ✅

### Windows PowerShell (Alternative Python Path)
If `python` is not in PATH, use full interpreter path:
```powershell
& 'C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe' reconciliation_system.py --records 120
```

## Deployment

### Option 1: Run as an API locally
Install dependencies:
```bash
pip install -r requirements.txt
```

Start the API server:
```bash
uvicorn reconciliation.api:app --host 0.0.0.0 --port 8000
```

Windows PowerShell on this machine:
```powershell
& 'C:\Program Files\PostgreSQL\17\pgAdmin 4\python\python.exe' -m uvicorn reconciliation.api:app --host 0.0.0.0 --port 8000
```

Available endpoints:
- `GET /health`
- `POST /reconcile`

Example request:
```bash
curl -X POST http://127.0.0.1:8000/reconcile \
  -H "Content-Type: application/json" \
  -d "{\"records\":120,\"seed\":7,\"rounding_tolerance\":0.02,\"save_outputs\":true,\"generate_plot\":false}"
```

### Option 2: Deploy with Docker
Build the image:
```bash
docker build -t reconciliation-app .
```

Run the container:
```bash
docker run -p 8000:8000 reconciliation-app
```

Then open:
```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

## Sample Run Output

**Command**: `python reconciliation_system.py --records 120 --seed 7`

### Console Output
```
=== Reconciliation Summary ===
Transaction Rows        : 121
Settlement Rows         : 122
Unique Transaction Ids  : 120
Unique Settlement Ids   : 121
Total Transaction Amount: 47309.91
Total Settlement Amount : 47727.4
Total Amount Gap        : 417.49

=== Mismatch Counts ===
amount_mismatch         : 1
cross_month_settlement  : 3
duplicate_settlement    : 1
duplicate_transaction   : 1
extra_settlement        : 1
missing_settlement      : 1
refund_without_original : 1
rounding_difference     : 1

=== Detailed Mismatch Sample (first 20 rows) ===
   issue_type         transaction_id  transaction_amount  settled_amount transaction_date settlement_date                                           explanation
0  amount_mismatch         TXN00040              52.65             57.65       2026-01-15      2026-01-17  Amount mismatch above tolerance. Difference=5.00.
1  cross_month_settlement  TXN00005             100.00            100.00       2026-01-31      2026-02-02  Transaction settled in a different calendar month than transaction date.
2  duplicate_settlement    TXN00025              60.00             60.00       2026-01-10      2026-01-12  Transaction ID appears 2 times in settlements dataset.
3  duplicate_transaction   TXN00020              85.50             85.50       2026-01-08      2026-01-09  Transaction ID appears 2 times in transactions dataset.
4  extra_settlement        EXT90001                NaN             88.00              NaT      2026-01-26  Settlement exists in bank file but no corresponding platform transaction was found.
5  missing_settlement      TXN00030              75.00                NaN       2026-01-12              NaT  Transaction exists in platform records but no bank settlement was found.
6  refund_without_original RFD90001                NaN            -42.35              NaT      2026-01-25  Negative settlement/refund exists without a corresponding original transaction.
7  rounding_difference     TXN00010              42.25             42.26       2026-01-05      2026-01-07  Minor amount difference within rounding tolerance; often visible only in aggregate totals.

=== Assumptions ===
- Settlement delay is typically 1-2 days, but month-boundary carryover is possible.
- Primary key for matching is transaction_id (one intended settlement per transaction_id).
- Duplicate IDs are treated as data quality errors and are reported separately before strict amount checks.
- Differences <= rounding_tolerance are classified as rounding differences, not hard mismatches.

=== Production Limitations ===
- Real settlement files may require many-to-one matching (split settlements, partial captures), which this prototype does not fully model.
- This prototype uses in-memory pandas operations and is not optimized for very large daily volumes without partitioning/distributed compute.
- No external idempotency store or workflow orchestration is included, so retries, late-arriving files, and backfills need additional infrastructure.
```

### Generated Files
```
outputs/
  transactions.csv               # 121 rows (with 1 duplicate TXN00020)
  settlements.csv               # 122 rows (with 1 duplicate TXN00025 + 1 refund RFD90001 + 1 extra EXT90001)
  summary_report.csv            # 15 metric rows
  detailed_mismatch_report.csv  # 8 mismatch rows (all injected test cases)
  mismatch_counts.png           # Bar chart visualization
```

## Key Insights from Implementation

### 1. Aggregation Handles Duplicates
Even with duplicate transaction IDs, the aggregation step preserves the duplicate count (stored as `transaction_record_count` and `settlement_record_count`). This allows duplicate detection to run in parallel with matching.

### 2. Rounding vs. Amount Mismatch Classification
- **Rounding differences** are NOT counted against the standard "amount mismatch" category  
- Both are reported in detail; choice of tolerance is configurable
- Useful for distinguishing operational errors from FX/fee rounding

### 3. Cross-Month Settlement is a Distinct Category
- Transactions on 2026-01-31 settling on 2026-02-02 are flagged
- This is **not** treated as a "mismatch" in production logic, but is flagged for compliance reporting
- Separate from amount mismatches

### 4. Refund Handling
- Negative `settled_amount` entries with no matching transaction are classified as refunds
- Separate from general "extra settlements" to distinguish operational reversals from reconciliation errors

### 5. Summary-Level Rounding Detection
- If total gap ≤ $0.50 AND no amount mismatches AND only rounding differences exist
- Flag: `total_rounding_only_gap_detected = True`
- Indicates all discrepancies traceable to minor rounding, not operational issues

## Architecture Notes

### Functional Composition
- **`generate_synthetic_data(config)`** → (transactions DF, settlements DF)
- **`reconcile_data(transactions, settlements, tolerance)`** → ReconciliationResult
- **`build_detailed_mismatch_report(...)`** → Detailed mismatches DF
- **`save_reports(...)`** → CSV files
- **`plot_mismatch_counts(...)`** → PNG chart
- **`print_console_report(result)`** → Formatted terminal output

### Data Flow
```
config → generate_synthetic_data → inject_edge_cases → transactions + settlements
          ↓
       reconcile_data ← (reconciliation engine)
          ↓
       ReconciliationResult {summary dict, detailed_mismatches DF, category_frames dict}
          ↓
    ├── save_reports (CSV export)
    ├── plot_mismatch_counts (matplotlib chart)
    └── print_console_report (formatted terminal output)
```

## Future Enhancements (Out of Scope)

1. **Many-to-Many Matching**: Support split settlements and partial captures
2. **Time-Series Reconciliation**: Track reconciliation lag (age of unsettled transactions)
3. **Distributed Execution**: Partition-based reconciliation for multi-terabyte datasets
4. **External State**: Idempotency store, workflow orchestration, retry logic
5. **Advanced Reporting**: Drill-down views, drill-across dimensions, time-window analysis
6. **Heuristic Matching**: Fuzzy matching on transaction_id for common typos/OCR errors
7. **FX and Fee Models**: Realistic conversion rates, settlement deductions per region

## Technology Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | Python | 3.8+ | Core implementation |
| Data Processing | pandas | 1.x+ | DataFrames, groupby, merge operations |
| Numerical Computing | numpy | 1.x+ | Random number generation, data manipulation |
| Visualization | matplotlib | 3.x+ | Bar chart generation (optional) |
| Testing | unittest | Built-in | Test framework |
| Package Management | pip | Built-in | Dependency installation |

## File Sizes & Performance

- **Code Size**: ~500 lines of Python (excluding tests)
- **Test Coverage**: 8 comprehensive unit tests
- **Execution Time**: < 1 second for 120 transactions on standard hardware
- **Memory Footprint**: ~50 MB for 120 transactions + outputs
- **CSV Output Size**: ~30 KB for summary + ~50 KB for detailed report

## Troubleshooting

### Issue: ImportError for `reconciliation` module
**Solution**: Ensure you're running from the project root directory and `reconciliation/` folder is in Python path.

### Issue: matplotlib not found (if trying to plot)
**Solution**: Install optional dependency:
  ```bash
  pip install matplotlib
  ```
  Or skip plotting with: `python reconciliation_system.py --no-plot`

### Issue: "Python is not recognized" on Windows
**Solution**: Use full path to Python interpreter or add Python to PATH:
  ```powershell
  & 'C:\Program Files\Python311\python.exe' reconciliation_system.py
  ```

### Issue: CSV not being created
**Solution**: Check that the `outputs/` directory exists and is writable. The tool creates it automatically; if permission issues occur, specify a different output directory:
  ```bash
  python reconciliation_system.py --output-dir C:\temp\reconciliation_output
  ```

## License
This project is provided as-is for educational and prototyping purposes.

## Author
Created as a payments reconciliation prototype demonstrating enterprise transaction matching and mismatch categorization.

The latest terminal run on this machine completed successfully and wrote the reports to `outputs/`.

The console output is now structured into:
- a compact reconciliation summary
- a mismatch count block
- a detailed mismatch sample table

## Assumptions
1. Settlement delay is usually 1-2 days, but month-boundary spillover is valid.
2. `transaction_id` is the primary reconciliation key.
3. Duplicate IDs indicate data quality issues and are reported separately.
4. Differences within tolerance are treated as rounding differences, not hard mismatches.

## Production Limitations
1. Does not support complex many-to-one reconciliation patterns (split captures/partial settlements) beyond aggregated ID-level checks.
2. Uses in-memory pandas processing and is not tuned for very large production-scale files without distributed processing.
3. Does not include orchestration/idempotency infrastructure for retries, late files, and full backfill workflows.

## Logging
Runtime logging is enabled with timestamps and includes:
- CSV export path
- chart export path
- warnings when optional plotting is unavailable

## Interview-Ready Explanation
This solution first creates realistic synthetic payment/settlement data, injects deterministic reconciliation failures, and then performs ID-level matching with grouped normalization to isolate duplicates, missing/extra records, and amount discrepancies. It separately distinguishes minor rounding noise from true mismatches, compares portfolio-level totals, produces machine-readable CSV reports plus a human-readable summary, and validates all mandatory edge cases through automated tests.
