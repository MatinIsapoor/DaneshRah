/* DaneshRah — UI interactions (vanilla JS, no framework) */
(function () {
  'use strict';
  var root = document.documentElement;

  /* ---------- Persian-aware normalize (mirrors server normalize_fa) ---------- */
  function normalizeFa(s) {
    s = (s || '').toString();
    s = s.replace(/[\u200c\u200b\u200d\ufeff\u00a0]/g, ' ');
    s = s.replace(/[ً-ٰٟ]/g, '');
    s = s.replace(/\u0640/g, '');
    s = s.replace(/\u0643/g, '\u06a9').replace(/\u064a/g, '\u06cc').replace(/\u0649/g, '\u06cc');
    s = s.replace(/ة/g, 'ه').replace(/ؤ/g, 'و').replace(/[إأآ]/g, 'ا');
    s = s.toLowerCase();
    s = s.replace(/[۰-۹٠-٩]/g, function (d) {
      var fa = '۰۱۲۳۴۵۶۷۸۹'.indexOf(d);
      if (fa !== -1) return String(fa);
      return String('٠١٢٣٤٥٦٧٨٩'.indexOf(d));
    });
    return s.replace(/\s+/g, ' ').trim();
  }

  /* ---------- storage (DaneshRah keys, migrate old isg-* silently) ---------- */
  function readJSON(key, fallback) {
    try {
      var v = localStorage.getItem(key);
      return v == null ? fallback : JSON.parse(v);
    } catch (e) { return fallback; }
  }
  function migrateKey(newKey, oldKey) {
    try {
      if (localStorage.getItem(newKey) == null && localStorage.getItem(oldKey) != null) {
        localStorage.setItem(newKey, localStorage.getItem(oldKey));
      }
    } catch (e) { /* private mode */ }
  }
  migrateKey('daneshrah-theme', 'isg-theme');
  migrateKey('daneshrah-favs', 'isg-favs');
  migrateKey('daneshrah-checklist-v1', 'isg-checklist-v1');

  /* ---------- theme ---------- */
  function currentTheme() {
    try {
      return localStorage.getItem('daneshrah-theme') ||
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    } catch (e) { return 'light'; }
  }
  function applyTheme(t) {
    root.setAttribute('data-theme', t);
    try { localStorage.setItem('daneshrah-theme', t); } catch (e) {}
    document.querySelectorAll('[data-theme-btn]').forEach(function (b) {
      b.innerHTML = t === 'dark' ? sunIcon() : moonIcon();
      b.setAttribute('aria-label', t === 'dark' ? 'تغییر به حالت روشن' : 'تغییر به حالت تیره');
    });
  }
  function moonIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>';
  }
  function sunIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  }
  applyTheme(currentTheme());
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-theme-btn]');
    if (b) applyTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });

  /* ---------- mobile nav ---------- */
  var menuBtn = document.querySelector('[data-menu-btn]');
  var navLinks = document.querySelector('[data-nav-links]');
  function setMenu(open) {
    if (!navLinks) return;
    navLinks.classList.toggle('open', open);
    if (menuBtn) {
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      menuBtn.setAttribute('aria-label', open ? 'بستن منو' : 'باز کردن منو');
    }
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-menu-btn]');
    if (b) setMenu(!navLinks.classList.contains('open'));
  });
  // Keyboard: Escape closes menu / blurs; Enter/Space activates custom toggles.
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (navLinks && navLinks.classList.contains('open')) { setMenu(false); if (menuBtn) menuBtn.focus(); return; }
      if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
      return;
    }
    if ((e.key === 'Enter' || e.key === ' ') && e.target && e.target.closest) {
      var t = e.target.closest('[data-guide-head]') || e.target.closest('[data-check-item]');
      // Fav buttons are native <button> now — no manual handling needed.
      if (t) { e.preventDefault(); t.click(); }
    }
  });

  /* ---------- reveal on scroll ---------- */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
    });
  }, { threshold: 0.08 });
  document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });

  /* ---------- animated counters ---------- */
  var cio = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      var el = en.target, target = parseInt(el.dataset.count || '0', 10), t0 = null;
      function tick(t) {
        if (!t0) t0 = t;
        var p = Math.min(1, (t - t0) / 1200);
        el.textContent = Math.round(target * (0.2 + 0.8 * (1 - Math.pow(1 - p, 3)))).toLocaleString('fa-IR');
        if (p < 1) requestAnimationFrame(tick);
        else el.textContent = target.toLocaleString('fa-IR');
      }
      requestAnimationFrame(tick);
      cio.unobserve(el);
    });
  }, { threshold: 0.4 });
  document.querySelectorAll('[data-count]').forEach(function (el) { cio.observe(el); });

  /* ---------- homepage: filter + search countries ---------- */
  var q = document.querySelector('[data-country-search]');
  var pills = document.querySelectorAll('[data-region-pill]');
  var gridStatus = document.querySelector('[data-grid-status]');
  var activeRegion = 'all';
  function filterCountries() {
    var term = normalizeFa(q && q.value || '');
    var visible = 0, total = 0;
    document.querySelectorAll('[data-country-card]').forEach(function (card) {
      total++;
      var name = normalizeFa(card.dataset.name || '');
      var region = card.dataset.region || '';
      var okRegion = activeRegion === 'all' || region === activeRegion || (activeRegion === 'fav' && card.dataset.fav === '1');
      var okTerm = !term || name.indexOf(term) !== -1;
      var show = okRegion && okTerm;
      card.style.display = show ? '' : 'none';
      // Hide from keyboard/AT when filtered out.
      if (show) { card.removeAttribute('tabindex'); visible++; }
    });
    var empty = document.querySelector('[data-no-result]');
    if (empty) empty.style.display = visible ? 'none' : '';
    if (gridStatus) {
      gridStatus.textContent = term || activeRegion !== 'all'
        ? visible.toLocaleString('fa-IR') + ' کشور از ' + total.toLocaleString('fa-IR')
        : '';
    }
  }
  if (q) q.addEventListener('input', filterCountries);
  pills.forEach(function (p) {
    p.addEventListener('click', function () {
      pills.forEach(function (x) { x.classList.remove('active'); x.setAttribute('aria-pressed', 'false'); });
      p.classList.add('active');
      p.setAttribute('aria-pressed', 'true');
      activeRegion = p.dataset.regionPill;
      filterCountries();
    });
  });

  /* ---------- favorites ---------- */
  function getFavs() { return readJSON('daneshrah-favs', []); }
  function paintFavs() {
    var favs = getFavs();
    document.querySelectorAll('[data-fav-btn]').forEach(function (b) {
      var on = favs.indexOf(b.dataset.favBtn) !== -1;
      b.classList.toggle('on', on);
      b.textContent = on ? '★' : '☆';
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      var card = b.closest('[data-country-card]');
      if (card) card.dataset.fav = on ? '1' : '0';
    });
    var count = document.querySelector('[data-fav-count]');
    if (count) count.textContent = favs.length ? '(' + favs.length.toLocaleString('fa-IR') + ')' : '';
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-fav-btn]');
    if (!b) return;
    e.preventDefault(); e.stopPropagation();
    var favs = getFavs(), code = b.dataset.favBtn;
    var i = favs.indexOf(code);
    if (i === -1) favs.push(code); else favs.splice(i, 1);
    try { localStorage.setItem('daneshrah-favs', JSON.stringify(favs)); } catch (err) {}
    paintFavs();
    if (activeRegion === 'fav') filterCountries();
  });
  paintFavs();
  filterCountries();

  /* ---------- "/" focuses search ---------- */
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && !(e.ctrlKey || e.metaKey || e.altKey)) {
      var tag = document.activeElement ? document.activeElement.tagName : '';
      if (!/INPUT|TEXTAREA/.test(tag)) {
        var s = document.querySelector('[data-country-search]') || document.querySelector('[data-global-search]');
        if (s) { e.preventDefault(); s.focus(); }
      }
    }
  });

  /* ---------- reading progress + TOC + back-to-top ---------- */
  var prog = document.querySelector('[data-read-progress]');
  var toTop = document.querySelector('[data-to-top]');
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('[data-toc-link]'));
  function onScroll() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    if (prog) prog.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
    if (toTop) toTop.classList.toggle('show', h.scrollTop > 600);
    if (tocLinks.length) {
      var cur = null;
      document.querySelectorAll('[data-guide-item]').forEach(function (sec) {
        if (sec.getBoundingClientRect().top < 160) cur = sec.id;
      });
      tocLinks.forEach(function (a) {
        var active = a.getAttribute('href') === '#' + cur;
        a.classList.toggle('active', active);
        if (active) a.setAttribute('aria-current', 'true');
        else a.removeAttribute('aria-current');
      });
    }
  }
  document.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  if (toTop) toTop.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });

  /* ---------- guide accordion + copy link ---------- */
  function toggleGuide(head) {
    var item = head.closest('[data-guide-item]');
    if (!item) return;
    item.classList.toggle('closed');
    head.setAttribute('aria-expanded', item.classList.contains('closed') ? 'false' : 'true');
  }
  document.addEventListener('click', function (e) {
    var head = e.target.closest('[data-guide-head]');
    if (head) {
      if (e.target.closest('[data-copy-link]') || e.target.closest('a')) return;
      toggleGuide(head);
      return;
    }
    var copy = e.target.closest('[data-copy-link]');
    if (copy) {
      e.preventDefault(); e.stopPropagation();
      var url = location.origin + location.pathname + copy.dataset.copyLink;
      var done = function () {
        copy.textContent = '✓ کپی شد';
        setTimeout(function () { copy.textContent = 'کپی لینک'; }, 1500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, done);
      } else { done(); }
      return;
    }
    var print = e.target.closest('[data-print]');
    if (print) window.print();
  });

  /* ---------- checklist ---------- */
  var boxes = document.querySelectorAll('[data-check-item]');
  if (boxes.length) {
    var KEY = 'daneshrah-checklist-v1';
    var state = readJSON(KEY, {});
    function paintCheck() {
      var done = 0;
      boxes.forEach(function (box) {
        var id = box.dataset.checkItem;
        var on = !!state[id];
        box.classList.toggle('done', on);
        box.querySelector('.check-box').textContent = on ? '✓' : '';
        box.setAttribute('aria-checked', on ? 'true' : 'false');
        if (on) done++;
      });
      var pct = Math.round((done / boxes.length) * 100);
      var bar = document.querySelector('[data-check-bar]');
      var txt = document.querySelector('[data-check-text]');
      var wrap = document.querySelector('[data-check-progress]');
      if (bar) bar.style.width = pct + '%';
      if (wrap) wrap.setAttribute('aria-valuenow', String(pct));
      if (txt) txt.textContent = done.toLocaleString('fa-IR') + ' از ' + boxes.length.toLocaleString('fa-IR') + ' قدم (' + pct.toLocaleString('fa-IR') + '٪)';
      var cel = document.querySelector('[data-celebrate]');
      if (cel) cel.classList.toggle('show', pct === 100);
    }
    boxes.forEach(function (box) {
      box.addEventListener('click', function () {
        var id = box.dataset.checkItem;
        state[id] = !state[id];
        try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (err) {}
        paintCheck();
      });
    });
    var reset = document.querySelector('[data-check-reset]');
    if (reset) reset.addEventListener('click', function () {
      state = {}; try { localStorage.removeItem(KEY); } catch (err) {}
      paintCheck();
    });
    paintCheck();
  }

  /* ---------- emergency table filter ---------- */
  var ef = document.querySelector('[data-em-search]');
  if (ef) {
    var emCount = document.querySelector('[data-em-count]');
    ef.addEventListener('input', function () {
      var t = normalizeFa(ef.value.trim());
      var visible = 0, total = 0;
      document.querySelectorAll('[data-em-row]').forEach(function (r) {
        total++;
        var hay = normalizeFa(r.dataset.search || '');
        var show = !t || hay.indexOf(t) !== -1;
        r.style.display = show ? '' : 'none';
        if (show) visible++;
      });
      if (emCount) emCount.textContent = visible.toLocaleString('fa-IR') + ' کشور از ' + total.toLocaleString('fa-IR');
    });
  }

  /* ---------- hero search submits to /search ---------- */
  var hs = document.querySelector('[data-hero-search]');
  if (hs) {
    hs.addEventListener('submit', function (e) {
      var inp = hs.querySelector('input');
      if (!inp.value.trim()) { e.preventDefault(); inp.focus(); }
    });
  }
})();
