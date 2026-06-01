/**
 * Sheets.gs — Pull ERP data into named sheets
 *
 * Each function fetches data from the backend API and writes it to a
 * dedicated sheet tab, replacing old data. A timestamp header is added.
 */

// ─── Shared helpers ──────────────────────────────────────────────────────────

/**
 * Get or create a sheet with the given name, clear it, and return it.
 */
function getOrCreateSheet_(name) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  } else {
    sheet.clearContents();
  }
  return sheet;
}

/**
 * Write a 2D array to a sheet starting at row 1, col 1.
 * Adds a "Last updated" timestamp in the row after the data.
 */
function writeTable_(sheet, headers, rows) {
  if (rows.length === 0) {
    sheet.getRange(1, 1).setValue('No data returned for this period.');
    return;
  }
  var data = [headers].concat(rows);
  sheet.getRange(1, 1, data.length, headers.length).setValues(data);

  // Format header row
  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setFontWeight('bold').setBackground('#1e293b').setFontColor('#ffffff');

  // Auto-resize columns
  for (var i = 1; i <= headers.length; i++) {
    sheet.autoResizeColumn(i);
  }

  // Timestamp
  sheet.getRange(data.length + 2, 1).setValue('Last updated: ' + new Date().toLocaleString('en-IN'));
}

/**
 * Show a toast notification on the spreadsheet.
 */
function toast_(msg, title) {
  SpreadsheetApp.getActiveSpreadsheet().toast(msg, title || 'SmarterP', 4);
}


// ─── Dashboard KPIs ──────────────────────────────────────────────────────────

function pullDashboard(period) {
  period = period || DEFAULT_PERIOD;
  toast_('Fetching dashboard KPIs…', 'SmarterP');

  var data = apiGet_('/analytics/dashboard?period=' + period);
  var summary = data.summary || {};
  var sheet = getOrCreateSheet_('Dashboard KPIs');

  var rows = [
    ['Period',        data.period_label || period],
    ['Date Range',    (data.date_range && data.date_range.start) + ' → ' + (data.date_range && data.date_range.end)],
    [''],
    ['Metric',        'Current',                                     'Last Year',                    'Growth %'],
    ['Revenue (₹)',   summary.mtd_sales || 0,                        summary.ly_sales || 0,           summary.sales_growth_pct != null ? summary.sales_growth_pct + '%' : '—'],
    ['Bills',         summary.bills || 0,                            '',                              ''],
    ['Quantity',      summary.quantity || 0,                         '',                              ''],
    ['Customers',     summary.customers != null ? summary.customers : '—', '',                       ''],
  ];

  sheet.clearContents();
  rows.forEach(function(row, i) {
    if (row.length > 0 && row[0] !== '') {
      sheet.getRange(i + 1, 1, 1, row.length).setValues([row]);
    }
  });

  // Bold the "Metric" header row (row 4)
  sheet.getRange(4, 1, 1, 4).setFontWeight('bold').setBackground('#1e293b').setFontColor('#ffffff');
  sheet.autoResizeColumn(1); sheet.autoResizeColumn(2); sheet.autoResizeColumn(3); sheet.autoResizeColumn(4);
  sheet.getRange(rows.length + 2, 1).setValue('Last updated: ' + new Date().toLocaleString('en-IN'));

  toast_('Dashboard KPIs updated (' + period.toUpperCase() + ')', 'SmarterP ✓');
}


// ─── Transactions ─────────────────────────────────────────────────────────────

function pullTransactions(period) {
  period = period || DEFAULT_PERIOD;
  toast_('Fetching transactions…', 'SmarterP');

  // Fetch up to 500 rows (paginated if needed)
  var data = apiGet_('/analytics/transactions?period=' + period + '&page=1&page_size=200');
  var records = data.transactions || data.records || data.data || [];

  var sheet = getOrCreateSheet_('Transactions');

  if (records.length === 0) {
    sheet.getRange(1,1).setValue('No transactions found for period: ' + period);
    toast_('No data.', 'SmarterP');
    return;
  }

  // Dynamic headers from first record
  var headers = Object.keys(records[0]);
  var rows = records.map(function(r) {
    return headers.map(function(h) { return r[h] != null ? r[h] : ''; });
  });

  writeTable_(sheet, headers, rows);
  toast_(records.length + ' transactions loaded (' + period.toUpperCase() + ')', 'SmarterP ✓');
}


// ─── Branches ────────────────────────────────────────────────────────────────

