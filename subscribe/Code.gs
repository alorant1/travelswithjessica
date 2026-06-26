// Google Apps Script for Travels with Jessica subscriber management
// Deploy as Web App: Execute as "Me", Access "Anyone"

var SHEET_ID = '1AYFDxX0TO2DWDNAyMDDjdKRs25NgA_JXsicpD1GF97g';
var SHEET_NAME = 'Subscribers';

function getSheet() {
  return SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_NAME);
}

function generateToken() {
  var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  var token = '';
  for (var i = 0; i < 32; i++) {
    token += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return token;
}

function doPost(e) {
  var result;
  try {
    var body = JSON.parse(e.postData.contents);
    if (body.action === 'error') {
      handleErrorNotification(body.message || 'Unknown error');
      result = { success: true };
    } else {
      result = handleSubscribe(e);
    }
  } catch (err) {
    result = { success: false, message: 'Something went wrong. Please try again.' };
  }
  var output = ContentService.createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
  return output;
}

function doGet(e) {
  var action = e.parameter.action;
  if (action === 'unsubscribe') {
    return handleUnsubscribe(e.parameter.token);
  }
  return ContentService.createTextOutput('Invalid request');
}

function handleErrorNotification(message) {
  try {
    MailApp.sendEmail({
      to: 'adam@lorant.com',
      subject: 'Travels with Jessica — Subscribe Error',
      body: 'A subscription error occurred on travelswithjessica.ca:\n\n' + message + '\n\nTimestamp: ' + new Date().toISOString()
    });
  } catch (err) {
    // silently fail if email can't be sent
  }
}

function handleSubscribe(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var email = (body.email || '').toLowerCase().trim();

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return { success: false, message: 'Invalid email address.' };
    }

    var sheet = getSheet();
    var data = sheet.getDataRange().getValues();

    // Check for existing subscriber
    for (var i = 1; i < data.length; i++) {
      if (data[i][0].toLowerCase() === email) {
        if (data[i][2] === 'active') {
          return { success: false, message: 'You are already subscribed!' };
        } else {
          // Re-subscribe
          sheet.getRange(i + 1, 3).setValue('active');
          sheet.getRange(i + 1, 4).setValue(new Date().toISOString());
          return { success: true, message: 'Welcome back! You have been re-subscribed.' };
        }
      }
    }

    // New subscriber
    var token = generateToken();
    sheet.appendRow([email, new Date().toISOString(), 'active', token]);
    return { success: true, message: 'Thank you for subscribing!' };

  } catch (err) {
    return { success: false, message: 'Something went wrong. Please try again.' };
  }
}

function handleUnsubscribe(token) {
  if (!token) {
    return HtmlService.createHtmlOutput('<h2>Invalid unsubscribe link.</h2>');
  }

  var sheet = getSheet();
  var data = sheet.getDataRange().getValues();

  for (var i = 1; i < data.length; i++) {
    if (data[i][3] === token) {
      if (data[i][2] === 'unsubscribed') {
        return HtmlService.createHtmlOutput(unsubscribePage('You are already unsubscribed.'));
      }
      sheet.getRange(i + 1, 3).setValue('unsubscribed');
      return HtmlService.createHtmlOutput(unsubscribePage('You have been unsubscribed successfully.'));
    }
  }

  return HtmlService.createHtmlOutput(unsubscribePage('Unsubscribe link not found.'));
}

function unsubscribePage(message) {
  return '<html><head><meta charset="UTF-8"><style>'
    + 'body{font-family:Georgia,serif;max-width:500px;margin:80px auto;text-align:center;color:#3d2b1f}'
    + 'h2{color:#9e6555}</style></head><body>'
    + '<h2>Travels with Jessica</h2>'
    + '<p>' + message + '</p>'
    + '<p><a href="https://travelswithjessica.ca" style="color:#9e6555">Return to the site</a></p>'
    + '</body></html>';
}
