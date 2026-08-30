/**
 * Abvorn merged Apps Script backend = existing LEAD form handler + new like/love reactions.
 *
 * Replace your entire Code.gs with this file, add a sheet named  "reactions"
 * to spreadsheet 1NnDwOewcMNr68D5x8uVHGzKx1SVI7Xv8c5fEjdKm6uI , then deploy a NEW
 * web-app version with access = "Anyone, even anonymous".
 */

var REACTIONS_SHEET_NAME = 'reactions';
var REACTIONS_SPREADSHEET_ID = '1lw7u8rX9eVbXTF8Dyw1gzwZxWKjLrTgUAxM-lroI024';
var LEADS_SHEET_NAME = 'Sheet1';   // capture email leads here
var REACTIONS_LOCK = LockService.getScriptLock();

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
  var email = data.email;
  var niche = data.niche;
  var source = data.source || 'blog';
  var leadMagnet = data.lead_magnet || 'Free Guide';

  var sheet = SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).getSheetByName(LEADS_SHEET_NAME)
    || SpreadsheetApp.openById(REACTIONS_SPREADSHEET_ID).insertSheet(LEADS_SHEET_NAME);
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['email', 'niche', 'source', 'subscribed_at', 'status', 'lead_magnet']);
  }

  var emails = sheet.getRange(1, 1, sheet.getLastRow(), 1).getValues().flat();
  if (emails.indexOf(email) > -1) {
    return json_({ success: false, message: 'Already subscribed.' });
  }

  sheet.appendRow([email, niche, source, new Date().toISOString(), 'active', leadMagnet]);

  sendWelcomeEmail(email, niche, leadMagnet);

  return json_({ success: true });
}

function sendWelcomeEmail(email, niche, leadMagnet) {
  var subject = 'Your ' + leadMagnet + ' is ready';
  var body = '<h1>Welcome to Abvorn</h1>'
    + '<p>Thanks for requesting the <strong>' + leadMagnet + '</strong>.</p>'
    + '<p><a href="https://abvorn.com/' + niche + '/" style="display:inline-block;padding:12px 24px;background:#ec4899;color:#fff;text-decoration:none;">Browse Reviews</a></p>';

  MailApp.sendEmail({
    to: email,
    subject: subject,
    htmlBody: body
  });
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
  var htmlBody =
    '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
    'Hi there,</p>' +
    '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
    'Your copy of <strong>' + title + '</strong> is ready. Every score, price, and verdict from the guide, ' +
    'in one clean downloadable document.</p>' +
    '<p style="margin:0 0 16px;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#333;line-height:1.6">' +
    'No sign-up walls and no paywall \u2014 just the guide, so you can read it at your own pace.</p>' + liveLine +
    '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0"><tr><td style="background-color:#d4633e;border-radius:8px;padding:12px 28px">' +
    '<a href="' + pdfUrl + '" style="color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;display:inline-block">' +
    'Download Your Guide (PDF) \u2192</a></td></tr></table>' +
    '<p style="margin:16px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9e9690">' +
    'As an Amazon Associate we earn from qualifying purchases.</p>';

  MailApp.sendEmail({ to: email, subject: subject, htmlBody: htmlBody });
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