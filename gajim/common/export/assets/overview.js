var _scrollPos = Object.create(null);
var _matchIdx = 0;
var _matchTotal = 0;
var _matchTruncated = false;
var _optHighlight = false;
var _optMatchCase = false;
var _optWholeWords = false;
var _optMatchDiacritics = false;
var _senderFilter = '';
var _fromDate = null;
var _toDate = null;
/* Last-run search snapshot; used to skip re-runs with identical parameters. */
var _lastSearch = null;

function _searchOpts() {
  return {
    highlight: _optHighlight,
    matchCase: _optMatchCase,
    wholeWords: _optWholeWords,
    matchDiacritics: _optMatchDiacritics,
    sender: _senderFilter,
    from: _fromDate,
    to: _toDate
  };
}

function _updateNavUI() {
  var countEl = document.getElementById('search-count');
  var prevBtn = document.getElementById('prev-btn');
  var nextBtn = document.getElementById('next-btn');
  var hasMatches = _matchTotal > 0;
  if (countEl) {
    if (_lastSearch === null) {
      countEl.textContent = '';
      countEl.title = '';
      countEl.classList.remove('truncated');
    } else {
      var suffix = _matchTruncated ? '+' : '';
      countEl.textContent = hasMatches
        ? (_matchIdx + 1) + ' / ' + _matchTotal + suffix
        : 'No results';
      countEl.title = _matchTruncated
        ? 'Result limit reached — refine your search for full results'
        : '';
      countEl.classList.toggle('truncated', _matchTruncated);
    }
  }
  if (prevBtn) prevBtn.disabled = !hasMatches;
  if (nextBtn) nextBtn.disabled = !hasMatches;
}

function _navTo(idx) {
  if (!_matchTotal) return;
  _matchIdx = ((idx % _matchTotal) + _matchTotal) % _matchTotal;
  var frame = document.getElementById('chat-frame');
  if (frame && frame.contentWindow && frame.contentWindow._searchGoTo) {
    frame.contentWindow._searchGoTo(_matchIdx);
  }
  _updateNavUI();
}

function loadChat(path, el) {
  var frame = document.getElementById('chat-frame');

  if (window._currentPath !== null && frame.contentWindow) {
    try { _scrollPos[window._currentPath] = frame.contentWindow.scrollY; } catch(e) {}
  }

  document.querySelectorAll('.chat-item').forEach(function(i) {
    i.classList.remove('active');
  });
  el.classList.add('active');

  if (path === window._currentPath) return;
  window._currentPath = path;

  /* Reset search state when switching chats. */
  _matchIdx = 0;
  _matchTotal = 0;
  _lastSearch = null;
  _updateNavUI();

  frame.src = path;
  frame.onload = function() {
    var saved = _scrollPos[path];
    if (saved) {
      try { frame.contentWindow.scrollTo(0, saved); } catch(e) {}
    }
  };
}

function _doSearch() {
  var input = document.getElementById('search-input');
  var frame = document.getElementById('chat-frame');
  var countEl = document.getElementById('search-count');
  var prevBtn = document.getElementById('prev-btn');
  var nextBtn = document.getElementById('next-btn');
  if (!input || !frame.contentWindow || !frame.contentWindow._searchMessages) return;

  var query = input.value.trim();
  var senderInputEl = document.getElementById('sender-input');
  _senderFilter = senderInputEl ? senderInputEl.value.trim() : '';
  var opts = _searchOpts();
  var path = window._currentPath;

  /* Skip the search when nothing has changed since the last run — same query,
     same match options, same date range, same chat. Results would be
     identical, and re-running wipes highlights and re-scrolls unnecessarily. */
  if (_lastSearch
      && _lastSearch.query === query
      && _lastSearch.matchCase === opts.matchCase
      && _lastSearch.wholeWords === opts.wholeWords
      && _lastSearch.matchDiacritics === opts.matchDiacritics
      && _lastSearch.sender === opts.sender
      && _lastSearch.from === opts.from
      && _lastSearch.to === opts.to
      && _lastSearch.path === path) {
    return;
  }
  _lastSearch = {
    query: query,
    matchCase: opts.matchCase,
    wholeWords: opts.wholeWords,
    matchDiacritics: opts.matchDiacritics,
    sender: opts.sender,
    from: opts.from,
    to: opts.to,
    path: path
  };

  _matchIdx = 0;
  _matchTotal = 0;

  var active = !!(query || opts.sender);
  if (active) {
    if (countEl) countEl.textContent = 'Searching…';
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;
  }

  frame.contentWindow._searchDone = function(n, truncated) {
    _matchTotal = n;
    _matchTruncated = !!truncated;
    _matchIdx = frame.contentWindow._searchMatchIdx || 0;
    _updateNavUI();
  };
  /* Keep the counter and prev/next in sync with the user's scroll position. */
  frame.contentWindow._onMatchIdxChange = function(idx) {
    _matchIdx = idx;
    _updateNavUI();
  };
  frame.contentWindow._searchMessages(query, opts);
}

