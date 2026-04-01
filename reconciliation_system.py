import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reconciliation import (
    AMOUNT_MISMATCH_ID,
    DUPLICATE_SETTLEMENT_ID,
    DUPLICATE_TXN_ID,
    EXTRA_SETTLEMENT_ID,
    MISSING_SETTLEMENT_ID,
    NEXT_MONTH_ID,
    REFUND_ONLY_ID,
    ROUNDING_DIFF_ID,
    ReconciliationConfig,
    ReconciliationResult,
    app,
    assumptions,
    build_detailed_mismatch_report,
    generate_synthetic_data,
    production_limitations,
    reconcile_data,
    run_pipeline,
)
from reconciliation.cli import main

__all__ = [
    "AMOUNT_MISMATCH_ID",
    "DUPLICATE_SETTLEMENT_ID",
    "DUPLICATE_TXN_ID",
    "EXTRA_SETTLEMENT_ID",
    "MISSING_SETTLEMENT_ID",
    "NEXT_MONTH_ID",
    "REFUND_ONLY_ID",
    "ROUNDING_DIFF_ID",
    "ReconciliationConfig",
    "ReconciliationResult",
    "app",
    "generate_synthetic_data",
    "reconcile_data",
    "build_detailed_mismatch_report",
    "assumptions",
    "production_limitations",
    "run_pipeline",
    "main",
]

if __name__ == "__main__":
    main()
