/* DaneshRah — shared helpers (no DOM dependencies beyond the clipboard).
   Exposed as window.DaneshRahUtils in the browser and as a CommonJS module
   for the Node-based unit tests. */
(function (global) {
  'use strict';

  /* ---------- Persian-aware normalize (mirrors server normalize_fa) ---------- */
  function normalizeFa(s) {
    s = (s || '').toString();
    s = s.replace(/[\u200c\u200b\u200d\ufeff\u00a0]/g, ' ');
    s = s.replace(/[\u064B-\u0652\u0670]/g, '');
    s = s.replace(/\u0640/g, '');
    s = s.replace(/\u0643/g, '\u06a9').replace(/\u064a/g, '\u06cc').replace(/\u0649/g, '\u06cc');
    s = s.replace(/ة/g, 'ه').replace(/ؤ/g, 'و').replace(/[إأآ]/g, 'ا');
    s = s.toLowerCase();
    s = s.replace(/[۰-۹]/g, function (d) { return String(d.charCodeAt(0) - 0x06F0); });
    s = s.replace(/[٠-٩]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); });
    return s.replace(/\s+/g, ' ').trim();
  }

  /* ---------- clipboard ---------- */
  function legacyCopy(text) {
    var active = null;
    var field = null;
    try {
      if (typeof document === 'undefined') return false;
      field = document.createElement('textarea');
      field.value = text;
      field.setAttribute('readonly', 'readonly');
      field.style.position = 'fixed';
      field.style.top = '-1000px';
      field.style.opacity = '0';
      active = document.activeElement;
      document.body.appendChild(field);
      field.select();
      if (field.setSelectionRange) field.setSelectionRange(0, text.length);
      var ok = false;
      try {
        ok = !!(document.execCommand && document.execCommand('copy'));
      } catch (err) {
        ok = false;
      }
      return ok;
    } catch (err) {
      return false;
    } finally {
      try {
        if (field && field.parentNode) field.parentNode.removeChild(field);
      } catch (err) { /* ignore */ }
      try {
        if (active && active.focus) active.focus();
      } catch (err) { /* ignore */ }
    }
  }

  /* Copy text to the clipboard.
     Resolves with true only when the text really made it to the clipboard;
     falls back to execCommand('copy') when the async Clipboard API fails. */
  function copyText(text) {
    var value = (text == null ? '' : String(text));
    var clip = (typeof navigator !== 'undefined') ? navigator.clipboard : null;
    if (clip && typeof clip.writeText === 'function') {
      try {
        return Promise.resolve(clip.writeText(value)).then(
          function () { return true; },
          function () { return legacyCopy(value); }
        );
      } catch (err) {
        return Promise.resolve(legacyCopy(value));
      }
    }
    return Promise.resolve(legacyCopy(value));
  }

  var api = { normalizeFa: normalizeFa, copyText: copyText, legacyCopy: legacyCopy };

  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    global.DaneshRahUtils = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
