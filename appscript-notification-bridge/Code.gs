/**
 * Standalone NVGS notification relay.
 *
 * Django sends an HMAC-signed ticket event to doPost. The recipient and sender
 * alias come only from Script Properties, never from the request. Deploy this
 * separately from the NVGS login bridge.
 */

var NVGS_NOTIFICATION_EVENTS_ = {
  TICKET_CREATED: true,
  TICKET_ASSIGNED: true,
  TICKET_STATUS_CHANGED: true,
  TICKET_RESOLVED: true,
  TICKET_ESCALATED: true,
  TICKET_REOPENED: true,
  TICKET_COMMENT_ADDED: true,
};

function doGet() {
  return nvgsNotificationJson_({
    ok: true,
    service: 'NVGS Apps Script Notification Bridge',
  });
}

function doPost(e) {
  try {
    var raw = String(
      e && e.postData && e.postData.contents ? e.postData.contents : ''
    );
    if (!raw || raw.length > 180000) {
      throw new Error('Request body is missing or too large.');
    }

    var envelope = JSON.parse(raw);
    var timestamp = Number(envelope.timestamp);
    var nonce = String(envelope.nonce || '');
    var encodedPayload = String(envelope.payload || '');
    var signature = String(envelope.signature || '').toLowerCase();

    if (envelope.version !== 1) throw new Error('Unsupported request version.');
    if (!Number.isFinite(timestamp)) throw new Error('Invalid timestamp.');
    if (Math.abs(Date.now() - timestamp) > 300000) {
      throw new Error('Request expired.');
    }
    if (!/^[a-f0-9]{32,64}$/.test(nonce)) throw new Error('Invalid nonce.');
    if (!/^[A-Za-z0-9_-]{20,160000}={0,2}$/.test(encodedPayload)) {
      throw new Error('Invalid payload encoding.');
    }
    if (!/^[a-f0-9]{64}$/.test(signature)) {
      throw new Error('Invalid signature encoding.');
    }

    var properties = PropertiesService.getScriptProperties();
    var secret = String(
      properties.getProperty('NVGS_NOTIFICATION_SECRET') || ''
    );
    if (secret.length < 32) throw new Error('Bridge secret is not configured.');

    var signingInput = timestamp + '.' + nonce + '.' + encodedPayload;
    var expected = nvgsNotificationHex_(
      Utilities.computeHmacSha256Signature(
        signingInput,
        secret,
        Utilities.Charset.UTF_8
      )
    );
    if (!nvgsNotificationConstantTimeEqual_(signature, expected)) {
      throw new Error('Invalid request signature.');
    }

    nvgsNotificationRememberNonce_(nonce);
    var payloadText = Utilities.newBlob(
      Utilities.base64DecodeWebSafe(encodedPayload)
    ).getDataAsString('UTF-8');
    var payload = JSON.parse(payloadText);
    nvgsNotificationValidatePayload_(payload);
    nvgsNotificationSend_(payload, properties);

    return nvgsNotificationJson_({
      ok: true,
      eventType: payload.eventType,
      ticketId: payload.ticket.ticketId,
    });
  } catch (error) {
    console.warn('Rejected NVGS notification: ' + error.message);
    return nvgsNotificationJson_({
      ok: false,
      error: String(error.message || 'Notification rejected.'),
    });
  }
}

function checkNvgsNotificationBridgeConfiguration() {
  var properties = PropertiesService.getScriptProperties();
  var secret = String(
    properties.getProperty('NVGS_NOTIFICATION_SECRET') || ''
  );
  var recipients = nvgsNotificationRecipients_(
    properties.getProperty('NVGS_NOTIFICATION_INBOX_EMAIL')
  );
  var requestedAlias = String(
    properties.getProperty('NVGS_NOTIFICATION_SENDER_ALIAS') || ''
  ).trim().toLowerCase();
  var effective = '';
  try {
    effective = String(Session.getEffectiveUser().getEmail() || '')
      .trim().toLowerCase();
  } catch (_) {}
  var aliases = [];
  try {
    aliases = GmailApp.getAliases().map(function (value) {
      return String(value).trim().toLowerCase();
    });
  } catch (_) {}

  var result = {
    secretConfigured: secret.length >= 32,
    inboxConfigured: recipients.length > 0,
    senderAliasRequested: Boolean(requestedAlias),
    senderAliasAvailable:
      !requestedAlias ||
      requestedAlias === effective ||
      aliases.indexOf(requestedAlias) !== -1,
  };
  console.log(JSON.stringify(result));
  return result;
}

