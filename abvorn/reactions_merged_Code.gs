/**
 * Abvorn merged Apps Script backend = LEAD form handler + PDF guide email +
 * like/love reactions + niche welcome + new-post broadcast + unsubscribe.
 *
 * Replace your entire Code.gs with this file, add a sheet named  "reactions"
 * to spreadsheet 1NnDwOewcMNr68D5x8uVHGzKx1SVI7Xv8c5fEjdKm6uI , then deploy a NEW
 * web-app version with access = "Anyone, even anonymous".
 *
 * After deploying, run setupBroadcastTrigger_() once from the editor to install
 * the every-6h new-post broadcast that emails each niche's subscribers when
 * feed.xml gains new items.
 */

var REACTIONS_SHEET_NAME = 'reactions';
var REACTIONS_SPREADSHEET_ID = '1lw7u8rX9eVbXTF8Dyw1gzwZxWKjLrTgUAxM-lroI024';
var LEADS_SHEET_NAME = 'Sheet1';   // capture email leads here
var REACTIONS_LOCK = LockService.getScriptLock();
var FEED_URL = 'https://abvorn.com/feed.xml';
var MAX_BROADCAST_PER_RUN = 80;    // MailApp quota guard (consumer = 100/day)
var NICHES = {
  '4k-monitors': '4K Monitors', 'wireless-earbuds': 'Wireless Earbuds',
  'mechanical-keyboards': 'Mechanical Keyboards', 'streaming-devices': 'Streaming Devices',
  'wireless-headphones': 'Wireless Headphones', 'fitness-trackers': 'Fitness Trackers',
  'laptops': 'Laptops', 'gaming-mice': 'Gaming Mice', 'webcams': 'Webcams',
  'smart-home': 'Smart Home'
};

/* ---------------------------------------------------------------------------
 * Main entry — called by BOTH POST and GET (GET used by the site to test CORS).
 * Routes: reactions / reactions-read / email leads.
 * ------------------------------------------------------------------------- */
function doPost(e) {
  return doRoute_(e);
}

// Browsers/paste-in-URL send a GET; route it the same as POST so you can
// test in the address bar:  ?action=test-lead&email=a@b.com
function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) || '';
  if (action === 'unsubscribe') return unsubscribePage_(e.parameter);
  return doRoute_(e);
}

function doRoute_(e) {
  var body = parseBody_(e);
  var action = (body && body.action) || (e && e.parameter && e.parameter.action) || '';

  // New like/love reaction endpoints (the review buttons).
  if (action === 'reaction') return handleReaction_(body);   // writes +1
  if (action === 'reactions') return handleRead_(body);       // reads aggregate counts

  // 'Email this review' CTA: email the review's PDF link to the reader.
  if (action === 'pdf_guide') return handlePdfGuide_(body);

  // One-click unsubscribe from the footer link in every email.
  if (action === 'unsubscribe') return handleUnsubscribe_(body);

  // One-time onboarding from a browser: seed sent-GUIDs + install the 6h
  // broadcast trigger in a single call (no editor needed).
  if (action === 'setup-broadcast') return runSetup_();

  // Authorization probe — open /dev?action=auth-check while signed in as the
  // owner to force the permission-consent screen for the feed-fetch scope.
  if (action === 'auth-check') return authProbe_();

  // Manual test: fills Sheet1 with a fake lead without needing live traffic.
  if (action === 'test-lead') return handleLeadForm_({
      email: body.email || (e.parameter && e.parameter.email) || 'test@example.com',
      niche: body.niche || (e.parameter && e.parameter.niche) || 'test',
      source: 'test', lead_magnet: 'Test'
  });

  // Fall through to your existing email lead form (unchanged).
  if (!body || !body.email) return json_({ success:false, message:'no payload' });
  return handleLeadForm_(body);
}

/* ---------------------------------------------------------------------------
 * REACTIONS  (these two are new)
 * ------------------------------------------------------------------------- */
