(function() {
  /* ── Timeline scrubber — runs before messages are parsed:
     ticks use pre-calculated fractions, no message DOM needed. ── */
  var tlDataEl = document.getElementById('tl-data');
  var tlData = tlDataEl ? JSON.parse(tlDataEl.textContent) : [];
  if (tlData.length >= 2) {
    var tlInner = document.getElementById('tl-inner');
    var tlTooltip = document.getElementById('tl-tooltip');
    var tlHandle = document.getElementById('tl-handle');
    var tlDragging = false;
    var tlHovering = false;

    function scrollable() {
      return Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    }

    /* Lookup the separator entry at or before a given bar fraction (0–1). */
    function sepAtFrac(frac) {
      var cur = tlData[0];
      for (var i = 0; i < tlData.length; i++) {
        if (tlData[i].frac <= frac) { cur = tlData[i]; } else { break; }
      }
      return cur;
    }
    function labelForSep(sep) {
      var d = new Date(sep.date + 'T00:00:00');
      return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
    }

    /* Map scrollY to bar fraction. */
    function scrollFrac() {
      return Math.min(1, window.scrollY / document.documentElement.scrollHeight);
    }

    /* Sync handle + tooltip position and refresh the label. Called on scroll.
       These are position:absolute/fixed elements — style updates don't affect
       document layout, so this is safe during inertial scroll. */
    function updateScrubber() {
      var frac = scrollFrac();
      var pct = (frac * 100) + '%';
      tlHandle.style.top = pct;
      if (!tlHovering) {
        tlTooltip.style.top = pct;
        tlTooltip.textContent = labelForSep(sepAtFrac(frac));
      }
    }

    tlInner.addEventListener('mousemove', function(e) {
      tlHovering = true;
      var rect = tlInner.getBoundingClientRect();
      var frac = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
      tlTooltip.style.top = (frac * 100) + '%';
      tlTooltip.textContent = labelForSep(sepAtFrac(frac));
    });
    tlInner.addEventListener('mouseleave', function() {
      tlHovering = false;
      updateScrubber();
    });

    tlInner.addEventListener('click', function(e) {
      if (e.target.closest('.tl-tick, #tl-handle')) return;
      var rect = tlInner.getBoundingClientRect();
      var frac = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
      window.scrollTo({ top: frac * scrollable(), behavior: 'smooth' });
    });

    tlHandle.addEventListener('mousedown', function(e) {
      tlDragging = true;
      tlHovering = false;
      e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
      if (!tlDragging) return;
      var rect = tlInner.getBoundingClientRect();
      var frac = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
      window.scrollTo({ top: frac * scrollable() });
    });
    document.addEventListener('mouseup', function() { tlDragging = false; });

    window.addEventListener('scroll', updateScrubber, { passive: true });
    window.addEventListener('resize', updateScrubber, { passive: true });
    /* Defer initial position until full DOM is parsed and scrollHeight is final. */
    document.addEventListener('DOMContentLoaded', updateScrubber);
    window._tlRebuild = updateScrubber;
  }

  /* ── Lightbox ── */
  var lb = document.getElementById('lightbox');
  var lbContent = document.getElementById('lightbox-content');
  var lbIdx = -1;

  function _mediaItems() {
    return Array.from(document.querySelectorAll('.lazy-media'));
  }

  function _optsFromEl(c) {
    return {
      type: c.dataset.type,
      src: c.dataset.src,
      alt: c.dataset.alt || '',
      mime: c.dataset.mime || ''
    };
  }

  function openLightbox(opts, idx) {
    lbContent.innerHTML = '';
    lbIdx = (idx !== undefined) ? idx : -1;
    var el;
    if (opts.type === 'img') {
      el = document.createElement('img');
      el.src = opts.src;
      el.alt = opts.alt || '';
      el.className = 'lightbox-img';
    } else {
      el = document.createElement('video');
      var source = document.createElement('source');
      source.src = opts.src;
      if (opts.mime) source.type = opts.mime;
      el.appendChild(source);
      el.controls = true;
      el.autoplay = true;
      el.className = 'lightbox-video';
    }
    el.addEventListener('click', closeLightbox);
    lbContent.appendChild(el);
    lb.hidden = false;
    lb.focus();
  }

  function closeLightbox() {
    var video = lbContent.querySelector('video');
    if (video) video.pause();
    lb.hidden = true;
    lbContent.innerHTML = '';
    lbIdx = -1;
  }

  window.navigateLightbox = function(dir) {
    var items = _mediaItems();
    if (!items.length) return;
    lbIdx = (lbIdx + dir + items.length) % items.length;
    openLightbox(_optsFromEl(items[lbIdx]), lbIdx);
  };

  /* ── Copy URL to clipboard ── */
  window.copyLink = function(url, btn) {
    function _showCopied() {
      if (!btn) return;
      btn.classList.add('copied');
      setTimeout(function() { btn.classList.remove('copied'); }, 1500);
    }
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(_showCopied, _showCopied);
    } else {
      var ta = document.createElement('textarea');
      ta.value = url;
      ta.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand('copy'); } catch(e) {}
      document.body.removeChild(ta);
      _showCopied();
    }
  };

  /* ── Remote media download ── */
  window.downloadMedia = function(url, filename, btn) {
    if (btn) { btn.disabled = true; btn.textContent = '⧖ …'; }
    fetch(url)
      .then(function(r) { return r.blob(); })
      .then(function(blob) {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function() { URL.revokeObjectURL(a.href); }, 10000);
        if (btn) { btn.disabled = false; btn.textContent = '✓ ' + filename; }
      })
      .catch(function() {
        if (btn) { btn.disabled = false; }
        window.open(url, '_blank');
      });
  };

  document.getElementById('lightbox-backdrop').addEventListener('click', closeLightbox);

  document.addEventListener('keydown', function(e) {
    if (lb.hidden) return;
    if (e.key === 'Escape') { closeLightbox(); }
    else if (e.key === 'ArrowLeft')  { window.navigateLightbox(-1); }
    else if (e.key === 'ArrowRight') { window.navigateLightbox(1); }
  });

  document.addEventListener('click', function(e) {
    var isExpand = !!e.target.closest('.media-expand');
    var c = e.target.closest('.lazy-media');
    if (!c || c.closest('#lightbox')) return;
    if (c.dataset.type === 'video' && !isExpand) return;
    if (c.dataset.type === 'img' && c.dataset.loaded !== '1') return;
    var items = _mediaItems();
    openLightbox(_optsFromEl(c), items.indexOf(c));
  });

  /* ── Media lazy loader ── */
  document.addEventListener('DOMContentLoaded', function() {
    var _EXPAND_SVG = (
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"'
      + ' stroke="currentColor" stroke-width="2.5">'
      + '<polyline points="15 3 21 3 21 9"/>'
      + '<polyline points="9 21 3 21 3 15"/>'
      + '<line x1="21" y1="3" x2="14" y2="10"/>'
      + '<line x1="3" y1="21" x2="10" y2="14"/>'
      + '</svg>'
    );

    var _lazy = Array.from(document.querySelectorAll('.lazy-media'));
    if (!_lazy.length) return;

    var _visible = new Set(); /* message indices of currently intersecting containers */
    var _timer = null;
    var KEEP = 10; /* messages to keep loaded outside the viewport */

    function _msgIdx(c) {
      var row = c.closest('article.message-row');
      return row ? +row.dataset.msgIdx : -1;
    }

    function _loadMedia(c) {
      if (c.dataset.loaded === '1') return;
      c.dataset.loaded = '1';
      if (c.dataset.type === 'img') {
        var img = document.createElement('img');
        img.className = 'lazy-img';
        img.alt = c.dataset.alt || '';
        img.src = c.dataset.src;
        c.appendChild(img);
      } else if (c.dataset.type === 'video') {
        var wrapper = document.createElement('div');
        wrapper.className = 'media-wrapper';
        var video = document.createElement('video');
        video.className = 'media-preview';
        video.controls = true;
        var source = document.createElement('source');
        source.src = c.dataset.src;
        if (c.dataset.mime) source.type = c.dataset.mime;
        video.appendChild(source);
        var btn = document.createElement('button');
        btn.className = 'media-expand';
        btn.dataset.src = c.dataset.src;
        if (c.dataset.mime) btn.dataset.mime = c.dataset.mime;
        btn.setAttribute('aria-label', 'Open in viewer');
        btn.innerHTML = _EXPAND_SVG;
        wrapper.appendChild(video);
        wrapper.appendChild(btn);
        c.appendChild(wrapper);
      }
    }

    function _unloadMedia(c) {
      if (c.dataset.loaded !== '1') return;
      delete c.dataset.loaded;
      var video = c.querySelector('video');
      if (video) video.pause();
      while (c.lastChild) c.removeChild(c.lastChild);
    }

    function _applyRange() {
      _timer = null;
      if (!_visible.size) return;
      var arr = Array.from(_visible);
      var lo = Math.min.apply(null, arr) - KEEP;
      var hi = Math.max.apply(null, arr) + KEEP;
      _lazy.forEach(function(c) {
        var idx = _msgIdx(c);
        if (idx >= lo && idx <= hi) { _loadMedia(c); }
        else { _unloadMedia(c); }
      });
    }

    if ('IntersectionObserver' in window) {
      var _obs = new IntersectionObserver(function(entries) {
        entries.forEach(function(e) {
          var idx = _msgIdx(e.target);
          if (idx < 0) return;
          if (e.isIntersecting) { _visible.add(idx); }
          else { _visible.delete(idx); }
        });
        if (_timer) clearTimeout(_timer);
        _timer = setTimeout(_applyRange, 50);
      }, { rootMargin: '0px', threshold: 0 });
      _lazy.forEach(function(c) { _obs.observe(c); });
    } else {
      console.debug('[lazy-media] IntersectionObserver unavailable, loading all media immediately');
      _lazy.forEach(_loadMedia);
    }

    /* Hash navigation — all messages are in DOM, just scroll. */
    function _seekToHash() {
      if (!location.hash) return;
      var el = document.getElementById(location.hash.slice(1));
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
    window.addEventListener('hashchange', _seekToHash);
    _seekToHash();
  });

  /* ── Jump to top / bottom nav buttons ── */
  document.addEventListener('DOMContentLoaded', function() {
    var btnTop = document.getElementById('btn-top');
    var btnBottom = document.getElementById('btn-bottom');
    var anchorTop = document.getElementById('anchor-top');
    var anchorBottom = document.getElementById('anchor-bottom');
    if (!btnTop || !btnBottom) return;

    btnTop.addEventListener('click', function() {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    btnBottom.addEventListener('click', function() {
      window.scrollTo({
        top: document.documentElement.scrollHeight, behavior: 'smooth'
      });
    });

    /* Hide each button when its anchor is in view (i.e. we're already there). */
    if ('IntersectionObserver' in window && anchorTop && anchorBottom) {
      new IntersectionObserver(function(entries) {
        btnTop.hidden = entries[entries.length - 1].isIntersecting;
      }).observe(anchorTop);
      new IntersectionObserver(function(entries) {
        btnBottom.hidden = entries[entries.length - 1].isIntersecting;
      }).observe(anchorBottom);
    } else {
      btnTop.hidden = false;
      btnBottom.hidden = false;
    }
  });

  /* Remove all inline <mark class="search-hit"> wrappers, restoring
     the original text nodes. */
  function _clearInlineHighlights() {
    var marks = document.querySelectorAll('mark.search-hit');
    var parents = new Set();
    marks.forEach(function(mk) {
      var parent = mk.parentNode;
      while (mk.firstChild) parent.insertBefore(mk.firstChild, mk);
      parent.removeChild(mk);
      parents.add(parent);
    });
    /* Coalesce split text nodes so subsequent searches see clean strings. */
    parents.forEach(function(p) { p.normalize(); });
  }

  function _escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function _stripDiacritics(s) {
    return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function _buildIterRe(query, matchCase, wholeWords) {
    var esc = _escapeRe(query);
    if (wholeWords) {
      return new RegExp('\\b' + esc + '\\b', matchCase ? 'g' : 'gi');
    }
    return new RegExp(esc, matchCase ? 'g' : 'gi');
  }

  /* Wrap matched substrings in <mark class="search-hit"> within a row.
     Walks text nodes so we don't corrupt inline HTML (links, code, etc.),
     and skips content that is already inside a <mark>. */
  function _wrapMatchesInRow(row, iterRe) {
    var body = row.querySelector('.message-body');
    if (!body) return;
    var walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
      acceptNode: function(node) {
        if (node.parentNode && node.parentNode.tagName === 'MARK') {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var textNodes = [];
    var n;
    while ((n = walker.nextNode())) textNodes.push(n);
    textNodes.forEach(function(tn) {
      var text = tn.nodeValue;
      iterRe.lastIndex = 0;
      var hits = [];
      var m;
      while ((m = iterRe.exec(text)) !== null) {
        hits.push([m.index, m.index + m[0].length]);
        if (m[0].length === 0) iterRe.lastIndex++;
      }
      if (!hits.length) return;
      var frag = document.createDocumentFragment();
      var pos = 0;
      hits.forEach(function(h) {
        if (h[0] > pos)
          frag.appendChild(document.createTextNode(text.slice(pos, h[0])));
        var mk = document.createElement('mark');
        mk.className = 'search-hit';
        mk.textContent = text.slice(h[0], h[1]);
        frag.appendChild(mk);
        pos = h[1];
      });
      if (pos < text.length) frag.appendChild(document.createTextNode(text.slice(pos)));
      tn.parentNode.replaceChild(frag, tn);
    });
  }

  /* Toggle the visual highlight decorations (row background + inline marks)
     on the CURRENT search matches, without re-running the search. Cheap
     because window._searchMatches already holds the list of match rows. */
  window._setHighlight = function(on, query, opts) {
    _clearInlineHighlights();
    var ms = window._searchMatches;
    if (ms) ms.forEach(function(el) { el.classList.remove('search-match'); });
    if (!on || !query || !ms || !ms.length) return;
    opts = opts || {};
    var iterRe = _buildIterRe(query, !!opts.matchCase, !!opts.wholeWords);
    ms.forEach(function(row) {
      row.classList.add('search-match');
      _wrapMatchesInRow(row, iterRe);
    });
  };

  /* ── Message search ── */
  window._searchMessages = function(query, opts) {
    opts = opts || {};
    var highlight = opts.highlight !== false;
    var matchCase = !!opts.matchCase;
    var wholeWords = !!opts.wholeWords;
    var stripDiacritics = !opts.matchDiacritics;

    /* Clear previous highlights and timeline marks. */
    _clearInlineHighlights();
    document.querySelectorAll('.search-match-active, .search-match').forEach(function(el) {
      el.classList.remove('search-match-active', 'search-match');
    });
    document.querySelectorAll('.tl-search-mark').forEach(function(el) { el.remove(); });

    var senderFilter = (opts.sender || '').trim().toLowerCase();
    if (stripDiacritics && senderFilter) senderFilter = _stripDiacritics(senderFilter);

    if (!query && !senderFilter) {
      if (window._searchDone) window._searchDone(0);
      return;
    }

    /* Normalize query for diacritic-insensitive matching (default). */
    var qNorm = stripDiacritics ? _stripDiacritics(query) : query;
    var q = matchCase ? qNorm : qNorm.toLowerCase();
    var wordRe = null;
    if (wholeWords) {
      wordRe = new RegExp('\\b' + _escapeRe(qNorm) + '\\b', matchCase ? '' : 'i');
    }
    var iterRe = _buildIterRe(query, matchCase, wholeWords);

    function _matches(text) {
      var hay = stripDiacritics ? _stripDiacritics(text) : text;
      if (wordRe) return wordRe.test(matchCase ? hay : hay.toLowerCase());
      hay = matchCase ? hay : hay.toLowerCase();
      return hay.indexOf(q) !== -1;
    }

    function _runSearch() {
      /* Cap results so short queries in huge histories don't lock the tab.
         User is nudged to refine when this limit is hit. */
      var MAX_MATCHES = 1000;
      /* ISO YYYY-MM-DD sorts lexicographically, so plain string comparison
         is a valid date-range filter. */
      var fromDate = opts.from || '';
      var toDate = opts.to || '';
      var rows = document.querySelectorAll('article.message-row');
      var matches = [];
      var truncated = false;
      for (var i = 0; i < rows.length; i++) {
        var row = rows[i];
        if (fromDate || toDate) {
          var d = row.dataset.date || '';
          if (fromDate && d < fromDate) continue;
          if (toDate && d > toDate) continue;
        }
        if (senderFilter) {
          var senderRaw = (row.dataset.sender || '').toLowerCase();
          var senderHay = stripDiacritics ? _stripDiacritics(senderRaw) : senderRaw;
          if (senderHay.indexOf(senderFilter) === -1) continue;
        }
        var body = row.querySelector('.message-body');
        var textMatch = !query || (body && _matches(body.textContent));
        if (textMatch) {
          if (highlight) {
            row.classList.add('search-match');
            if (query) _wrapMatchesInRow(row, iterRe);
          }
          matches.push(row);
          if (matches.length >= MAX_MATCHES) { truncated = true; break; }
        }
      }

      /* Place timeline marks and scroll to first hit after layout settles.
         Timeline marks are intentionally independent of the Highlight toggle
         — they're a navigation aid, not part of in-body highlighting. */
      requestAnimationFrame(function() {
        var tlInner = document.getElementById('tl-inner');
        var scrollH = document.documentElement.scrollHeight;
        if (tlInner && scrollH > 0) {
          matches.forEach(function(row) {
            var frac = (row.offsetTop + row.offsetHeight / 2) / scrollH;
            var mark = document.createElement('div');
            mark.className = 'tl-search-mark';
            mark.style.top = (Math.min(frac, 0.99) * 100) + '%';
            tlInner.appendChild(mark);
          });
        }
        window._searchMatches = matches;
        if (matches.length > 0) {
          /* Start from the current viewport: pick the first match at or below
             the current scroll position; wrap to the first match otherwise. */
          var startY = window.scrollY;
          var startIdx = 0;
          for (var i = 0; i < matches.length; i++) {
            if (matches[i].offsetTop >= startY) { startIdx = i; break; }
          }
          window._searchMatchIdx = startIdx;
          matches[startIdx].classList.add('search-match-active');
          var maxScroll = scrollH - window.innerHeight;
          if (maxScroll > 0 && window.scrollY > maxScroll) {
            window.scrollTo(0, maxScroll);
          }
          matches[startIdx].scrollIntoView({ behavior: 'smooth', block: 'start' });
          _followMatchScroll(matches[startIdx]);
        } else {
          window._searchMatchIdx = 0;
        }
        if (window._searchDone) window._searchDone(matches.length, truncated);
      });
    }

    _runSearch();
  };

  /* ── Code block copy buttons ── */
  document.addEventListener('DOMContentLoaded', function() {
    var _copySVG = (
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none"'
      + ' stroke="currentColor" stroke-width="2"'
      + ' stroke-linecap="round" stroke-linejoin="round">'
      + '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
      + '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>'
      + '</svg>'
    );

    function _showCopiedBtn(btn) {
      btn.classList.add('copied');
      setTimeout(function() { btn.classList.remove('copied'); }, 1500);
    }

    function _attachCopyBtn(pre) {
      if (pre.getAttribute('data-copy')) return;
      pre.setAttribute('data-copy', '1');
      var btn = document.createElement('button');
      btn.className = 'code-copy-btn';
      btn.title = 'Copy code';
      btn.innerHTML = _copySVG;
      btn.addEventListener('click', function() {
        /* Each source line is wrapped in <span class="line"> with no text
           newlines between them (line breaks come from display:block).
           Reconstruct the plain source by joining line textContents with
           '
'. Line numbers live in ::before pseudo-elements and are
           naturally excluded from textContent. */
        var text;
        var lines = pre.querySelectorAll('code .line');
        if (lines.length) {
          text = Array.prototype.map.call(lines, function(el) {
            return el.textContent;
          }).join('\n');
        } else {
          var code = pre.querySelector('code');
          text = code ? code.textContent : pre.textContent;
        }
        if (navigator.clipboard) {
          navigator.clipboard.writeText(text).then(
            function() { _showCopiedBtn(btn); },
            function() { _showCopiedBtn(btn); }
          );
        } else {
          var ta = document.createElement('textarea');
          ta.value = text;
          ta.style.cssText = 'position:fixed;opacity:0';
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand('copy'); } catch(e) {}
          document.body.removeChild(ta);
          _showCopiedBtn(btn);
        }
      });
      pre.appendChild(btn);
    }

    function _attachAll() {
      document.querySelectorAll('pre:not([data-copy])').forEach(_attachCopyBtn);
    }

    _attachAll();

    /* Re-run after lazy chunks are inserted. */
    var msgList = document.querySelector('.message-list');
    if (msgList && 'MutationObserver' in window) {
      new MutationObserver(_attachAll)
        .observe(msgList, { childList: true, subtree: true });
    }
  });

  /* Re-scroll to a target row as layout shifts (lazy images load, etc.).
     Runs for a few seconds and cancels itself if the user takes over
     with wheel/touch/keyboard. Cancels any prior follow first. */
  var _followState = null;
  function _followMatchScroll(row) {
    if (_followState) _followState.stop();
    var stopped = false;
    var userScrolled = false;
    function onUserScroll() { userScrolled = true; }
    window.addEventListener('wheel', onUserScroll, { passive: true });
    window.addEventListener('touchmove', onUserScroll, { passive: true });
    window.addEventListener('keydown', onUserScroll);
    var ro = null;
    function stop() {
      if (stopped) return;
      stopped = true;
      if (ro) ro.disconnect();
      window.removeEventListener('wheel', onUserScroll);
      window.removeEventListener('touchmove', onUserScroll);
      window.removeEventListener('keydown', onUserScroll);
      if (_followState && _followState.stop === stop) _followState = null;
    }
    _followState = { stop: stop };
    var msgList = document.querySelector('.message-list');
    if (msgList && 'ResizeObserver' in window) {
      ro = new ResizeObserver(function() {
        if (stopped || userScrolled) return;
        row.scrollIntoView({ block: 'start' });
      });
      ro.observe(msgList);
    }
    setTimeout(stop, 3000);
  }

  /* ── Track current match by scroll position ──
     Debounced: after the user (or a settling animation) stops scrolling,
     figure out which match is closest to the viewport top, promote it to
     "active", and notify the parent overview so its "N / M" counter and
     prev/next targets stay in sync with what the user is looking at. */
  var _syncTimer = null;
  function _syncMatchToViewport() {
    var ms = window._searchMatches;
    if (!ms || !ms.length) return;
    var best = 0;
    var bestDist = Infinity;
    for (var i = 0; i < ms.length; i++) {
      var top = ms[i].getBoundingClientRect().top;
      var d = Math.abs(top);
      if (d < bestDist) { bestDist = d; best = i; }
    }
    if (best === window._searchMatchIdx) return;
    var prev = ms[window._searchMatchIdx];
    if (prev) prev.classList.remove('search-match-active');
    window._searchMatchIdx = best;
    ms[best].classList.add('search-match-active');
    if (window._onMatchIdxChange) window._onMatchIdxChange(best);
  }
  window.addEventListener('scroll', function() {
    if (_syncTimer) clearTimeout(_syncTimer);
    _syncTimer = setTimeout(_syncMatchToViewport, 150);
  }, { passive: true });

  /* ── Navigate to a specific search result by index ── */
  window._searchGoTo = function(idx) {
    var ms = window._searchMatches;
    if (!ms || !ms.length) return;
    var row = ms[idx];
    if (!row) return;
    var prev = ms[window._searchMatchIdx];
    if (prev && prev !== row) prev.classList.remove('search-match-active');
    window._searchMatchIdx = idx;
    row.classList.add('search-match-active');
    var maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    if (maxScroll > 0 && window.scrollY > maxScroll) window.scrollTo(0, maxScroll);
    row.scrollIntoView({ behavior: 'smooth', block: 'start' });
    _followMatchScroll(row);
  };

})();
