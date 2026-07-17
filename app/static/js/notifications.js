(function () {
  "use strict";

  var widget = document.getElementById("notifWidget");
  if (!widget) return;

  var FEED_URL = widget.dataset.feedUrl;
  var DETAIL_BASE = widget.dataset.detailBase; // ends with ".../requests/0"
  var POLL_MS = 5000;
  var LS_LAST_SEEN = "np_last_seen_id";
  var LS_SOUND = "np_sound";
  var LS_VOLUME = "np_volume";

  var bellBtn = document.getElementById("notifBellBtn");
  var badge = document.getElementById("notifBadge");
  var panel = document.getElementById("notifPanel");
  var settingsBtn = document.getElementById("notifSettingsBtn");
  var settingsBox = document.getElementById("notifSettings");
  var soundSelect = document.getElementById("notifSoundSelect");
  var volumeRange = document.getElementById("notifVolumeRange");
  var testBtn = document.getElementById("notifTestBtn");
  var listEl = document.getElementById("notifList");

  var lastSeenId = parseInt(localStorage.getItem(LS_LAST_SEEN) || "0", 10);
  var bootstrapped = localStorage.getItem(LS_LAST_SEEN) !== null;
  var unseenItems = [];
  var audioCtx = null;

  soundSelect.value = localStorage.getItem(LS_SOUND) || "bell";
  volumeRange.value = localStorage.getItem(LS_VOLUME) || "0.5";

  function getAudioCtx() {
    if (!audioCtx) {
      var Ctx = window.AudioContext || window.webkitAudioContext;
      audioCtx = new Ctx();
    }
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
  }

  // Resume audio on first user gesture (browser autoplay policy).
  document.addEventListener("click", function once() {
    getAudioCtx();
    document.removeEventListener("click", once);
  }, { once: true });

  function tone(ctx, freq, startAt, duration, gain, type) {
    var osc = ctx.createOscillator();
    var g = ctx.createGain();
    osc.type = type || "sine";
    osc.frequency.setValueAtTime(freq, startAt);
    g.gain.setValueAtTime(0, startAt);
    g.gain.linearRampToValueAtTime(gain, startAt + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, startAt + duration);
    osc.connect(g);
    g.connect(ctx.destination);
    osc.start(startAt);
    osc.stop(startAt + duration + 0.05);
  }

  var SOUNDS = {
    bell: function (ctx, vol) {
      var t = ctx.currentTime;
      tone(ctx, 1318.5, t, 0.35, vol, "sine");
      tone(ctx, 1046.5, t + 0.14, 0.4, vol * 0.85, "sine");
    },
    chime: function (ctx, vol) {
      var t = ctx.currentTime;
      [880, 1108, 1318.5].forEach(function (f, i) {
        tone(ctx, f, t + i * 0.09, 0.3, vol * 0.8, "triangle");
      });
    },
    beep: function (ctx, vol) {
      tone(ctx, 1500, ctx.currentTime, 0.16, vol, "square");
    },
    pop: function (ctx, vol) {
      var t = ctx.currentTime;
      var osc = ctx.createOscillator();
      var g = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(320, t);
      osc.frequency.exponentialRampToValueAtTime(90, t + 0.18);
      g.gain.setValueAtTime(vol, t);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.2);
      osc.connect(g);
      g.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.25);
    },
    none: function () {}
  };

  function playSound() {
    var kind = soundSelect.value;
    var fn = SOUNDS[kind];
    if (!fn || kind === "none") return;
    try {
      fn(getAudioCtx(), parseFloat(volumeRange.value));
    } catch (e) {
      // Audio may be blocked until the user interacts with the page — safe to ignore.
    }
  }

  function ringBell() {
    bellBtn.classList.remove("ringing");
    void bellBtn.offsetWidth; // restart animation
    bellBtn.classList.add("ringing");
  }

  function renderList() {
    if (!unseenItems.length) {
      listEl.innerHTML = '<div class="notif-empty">Hozircha yangi murojaat yo\'q.</div>';
      return;
    }
    listEl.innerHTML = unseenItems.map(function (item) {
      var href = DETAIL_BASE.replace(/\/0$/, "/" + item.id);
      var time = new Date(item.created_at).toLocaleString("uz-UZ", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
      });
      return (
        '<a class="notif-item" href="' + href + '">' +
          '<div class="notif-item-top"><span>' + escapeHtml(item.number) + '</span>' +
          '<span class="priority-' + escapeHtml(item.priority || "") + '">' + escapeHtml(item.priority || "") + '</span></div>' +
          '<div class="notif-item-desc">' + escapeHtml(item.category) + ' — ' + escapeHtml(item.description || "") + '</div>' +
          '<div class="notif-item-meta">' + escapeHtml(item.org_display || "") + ' · ' + time + '</div>' +
        '</a>'
      );
    }).join("");
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function updateBadge() {
    if (unseenItems.length > 0) {
      badge.textContent = unseenItems.length > 99 ? "99+" : String(unseenItems.length);
      badge.hidden = false;
    } else {
      badge.hidden = true;
    }
  }

  function poll() {
    var since = bootstrapped ? lastSeenId : 0;
    fetch(FEED_URL + "?since_id=" + since, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (bootstrapped && data.items.length) {
          unseenItems = data.items.concat(unseenItems).slice(0, 30);
          updateBadge();
          renderList();
          ringBell();
          playSound();
        }
        lastSeenId = data.latest_id;
        bootstrapped = true;
        localStorage.setItem(LS_LAST_SEEN, String(lastSeenId));
      })
      .catch(function () { /* network hiccup — will retry on next poll */ });
  }

  bellBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    var opening = panel.hidden;
    panel.hidden = !opening;
    settingsBox.hidden = true;
    if (opening) {
      unseenItems = [];
      updateBadge();
    }
  });

  settingsBtn.addEventListener("click", function (e) {
    e.stopPropagation();
    settingsBox.hidden = !settingsBox.hidden;
  });

  soundSelect.addEventListener("change", function () {
    localStorage.setItem(LS_SOUND, soundSelect.value);
  });

  volumeRange.addEventListener("input", function () {
    localStorage.setItem(LS_VOLUME, volumeRange.value);
  });

  testBtn.addEventListener("click", function () {
    playSound();
  });

  document.addEventListener("click", function (e) {
    if (!widget.contains(e.target)) {
      panel.hidden = true;
      settingsBox.hidden = true;
    }
  });

  poll();
  setInterval(poll, POLL_MS);
})();