function handleReaction_(body) {
  var slug = String(body.slug || '').trim();
  var type = String(body.type || '').toLowerCase();
  var visitor = String(body.visitor || '');
  if (!slug || !visitor) return json_({ success:false, message:'slug & visitor required' });
  if (type !== 'like' && type !== 'love') return json_({ success:false, message:'type must be like|love' });

  REACTIONS_LOCK.waitLock(15000);
  try {
    var votes = readReactions_();
    votes[slug] = votes[slug] || { like:{}, love:{} };
    votes[slug][type][visitor] = true;   // idempotent add; toggling is client-side
    writeReactions_(votes);
    return returnReads_(votes, slug);    // return updated counts for this slug
  } catch (err) {
    return json_({ success:false, message:'server error: ' + err });
  } finally {
    if (REACTIONS_LOCK.hasLock()) REACTIONS_LOCK.releaseLock();
  }
}

function handleRead_(body) {
  var slugs = body.slugs;
  if (typeof slugs === 'string') slugs = slugs.split(',');
  if (!Array.isArray(slugs) || !slugs.length) return json_({ success:false, message:'slugs required' });
  try {
    var votes = readReactions_();
    var reactions = slugs.map(function (slug) {
      var t = votes[slug] || { like:{}, love:{} };
      return { slug: slug, like: Object.keys(t.like).length, love: Object.keys(t.love).length };
    });
    return json_({ success:true, reactions: reactions });
  } catch (err) {
    return json_({ success:false, message:'server error: ' + err });
  }
}

function returnReads_(votes, slug) {
  var t = votes[slug] || { like:{}, love:{} };
  return json_({ success:true, reactions:[{ slug: slug, like: Object.keys(t.like).length, love: Object.keys(t.love).length }] });
}

function readReactions_() {
  var sh = SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).getSheetByName(REACTIONS_SHEET_NAME);
  if (!sh) return {};
  var data = sh.getDataRange().getValues();
  var votes = {};
  for (var i = 0; i < data.length; i++) {
    var slug = String(data[i][0] || ''), type = String(data[i][1] || ''), visitor = String(data[i][2] || '');
    if (!slug || !visitor) continue;
    if (type !== 'like' && type !== 'love') continue;
    if (!votes[slug]) votes[slug] = { like:{}, love:{} };
    votes[slug][type][visitor] = true;
  }
  return votes;
}

function writeReactions_(votes) {
  var ss = SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID);
  var sh = ss.getSheetByName(REACTIONS_SHEET_NAME);
  if (!sh) { sh = ss.insertSheet(REACTIONS_SHEET_NAME); }
  sh.clearContents();
  sh.appendRow(['slug', 'type', 'visitor']);
  for (var slug in votes) {
    for (var type in { like:1, love:1 }) {
      var visitors = Object.keys(votes[slug][type]);
      visitors.forEach(function (v) { sh.appendRow([slug, type, v]); });
    }
  }
}

/* ---------------------------------------------------------------------------
   YOUR EXISTING EMAIL LEAD FORM (unchanged)
 * ------------------------------------------------------------------------- */
function handleLeadForm_(data) {
  var email = String(data.email || '').trim();
  var niche = String(data.niche || 'general').trim();
  var source = data.source || 'blog';
  var leadMagnet = data.lead_magnet || 'Free Guide';
  if (!isEmail_(email)) return json_({ success: false, message: 'Please use a valid email address.' });

  var sheet = SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).getSheetByName(LEADS_SHEET_NAME)
    || SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).insertSheet(LEADS_SHEET_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['email', 'niche', 'source', 'subscribed_at', 'status', 'lead_magnet']);
  }

  var dataRows = sheet.getDataRange().getValues();
  var rowIndex = -1, status = '';
  for (var i = 1; i < dataRows.length; i++) {
    if (String(dataRows[i][0] || '').trim().toLowerCase() === email.toLowerCase()) {
      rowIndex = i + 1; status = String(dataRows[i][4] || 'active'); break;
    }
  }

  if (rowIndex > -1 && status === 'active') {
    return json_({ success: false, message: 'Already subscribed.' });
  }

  if (rowIndex > -1) {
    // Re-subscribe after unsubscribing: flip status back and refresh niche.
    sheet.getRange(rowIndex, 1, 1, 6).setValues([[dataRows[rowIndex - 1][0], niche, source, dataRows[rowIndex - 1][3], 'active', leadMagnet]]);
  } else {
    sheet.appendRow([email, niche, source, new Date().toISOString(), 'active', leadMagnet]);
  }

  sendWelcomeEmail(email, niche, leadMagnet);
  return json_({ success: true });
}

