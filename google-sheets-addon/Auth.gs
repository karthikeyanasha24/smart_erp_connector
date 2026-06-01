/**
 * Auth.gs — JWT login + token caching for SmarterP API calls
 */

var TOKEN_CACHE_MINUTES = 60; // re-use token for up to 60 min

/**
 * Returns a valid JWT bearer token.
 * Logs in automatically if none is cached or it has expired.
 */
function getToken_() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get('smarterp_token');
  if (cached) return cached;

  var cfg = getConfig_();
  if (!cfg.url)   throw new Error('SmarterP URL not configured. Use SmarterP → Settings.');
  if (!cfg.email) throw new Error('SmarterP email not configured. Use SmarterP → Settings.');

  var resp = UrlFetchApp.fetch(cfg.url + '/auth/login', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ email: cfg.email, password: cfg.pass }),
    muteHttpExceptions: true,
  });

  if (resp.getResponseCode() !== 200) {
    throw new Error('Login failed (' + resp.getResponseCode() + '): ' + resp.getContentText().slice(0, 200));
  }

  var data = JSON.parse(resp.getContentText());
  var token = data.token || data.access_token || data.jwt;
  if (!token) throw new Error('Login response did not contain a token: ' + resp.getContentText().slice(0, 200));

  // Cache for TOKEN_CACHE_MINUTES - 2 min buffer
  cache.put('smarterp_token', token, (TOKEN_CACHE_MINUTES - 2) * 60);
  return token;
}

/**
 * Make an authenticated GET request to the backend API.
 * @param {string} path  e.g. '/analytics/dashboard?period=mtd'
 * @returns {Object} parsed JSON response
 */
function apiGet_(path) {
  var cfg = getConfig_();
  var token = getToken_();
  var url = cfg.url + path;

  var resp = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: { Authorization: 'Bearer ' + token },
    muteHttpExceptions: true,
  });

  if (resp.getResponseCode() === 401) {
    // Token expired — clear cache and retry once
    CacheService.getScriptCache().remove('smarterp_token');
    token = getToken_();
    resp = UrlFetchApp.fetch(url, {
      method: 'get',
      headers: { Authorization: 'Bearer ' + token },
      muteHttpExceptions: true,
    });
  }

  if (resp.getResponseCode() !== 200) {
    throw new Error('API error ' + resp.getResponseCode() + ' for ' + path + ': ' + resp.getContentText().slice(0, 300));
  }

  return JSON.parse(resp.getContentText());
}

/**
 * Make an authenticated POST request to the backend API.
 */
function apiPost_(path, body) {
  var cfg = getConfig_();
  var token = getToken_();

  var resp = UrlFetchApp.fetch(cfg.url + path, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token },
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  });

  if (resp.getResponseCode() === 401) {
    CacheService.getScriptCache().remove('smarterp_token');
    token = getToken_();
    resp = UrlFetchApp.fetch(cfg.url + path, {
      method: 'post',
      contentType: 'application/json',
      headers: { Authorization: 'Bearer ' + token },
      payload: JSON.stringify(body),
      muteHttpExceptions: true,
    });
  }

  if (resp.getResponseCode() !== 200) {
    throw new Error('API error ' + resp.getResponseCode() + ': ' + resp.getContentText().slice(0, 300));
  }

  return JSON.parse(resp.getContentText());
}
