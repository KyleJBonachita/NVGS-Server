/**
 * Standalone NVGS login bridge web entry point.
 *
 * Do not click Run in the Apps Script editor. Deploy the project as a web app,
 * then start authentication from Django's /api/auth/appscript/start/ URL.
 */
function doGet(e) {
  var loginPage = maybeHandleNvgsLogin_(e);
  if (loginPage) return loginPage;

  var html = [
    '<!doctype html><html><head>',
    '<meta charset="utf-8">',
    '<meta name="referrer" content="no-referrer">',
    '<meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>NVGS Login Bridge</title>',
    '</head><body>',
    '<main><h1>NVGS Login Bridge</h1>',
    '<p>Start sign-in from the local NVGS server website.</p>',
    '</main></body></html>',
  ].join('');

  return HtmlService.createHtmlOutput(html)
    .setTitle('NVGS Login Bridge')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT);
}