function sendWelcomeEmail(email, niche, leadMagnet) {
  var isNicheSignup = leadMagnet && leadMagnet.indexOf('updates') > -1;
  var nicheName = NICHES[niche] || humanizeSlug_(niche);
  var browseUrl = niche === 'general' ? 'https://abvorn.com/' : 'https://abvorn.com/reviews/' + niche + '/';

  var subject, pre, post;
  if (isNicheSignup) {
    subject = 'You are subscribed to ' + nicheName + ' updates';
    pre = '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
      'You are now subscribed to <strong>' + nicheName + ' updates</strong>. One email whenever we publish a new ' +
      nicheName + ' guide \u2014 no spam, unsubscribe anytime.</p>';
    post = '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
      'In the meantime, here is the latest on ' + nicheName.toLowerCase() + ':</p>';
  } else {
    subject = (leadMagnet && leadMagnet !== 'Free Guide') ? 'Your ' + leadMagnet + ' is ready' : 'Welcome to Abvorn';
    pre = '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
      'Thanks for joining Abvorn' + (leadMagnet && leadMagnet !== 'Free Guide' ? ' and requesting the <strong>' + leadMagnet + '</strong>.' : '.') + '</p>';
    post = '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
      'Started browsing, rated, and reviewed mechanically \u2014 prices pulled fresh, verdicts scored, no sponsored picks.' +
      ' Start with the latest reviews:</p>';
  }

  var htmlBody = _renderEmail_(email, {
    pre: pre,
    post: post,
    cta: { text: isNicheSignup ? 'Browse ' + nicheName + ' reviews' : 'Read the latest reviews', url: browseUrl }
  });
  MailApp.sendEmail({ to: email, subject: subject, htmlBody: htmlBody });
}

/* ---------------------------------------------------------------------------
   'EMAIL THIS REVIEW' — sends the review's PDF link to the reader's inbox.
   Payload from the review page rail card:
     {action:'pdf_guide', email, title, niche, slug, niche_name,
      source:'review_rail', pdf_url, guide_url}
 * ------------------------------------------------------------------------- */
function handlePdfGuide_(data) {
  var email = String(data.email || '').trim();
  var title = String(data.title || 'guide').trim();
  var pdfUrl = String(data.pdf_url || '').trim();
  var niche = String(data.niche || data.slug || 'products').trim();
  var guideUrl = String(data.guide_url || '').trim();
  var source = String(data.source || 'review_rail').trim();

  if (!isEmail_(email)) return json_({ success:false, message:'Please use a valid email address.' });
  if (!pdfUrl) return json_({ success:false, message:'The PDF is still being prepared. Please try again in a few minutes.' });

  // Log the lead (single row per email).
  try {
    var sheet = SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).getSheetByName(LEADS_SHEET_NAME)
      || SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).insertSheet(LEADS_SHEET_NAME);
    if (sheet.getLastRow() === 0) sheet.appendRow(['email', 'niche', 'source', 'subscribed_at', 'status', 'lead_magnet']);
    var known = sheet.getRange(1, 1, sheet.getLastRow(), 1).getValues()
      .map(function (r) { return String(r[0]).trim(); });
    if (known.indexOf(email) === -1) {
      sheet.appendRow([email, niche, source, new Date().toISOString(), 'active', 'PDF: ' + title]);
    }
  } catch (err) {
    // Lead logging must never block the email.
  }

  sendPdfGuideEmail_(email, title, pdfUrl, guideUrl, niche);
  return json_({ success:true });
}

function sendPdfGuideEmail_(email, title, pdfUrl, guideUrl, niche) {
  var liveLine = guideUrl
    ? '<p style="margin:12px 0;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
      'Prefer the live version? <a href="' + guideUrl + '" style="color:#d4633e">Read the full guide online</a> instead.</p>'
    : '';
  var subject = 'Your guide is ready: ' + title;
  var htmlBody = _renderEmail_(email, {
    pre:
    '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
    'Hi there,</p>' +
    '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
    'Your copy of <strong>' + title + '</strong> is ready. Every score, price, and verdict from the guide, ' +
    'in one clean downloadable document.</p>' +
    '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
    'No sign-up walls and no paywall \u2014 just the guide, so you can read it at your own pace.</p>' + liveLine,
    post: '',
    cta: { text: 'Download Your Guide (PDF)', url: pdfUrl, arrow: true }
  });

  MailApp.sendEmail({ to: email, subject: subject, htmlBody: htmlBody });
}

