/**
 * Abvorn like/love reaction backend — add to your existing Apps Script
 * (the same web app bound to APPS_SCRIPT_URL that already handles the
 * email lead forms).
 *
 * Paste ADD_REACTION_HANDLERS() into your existing doPost (or replace it if
 * this is the only thing the script does), then deploy a NEW version as a web
 * app with access set to "Anyone, even anonymous".
 *
 * Payloads the site sends:
 *   {action:'reaction',   slug, type:'like'|'love', visitor}   -> record +1 (dedup per visitor)
 *   {action:'reactions',  slugs:[...]}                          -> read aggregate counts only
 *
 * Response shape the site expects:
 *   {action, success}
 *   on 'reaction':  {action, success}
 *   on 'reactions': {success, reactions:[{slug, like, love}, ...]}
 */
var REACTIONS_SHEET_NAME = 'reactions';
var REACTIONS_LOCK = LockService.getScriptLock();

function doGet(e) {
  return doPostFor_(e);
}

function doPost(e) {
  return doPostFor_(e);
}

function doPostFor_(e) {
  // Allow CORS for browser calls from the GitHub Pages site.
  var out = ContentService.createTextOutput().setMimeType(ContentService.MimeType.JSON);
  var origin = (e && e.parameter && e.parameter.origin) || getHeader_(e, 'Origin');
  if (origin) out.setHeaders({ 'Access-Control-Allow-Origin': origin,
                               'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
                               'Access-Control-Allow-Headers': 'Content-Type' });

  var body = parseBody_(e);
  if (!body) return respond_(out, { success:false, message:'no payload' });

  var action = body.action || (e.parameter && e.parameter.action) || '';
  if (action === 'reaction') return handleReaction_(out, body);
  if (action === 'reactions') return handleRead_(out, body);
  // Let your existing email form handler keep working unchanged.
  if (action === '' && body.email) return handleLeadForm_(out, body);

  return respond_(out, { success:false, message:'unknown action' });
}

function handleReaction_(out, body) {
  var slug = String(body.slug || '').trim();
  var type = String(body.type || '').toLowerCase();
  var visitor = String(body.visitor || '');   // per-visitor id so a person can toggle
  if (!slug || !visitor) return respond_(out, { success:false, message:'slug & visitor required' });
  if (type !== 'like' && type !== 'love') return respond_(out, { success:false, message:'type must be like|love' });

  REACTIONS_LOCK.waitLock(15000);
  try {
    var votes = readReactions_();              // {slug: {like: Set, love: Set}} keyed by visitor
    var tbl = votes[slug] = votes[slug] || { like : {}, love : {} };
    var set = tbl[type];
    set[visitor] = true;                        // add (or keep) the visitor's reaction; simplify to add-only below
    // Toggle semantics are handled client-side via localStorage; here we keep idempotent adds.
    writeReactions_(votes);
    return handleRead_(out, { action:'reactions', slugs:[slug] });
  } catch (err) {
    return respond_(out, { success:false, message:'server error: ' + err });
  } finally {
    if (REACTIONS_LOCK.hasLock()) REACTIONS_LOCK.releaseLock();
  }
}

function handleRead_(out, body) {
  var slugs = body.slugs;
  if (typeof slugs === 'string') slugs = slugs.split(',');
  if (!Array.isArray(slugs) || !slugs.length) return respond_(out, { success:false, message:'slugs required' });
  return handleData_(out, slugs);
}

function handleData_(out, slugs) {
  try {
    var votes = readReactions_();
    var reactions = slugs.map(function (slug) {
      var t = votes[slug] || { like:{}, love:{} };
      return { slug: slug, like: Object.keys(t.like).length, love: Object.keys(t.love).length };
    });
    return respond_(out, { success: true, reactions: reactions });
  } catch (err) {
    return respond_(out, { success:false, message:'server error: ' + err });
  }
}

function readReactions_() {
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(REACTIONS_SHEET_NAME);
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
  var ss = SpreadsheetApp.getActive();
  var sh = ss.getSheetByName(REACTIONS_SHEET_NAME);
  if (!sh) { sh = ss.insertSheet(REACTIONS_SHEET_NAME); sh.appendRow(['slug', 'type', 'visitor']); }
  sh.clearContents();
  sh.appendRow(['slug', 'type', 'visitor']);
  for (var slug in votes) {
    for (var type in { like:1, love:1 }) {
      var visitors = Object.keys(votes[slug][type]);
      visitors.forEach(function (v) { sh.appendRow([slug, type, v]); });
    }
  }
}

function respond_(out, obj) {
  return out.setContent(JSON.stringify(obj));
}

function parseBody_(e) {
  try {
    if (e && e.postData && e.postData.contents) return JSON.parse(e.postData.contents);
  } catch (err) {}
  if (e && e.parameter) return e.parameter;
  return null;
}

function getHeader_(e, name) {
  try { if (e && e.parameter) return e.parameter[name]; } catch (err) {}
  return null;
}

function handleLead_(out, body) {
  // Placeholder for your existing email form handler — route it here.
  return respond_(out, { success: true });
}