function pullBranches(period) {
  period = period || DEFAULT_PERIOD;
  toast_('Fetching branch data…', 'SmarterP');

  var data = apiGet_('/analytics/bundle?period=' + period + '&top_n=100');
  var branches = data.branches || [];

  var sheet = getOrCreateSheet_('Branch Intel');

  if (branches.length === 0) {
    sheet.getRange(1,1).setValue('No branch data found for period: ' + period);
    toast_('No data.', 'SmarterP');
    return;
  }

  var headers = ['Branch', 'Revenue (₹)', 'Growth %', 'Bills', 'Quantity'];
  var rows = branches.map(function(b) {
    return [
      b.name        || b.branch || '',
      b.revenue     || 0,
      b.growth != null ? b.growth : '—',
      b.bills       || 0,
      b.quantity    || 0,
    ];
  });

  writeTable_(sheet, headers, rows);
  toast_(branches.length + ' branches loaded (' + period.toUpperCase() + ')', 'SmarterP ✓');
}


// ─── Products / Categories ───────────────────────────────────────────────────

function pullProducts(period) {
  period = period || DEFAULT_PERIOD;
  toast_('Fetching product/category data…', 'SmarterP');

  // Try the dedicated products endpoint first, fall back to bundle categories
  var categories = [];
  try {
    var data = apiGet_('/analytics/bundle?period=' + period + '&top_n=200');
    categories = data.categories || [];
  } catch(e) {
    toast_('Products fetch failed: ' + e.message, 'SmarterP');
    return;
  }

  var sheet = getOrCreateSheet_('Products');

  if (categories.length === 0) {
    sheet.getRange(1,1).setValue('No product data found for period: ' + period);
    return;
  }

  var headers = ['Category', 'Revenue (₹)', 'Share %', 'Bills', 'Quantity'];
  var rows = categories.map(function(c) {
    return [
      c.name        || c.category || '',
      c.revenue     || 0,
      c.percentage  != null ? (c.percentage + '%') : '—',
      c.bills       || 0,
      c.quantity    || 0,
    ];
  });

  writeTable_(sheet, headers, rows);
  toast_(categories.length + ' categories loaded (' + period.toUpperCase() + ')', 'SmarterP ✓');
}


// ─── Data Explorer (all views raw) ───────────────────────────────────────────

function pullDataExplorer(viewKey, period) {
  viewKey = viewKey || 'sales';
  period  = period  || DEFAULT_PERIOD;
  toast_('Fetching ' + viewKey + ' data…', 'SmarterP');

  // UI keys → backend view catalog keys (see backend/data/view_catalog.json)
  var catalogKey = {
    sales: 'sales_lines',
    branches: 'sales_app',
    categories: 'category_master',
    salespersons: 'salesperson_lines',
    customers: 'ai_customer',
    stock: 'stock',
    invoices: 'sales_billcount',
    suppliers: 'vendor_master',
  }[viewKey] || viewKey;

  var path = '/analytics/views/query?view=' + encodeURIComponent(catalogKey)
    + '&page=1&page_size=500';
  var data;
  try {
    data = apiGet_(path);
  } catch(e) {
    toast_('Data Explorer error: ' + e.message, 'SmarterP');
    return;
  }

  var records = data.rows || data.records || data.data || [];
  var sheetName = 'DE: ' + viewKey;
  var sheet = getOrCreateSheet_(sheetName);

  if (records.length === 0) {
    sheet.getRange(1,1).setValue('No data for view: ' + viewKey + ', period: ' + period);
    return;
  }

  var headers = Object.keys(records[0]);
  var rows = records.map(function(r) {
    return headers.map(function(h) { return r[h] != null ? r[h] : ''; });
  });

  writeTable_(sheet, headers, rows);
  toast_(records.length + ' rows loaded into "' + sheetName + '"', 'SmarterP ✓');
}


// ─── Salesperson leaderboard ─────────────────────────────────────────────────

function pullSalespersons(period) {
  period = period || DEFAULT_PERIOD;
  toast_('Fetching salesperson data…', 'SmarterP');

  var data;
  try {
    data = apiGet_('/analytics/salespersons?period=' + period + '&top_n=50');
  } catch(e) {
    // fallback: not all backends expose this endpoint
    toast_('Salesperson endpoint not available: ' + e.message, 'SmarterP');
    return;
  }

  var records = data.salespersons || data.records || [];
  var sheet   = getOrCreateSheet_('Salespersons');

  if (records.length === 0) {
    sheet.getRange(1,1).setValue('No salesperson data for period: ' + period);
    return;
  }

  var headers = Object.keys(records[0]);
  var rows    = records.map(function(r) {
    return headers.map(function(h) { return r[h] != null ? r[h] : ''; });
  });

  writeTable_(sheet, headers, rows);
  toast_(records.length + ' salespersons loaded (' + period.toUpperCase() + ')', 'SmarterP ✓');
}


// ─── Refresh ALL sheets ───────────────────────────────────────────────────────

function refreshAllSheets(period) {
  period = period || DEFAULT_PERIOD;
  try {
    pullDashboard(period);
    pullBranches(period);
    pullProducts(period);
    pullTransactions(period);
    toast_('All sheets refreshed (' + period.toUpperCase() + ')', 'SmarterP ✓');
  } catch(e) {
    SpreadsheetApp.getUi().alert('Refresh failed: ' + e.message);
  }
}
