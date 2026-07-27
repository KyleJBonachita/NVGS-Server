/**
 * NVGS local-server login bridge.
 *
 * Add this file beside Code.gs in the standalone NVGS Login Bridge project.
 * It issues a 60-second HMAC-signed assertion for Google's verified active
 * user. Never use Session.getEffectiveUser() as a fallback here.
 */

function checkNvgsBridgeConfiguration() {
  var properties = PropertiesService.getScriptProperties();
  var secret = String(properties.getProperty('NVGS_BRIDGE_SECRET') || '');
  var callbackUrl = String(
    properties.getProperty('NVGS_BRIDGE_CALLBACK_URL') || ''
  );
  var issuerProperty = String(
    properties.getProperty('NVGS_BRIDGE_ISSUER') || ''
  );
  var audienceProperty = String(
    properties.getProperty('NVGS_BRIDGE_AUDIENCE') || ''
  );
  var domainProperty = String(
    properties.getProperty('NVGS_BRIDGE_ALLOWED_DOMAIN') || ''
  ).toLowerCase();
  var email = String(Session.getActiveUser().getEmail() || '')
    .trim()
    .toLowerCase();
  var emailDomain = email.indexOf('@') === -1 ? '' : email.split('@').pop();

  var result = {
    secretConfigured: secret.length >= 32,
    callbackConfigured:
      /^https:\/\/[^?#]+\/api\/auth\/appscript\/consume\/$/.test(callbackUrl),
    issuerConfigured: issuerProperty === 'nvgs-appscript',
    audienceConfigured: audienceProperty === 'nvgs-server',
    allowedDomainConfigured: domainProperty === 'nvidia.com',
    activeUserEmailAvailable: Boolean(email),
    activeUserDomainMatches: emailDomain === domainProperty,
  };
  console.log(JSON.stringify(result));
  return result;
}

function maybeHandleNvgsLogin_(e) {
  var parameters = (e && e.parameter) || {};
  if (parameters.nvgs_action !== 'login') return null;

  var state = String(parameters.state || '');
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(state)) {
    return nvgsBridgeErrorPage_('The login request state was invalid.');
  }

  var properties = PropertiesService.getScriptProperties();
  var secret = String(properties.getProperty('NVGS_BRIDGE_SECRET') || '');
  var callbackUrl = String(
    properties.getProperty('NVGS_BRIDGE_CALLBACK_URL') || ''
  );
  var issuer = String(
    properties.getProperty('NVGS_BRIDGE_ISSUER') || 'nvgs-appscript'
  );
  var audience = String(
    properties.getProperty('NVGS_BRIDGE_AUDIENCE') || 'nvgs-server'
  );
  var allowedDomain = String(
    properties.getProperty('NVGS_BRIDGE_ALLOWED_DOMAIN') || 'nvidia.com'
  ).toLowerCase();

  if (secret.length < 32) {
    return nvgsBridgeErrorPage_('The bridge secret is not configured.');
  }
  if (
    !/^https:\/\/[^?#]+\/api\/auth\/appscript\/consume\/$/.test(callbackUrl)
  ) {
    return nvgsBridgeErrorPage_('The bridge callback URL is invalid.');
  }

  var email = String(Session.getActiveUser().getEmail() || '')
    .trim()
    .toLowerCase();
  if (!email) {
    return nvgsBridgeErrorPage_(
      'Google did not provide an active-user email. Check the web app deployment.'
    );
  }
  var domain = email.indexOf('@') === -1 ? '' : email.split('@').pop();
  if (domain !== allowedDomain) {
    return nvgsBridgeErrorPage_('This Google account is not in the allowed domain.');
  }

  var issuedAt = Math.floor(Date.now() / 1000);
  var header = {
    alg: 'HS256',
    typ: 'JWT',
  };
  var payload = {
    iss: issuer,
    aud: audience,
    sub: email,
    email: email,
    state: state,
    nonce: Utilities.getUuid(),
    iat: issuedAt,
    exp: issuedAt + 60,
  };

  var headerPart = nvgsBridgeBase64Url_(JSON.stringify(header));
  var payloadPart = nvgsBridgeBase64Url_(JSON.stringify(payload));
  var signingInput = headerPart + '.' + payloadPart;
  var signature = Utilities.computeHmacSha256Signature(
    signingInput,
    secret,
    Utilities.Charset.UTF_8
  );
  var signaturePart = Utilities.base64EncodeWebSafe(signature)
    .replace(/=+$/g, '');
  var token = signingInput + '.' + signaturePart;
  var continueUrl = callbackUrl + '#token=' + encodeURIComponent(token);

  var html = [
    '<!doctype html>',
    '<html><head>',
    '<base target="_top">',
    '<meta charset="utf-8">',
    '<meta name="referrer" content="no-referrer">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>Continue to NVGS</title>',
    '<style>',
    'body{background:#111827;color:#f9fafb;font-family:Arial,sans-serif;',
    'display:flex;align-items:center;justify-content:center;min-height:100vh;',
    'margin:0}main{text-align:center;max-width:38rem;padding:2rem}',
    'a{background:#76b900;color:#071000;display:inline-block;font-weight:700;',
    'padding:1rem 1.5rem;border-radius:.5rem;text-decoration:none}',
    '</style></head><body><main>',
    '<h1>NVIDIA account verified</h1>',
    '<p>' + nvgsBridgeEscapeHtml_(email) + '</p>',
    '<p>Continue within 60 seconds to sign in to the local NVGS server.</p>',
    '<a target="_top" rel="noreferrer" href="',
    nvgsBridgeEscapeHtml_(continueUrl),
    '">Continue to NVGS</a>',
    '</main></body></html>',
  ].join('');

  return HtmlService.createHtmlOutput(html)
    .setTitle('Continue to NVGS')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT);
}

function nvgsBridgeBase64Url_(value) {
  return Utilities.base64EncodeWebSafe(value, Utilities.Charset.UTF_8)
    .replace(/=+$/g, '');
}

function nvgsBridgeEscapeHtml_(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function nvgsBridgeErrorPage_(message) {
  var html = [
    '<!doctype html><html><head>',
    '<meta charset="utf-8">',
    '<meta name="referrer" content="no-referrer">',
    '<title>NVGS login failed</title>',
    '</head><body>',
    '<h1>NVGS login failed</h1><p>',
    nvgsBridgeEscapeHtml_(message),
    '</p></body></html>',
  ].join('');
  return HtmlService.createHtmlOutput(html).setTitle('NVGS login failed');
}
