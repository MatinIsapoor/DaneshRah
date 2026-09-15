/* Iranian Student Guide — UI interactions */
(function () {
  'use strict';
  var root = document.documentElement;

  /* ---------- theme ---------- */
  function currentTheme() {
    return localStorage.getItem('isg-theme') ||
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }
  function applyTheme(t) {
    root.setAttribute('data-theme', t);
    localStorage.setItem('isg-theme', t);
    document.querySelectorAll('[data-theme-btn]').forEach(function (b) {
      b.innerHTML = t === 'dark' ? sunIcon() : moonIcon();
      b.setAttribute('aria-label', t === 'dark' ? 'حالت روشن' : 'حالت تیره');
    });
  }
  function moonIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>';
  }
  function sunIcon() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  }
  applyTheme(currentTheme());
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-theme-btn]');
    if (b) applyTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });

  /* ---------- mobile nav ---------- */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-menu-btn]');
    if (b) document.querySelector('[data-nav-links]').classList.toggle('open');
  });
  // Escape closes the mobile menu; activating toggleables via keyboard
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var nav = document.querySelector('[data-nav-links]');
      if (nav) nav.classList.remove('open');
      if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
      return;
    }
    if ((e.key === 'Enter' || e.key === ' ') && e.target) {
      var t = e.target.closest
        ? (e.target.closest('[data-fav-btn]') || e.target.closest('[data-guide-head]') || e.target.closest('[data-check-item]'))
        : null;
      if (t) {
        e.preventDefault();
        t.click();
      }
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
  var activeRegion = 'all';
  function filterCountries() {
    var term = (q && q.value || '').trim();
    document.querySelectorAll('[data-country-card]').forEach(function (card) {
      var name = card.dataset.name || '';
      var region = card.dataset.region || '';
      var okRegion = activeRegion === 'all' || region === activeRegion || (activeRegion === 'fav' && card.dataset.fav === '1');
      var okTerm = !term || name.indexOf(term) !== -1;
      card.style.display = okRegion && okTerm ? '' : 'none';
    });
    var visible = document.querySelectorAll('[data-country-card]:not([style*="none"])').length;
    var empty = document.querySelector('[data-no-result]');
    if (empty) empty.style.display = visible ? 'none' : '';
  }
  if (q) q.addEventListener('input', filterCountries);
  pills.forEach(function (p) {
    p.addEventListener('click', function () {
      pills.forEach(function (x) { x.classList.remove('active'); });
      p.classList.add('active');
      activeRegion = p.dataset.regionPill;
      filterCountries();
    });
  });

  /* ---------- favorites ---------- */
  function getFavs() {
    try { return JSON.parse(localStorage.getItem('isg-favs') || '[]'); } catch (e) { return []; }
  }
  function paintFavs() {
    var favs = getFavs();
    document.querySelectorAll('[data-fav-btn]').forEach(function (b) {
      var on = favs.indexOf(b.dataset.favBtn) !== -1;
      b.classList.toggle('on', on);
      b.textContent = on ? '★' : '☆';
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
    localStorage.setItem('isg-favs', JSON.stringify(favs));
    paintFavs();
    if (activeRegion === 'fav') filterCountries();
  });
  paintFavs();

  /* ---------- "/" focuses search ---------- */
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
      var s = document.querySelector('[data-country-search]') || document.querySelector('[data-global-search]');
      if (s) { e.preventDefault(); s.focus(); }
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
      tocLinks.forEach(function (a) { a.classList.toggle('active', a.getAttribute('href') === '#' + cur); });
    }
  }
  document.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  if (toTop) toTop.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });

  /* ---------- guide accordion + copy link ---------- */
  document.addEventListener('click', function (e) {
    var head = e.target.closest('[data-guide-head]');
    if (head) {
      var item = head.closest('[data-guide-item]');
      if (e.target.closest('[data-copy-link]') || e.target.closest('a')) return;
      item.classList.toggle('closed');
      return;
    }
    var copy = e.target.closest('[data-copy-link]');
    if (copy) {
      e.preventDefault(); e.stopPropagation();
      var url = location.origin + location.pathname + copy.dataset.copyLink;
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () {
        copy.textContent = '✓ کپی شد';
        setTimeout(function () { copy.textContent = 'کپی لینک'; }, 1500);
      });
    }
    var print = e.target.closest('[data-print]');
    if (print) window.print();
  });

  /* ---------- checklist ---------- */
  var boxes = document.querySelectorAll('[data-check-item]');
  if (boxes.length) {
    var KEY = 'isg-checklist-v1';
    var state = {};
    try { state = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { state = {}; }
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
      if (bar) bar.style.width = pct + '%';
      if (txt) txt.textContent = done.toLocaleString('fa-IR') + ' از ' + boxes.length.toLocaleString('fa-IR') + ' قدم (' + pct.toLocaleString('fa-IR') + '٪)';
      var cel = document.querySelector('[data-celebrate]');
      if (cel) cel.classList.toggle('show', pct === 100);
    }
    boxes.forEach(function (box) {
      box.addEventListener('click', function () {
        var id = box.dataset.checkItem;
        state[id] = !state[id];
        localStorage.setItem(KEY, JSON.stringify(state));
        paintCheck();
      });
    });
    var reset = document.querySelector('[data-check-reset]');
    if (reset) reset.addEventListener('click', function () {
      state = {}; localStorage.removeItem(KEY); paintCheck();
    });
    paintCheck();
  }

  /* ---------- emergency table filter ---------- */
  var ef = document.querySelector('[data-em-search]');
  if (ef) {
    ef.addEventListener('input', function () {
      var t = ef.value.trim();
      document.querySelectorAll('[data-em-row]').forEach(function (r) {
        r.style.display = !t || (r.dataset.search || '').indexOf(t) !== -1 ? '' : 'none';
      });
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