function sendNvgsNotificationBridgeTestEmail() {
  var now = new Date().toISOString();
  var payload = {
    app: 'GRTKT',
    eventType: 'TICKET_CREATED',
    eventCase: 'Ticket created',
    deliveryOption: 'EMAIL_FLOW',
    ticketUrl: '',
    ticket: {
      ticketId: 'TEST-00000',
      title: 'NVGS Apps Script notification bridge test',
      description: 'Synthetic setup test. This is not a production ticket.',
      status: 'Open',
      priority: 'Moderate',
      ticketType: 'Others',
      workstation: 'TEST',
      location: '',
      requesterName: 'NVGS Setup',
      requesterEmail: '',
      assignedName: 'Unassigned',
      assignedTo: '',
      impactLevel: 'Low',
      updatedAt: now,
      downtimeStart: now,
      downtimeEnd: '',
      downtimeMinutes: null,
    },
    actor: {
      email: '',
      name: 'NVGS Setup',
      role: 'system_test',
    },
    note: 'Power Automate and Teams notification setup test.',
    teams: {
      targetType: 'groupChat',
      targetName: 'OpsGroupChat',
      groupChatId: '',
      mentions: [],
    },
    actions: [],
    actionExpiresAt: '',
    idempotencyKey: 'nvgs-appscript-bridge-test-' + Date.now(),
    sentAt: now,
  };
  nvgsNotificationSend_(payload, PropertiesService.getScriptProperties());
  return {
    ok: true,
    subject: 'GRTKT_EVENT TICKET_CREATED TEST-00000',
    sentAt: now,
  };
}

function nvgsNotificationValidatePayload_(payload) {
  if (!payload || payload.app !== 'GRTKT') {
    throw new Error('Unexpected application payload.');
  }
  if (!NVGS_NOTIFICATION_EVENTS_[String(payload.eventType || '')]) {
    throw new Error('Unsupported ticket event.');
  }
  if (!payload.ticket || typeof payload.ticket !== 'object') {
    throw new Error('Ticket payload is missing.');
  }
  var ticketId = String(payload.ticket.ticketId || '');
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{2,39}$/.test(ticketId)) {
    throw new Error('Ticket ID is invalid.');
  }
  var title = String(payload.ticket.title || '');
  if (!title || title.length > 180) throw new Error('Ticket title is invalid.');
  if (JSON.stringify(payload).length > 100000) {
    throw new Error('Ticket payload is too large.');
  }
}

function nvgsNotificationSend_(payload, properties) {
  var recipients = nvgsNotificationRecipients_(
    properties.getProperty('NVGS_NOTIFICATION_INBOX_EMAIL')
  );
  if (!recipients.length) {
    throw new Error('Power Automate inbox is not configured.');
  }

  var alias = String(
    properties.getProperty('NVGS_NOTIFICATION_SENDER_ALIAS') || ''
  ).trim().toLowerCase();
  var options = {};
  var effective = '';
  try {
    effective = String(Session.getEffectiveUser().getEmail() || '')
      .trim().toLowerCase();
  } catch (_) {}
  if (alias && alias !== effective) {
    var availableAliases = GmailApp.getAliases().map(function (value) {
      return String(value).trim().toLowerCase();
    });
    if (availableAliases.indexOf(alias) === -1) {
      throw new Error('Configured Gmail sender alias is unavailable.');
    }
    options.from = alias;
  }

  var subject = [
    'GRTKT_EVENT',
    payload.eventType,
    payload.ticket.ticketId,
  ].join(' ');
  GmailApp.sendEmail(
    recipients.join(','),
    subject.slice(0, 250),
    JSON.stringify(payload, null, 2),
    options
  );
}

function nvgsNotificationRecipients_(value) {
  var seen = {};
  return String(value || '')
    .split(/[;,\n]+/)
    .map(function (entry) { return entry.trim().toLowerCase(); })
    .filter(function (entry) {
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(entry) || seen[entry]) {
        return false;
      }
      seen[entry] = true;
      return true;
    });
}

function nvgsNotificationRememberNonce_(nonce) {
  var lock = LockService.getScriptLock();
  lock.waitLock(5000);
  try {
    var cache = CacheService.getScriptCache();
    var key = 'nvgs-notification-nonce-' + nonce;
    if (cache.get(key)) throw new Error('Duplicate request rejected.');
    cache.put(key, 'used', 600);
  } finally {
    lock.releaseLock();
  }
}

function nvgsNotificationHex_(bytes) {
  return bytes.map(function (value) {
    var unsigned = value < 0 ? value + 256 : value;
    return ('0' + unsigned.toString(16)).slice(-2);
  }).join('');
}

function nvgsNotificationConstantTimeEqual_(left, right) {
  if (left.length !== right.length) return false;
  var difference = 0;
  for (var index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function nvgsNotificationJson_(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