/* ---------------------------------------------------------------------------
   Shared email shell — brand header, content, CTA, footer (disclosure +
   working one-click unsubscribe). Every outbound email goes through this so
   the opt-out is never missing.
 * ------------------------------------------------------------------------- */
function _renderEmail_(email, opts) {
  var arrow = opts.cta && opts.cta.arrow ? ' \u2192' : '';
  var ctaHtml = opts.cta
    ? '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0"><tr><td style="background-color:#d4633e;border-radius:8px;padding:12px 28px">' +
      '<a href="' + opts.cta.url + '" style="color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;display:inline-block">' +
      opts.cta.text + arrow + '</a></td></tr></table>'
    : '';
  return '<html><body style="margin:0;padding:0;background:#faf8f6">' +
    '<table role="presentation" cellpadding="0" cellspacing="0" width="100%" bgcolor="#faf8f6"><tr><td align="center" style="padding:32px 16px">' +
    '<table role="presentation" cellpadding="0" cellspacing="0" width="600" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden">' +
    '<tr><td style="background:#ffffff;padding:24px 32px 4px">' +
    '<a href="https://abvorn.com/" style="text-decoration:none"><span style="font-family:Arial,Helvetica,sans-serif;font-size:22px;font-weight:800;color:#d4633e;letter-spacing:-0.5px">abvorn</span>' +
    '<span style="font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:600;color:#9e9690;letter-spacing:1.5px;text-transform:uppercase;margin-left:6px">tested reviews</span></a></td></tr>' +
    '<tr><td style="background:#ffffff;padding:16px 32px 8px">' + (opts.pre || '') + '</td></tr>' +
    '<tr><td style="background:#ffffff;padding:8px 32px">' + ctaHtml + '</td></tr>' +
    '<tr><td style="background:#ffffff;padding:8px 32px 24px">' + (opts.post || '') + '</td></tr>' +
    '<tr><td style="background:#f1ece8;padding:20px 32px">' +
    '<p style="margin:0 0 8px;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9e9690;line-height:1.6">' +
    'As an Amazon Associate we earn from qualifying purchases. Every review is scored mechanically from real specs and current prices \u2014 commission never changes a verdict.</p>' +
    '<p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9e9690">You received this because you subscribed on <a href="https://abvorn.com/" style="color:#9e9690;text-decoration:underline">abvorn.com</a>.' +
    ' <a href="' + _unsubUrl_(email) + '" style="color:#9e9690;text-decoration:underline">Unsubscribe</a>.</p></td></tr>' +
    '</table></td></tr></table></body></html>';
}

function _unsubUrl_(email) {
  var base;
  try { base = ScriptApp.getService().getUrl(); } catch (err) { base = 'https://script.google.com/macros/s/'; }
  return base + '?action=unsubscribe&email=' + encodeURIComponent(email);
}

function humanizeSlug_(slug) {
  return slug.split('-').map(function (w) { return w ? w.charAt(0).toUpperCase() + w.slice(1) : w; }).join(' ');
}

/* ---------------------------------------------------------------------------
   ONE-CLICK UNSUBSCRIBE — flips the lead row to 'unsubscribed'. Email sends
   (welcome, PDF, broadcast) all skip non-active rows.
 * ------------------------------------------------------------------------- */
function handleUnsubscribe_(body) {
  var email = String((body && body.email) || '').trim();
  if (!isEmail_(email)) return json_({ success: false, message: 'Invalid email.' });
  var sheet = SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).getSheetByName(LEADS_SHEET_NAME);
  if (sheet) {
    var dataRows = sheet.getDataRange().getValues();
    for (var i = 1; i < dataRows.length; i++) {
      if (String(dataRows[i][0] || '').trim().toLowerCase() === email.toLowerCase()) {
        sheet.getRange(i + 1, 5).setValue('unsubscribed');
        break;
      }
    }
  }
  return json_({ success: true, message: 'Unsubscribed.' });
}

