/* Node unit tests for static/utils.js (clipboard + Persian normalization).
   Run with:  node --test tests/js_utils.test.js

   Persian literals are written as \u escapes so the expectations stay
   readable regardless of the editor's bidi handling. */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

const utils = require(path.join(__dirname, '..', 'static', 'utils.js'));

const SIM_KART_ZWNJ = 'سیم‌کارت';   // سیم‌کارت
const SIM_KART_SPACE = 'سیم کارت';    // سیم کارت
const SIM_KART_PLAIN = 'سیمکارت';     // سیمکارت
const ARABIC_YEH_KAF = 'سيم كارت'; // سيم كارت
const WADI_AH = 'ودیعه';          // ودیعه
const KETAB = 'کتاب';              // کتاب
const KETAB_AR = 'كتاب';           // كتاب
const FA_911 = '۹۱۱';              // ۹۱۱
const AR_911 = '٩١١';              // ٩١١

function overrideGlobal(name, value) {
  Object.defineProperty(globalThis, name, {
    value: value,
    configurable: true,
    writable: true,
  });
}

function makeDocument(execResult) {
  const state = { execCalls: 0, bodyChildren: [], focusCalls: 0, created: [] };
  const body = {
    appendChild(el) {
      el.parentNode = body;
      state.bodyChildren.push(el);
    },
    removeChild(el) {
      const i = state.bodyChildren.indexOf(el);
      if (i !== -1) state.bodyChildren.splice(i, 1);
      el.parentNode = null;
    },
  };
  const doc = {
    body: body,
    activeElement: {
      focus() { state.focusCalls += 1; },
    },
    createElement(tag) {
      const el = {
        tag: tag,
        value: '',
        style: {},
        attributes: {},
        parentNode: null,
        setAttribute(k, v) { this.attributes[k] = v; },
        select() { el.selected = true; },
        setSelectionRange() {},
      };
      state.created.push(el);
      return el;
    },
    execCommand(cmd) {
      state.execCalls += 1;
      assert.strictEqual(cmd, 'copy');
      return execResult;
    },
  };
  return { doc: doc, state: state };
}

test('normalizeFa unifies Persian/Arabic variants', () => {
  const a = utils.normalizeFa(SIM_KART_ZWNJ);
  assert.strictEqual(a, utils.normalizeFa(SIM_KART_SPACE), 'ZWNJ behaves like a space');
  assert.strictEqual(a.replace(/\s/g, ''), utils.normalizeFa(SIM_KART_PLAIN),
    'the space-less spelling matches too');
  assert.strictEqual(utils.normalizeFa(ARABIC_YEH_KAF).replace(/\s/g, ''),
    utils.normalizeFa(SIM_KART_PLAIN).replace(/\s/g, ''),
    'Arabic yeh/kaf are folded');
});

test('normalizeFa strips tashkeel, tatweel and converts digits', () => {
  assert.strictEqual(utils.normalizeFa('وُدیعَه'), WADI_AH);
  assert.strictEqual(utils.normalizeFa('وــدیعه'), WADI_AH);
  assert.strictEqual(utils.normalizeFa(FA_911), '911');
  assert.strictEqual(utils.normalizeFa(AR_911), '911');
  assert.strictEqual(utils.normalizeFa(KETAB), utils.normalizeFa(KETAB_AR));
});

test('copyText reports success when the Clipboard API works', async () => {
  const { doc, state } = makeDocument(false);
  overrideGlobal('document', doc);
  overrideGlobal('navigator', {
    clipboard: { writeText: () => Promise.resolve() },
  });
  assert.strictEqual(await utils.copyText('https://example.test/#item-1'), true);
  assert.strictEqual(state.execCalls, 0, 'fallback must not run when the API succeeds');
});

test('copyText falls back to execCommand when the Clipboard API rejects', async () => {
  const { doc, state } = makeDocument(true);
  overrideGlobal('document', doc);
  overrideGlobal('navigator', {
    clipboard: { writeText: () => Promise.reject(new Error('denied')) },
  });
  assert.strictEqual(await utils.copyText('hello'), true);
  assert.strictEqual(state.execCalls, 1);
  assert.strictEqual(state.bodyChildren.length, 0, 'temporary textarea must be removed');
  assert.strictEqual(state.focusCalls, 1, 'focus must be restored');
});

test('copyText reports failure when both mechanisms fail', async () => {
  const { doc, state } = makeDocument(false);
  overrideGlobal('document', doc);
  overrideGlobal('navigator', {
    clipboard: { writeText: () => Promise.reject(new Error('denied')) },
  });
  assert.strictEqual(await utils.copyText('hello'), false);
  assert.strictEqual(state.execCalls, 1);
});

test('copyText reports failure without a clipboard API', async () => {
  const { doc, state } = makeDocument(false);
  overrideGlobal('document', doc);
  overrideGlobal('navigator', {});
  assert.strictEqual(await utils.copyText('hello'), false);
  assert.strictEqual(state.execCalls, 1);
});

test('copyText survives a throwing execCommand', async () => {
  const { doc } = makeDocument(false);
  doc.execCommand = () => { throw new Error('not allowed'); };
  overrideGlobal('document', doc);
  overrideGlobal('navigator', {});
  assert.strictEqual(await utils.copyText('hello'), false);
});
