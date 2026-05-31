
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