function unsubscribePage_(params) {
  handleUnsubscribe_(params);
  var html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>Unsubscribed — Abvorn</title></head>' +
    '<body style="margin:0;padding:0;background:#faf8f6;font-family:Arial,Helvetica,sans-serif">' +
    '<div style="max-width:480px;margin:80px auto;background:#fff;border-radius:12px;padding:40px;text-align:center">' +
    '<div style="font-size:24px;font-weight:800;color:#d4633e">abvorn</div>' +
    '<p style="font-size:18px;font-weight:600;color:#333;margin:24px 0 8px">You are unsubscribed.</p>' +
    '<p style="font-size:14px;color:#9e9690;line-height:1.6;margin:0 0 24px">You will no longer receive email updates from Abvorn. If this was a mistake, subscribe again from any review page.</p>' +
    '<a href="https://abvorn.com/" style="display:inline-block;background:#d4633e;color:#fff;text-decoration:none;font-size:15px;font-weight:600;border-radius:8px;padding:12px 28px">Back to Abvorn</a>' +
    '</div></body></html>';
  return HtmlService.createHtmlOutput(html);
}

/* ---------------------------------------------------------------------------
   NEW-POST BROADCAST — reads docs/feed.xml, emails each niche's active
   subscribers whenever new items appear for their niche, then remembers the
   sent GUIDs so nothing is emailed twice. Install once with
   setupBroadcastTrigger_() to run on a time-based trigger.
 * ------------------------------------------------------------------------- */
function broadcastNewPosts_() {
  var props = PropertiesService.getScriptProperties();
  var sent = {};
  try { sent = JSON.parse(props.getProperty('SENT_GUIDS') || '{}'); } catch (err) { sent = {}; }

  var items = _fetchFeedItems_();
  var byNiche = {};
  items.forEach(function (it) {
    if (sent[it.guid]) return;
    (byNiche[it.niche] = byNiche[it.niche] || []).push(it);
  });

  var nNicheWithNew = Object.keys(byNiche).length;
  if (nNicheWithNew === 0) return -1;

  var sheet = SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).getSheetByName(LEADS_SHEET_NAME);
  var subs = [];   // {email,niche}
  if (sheet && sheet.getLastRow() > 0) {
    var rows = sheet.getDataRange().getValues();
    for (var i = 1; i < rows.length; i++) {
      if (String(rows[i][4] || '').trim() === 'active' && isEmail_(rows[i][0])) {
        subs.push({ email: String(rows[i][0]).trim(), niche: String(rows[i][1] || '').trim() });
      }
    }
  }
  if (subs.length === 0) return -1;

  var sentCount = 0, skipped = 0;
  for (var s = 0; s < subs.length && sentCount < MAX_BROADCAST_PER_RUN; s++) {
    var sub = subs[s];
    var nicheItems = byNiche[sub.niche] || (sub.niche === 'general' ? _allNew_(byNiche) : null);
    if (!nicheItems || nicheItems.length === 0) { skipped++; continue; }
    if (sub.niche === 'general' && nicheItems.length > 3) nicheItems = nicheItems.slice(0, 3);
    _sendDigest_(sub.email, sub.niche, nicheItems);
    sentCount++;
  }

  // Remember GUIDs we processed so the next run emails only genuinely new items.
  var newSent = {};
  Object.keys(byNiche).forEach(function (n) {
    byNiche[n].forEach(function (it) { newSent[it.guid] = 1; });
  });
  Object.keys(sent).forEach(function (g) { if (!newSent[g]) newSent[g] = sent[g]; });
  props.setProperty('SENT_GUIDS', JSON.stringify(newSent));

  Logger.log('broadcastNewPosts_: sent=' + sentCount + ' skipped(no match)=' + skipped + ' niches=' + nNicheWithNew);
  return sentCount;
}

function _allNew_(byNiche) {
  var out = [];
  Object.keys(byNiche).forEach(function (n) { out = out.concat(byNiche[n]); });
  return out.sort(function (a, b) { return (b.dateGMT || 0) - (a.dateGMT || 0); });
}

function _sendDigest_(email, niche, items) {
  var nicheName = NICHES[niche] || humanizeSlug_(niche);
  var titles = items.map(function (it) { return it.title; });
  var subject = titles.length === 1
    ? 'New on Abvorn: ' + titles[0]
    : 'New on Abvorn (' + nicheName + '): ' + titles.length + ' new guides';
  var list = items.map(function (it) {
    return '<p style="margin:0 0 14px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.5">' +
      '<a href="' + it.link + '" style="color:#d4633e;font-weight:600;text-decoration:none">' + it.title + '</a></p>';
  }).join('');
  var base = niche === 'general' ? 'https://abvorn.com/' : 'https://abvorn.com/reviews/' + niche + '/';
  var htmlBody = _renderEmail_(email, {
    pre: '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
      'Hi there,</p>' +
      '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
      'New ' + nicheName.toLowerCase() + ' guides just went live on Abvorn, scored and priced fresh:</p>' + list,
    post: '',
    cta: { text: 'Browse all ' + nicheName + ' reviews', url: base }
  });
  MailApp.sendEmail({ to: email, subject: subject, htmlBody: htmlBody });
}

