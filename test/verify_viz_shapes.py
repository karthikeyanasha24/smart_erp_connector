"""Smoke-test NLQ visualization builder against representative FAQ result shapes."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIZ = ROOT / "src" / "lib" / "nlqVisualization.ts"

MOCK_CASES = {
    "five_year_sales_dept_category": [
        {"MonthStart": "2021-07-01", "Department": "SA", "Category": "PLN", "TotalSales": 216336},
        {"MonthStart": "2021-07-01", "Department": "SA", "Category": "WOV", "TotalSales": 78200},
        {"MonthStart": "2021-08-01", "Department": "SA", "Category": "WOV", "TotalSales": 139410},
    ],
    "store_mtd_sales_customers_ats": [
        {"Store": "BR1", "MTDSales": 100000, "UniqueInvoices": 50, "ATS": 2000, "UniqueCustomers": 40},
        {"Store": "BR2", "MTDSales": 80000, "UniqueInvoices": 45, "ATS": 1777, "UniqueCustomers": 35},
    ],
    "monthly_sales_since_apr_2024": [
        {"MonthStart": "2024-04-01", "MonthLabel": "April 2024", "TotalSales": 500000},
        {"MonthStart": "2024-05-01", "MonthLabel": "May 2024", "TotalSales": 520000},
    ],
    "ytd_growth_vs_last_year": [
        {"PeriodLabel": "CurrentYTD", "TotalSales": 1000000},
        {"PeriodLabel": "LastYearYTD", "TotalSales": 900000},
    ],
    "average_sales_mtd_level": [
        {"MTDTotalSales": 500000, "TradingDays": 20, "AvgDailySales": 25000},
    ],
}


def main() -> int:
    runner = ROOT / "test" / "_run_viz_check.mjs"
    runner.write_text(
        """
import { buildNLQVisualization } from '../src/lib/nlqVisualization.ts';

const cases = JSON.parse(process.argv[1]);
let failed = 0;

for (const [name, records] of Object.entries(cases)) {
  const viz = buildNLQVisualization(records);
  const ok =
    (records.length === 1 && viz.kpiCards.length > 0) ||
    (records.length > 1 && (viz.chartData.length > 0 || viz.table));
  if (!ok) {
    console.log('FAIL', name, JSON.stringify(viz));
    failed += 1;
  } else {
    console.log('OK  ', name, viz.chartType, 'points=' + viz.chartData.length);
  }
}

// Five-year must aggregate to one point per month, not one per row
const fy = cases.five_year_sales_dept_category;
const fyViz = buildNLQVisualization(fy);
if (fyViz.chartData.length !== 2) {
  console.log('FAIL five_year aggregation expected 2 months got', fyViz.chartData.length);
  failed += 1;
}

process.exit(failed ? 1 : 0);
""",
        encoding="utf-8",
    )

    payload = json.dumps(MOCK_CASES)
    for cmd in (["npx", "tsx", str(runner), payload], ["node", "--import", "tsx", str(runner), payload]):
        try:
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
            print(proc.stdout)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
            return proc.returncode
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            print("Visualization check timed out", file=sys.stderr)
            return 1

    print("Could not run tsx — skipping visualization smoke test", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
