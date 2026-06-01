/**
 * Code.gs — SmarterP ERP Connector for Google Sheets
 *
 * Builds the "SmarterP" menu and wires up all actions.
 * Data logic lives in Sheets.gs  |  AI chat in Sidebar.html
 * Auth (JWT) lives in Auth.gs    |  Config in Config.gs
 */

// ─── Menu ────────────────────────────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🔗 SmarterP')
    .addItem('📱 Open SmarterP Sidebar',  'openAISidebar')
    .addSeparator()
    .addSubMenu(
      SpreadsheetApp.getUi().createMenu('📥 Pull Data — MTD')
        .addItem('📊 Dashboard KPIs',       'pullDashboardMtd')
        .addItem('🏪 Branch Intel',          'pullBranchesMtd')
        .addItem('📦 Products / Categories', 'pullProductsMtd')
        .addItem('🧾 Transactions',          'pullTransactionsMtd')
        .addItem('👤 Salespersons',          'pullSalespersonsMtd')
        .addItem('🔄 Refresh ALL Sheets',    'refreshAllMtd')
    )
    .addSubMenu(
      SpreadsheetApp.getUi().createMenu('📥 Pull Data — Today')
        .addItem('📊 Dashboard KPIs',       'pullDashboardToday')
        .addItem('🏪 Branch Intel',          'pullBranchesToday')
        .addItem('🧾 Transactions',          'pullTransactionsToday')
    )
    .addSubMenu(
      SpreadsheetApp.getUi().createMenu('📥 Pull Data — YTD')
        .addItem('📊 Dashboard KPIs',       'pullDashboardYtd')
        .addItem('🏪 Branch Intel',          'pullBranchesYtd')
        .addItem('📦 Products / Categories', 'pullProductsYtd')
    )
    .addSeparator()
    .addItem('🗄️  Data Explorer…',         'openDataExplorer')
    .addSeparator()
    .addItem('⚙️  Settings / Connect',      'showSetupDialog')
    .addItem('❓ Help',                      'showHelp')
    .addToUi();
}

// ─── MTD shortcuts ───────────────────────────────────────────────────────────
function pullDashboardMtd()    { pullDashboard('mtd'); }
function pullBranchesMtd()     { pullBranches('mtd'); }
function pullProductsMtd()     { pullProducts('mtd'); }
function pullTransactionsMtd() { pullTransactions('mtd'); }
function pullSalespersonsMtd() { pullSalespersons('mtd'); }
function refreshAllMtd()       { refreshAllSheets('mtd'); }

// ─── Today shortcuts ─────────────────────────────────────────────────────────
function pullDashboardToday()    { pullDashboard('today'); }
function pullBranchesToday()     { pullBranches('today'); }
function pullTransactionsToday() { pullTransactions('today'); }

// ─── YTD shortcuts ───────────────────────────────────────────────────────────
function pullDashboardYtd()  { pullDashboard('ytd'); }
function pullBranchesYtd()   { pullBranches('ytd'); }
function pullProductsYtd()   { pullProducts('ytd'); }

// ─── Data Explorer dialog ────────────────────────────────────────────────────

function openDataExplorer() {
  var html = HtmlService.createHtmlOutputFromFile('DataExplorer')
    .setWidth(380).setHeight(300)
    .setTitle('Data Explorer');
  SpreadsheetApp.getUi().showModalDialog(html, 'SmarterP — Data Explorer');
}

/** Called from DataExplorer.html dialog */
function runDataExplorer(viewKey, period) {
  try {
    pullDataExplorer(viewKey, period);
    return { ok: true };
  } catch(e) {
    return { ok: false, error: e.message };
  }
}

// ─── AI Sidebar ──────────────────────────────────────────────────────────────

function openAISidebar() {
  var html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('SmarterP');
  SpreadsheetApp.getUi().showSidebar(html);
}

/** Pull ERP data from sidebar (action + period). */
function sidebarPullData(action, period) {
  period = period || DEFAULT_PERIOD;
  try {
    switch (action) {
      case 'dashboard':     pullDashboard(period); break;
      case 'branches':      pullBranches(period); break;
      case 'products':      pullProducts(period); break;
      case 'transactions':  pullTransactions(period); break;
      case 'salespersons':  pullSalespersons(period); break;
      case 'refresh_all':   refreshAllSheets(period); break;
      default:
        return { ok: false, error: 'Unknown action: ' + action };
    }
    return { ok: true, action: action, period: period };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

/** Data Explorer pull from sidebar. */
function sidebarDataExplorer(viewKey, period) {
  try {
    pullDataExplorer(viewKey, period);
    return { ok: true, view: viewKey, period: period };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

/**
 * Called from Sidebar.html via google.script.run
 * Sends a question to the backend NLQ endpoint and returns the answer.
 */
function formatAiAnswer_(result) {
  if (result.summary) return result.summary;
  if (result.description) return result.description;
  if (result.insights && result.insights.length) {
    return result.insights.map(function(i) {
      return i.text || i.message || i.title || '';
    }).filter(String).join('\n\n');
  }
  if (result.answer) return result.answer;
  if (result.response) return result.response;
  if (result.message) return result.message;
  return '(No summary returned)';
}

function askAI(question, period) {
  try {
    period = period || 'mtd';
    var result = apiPost_('/ai/query', { query: question, period: period });

    return {
      ok:          true,
      answer:      formatAiAnswer_(result),
      sql:         result.sql          || null,
      rows:        result.records      || result.data     || null,
      intent:      result.intent       || null,
      period:      result.period_label || result.period   || period,
    };
  } catch(e) {
    return { ok: false, error: e.message };
  }
}

/**
 * Called from Sidebar.html — dumps AI query results into a new sheet.
 */
function dumpResultsToSheet(rows, question) {
  if (!rows || rows.length === 0) return { ok: false, error: 'No rows to dump.' };
  try {
    var sheetName = 'AI: ' + question.slice(0, 30).replace(/[^a-zA-Z0-9 ]/g, '');
    var sheet = getOrCreateSheet_(sheetName);
    var headers = Object.keys(rows[0]);
    var data = rows.map(function(r) {
      return headers.map(function(h) { return r[h] != null ? r[h] : ''; });
    });
    writeTable_(sheet, headers, data);
    SpreadsheetApp.getActiveSpreadsheet().setActiveSheet(sheet);
    return { ok: true, sheet: sheetName, count: rows.length };
  } catch(e) {
    return { ok: false, error: e.message };
  }
}

// ─── Help ─────────────────────────────────────────────────────────────────────

function showHelp() {
  var msg =
    'SmarterP ERP Connector — Help\n\n' +
    '1. First time? Go to SmarterP → Settings and enter your backend URL + login.\n\n' +
    '2. Pull Data menus fetch live ERP data into named sheet tabs.\n\n' +
    '3. AI Query opens a chat sidebar — ask any business question in plain English.\n' +
    '   Results can be dumped into a new sheet with one click.\n\n' +
    '4. Data Explorer lets you pull any raw ERP view into a sheet.\n\n' +
    'Periods: MTD = month-to-date | Today = today only | YTD = year-to-date\n\n' +
    'Backend URL format: https://your-app.onrender.com (no trailing slash)';
  SpreadsheetApp.getUi().alert('Help', msg, SpreadsheetApp.getUi().ButtonSet.OK);
}
