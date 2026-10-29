/* DaneshRah — progressive UI interactions.
   No framework, no inline event handlers, no HTML injection. */
(function () {
  'use strict';

  var root = document.documentElement;
  var utils = window.DaneshRahUtils || {};
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function fallbackNormalizeFa(value) {
    var s = (value || '').toString().toLowerCase();
    s = s.replace(/[\u200c\u200b\u200d\ufeff\u00a0]/g, ' ');
    s = s.replace(/[\u064b-\u0652\u0670]/g, '').replace(/\u0640/g, '');
    s = s.replace(/\u0643/g, '\u06a9').replace(/\u064a/g, '\u06cc').replace(/\u0649/g, '\u06cc');
    s = s.replace(/[\u0622\u0623\u0625]/g, '\u0627').replace(/\u0624/g, '\u0648');
    s = s.replace(/[\u06f0-\u06f9]/g, function (d) { return String(d.charCodeAt(0) - 0x06f0); });
    s = s.replace(/[\u0660-\u0669]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); });
    return s.replace(/\s+/g, ' ').trim();
  }

  var normalizeFa = typeof utils.normalizeFa === 'function' ? utils.normalizeFa : fallbackNormalizeFa;
  var copyText = typeof utils.copyText === 'function'
    ? utils.copyText
    : function () { return Promise.resolve(false); };

  function readJSON(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw == null ? fallback : JSON.parse(raw);
    } catch (e) {
      return fallback;
    }
  }

  function writeJSON(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) { /* storage disabled */ }
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

  function faNumber(value) {
    try {
      return Number(value).toLocaleString('fa-IR');
    } catch (e) {
      return String(value);
    }
  }

  /* ------------------------------------------------------------------
     Theme
     ------------------------------------------------------------------ */
  function currentTheme() {
    try {
      var stored = localStorage.getItem('daneshrah-theme');
      if (stored === 'dark' || stored === 'light') return stored;
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
    } catch (e) { /* ignore */ }
    return 'light';
  }

  function applyTheme(theme, persist) {
    if (theme !== 'dark' && theme !== 'light') theme = 'light';
    root.setAttribute('data-theme', theme);
    if (persist) {
      try { localStorage.setItem('daneshrah-theme', theme); } catch (e) { /* ignore */ }
    }
    var meta = document.querySelector('meta[data-theme-color]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#111815' : '#f4efe5');
    document.querySelectorAll('[data-theme-btn]').forEach(function (button) {
      var label = theme === 'dark' ? 'فعال کردن تم روشن' : 'فعال کردن تم تیره';
      button.setAttribute('aria-label', label);
      button.setAttribute('title', label);
    });
  }

  applyTheme(currentTheme(), false);

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-theme-btn]');
    if (!button) return;
    applyTheme(root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark', true);
  });

  /* ------------------------------------------------------------------
     Flag images: keep the emoji fallback if a remote SVG/PNG fails
     ------------------------------------------------------------------ */
  document.addEventListener('error', function (event) {
    var image = event.target;
    if (!image || image.tagName !== 'IMG') return;
    var frame = image.closest('.cc-flag, .country-emblem-flag, .flag-inline');
    if (frame) {
      frame.classList.add('flag-failed');
      image.setAttribute('aria-hidden', 'true');
    }
  }, true);

  /* ------------------------------------------------------------------
     Mobile navigation disclosure
     ------------------------------------------------------------------ */
  var menuButton = document.querySelector('[data-menu-btn]');
  var navLinks = document.querySelector('[data-nav-links]');

  function setMenu(open, returnFocus) {
    if (!navLinks || !menuButton) return;
    navLinks.classList.toggle('is-open', open);
    menuButton.setAttribute('aria-expanded', open ? 'true' : 'false');
    menuButton.setAttribute('aria-label', open ? 'بستن منو' : 'باز کردن منو');
    if (open) {
      var first = navLinks.querySelector('a');
      if (first) first.focus();
    } else if (returnFocus) {
      menuButton.focus();
    }
  }

  if (menuButton && navLinks) {
    menuButton.addEventListener('click', function () {
      var open = menuButton.getAttribute('aria-expanded') !== 'true';
      setMenu(open, false);
    });

    navLinks.addEventListener('click', function (event) {
      if (event.target.closest('a')) setMenu(false, false);
    });

    document.addEventListener('click', function (event) {
      if (!navLinks.classList.contains('is-open')) return;
      if (event.target.closest('[data-nav-links], [data-menu-btn]')) return;
      setMenu(false, false);
    });

    window.addEventListener('resize', function () {
      if (window.innerWidth > 920 && navLinks.classList.contains('is-open')) {
        setMenu(false, false);
      }
    });
  }

  /* ------------------------------------------------------------------
     Header search disclosure
     ------------------------------------------------------------------ */
  var searchDetails = document.querySelector('[data-search-details]');
  var searchSummary = searchDetails ? searchDetails.querySelector('summary') : null;
  var headerSearch = searchDetails ? searchDetails.querySelector('[data-global-search]') : null;

  if (searchDetails) {
    function setSearchLabel() {
      if (!searchSummary) return;
      searchSummary.setAttribute('aria-label', searchDetails.open ? 'بستن جست‌وجو' : 'باز کردن جست‌وجو');
    }
    setSearchLabel();
    searchDetails.addEventListener('toggle', function () {
      setSearchLabel();
      if (searchDetails.open && headerSearch) {
        headerSearch.focus();
        headerSearch.select();
      }
    });

    document.addEventListener('click', function (event) {
      if (!searchDetails.open) return;
      if (event.target.closest('[data-search-details]')) return;
      searchDetails.open = false;
    });
  }

  /* ------------------------------------------------------------------
     Keyboard shortcuts
     ------------------------------------------------------------------ */
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      if (searchDetails && searchDetails.open) {
        searchDetails.open = false;
        if (searchSummary) searchSummary.focus();
        return;
      }
      if (navLinks && navLinks.classList.contains('is-open')) {
        setMenu(false, true);
      }
      return;
    }

    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
    var activeTag = document.activeElement ? document.activeElement.tagName : '';
    if (/INPUT|TEXTAREA|SELECT/.test(activeTag)) return;

    event.preventDefault();
    var candidates = Array.prototype.slice.call(document.querySelectorAll('[data-global-search]'));
    var visible = candidates.filter(function (input) {
      return input.offsetParent !== null && !input.disabled;
    })[0];
    if (visible) {
      visible.focus();
      visible.select();
    } else if (searchDetails && headerSearch) {
      searchDetails.open = true;
      headerSearch.focus();
      headerSearch.select();
    }
  });

  /* ------------------------------------------------------------------
     Country directory: text filter, region pills and favorites
     ------------------------------------------------------------------ */
  var countrySearch = document.querySelector('[data-country-search]');
  var countryCards = Array.prototype.slice.call(document.querySelectorAll('[data-country-card]'));
  var regionPills = Array.prototype.slice.call(document.querySelectorAll('[data-region-pill]'));
  var gridStatus = document.querySelector('[data-grid-status]');
  var activeRegion = 'all';

  function getFavorites() {
    var value = readJSON('daneshrah-favs', []);
    if (!Array.isArray(value)) return [];
    return value.filter(function (item) { return typeof item === 'string' && item.length; });
  }

  function filterCountries() {
    if (!countryCards.length) return;
    var term = normalizeFa(countrySearch ? countrySearch.value : '');
    var visible = 0;
    countryCards.forEach(function (card) {
      var name = normalizeFa(card.dataset.name || '');
      var region = card.dataset.region || '';
      var regionMatches = activeRegion === 'all'
        || region === activeRegion
        || (activeRegion === 'fav' && card.dataset.fav === '1');
      var termMatches = !term || name.indexOf(term) !== -1;
      var show = regionMatches && termMatches;
      card.hidden = !show;
      if (show) visible += 1;
    });

    var empty = document.querySelector('[data-no-result]');
    if (empty) empty.hidden = visible !== 0;

    if (gridStatus) {
      if (!term && activeRegion === 'all') {
        gridStatus.textContent = '';
      } else if (activeRegion === 'fav') {
        gridStatus.textContent = faNumber(visible) + ' کشور ذخیره‌شده نمایش داده می‌شود';
      } else {
        gridStatus.textContent = faNumber(visible) + ' از ' + faNumber(countryCards.length) + ' کشور';
      }
    }
  }

  function paintFavorites() {
    if (!countryCards.length) return;
    var favorites = getFavorites();
    document.querySelectorAll('[data-fav-btn]').forEach(function (button) {
      var code = button.dataset.favBtn;
      var active = favorites.indexOf(code) !== -1;
      var card = button.closest('[data-country-card]');
      var name = card ? (card.querySelector('.cc-name') || {}).textContent : code;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
      button.setAttribute('aria-label', active
        ? 'حذف ' + name + ' از علاقه‌مندی‌ها'
        : 'ذخیره‌ی ' + name + ' در علاقه‌مندی‌ها');
      button.setAttribute('title', active ? 'حذف از علاقه‌مندی‌ها' : 'ذخیره در علاقه‌مندی‌ها');
      if (card) {
        card.dataset.fav = active ? '1' : '0';
        card.classList.toggle('is-fav', active);
      }
    });
    var count = document.querySelector('[data-fav-count]');
    if (count) count.textContent = favorites.length ? '(' + faNumber(favorites.length) + ')' : '';
  }

  if (countrySearch) countrySearch.addEventListener('input', filterCountries);

  regionPills.forEach(function (pill) {
    pill.addEventListener('click', function () {
      regionPills.forEach(function (other) {
        other.classList.remove('active');
        other.setAttribute('aria-pressed', 'false');
      });
      pill.classList.add('active');
      pill.setAttribute('aria-pressed', 'true');
      activeRegion = pill.dataset.regionPill || 'all';
      filterCountries();
    });
  });

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-fav-btn]');
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    var favorites = getFavorites();
    var code = button.dataset.favBtn;
    var index = favorites.indexOf(code);
    if (index === -1) favorites.push(code);
    else favorites.splice(index, 1);
    writeJSON('daneshrah-favs', favorites);
    paintFavorites();
    if (activeRegion === 'fav') filterCountries();
    var count = document.querySelector('[data-fav-count]');
    if (count) count.setAttribute('aria-live', 'polite');
  });

  paintFavorites();
  filterCountries();

  /* ------------------------------------------------------------------
     Reading progress, active table of contents, back-to-top
     ------------------------------------------------------------------ */
  var progress = document.querySelector('[data-read-progress]');
  var toTop = document.querySelector('[data-to-top]');
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('[data-toc-link]'));
  var guideItems = Array.prototype.slice.call(document.querySelectorAll('[data-guide-item]'));
  var scrollQueued = false;

  function updateScrollUI() {
    var doc = document.documentElement;
    var scrollTop = window.scrollY || doc.scrollTop || 0;
    var max = Math.max(1, doc.scrollHeight - window.innerHeight);

    if (progress) {
      var ratio = Math.min(1, Math.max(0, scrollTop / max));
      progress.style.transform = 'scaleX(' + ratio + ')';
    }

    if (toTop) toTop.classList.toggle('is-visible', scrollTop > 650);

    if (tocLinks.length && guideItems.length) {
      var current = null;
      guideItems.forEach(function (item) {
        if (item.getBoundingClientRect().top <= 150) current = item.id;
      });
      tocLinks.forEach(function (link) {
        var active = current !== null && link.getAttribute('href') === '#' + current;
        link.classList.toggle('is-active', active);
        if (active) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    }
    scrollQueued = false;
  }

  function onScroll() {
    if (scrollQueued) return;
    scrollQueued = true;
    window.requestAnimationFrame(updateScrollUI);
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  updateScrollUI();

  if (toTop) {
    toTop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
      var main = document.getElementById('main');
      if (main) main.focus({ preventScroll: true });
    });
  }

  /* ------------------------------------------------------------------
     Guide: accordion, deep links, copy, print
     ------------------------------------------------------------------ */
  function setGuideOpen(item, open) {
    if (!item) return;
    var head = item.querySelector('[data-guide-head]');
    var bodyId = head ? head.getAttribute('aria-controls') : '';
    var body = bodyId ? document.getElementById(bodyId) : null;
    item.classList.toggle('is-collapsed', !open);
    if (head) head.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (body) body.hidden = !open;
  }

  document.addEventListener('click', function (event) {
    var head = event.target.closest('[data-guide-head]');
    if (head) {
      if (event.target.closest('a, [data-copy-link]')) return;
      var item = head.closest('[data-guide-item]');
      if (item) setGuideOpen(item, head.getAttribute('aria-expanded') === 'false');
      return;
    }

    var copyButton = event.target.closest('[data-copy-link]');
    if (copyButton) {
      event.preventDefault();
      event.stopPropagation();
      var hash = copyButton.dataset.copyLink || '';
      var url = window.location.href.split('#')[0] + hash;
      var label = copyButton.querySelector('[data-copy-label]');
      var status = document.querySelector('[data-copy-status]');
      copyText(url).then(function (ok) {
        if (label) label.textContent = ok ? 'کپی شد' : 'کپی نشد';
        if (status) status.textContent = ok ? 'پیوند این نکته کپی شد.' : 'مرورگر اجازه‌ی کپی نداد؛ نشانی را دستی از نوار آدرس بردار.';
        window.setTimeout(function () {
          if (label) label.textContent = 'کپی پیوند';
        }, ok ? 1800 : 3200);
      });
      return;
    }

    if (event.target.closest('[data-print]')) {
      window.print();
    }
  });

  tocLinks.forEach(function (link) {
    link.addEventListener('click', function () {
      var hash = link.getAttribute('href') || '';
      var target = hash ? document.getElementById(hash.slice(1)) : null;
      if (target && target.hasAttribute('data-guide-item')) setGuideOpen(target, true);
    });
  });

  /* A direct link to a collapsed item should still reveal it. */
  if (guideItems.length && window.location.hash) {
    var initial = document.getElementById(window.location.hash.slice(1));
    if (initial && initial.hasAttribute('data-guide-item')) setGuideOpen(initial, true);
  }

  /* ------------------------------------------------------------------
     Checklist: local progress
     ------------------------------------------------------------------ */
  var checklistItems = Array.prototype.slice.call(document.querySelectorAll('[data-check-item]'));
  if (checklistItems.length) {
    var CHECK_KEY = 'daneshrah-checklist-v1';
    var checklistState = readJSON(CHECK_KEY, {});
    if (!checklistState || typeof checklistState !== 'object' || Array.isArray(checklistState)) {
      checklistState = {};
    }

    function cleanChecklistState() {
      Object.keys(checklistState).forEach(function (key) {
        if (checklistState[key] !== true) delete checklistState[key];
      });
    }

    function paintChecklist(announcement) {
      var done = 0;
      checklistItems.forEach(function (item) {
        var key = item.dataset.checkItem || '';
        var input = item.querySelector('[data-check-input]');
        var on = checklistState[key] === true;
        if (input && input.checked !== on) input.checked = on;
        item.classList.toggle('is-done', on);
        if (on) done += 1;
      });

      var total = checklistItems.length;
      var pct = total ? Math.round((done / total) * 100) : 0;
      var bar = document.querySelector('[data-check-bar]');
      var text = document.querySelector('[data-check-text]');
      var progressbar = document.querySelector('[data-check-progress]');
      var reset = document.querySelector('[data-check-reset]');
      var celebrate = document.querySelector('[data-celebrate]');
      var status = document.querySelector('[data-check-status]');
      var label = faNumber(done) + ' از ' + faNumber(total) + ' قدم';

      if (bar) bar.style.width = pct + '%';
      if (text) text.textContent = label;
      if (progressbar) {
        progressbar.setAttribute('aria-valuenow', String(pct));
        progressbar.setAttribute('aria-valuetext', label + '، ' + faNumber(pct) + ' درصد');
      }
      if (reset) reset.disabled = done === 0;
      if (celebrate) celebrate.hidden = pct !== 100;
      if (status && announcement) status.textContent = announcement;
    }

    cleanChecklistState();

    checklistItems.forEach(function (item) {
      var input = item.querySelector('[data-check-input]');
      if (!input) return;
      input.addEventListener('change', function () {
        var key = item.dataset.checkItem || '';
        if (input.checked) checklistState[key] = true;
        else delete checklistState[key];
        writeJSON(CHECK_KEY, checklistState);
        var title = item.querySelector('.check-title');
        var name = title ? title.textContent.trim() : '';
        paintChecklist(input.checked ? '«' + name + '» انجام شد.' : '«' + name + '» از انجام‌شده‌ها برداشته شد.');
      });
    });

    var resetButton = document.querySelector('[data-check-reset]');
    if (resetButton) {
      resetButton.addEventListener('click', function () {
        var checked = checklistItems.filter(function (item) {
          var input = item.querySelector('[data-check-input]');
          return input && input.checked;
        }).length;
        if (checked && !window.confirm('همه‌ی تیک‌های چک‌لیست پاک شوند؟')) return;
        checklistState = {};
        try { localStorage.removeItem(CHECK_KEY); } catch (e) { /* ignore */ }
        paintChecklist('پیشرفت چک‌لیست پاک شد.');
        resetButton.focus();
      });
    }

    paintChecklist('');
  }

  /* ------------------------------------------------------------------
     Emergency table filter
     ------------------------------------------------------------------ */
  var emergencySearch = document.querySelector('[data-em-search]');
  if (emergencySearch) {
    var emergencyRows = Array.prototype.slice.call(document.querySelectorAll('[data-em-row]'));
    var emergencyCount = document.querySelector('[data-em-count]');
    var emergencyEmpty = document.querySelector('[data-em-empty]');

    var filterEmergency = function () {
      var term = normalizeFa(emergencySearch.value);
      var visible = 0;
      emergencyRows.forEach(function (row) {
        var show = !term || normalizeFa(row.dataset.search || '').indexOf(term) !== -1;
        row.hidden = !show;
        if (show) visible += 1;
      });
      if (emergencyCount) {
        emergencyCount.textContent = faNumber(visible) + ' از ' + faNumber(emergencyRows.length) + ' کشور نمایش داده می‌شود';
      }
      if (emergencyEmpty) emergencyEmpty.hidden = visible !== 0;
    };

    emergencySearch.addEventListener('input', filterEmergency);
    filterEmergency();
  }
})();
