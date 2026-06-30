// landing.js
//
// Public landing page (served at /). Two lightweight canvas network animations
// (no WebGL, no Three.js) plus scroll-triggered reveals. Honors
// prefers-reduced-motion, pauses when offscreen, and never causes horizontal
// overflow. The page itself is static HTML; this only adds motion + reveals.
"use strict";
(function () {
  var REDUCED = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var ACCENT = "#38BDF8", ACCENT2 = "#7DD3FC", GOOD = "#00C46A", WARN = "#F59E0B";

  // ---- a drifting node network drawn on a canvas -------------------------
  // opts: { density, maxLink, hub, colors, speed, dot }
  function network(canvas, opts) {
    opts = opts || {};
    var ctx = canvas.getContext("2d");
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    var W = 0, H = 0, nodes = [], hub = null, raf = 0, running = false;
    var colors = opts.colors || [ACCENT, ACCENT, ACCENT, ACCENT2, GOOD, WARN];
    var maxLink = opts.maxLink || 130;
    var speed = (opts.speed || 0.18);

    function size() {
      var r = canvas.getBoundingClientRect();
      W = Math.max(1, Math.round(r.width));
      H = Math.max(1, Math.round(r.height));
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      build();
    }
    function build() {
      // node count scales with area, capped so phones stay light
      var target = Math.round((W * H) / (opts.density || 14000));
      target = Math.max(8, Math.min(opts.cap || 64, target));
      nodes = [];
      for (var i = 0; i < target; i++) {
        nodes.push({
          x: Math.random() * W, y: Math.random() * H,
          vx: (Math.random() - 0.5) * speed, vy: (Math.random() - 0.5) * speed,
          r: 1.4 + Math.random() * 1.8,
          c: colors[(Math.random() * colors.length) | 0],
        });
      }
      hub = opts.hub ? { x: W / 2, y: H / 2, r: 6.5, c: ACCENT } : null;
    }
    function step() {
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > W) n.vx *= -1;
        if (n.y < 0 || n.y > H) n.vy *= -1;
      }
    }
    function draw() {
      ctx.clearRect(0, 0, W, H);
      // links between nearby nodes
      for (var i = 0; i < nodes.length; i++) {
        var a = nodes[i];
        if (hub) {
          var dxh = a.x - hub.x, dyh = a.y - hub.y, dh = Math.sqrt(dxh * dxh + dyh * dyh);
          if (dh < maxLink * 1.6) {
            ctx.strokeStyle = "rgba(56,189,248," + (0.22 * (1 - dh / (maxLink * 1.6))).toFixed(3) + ")";
            ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(hub.x, hub.y); ctx.stroke();
          }
        }
        for (var j = i + 1; j < nodes.length; j++) {
          var b = nodes[j], dx = a.x - b.x, dy = a.y - b.y, d = Math.sqrt(dx * dx + dy * dy);
          if (d < maxLink) {
            ctx.strokeStyle = "rgba(148,163,184," + (0.16 * (1 - d / maxLink)).toFixed(3) + ")";
            ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
      // nodes
      for (var k = 0; k < nodes.length; k++) {
        var p = nodes[k];
        ctx.fillStyle = p.c; ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, 6.2832); ctx.fill();
      }
      if (hub) {
        ctx.fillStyle = "rgba(56,189,248,0.18)"; ctx.beginPath(); ctx.arc(hub.x, hub.y, hub.r * 2.6, 0, 6.2832); ctx.fill();
        ctx.fillStyle = ACCENT; ctx.beginPath(); ctx.arc(hub.x, hub.y, hub.r, 0, 6.2832); ctx.fill();
      }
    }
    function frame() { if (!running) return; step(); draw(); raf = requestAnimationFrame(frame); }
    function start() { if (running || REDUCED) return; running = true; raf = requestAnimationFrame(frame); }
    function stop() { running = false; if (raf) cancelAnimationFrame(raf); raf = 0; }

    size();
    draw();                       // one static frame (also the reduced-motion result)
    var ro = null;
    var resizeT = 0;
    window.addEventListener("resize", function () { clearTimeout(resizeT); resizeT = setTimeout(function () { size(); draw(); }, 150); });
    // run only while the canvas is on screen
    if ("IntersectionObserver" in window) {
      ro = new IntersectionObserver(function (es) { es.forEach(function (e) { e.isIntersecting ? start() : stop(); }); }, { threshold: 0.05 });
      ro.observe(canvas);
    } else { start(); }
    document.addEventListener("visibilitychange", function () { document.hidden ? stop() : start(); });
  }

  // ---- scroll reveals -----------------------------------------------------
  function reveals() {
    var els = document.querySelectorAll(".reveal");
    if (REDUCED || !("IntersectionObserver" in window)) {
      els.forEach(function (el) { el.classList.add("in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    els.forEach(function (el) { io.observe(el); });
  }

  function init() {
    var hero = document.getElementById("lp-net");
    if (hero) network(hero, { density: 13000, cap: 70, maxLink: 132, hub: false, speed: 0.16 });
    var map = document.getElementById("lp-map");
    if (map) network(map, { density: 5200, cap: 30, maxLink: 120, hub: true, speed: 0.22 });
    reveals();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