document.addEventListener('DOMContentLoaded', function() {
  var sidebarSearch = document.querySelector('.sidebar-search');
  if (sidebarSearch) {
    sidebarSearch.hidden = false;
    console.debug('[overview] Search enabled');
  }

  var chatList = document.getElementById('chat-list');
  if (chatList) {
    chatList.addEventListener('click', function(e) {
      var item = e.target.closest('.chat-item');
      if (!item) return;
      var link = item.querySelector('.chat-link');
      if (!link) return;
      e.preventDefault();
      loadChat(link.getAttribute('href'), item);
    });
  }

  var btn = document.getElementById('search-btn');
  var input = document.getElementById('search-input');
  var prevBtn = document.getElementById('prev-btn');
  var nextBtn = document.getElementById('next-btn');

  var clearBtn = document.getElementById('search-clear');
  var senderBtn = document.getElementById('opt-sender');
  var senderPopup = document.getElementById('sender-popup');
  var senderInput = document.getElementById('sender-input');
  var senderReset = document.getElementById('sender-reset');
  if (btn) btn.addEventListener('click', _doSearch);
  if (input) {
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') _doSearch();
    });
  }
  if (clearBtn) {
    clearBtn.addEventListener('click', function() {
      input.value = '';
      _doSearch();
      input.focus();
    });
  }
  /* Sender popup toggle: open on first click, close+clear on second click. */
  if (senderBtn) {
    senderBtn.addEventListener('click', function() {
      var open = senderPopup && !senderPopup.hidden;
      if (open) {
        senderPopup.hidden = true;
        senderBtn.setAttribute('aria-pressed', 'false');
        if (senderInput) senderInput.value = '';
        _senderFilter = '';
        _doSearch();
      } else {
        if (senderPopup) senderPopup.hidden = false;
        senderBtn.setAttribute('aria-pressed', 'true');
        if (senderInput) senderInput.focus();
      }
    });
  }
  if (senderInput) {
    senderInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') _doSearch();
    });
  }
  if (senderReset) {
    senderReset.addEventListener('click', function() {
      if (senderInput) { senderInput.value = ''; senderInput.focus(); }
      _senderFilter = '';
      _doSearch();
    });
  }
  if (prevBtn) prevBtn.addEventListener('click', function() { _navTo(_matchIdx - 1); });
  if (nextBtn) nextBtn.addEventListener('click', function() { _navTo(_matchIdx + 1); });

  /* Search option toggles. */
  function _applyHighlight() {
    var frame = document.getElementById('chat-frame');
    var cw = frame && frame.contentWindow;
    if (!input || !cw || !cw._setHighlight) return;
    var query = input.value.trim();
    cw._setHighlight(_optHighlight, query, _searchOpts());
  }
  function _bindOpt(id, getVal, setVal, onToggle) {
    var btn = document.getElementById(id);
    if (!btn) return;
    btn.setAttribute('aria-pressed', getVal() ? 'true' : 'false');
    btn.addEventListener('click', function() {
      setVal(!getVal());
      btn.setAttribute('aria-pressed', getVal() ? 'true' : 'false');
      onToggle();
    });
  }
  /* Highlight only changes visuals — apply directly, don't re-run search. */
  _bindOpt('opt-highlight', function() { return _optHighlight; },
                            function(v) { _optHighlight = v; },
                            _applyHighlight);
  /* Match Case and Whole Words change what matches — re-run search. */
  function _reSearchIfActive() {
    if (input && input.value.trim()) _doSearch();
  }
  _bindOpt('opt-case', function() { return _optMatchCase; },
                       function(v) { _optMatchCase = v; },
                       _reSearchIfActive);
  _bindOpt('opt-diacritic', function() { return _optMatchDiacritics; },
                            function(v) { _optMatchDiacritics = v; },
                            _reSearchIfActive);
  _bindOpt('opt-word', function() { return _optWholeWords; },
                       function(v) { _optWholeWords = v; },
                       _reSearchIfActive);

  /* Date filter buttons: always open the native date picker on click.
     Clearing is handled by the reset button inside the date picker popup. */
  function _bindDate(btnId, inputId, getVal, setVal) {
    var dateBtn = document.getElementById(btnId);
    var dateInput = document.getElementById(inputId);
    if (!dateBtn || !dateInput) return;
    var baseTitle = dateBtn.title;
    function _refresh() {
      var v = getVal();
      dateBtn.setAttribute('aria-pressed', v ? 'true' : 'false');
      dateBtn.title = v ? baseTitle + ': ' + v : baseTitle;
    }
    dateBtn.addEventListener('click', function() {
      if (dateInput.showPicker) {
        dateInput.showPicker();
      } else {
        dateInput.focus();
      }
    });
    dateInput.addEventListener('change', function() {
      setVal(dateInput.value || null);
      _refresh();
      _reSearchIfActive();
    });
  }
  _bindDate('opt-from-btn', 'opt-from-date',
            function() { return _fromDate; },
            function(v) { _fromDate = v; });
  _bindDate('opt-to-btn', 'opt-to-date',
            function() { return _toDate; },
            function(v) { _toDate = v; });
});
