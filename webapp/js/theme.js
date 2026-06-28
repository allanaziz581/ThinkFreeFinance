/*
 * theme.js -- ThinkFree Finance display customization engine.
 *
 * Provides the "Customize Display" slide-out panel: a set of accent color
 * families (each expanding into shades), a light/dark mode toggle, instant
 * hover/focus preview (no click required), and confirm-before-save persistence.
 *
 * How it works: themes are applied by writing CSS custom properties inline onto
 * <body>. Inline styles win over the class-based :root / body.light palettes, so
 * a theme can retint backgrounds, cards, and accents live. The widely-used
 * --info / --info-dim accents are aliased to the chosen accent so existing
 * components (buttons, links, nav, chips, graphs, highlights) recolor instantly.
 *
 * Mode (light vs dark) is the inversion axis: it toggles body.light (which swaps
 * the base surface/text palette) and the accent is recomputed for the mode, so
 * the same hue gives e.g. "Dark Pink" or "Light Pink".
 *
 * Not security-sensitive, so this loads for everyone (including the lock screen)
 * and persists to localStorage. In server mode the saved preference can also be
 * mirrored to the account via Auth.setDisplay (optional; see saveState).
 */
(function () {
  "use strict";

  // ---- Theme catalogue ---------------------------------------------------
  // Each shade is an HSL triple. h = hue, s = saturation %, l = lightness %.
  // Neutral families (black/white) carry no hue: they just set the mode and
  // fall back to the default cyan accent of the base palette.
  const THEMES = [
    { key: "black", label: "Black", neutral: true, mode: "dark",  swatch: "#0c1628" },
    { key: "white", label: "White", neutral: true, mode: "light", swatch: "#f1f5f9" },
    { key: "blue", label: "Blue", shades: [
      { name: "Sky Blue",   h: 200, s: 90, l: 60 },
      { name: "Azure",      h: 213, s: 85, l: 56 },
      { name: "Royal Blue", h: 225, s: 80, l: 60 },
      { name: "Ocean",      h: 190, s: 82, l: 48 },
      { name: "Steel Blue", h: 205, s: 42, l: 56 },
    ] },
    { key: "green", label: "Green", shades: [
      { name: "Emerald", h: 155, s: 72, l: 46 },
      { name: "Mint",    h: 150, s: 62, l: 58 },
      { name: "Lime",    h: 95,  s: 62, l: 48 },
      { name: "Teal",    h: 175, s: 68, l: 44 },
      { name: "Forest",  h: 140, s: 52, l: 40 },
    ] },
    { key: "red", label: "Red", shades: [
      { name: "Crimson", h: 350, s: 80, l: 54 },
      { name: "Scarlet", h: 8,   s: 84, l: 56 },
      { name: "Ruby",    h: 345, s: 74, l: 50 },
      { name: "Coral",   h: 12,  s: 84, l: 62 },
      { name: "Brick",   h: 0,   s: 54, l: 46 },
    ] },
    { key: "pink", label: "Pink", shades: [
      // ThinkFree brand pink (the mockup palette ~#F06090 dark / #F080A0 light).
      // Selecting it here is now the ONLY way pink is applied; pink is no longer
      // part of the default theme.
      { name: "ThinkFree Pink", h: 342, s: 80, l: 66 },
      { name: "Light Pink",  h: 332, s: 80, l: 74 },
      { name: "Rose Pink",   h: 345, s: 70, l: 60 },
      { name: "Hot Pink",    h: 330, s: 88, l: 58 },
      { name: "Neon Pink",   h: 322, s: 96, l: 62 },
      { name: "Pastel Pink", h: 335, s: 58, l: 80 },
      { name: "Magenta",     h: 312, s: 80, l: 56 },
    ] },
    { key: "purple", label: "Purple", shades: [
      { name: "Violet",   h: 270, s: 70, l: 62 },
      { name: "Lavender", h: 265, s: 58, l: 72 },
      { name: "Indigo",   h: 245, s: 70, l: 60 },
      { name: "Plum",     h: 290, s: 54, l: 52 },
      { name: "Grape",    h: 280, s: 74, l: 56 },
    ] },
  ];

  const LS_KEY = "tf-display";       // {key, shade, mode}
  const LS_MODE = "tf-theme";        // legacy mode key shared with app.js

  // Accent variables we set inline on <body>. Cleared for neutral themes.
  const ACCENT_VARS = [
    "--accent", "--accent-strong", "--accent-soft",
    "--info", "--info-dim",
    "--bg-primary", "--bg-secondary", "--bg-card", "--bg-inner", "--bg-hover",
    "--border-subtle", "--border-soft",
  ];

  // ---- State -------------------------------------------------------------
  let state = loadState();
  let savedState = Object.assign({}, state);   // what's persisted (for revert)

  function loadState() {
    let s = null;
    try { s = JSON.parse(localStorage.getItem(LS_KEY) || "null"); } catch (e) {}
    if (!s || typeof s !== "object") {
      let mode = "dark";
      try { if (localStorage.getItem(LS_MODE) === "light") mode = "light"; } catch (e) {}
      s = { key: mode === "light" ? "white" : "black", shade: 0, mode: mode };
    }
    if (!THEMES.some((t) => t.key === s.key)) s.key = "black";
    if (s.mode !== "light" && s.mode !== "dark") s.mode = "dark";
    return s;
  }

  function themeByKey(k) { return THEMES.find((t) => t.key === k) || THEMES[0]; }

  // ---- Applying a theme --------------------------------------------------
  function clearAccent() {
    ACCENT_VARS.forEach((v) => document.body.style.removeProperty(v));
  }

  function applyMode(mode) {
    const light = mode === "light";
    document.body.classList.toggle("light", light);
    // keep the sidebar dark-mode switch (managed by app.js) visually in sync
    const tog = document.getElementById("darkToggle");
    if (tog) {
      tog.classList.toggle("off", light);
      tog.setAttribute("aria-checked", light ? "false" : "true");
    }
    try { localStorage.setItem(LS_MODE, light ? "light" : "dark"); } catch (e) {}
  }

  // Apply a {key, shade, mode} theme to the live document.
  function applyTheme(st) {
    applyMode(st.mode);
    const theme = themeByKey(st.key);
    if (theme.neutral) { clearAccent(); return; }
    const shade = (theme.shades && theme.shades[st.shade]) || theme.shades[0];
    const light = st.mode === "light";
    const h = shade.h;
    const s = shade.s;
    // Cap accent lightness on a light base so accent-colored text stays readable.
    const accentL = light ? Math.min(shade.l, 50) : shade.l;
    const set = (k, v) => document.body.style.setProperty(k, v);

    // The accent is where ALL the vibrancy lives. It is aliased onto --info, which
    // every existing component uses for buttons, links, nav, chips, meters, and
    // highlights, so the chosen color pops everywhere. Surfaces stay near-neutral
    // (below) so text never sits on a clashing colored background.
    const accent = `hsl(${h} ${Math.min(s + 6, 100)}% ${accentL}%)`;
    set("--accent", accent);
    set("--accent-strong", `hsl(${h} ${Math.min(s + 10, 100)}% ${Math.max(accentL - 10, 22)}%)`);
    set("--accent-soft", `hsla(${h}, ${s}%, ${accentL}%, 0.18)`);
    set("--info", accent);
    set("--info-dim", `hsla(${h}, ${s}%, ${accentL}%, 0.18)`);
    // Just a hint of the hue on borders so the theme reads without clashing.
    set("--border-subtle", `hsla(${h}, 30%, 55%, 0.16)`);
    set("--border-soft", `hsla(${h}, 35%, 58%, 0.26)`);

    if (light) {
      // Clean light surfaces with only a whisper of the hue (white cards, dark text).
      set("--bg-primary",   `hsl(${h} 28% 95%)`);
      set("--bg-secondary", "#ffffff");
      set("--bg-card",      "#ffffff");
      set("--bg-inner",     `hsl(${h} 22% 94%)`);
      set("--bg-hover",     `hsla(${h}, 40%, 45%, 0.07)`);
    } else {
      // Clean near-black surfaces with only a whisper of the hue (light text stays crisp).
      set("--bg-primary",   `hsl(${h} 16% 6%)`);
      set("--bg-secondary", `hsl(${h} 15% 8%)`);
      set("--bg-card",      `hsl(${h} 14% 10%)`);
      set("--bg-inner",     `hsl(${h} 15% 7%)`);
      set("--bg-hover",     `hsla(${h}, 70%, 65%, 0.10)`);
    }
  }

  function saveState() {
    savedState = Object.assign({}, state);
    try { localStorage.setItem(LS_KEY, JSON.stringify(savedState)); } catch (e) {}
    // Mirror to the account in server mode if the auth layer supports it.
    if (window.Auth && typeof window.Auth.setDisplay === "function") {
      try { window.Auth.setDisplay(savedState); } catch (e) {}
    }
  }

  function revertToSaved() { state = Object.assign({}, savedState); applyTheme(state); }

  // ---- Public API --------------------------------------------------------
  window.TFTheme = {
    apply: applyTheme,
    setMode: function (light) { state.mode = light ? "light" : "dark"; applyTheme(state); saveState(); refreshPanel(); },
    toggleMode: function () { window.TFTheme.setMode(state.mode !== "light"); },
    isLight: function () { return state.mode === "light"; },
    current: function () { return Object.assign({}, state); },
  };

  // Apply the saved theme immediately (before paint where possible).
  applyTheme(state);

  // ---- Panel UI ----------------------------------------------------------
  let panelEl = null, fabEl = null, lastFocus = null, pending = null;

  function buildSwatch(theme, shadeIdx, shade) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tf-sw";
    btn.dataset.key = theme.key;
    btn.dataset.shade = shadeIdx;
    var bg;
    if (theme.neutral) { bg = theme.swatch; btn.classList.add("tf-sw-neutral"); }
    else bg = `hsl(${shade.h} ${shade.s}% ${shade.l}%)`;
    btn.style.background = bg;
    const label = theme.neutral ? theme.label : shade.name;
    btn.setAttribute("aria-label", "Preview " + label + " theme");
    btn.title = label;
    // Hover and keyboard focus both preview instantly (no click needed).
    btn.addEventListener("mouseenter", () => preview(theme.key, shadeIdx));
    btn.addEventListener("focus", () => preview(theme.key, shadeIdx));
    btn.addEventListener("mouseleave", () => { if (!pending) revertToSaved(); });
    btn.addEventListener("blur", () => { if (!pending) revertToSaved(); });
    btn.addEventListener("click", () => askSave(theme.key, shadeIdx, label));
    return btn;
  }

  function preview(key, shadeIdx) {
    state = { key: key, shade: shadeIdx, mode: state.mode };
    applyTheme(state);
  }

  function askSave(key, shadeIdx, label) {
    pending = { key: key, shade: shadeIdx };
    preview(key, shadeIdx);
    const bar = panelEl.querySelector(".tf-confirm");
    bar.querySelector(".tf-confirm-text").textContent = "Save the " + label + " theme?";
    bar.classList.add("show");
    bar.querySelector(".tf-confirm-yes").focus();
  }

  function confirmSave(yes) {
    const bar = panelEl.querySelector(".tf-confirm");
    bar.classList.remove("show");
    if (yes && pending) { state = { key: pending.key, shade: pending.shade, mode: state.mode }; applyTheme(state); saveState(); }
    else { revertToSaved(); }
    pending = null;
    refreshPanel();
  }

  function refreshPanel() {
    if (!panelEl) return;
    // mark the active swatch + sync the mode switch
    panelEl.querySelectorAll(".tf-sw").forEach((b) => {
      const active = b.dataset.key === savedState.key &&
        (themeByKey(savedState.key).neutral || Number(b.dataset.shade) === savedState.shade);
      b.classList.toggle("active", active);
      b.setAttribute("aria-pressed", active ? "true" : "false");
    });
    const ms = panelEl.querySelector("#tf-mode-switch");
    if (ms) {
      const light = state.mode === "light";
      ms.classList.toggle("off", !light);
      ms.setAttribute("aria-checked", light ? "true" : "false");
      panelEl.querySelector("#tf-mode-label").textContent = light ? "Light mode" : "Dark mode";
    }
  }

  function buildPanel() {
    fabEl = document.createElement("button");
    fabEl.type = "button";
    fabEl.id = "tf-theme-fab";
    fabEl.className = "tf-theme-fab";
    fabEl.setAttribute("aria-haspopup", "dialog");
    fabEl.setAttribute("aria-expanded", "false");
    fabEl.setAttribute("aria-label", "Customize display");
    fabEl.innerHTML =
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">' +
      '<circle cx="13.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="10.5" r="2.5"/><circle cx="8.5" cy="7.5" r="2.5"/><circle cx="6.5" cy="12.5" r="2.5"/>' +
      '<path d="M12 22a10 10 0 1 1 10-10c0 2-2 3-4 3h-2a2 2 0 0 0-1.5 3.3A2 2 0 0 1 12 22Z"/></svg>' +
      '<span>Customize Display</span>';
    fabEl.addEventListener("click", openPanel);
    document.body.appendChild(fabEl);

    const overlay = document.createElement("div");
    overlay.className = "tf-theme-overlay";
    overlay.addEventListener("click", closePanel);
    document.body.appendChild(overlay);

    panelEl = document.createElement("aside");
    panelEl.className = "tf-theme-panel";
    panelEl.id = "tf-theme-panel";
    panelEl.setAttribute("role", "dialog");
    panelEl.setAttribute("aria-modal", "true");
    panelEl.setAttribute("aria-label", "Display customization");
    panelEl.setAttribute("aria-hidden", "true");

    let html = '<div class="tf-tp-head"><h2 id="tf-tp-title">Customize Display</h2>' +
      '<button type="button" class="tf-tp-close" aria-label="Close customization panel">&times;</button></div>' +
      '<p class="tf-tp-hint">Hover a color to preview instantly. Click to save.</p>' +
      '<div class="tf-mode-row"><span id="tf-mode-label">Dark mode</span>' +
      '<div class="switch" id="tf-mode-switch" role="switch" tabindex="0" aria-label="Toggle light or dark mode"></div></div>';

    THEMES.forEach((theme) => {
      html += '<div class="tf-fam"><div class="tf-fam-name">' + theme.label + '</div>' +
        '<div class="tf-fam-swatches" data-fam="' + theme.key + '"></div></div>';
    });
    html += '<div class="tf-confirm" role="alertdialog" aria-live="polite">' +
      '<span class="tf-confirm-text"></span>' +
      '<div class="tf-confirm-btns"><button type="button" class="tf-confirm-yes">Save</button>' +
      '<button type="button" class="tf-confirm-no">Cancel</button></div></div>';
    panelEl.innerHTML = html;
    document.body.appendChild(panelEl);

    // populate swatches
    THEMES.forEach((theme) => {
      const wrap = panelEl.querySelector('[data-fam="' + theme.key + '"]');
      if (theme.neutral) wrap.appendChild(buildSwatch(theme, 0, null));
      else theme.shades.forEach((sh, i) => wrap.appendChild(buildSwatch(theme, i, sh)));
    });

    panelEl.querySelector(".tf-tp-close").addEventListener("click", closePanel);
    panelEl.querySelector(".tf-confirm-yes").addEventListener("click", () => confirmSave(true));
    panelEl.querySelector(".tf-confirm-no").addEventListener("click", () => confirmSave(false));

    const ms = panelEl.querySelector("#tf-mode-switch");
    ms.addEventListener("click", () => window.TFTheme.toggleMode());
    ms.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); window.TFTheme.toggleMode(); } });

    // keyboard handling within the panel
    panelEl.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.preventDefault(); closePanel(); return; }
      if (e.key === "Enter" || e.key === " ") {
        const sw = e.target.closest(".tf-sw");
        if (sw) { e.preventDefault(); sw.click(); }
      }
      if (e.key === "Tab") trapFocus(e);
    });
  }

  function trapFocus(e) {
    const f = panelEl.querySelectorAll('button, [tabindex="0"]');
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  function openPanel() {
    if (!panelEl) buildPanel();
    lastFocus = document.activeElement;
    document.body.classList.add("tf-tp-open");
    panelEl.setAttribute("aria-hidden", "false");
    fabEl.setAttribute("aria-expanded", "true");
    refreshPanel();
    const c = panelEl.querySelector(".tf-tp-close");
    if (c) c.focus();
  }

  function closePanel() {
    if (!panelEl) return;
    revertToSaved();   // discard any unsaved preview
    pending = null;
    panelEl.querySelector(".tf-confirm").classList.remove("show");
    document.body.classList.remove("tf-tp-open");
    panelEl.setAttribute("aria-hidden", "true");
    fabEl.setAttribute("aria-expanded", "false");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  // Build the launcher once the DOM is ready.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", buildPanel);
  } else {
    buildPanel();
  }
})();