function _fetchFeedItems_() {
  var res = UrlFetchApp.fetch(FEED_URL, { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) return [];
  var doc = XmlService.parse(res.getContentText());
  var ns = XmlService.getNamespace('http://purl.org/rss/1.0/');
  var items = doc.getRootElement().getChild('channel').getChildren('item');
  return items.map(function (item) {
    var title = item.getChildText('title') || '';
    var link = item.getChildText('link') || '';
    var guidEl = item.getChild('guid');
    var guid = guidEl ? (guidEl.getText() || link) : link;
    var pubDate = item.getChildText('pubDate') || '';
    return {
      title: title, link: link, guid: guid, niche: _nicheForLink_(link),
      dateGMT: new Date(pubDate).getTime() || 0
    };
  });
}

function _nicheForLink_(link) {
  var m = link.match(/\/reviews\/([a-z0-9-]+)\//);
  return m ? m[1] : 'general';
}

/** Record every item currently in the feed as already-sent, WITHOUT emailing. Run once after deploy so the first broadcast only covers genuinely new posts. */
function seedBroadcastState_() {
  var props = PropertiesService.getScriptProperties();
  var sent = {};
  try { sent = JSON.parse(props.getProperty('SENT_GUIDS') || '{}'); } catch (err) { sent = {}; }
  var items = _fetchFeedItems_();
  items.forEach(function (it) { sent[it.guid] = 1; });
  props.setProperty('SENT_GUIDS', JSON.stringify(sent));
  Logger.log('seedBroadcastState_: recorded ' + items.length + ' existing feed items without sending.');
  return items.length;
}

/** Install (or replace) the 6-hourly new-post broadcast trigger. Run once after deploy. */
function setupBroadcastTrigger_() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'broadcastNewPosts_') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger('broadcastNewPosts_').timeBased().everyHours(6).create();
  Logger.log('Broadcast trigger installed (every 6h).');
}

/** One-time onboarding, callable from a browser URL: seeds the sent-GUID set
 * (so the first broadcast only covers genuinely new posts) and installs the
 * 6-hourly broadcast trigger in one shot. Runs under the owner's
 * authorization when the web app is deployed as "Execute as: Me". */
function runSetup_() {
  try {
    var seeded = seedBroadcastState_();
    setupBroadcastTrigger_();
    return json_({
      success: true,
      seeded: seeded,
      trigger: 'installed (every 6h)',
      message: 'Sent-GUID set seeded. First broadcast will only cover posts published after this moment.'
    });
  } catch (err) {
    return json_({ success: false, error: 'setup failed: ' + err });
  }
}

/** Authorization probe — hit /dev?action=auth-check once while signed in as
 * the owner. It performs a real scoped call (fetch the feed), which makes
 * Google show the consent screen so script.external_request etc. get granted
 * to the project; anonymous /exec calls inherit them after a fresh deploy. */
function authProbe_() {
  var out = {};
  try {
    var res = UrlFetchApp.fetch(FEED_URL, { muteHttpExceptions: true });
    out.fetch = 'ok:' + res.getResponseCode();
  } catch (e) {
    out.fetch = 'error: ' + e;
    return json_({ success: false, detail: out });
  }
  try {
    SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID);
    out.sheets = 'ok';
  } catch (e2) {
    out.sheets = 'error: ' + e2;
  }
  return json_({ success: true, detail: out });
}

function isEmail_(email) {
  return /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/.test(email);
}

/* ---------------------------------------------------------------------------
   Helpers
   ------------------------------------------------------------------------- */
function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function parseBody_(e) {
  try {
    if (e && e.postData && e.postData.contents) return JSON.parse(e.postData.contents);
  } catch (err) {}
  if (!e) return {};
  var p = e.parameter || {};
  var out = {};
  Object.keys(p).forEach(function (k) { out[k] = p[k]; });
  return out;
}