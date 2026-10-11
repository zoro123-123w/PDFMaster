/**
 * PDF Master ad-gate.
 *
 * When the site operator enables the ad-gate (AD_GATE_ENABLED + AD_GATE_URL),
 * the first "Download" or "Start OCR" click inside a tab opens the ad URL in a
 * new tab via window.open(url, "_blank", "noopener"). The original action is
 * NOT interrupted: the download / OCR still runs on the same page, and the
 * current page is never redirected. Repeat clicks inside the same tab are
 * suppressed for the configured cooldown (sessionStorage, per tab).
 *
 * No-op when the URL is empty or the script was not injected (gate disabled).
 */
(function () {
  'use strict';

  var cfg = document.querySelector('script[data-ad-gate-url]');
  var url = cfg && cfg.getAttribute('data-ad-gate-url');
  if (!url) {
    return; // disabled or empty: load nothing, do nothing
  }

  var cooldownMin = parseInt(cfg.getAttribute('data-ad-gate-cooldown') || '10', 10);
  if (isNaN(cooldownMin) || cooldownMin < 0) {
    cooldownMin = 10;
  }
  var STORAGE_KEY = 'adgate:lastOpenMs';

  function inCooldown() {
    if (cooldownMin <= 0) {
      return false;
    }
    try {
      var last = parseInt(sessionStorage.getItem(STORAGE_KEY) || '0', 10);
      return last > 0 && (Date.now() - last) < cooldownMin * 60000;
    } catch (e) {
      return false; // sessionStorage unavailable -> always open
    }
  }

  function gate() {
    if (inCooldown()) {
      return;
    }
    try {
      sessionStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch (e) { /* ignore quota/private-mode errors */ }
    window.open(url, '_blank', 'noopener');
  }

  // "Download" clicks: result-screen download buttons/links across tools
  // (compress, OCR, zip tools) share the .ocr-download class. The handler only
  // opens the ad - it never calls preventDefault, so the download proceeds.
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('.ocr-download') : null;
    if (el) {
      gate();
    }
  });

  // "Start OCR" click: the OCR page's submit button. The form still submits
  // on this page after the ad opens.
  var ocrBtn = document.getElementById('ocrSubmit');
  if (ocrBtn) {
    ocrBtn.addEventListener('click', gate);
  }
})();
