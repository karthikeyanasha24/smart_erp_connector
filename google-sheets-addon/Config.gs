/**
 * Config.gs — Central configuration for SmarterP ERP Connector
 *
 * HOW TO SET YOUR BACKEND URL:
 *   In the Apps Script editor: File → Project Settings → Script Properties
 *   Add:  SMARTERP_URL   →  https://your-backend.onrender.com
 *         SMARTERP_EMAIL →  your-login@email.com
 *         SMARTERP_PASS  →  your-password
 *
 * OR run Config.showSetupDialog() from the SmarterP menu the first time.
 */

// ─── Script Property Keys ────────────────────────────────────────────────────
var PROP_URL   = 'SMARTERP_URL';
var PROP_EMAIL = 'SMARTERP_EMAIL';
var PROP_PASS  = 'SMARTERP_PASS';
var PROP_TOKEN = 'SMARTERP_JWT';

// ─── Defaults (override via Script Properties) ───────────────────────────────
var DEFAULT_PERIOD = 'mtd';

function getConfig_() {
  var props = PropertiesService.getScriptProperties();
  return {
    url:   (props.getProperty(PROP_URL)   || '').replace(/\/$/, ''),
    email: props.getProperty(PROP_EMAIL)  || '',
    pass:  props.getProperty(PROP_PASS)   || '',
  };
}

function saveConfig_(url, email, pass) {
  var props = PropertiesService.getScriptProperties();
  props.setProperty(PROP_URL,   url.replace(/\/$/, ''));
  props.setProperty(PROP_EMAIL, email);
  props.setProperty(PROP_PASS,  pass);
  // Clear cached token so it re-logs in with new credentials
  props.deleteProperty(PROP_TOKEN);
}

/** Show the first-time setup dialog */
/** Returns config (without password) to the Setup dialog */
function getConfig_exposed() {
  var cfg = getConfig_();
  return { url: cfg.url, email: cfg.email };
}

/**
 * Public wrappers for Setup.html.
 * Functions ending in "_" are private and cannot be called via google.script.run.
 */
function testConnection(url, email, pass) {
  return testConnection_(url, email, pass);
}

function saveAndVerify(url, email, pass) {
  return saveAndVerify_(url, email, pass);
}

/** Test connection — used by Setup.html "Test" button */
function testConnection_(url, email, pass) {
  try {
    var resp = UrlFetchApp.fetch(url.replace(/\/$/, '') + '/auth/login', {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify({ email: email, password: pass }),
      muteHttpExceptions: true,
    });
    if (resp.getResponseCode() !== 200) {
      return { ok: false, error: 'HTTP ' + resp.getResponseCode() + ': ' + resp.getContentText().slice(0, 150) };
    }
    var data = JSON.parse(resp.getContentText());
    var token = data.token || data.access_token || data.jwt;
    if (!token) return { ok: false, error: 'No token in response: ' + resp.getContentText().slice(0, 100) };
    return { ok: true };
  } catch(e) {
    return { ok: false, error: e.message };
  }
}

/** Save config and verify by logging in — used by Setup.html "Save" button */
function saveAndVerify_(url, email, pass) {
  var test = testConnection_(url, email, pass);
  if (!test.ok) return test;
  saveConfig_(url, email, pass);
  return { ok: true };
}

/** Show the first-time setup dialog */
function showSetupDialog() {
  var html = HtmlService.createHtmlOutputFromFile('Setup')
    .setWidth(420).setHeight(380)
    .setTitle('SmarterP — Connect to ERP');
  SpreadsheetApp.getUi().showModalDialog(html, 'SmarterP Setup');
}
