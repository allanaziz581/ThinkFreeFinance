import { useEffect, useRef } from "react";

/**
 * Hero influence network. A detailed, live rendition of the app's InfluenceWeb:
 * Congress at the center with sector hubs radiating out, real company tickers
 * clustered by sector, plus politician and financial nodes cross-linked to the
 * companies they touch. Category color-coding mirrors the app's TYPE_COLOR
 * (company #E5E9F0, government #38BDF8, political #EF4444, financial #E9C46A).
 *
 * Behaviour: continuous gentle drift with a spring back to home slots, pulsing
 * connection lines with a signal dot travelling along each edge, cursor
 * repulsion, and hover focus (the hovered node and its links light up while the
 * rest dim). Canvas 2D, no WebGL. Pauses offscreen; static under reduced-motion.
 */

// Category palette (mirrors app.js TYPE_COLOR).
const CAT = {
  company:    { fill: "rgba(229,233,240,0.10)", ring: "#E5E9F0", text: "#EAF0F7" },
  government: { fill: "rgba(56,189,248,0.18)",  ring: "#38BDF8", text: "#DCF3FF" },
  political:  { fill: "rgba(239,68,68,0.14)",   ring: "#EF4444", text: "#FBD5D5" },
  financial:  { fill: "rgba(233,196,110,0.14)", ring: "#E9C46A", text: "#F4E7C6" },
  sector:     { fill: "rgba(56,189,248,0.10)",  ring: "rgba(56,189,248,0.55)", text: "#BFE6FB" },
};

// Sectors (evenly spaced around Congress) and their top tickers with a weight.
const SECTORS = [
  { id: "defense", label: "Defense", companies: [["LMT", 3], ["RTX", 2], ["NOC", 2]] },
  { id: "tech", label: "Technology", companies: [["NVDA", 3], ["AAPL", 3], ["MSFT", 2]] },
  { id: "energy", label: "Energy", companies: [["XOM", 2], ["CVX", 2]] },
  { id: "financials", label: "Financials", companies: [["JPM", 2], ["GS", 2]] },
  { id: "health", label: "Health", companies: [["UNH", 2], ["PFE", 2]] },
];

// Politician + financial nodes, cross-linked to Congress and to tickers.
const POLITICAL = [
  { id: "pol_morgan", label: "Rep. Morgan", links: ["NVDA", "LMT"] },
  { id: "pol_blake", label: "Sen. Blake", links: ["XOM", "RTX"] },
  { id: "pol_reed", label: "Sen. Reed", links: ["JPM", "AAPL"] },
];
const FINANCIAL = [
  { id: "fin_blk", label: "BlackRock", links: ["AAPL", "MSFT", "JPM"] },
  { id: "fin_lobby", label: "Lobbying", links: ["defense", "energy"] },
];

// Build the graph (normalized home positions in 0..1) once.
function buildGraph() {
  const nodes = [];
  const edges = [];
  const push = (n) => { nodes.push(n); return n; };
  const byId = {};
  const add = (n) => { const x = push(n); byId[n.id] = x; return x; };

  add({ id: "congress", label: "Congress", type: "government", r: 33, hx: 0.5, hy: 0.5 });

  const N = SECTORS.length;
  SECTORS.forEach((sec, i) => {
    const ang = (i / N) * Math.PI * 2 - Math.PI / 2;
    const sx = 0.5 + Math.cos(ang) * 0.24;
    const sy = 0.5 + Math.sin(ang) * 0.28;
    add({ id: sec.id, label: sec.label, type: "sector", r: 20, hx: sx, hy: sy });
    edges.push({ a: "congress", b: sec.id, w: 2 });

    const m = sec.companies.length;
    sec.companies.forEach(([tk, w], j) => {
      const spread = 0.5;
      const ca = ang + (j - (m - 1) / 2) * spread;
      const cx = 0.5 + Math.cos(ca) * 0.42;
      const cy = 0.5 + Math.sin(ca) * 0.46;
      add({ id: tk, label: tk, type: "company", r: 11 + w * 2.4, hx: cx, hy: cy });
      edges.push({ a: sec.id, b: tk, w: 1 });
    });
  });

  // politicians sit in the gaps between sectors, on an inner ring
  POLITICAL.forEach((p, i) => {
    const ang = ((i + 0.5) / POLITICAL.length) * Math.PI * 2 - Math.PI / 2 + 0.6;
    const px = 0.5 + Math.cos(ang) * 0.16;
    const py = 0.5 + Math.sin(ang) * 0.18;
    add({ id: p.id, label: p.label, type: "political", r: 14, hx: px, hy: py });
    edges.push({ a: "congress", b: p.id, w: 1 });
    p.links.forEach((t) => edges.push({ a: p.id, b: t, w: 1, cross: true }));
  });

  FINANCIAL.forEach((f, i) => {
    const ang = (i / FINANCIAL.length) * Math.PI * 2 + 0.9;
    const fx = 0.5 + Math.cos(ang) * 0.13;
    const fy = 0.5 + Math.sin(ang) * 0.14;
    add({ id: f.id, label: f.label, type: "financial", r: 14, hx: fx, hy: fy });
    f.links.forEach((t) => edges.push({ a: f.id, b: t, w: 1, cross: true }));
  });

  // resolve edge endpoints to node indices, drop any dangling
  const index = Object.fromEntries(nodes.map((n, i) => [n.id, i]));
  const E = edges
    .filter((e) => index[e.a] != null && index[e.b] != null)
    .map((e, i) => ({ ai: index[e.a], bi: index[e.b], w: e.w, cross: !!e.cross, phase: (i * 0.37) % 1 }));

  // adjacency for hover focus
  const adj = nodes.map(() => new Set());
  E.forEach((e) => { adj[e.ai].add(e.bi); adj[e.bi].add(e.ai); });

  return { nodes, edges: E, adj, index };
}

export default function InfluenceMap() {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const G = buildGraph();
    const S = G.nodes.map((n) => ({ ...n, x: 0, y: 0, vx: 0, vy: 0, seeded: false }));
    let W = 0, H = 0, dpr = Math.min(window.devicePixelRatio || 1, 2), t = 0;
    const mouse = { x: -9999, y: -9999, on: false };
    let hover = -1;

    function resize() {
      const rect = wrap.getBoundingClientRect();
      W = rect.width; H = rect.height;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      canvas.style.width = W + "px"; canvas.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      S.forEach((s) => {
        s.homeX = s.hx * W; s.homeY = s.hy * H;
        if (!s.seeded) { s.x = s.homeX; s.y = s.homeY; s.seeded = true; }
      });
    }

    function nodeFocus(i) {
      if (hover < 0) return 1;
      if (i === hover) return 1;
      return G.adj[hover].has(i) ? 0.95 : 0.16;
    }
    function edgeFocus(e) {
      if (hover < 0) return 1;
      return e.ai === hover || e.bi === hover ? 1 : 0.12;
    }

    function draw() {
      t += 1;
      ctx.clearRect(0, 0, W, H);

      // physics
      if (!reduce) {
        for (const s of S) {
          s.vx += Math.cos(t * 0.006 + s.homeY * 0.6) * 0.004;
          s.vy += Math.sin(t * 0.007 + s.homeX * 0.6) * 0.004;
          s.vx += (s.homeX - s.x) * 0.01;
          s.vy += (s.homeY - s.y) * 0.01;
          if (mouse.on) {
            const dx = s.x - mouse.x, dy = s.y - mouse.y, d2 = dx * dx + dy * dy, R = 110;
            if (d2 < R * R) {
              const d = Math.max(Math.sqrt(d2), 0.001), f = (1 - d / R) * 1.8;
              s.vx += (dx / d) * f; s.vy += (dy / d) * f;
            }
          }
          s.vx *= 0.88; s.vy *= 0.88;
          s.x += s.vx; s.y += s.vy;
          const pad = s.r + 3;
          s.x = Math.max(pad, Math.min(W - pad, s.x));
          s.y = Math.max(pad, Math.min(H - pad, s.y));
        }
      }

      // edges + travelling signal dots
      for (const e of G.edges) {
        const a = S[e.ai], b = S[e.bi];
        const fo = edgeFocus(e);
        const base = e.cross ? "233,196,110" : "56,189,248";
        const pulse = 0.16 + 0.16 * (0.5 + 0.5 * Math.sin(t * 0.02 + e.phase * 6));
        ctx.strokeStyle = `rgba(${base},${(reduce ? 0.22 : pulse) * fo})`;
        ctx.lineWidth = (e.w > 1 ? 1.3 : 0.9);
        if (e.cross) ctx.setLineDash([4, 4]); else ctx.setLineDash([]);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        ctx.setLineDash([]);

        if (!reduce) {
          const frac = (t * 0.006 + e.phase) % 1;
          const px = a.x + (b.x - a.x) * frac, py = a.y + (b.y - a.y) * frac;
          ctx.beginPath();
          ctx.arc(px, py, 1.7, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${e.cross ? "245,231,198" : "125,211,252"},${0.85 * fo})`;
          ctx.fill();
        }
      }

      // nodes (companies first, hubs on top for layering/depth)
      const order = S.map((_, i) => i).sort((i, j) => S[i].r - S[j].r);
      for (const i of order) {
        const s = S[i];
        const c = CAT[s.type];
        const fo = nodeFocus(i);
        const rr = s.r + (reduce ? 0 : Math.sin(t * 0.03 + s.homeX) * 0.9);

        // soft depth ring
        ctx.beginPath();
        ctx.arc(s.x, s.y, rr + 3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(8,10,14,${0.5 * fo})`;
        ctx.fill();

        // body
        ctx.beginPath();
        ctx.arc(s.x, s.y, rr, 0, Math.PI * 2);
        ctx.fillStyle = c.fill.replace(/[\d.]+\)$/, (m) => `${parseFloat(m) * fo})`);
        ctx.fill();
        ctx.lineWidth = i === hover ? 2 : s.type === "government" ? 1.6 : 1.1;
        ctx.strokeStyle = withAlpha(c.ring, (i === hover ? 1 : 0.85) * fo);
        ctx.stroke();

        // inner accent ring for weightier nodes
        if (s.r > 15) {
          ctx.beginPath();
          ctx.arc(s.x, s.y, rr - 3.5, 0, Math.PI * 2);
          ctx.strokeStyle = withAlpha(c.ring, 0.28 * fo);
          ctx.lineWidth = 1; ctx.stroke();
        }

        // label
        const fs = Math.max(8.5, Math.min(13, s.r * 0.6));
        ctx.fillStyle = withAlpha(c.text, fo);
        ctx.font = `${s.type === "company" ? 700 : 600} ${fs}px Inter, system-ui, sans-serif`;
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(s.label, s.x, s.y);
      }
    }

    function withAlpha(color, a) {
      if (color.startsWith("#")) {
        const v = color.slice(1);
        const r = parseInt(v.slice(0, 2), 16), g = parseInt(v.slice(2, 4), 16), b = parseInt(v.slice(4, 6), 16);
        return `rgba(${r},${g},${b},${a})`;
      }
      // rgba(...) already
      return color.replace(/[\d.]+\)$/, `${a})`);
    }

    let raf = 0, running = true;
    const loop = () => { if (!running) return; draw(); raf = requestAnimationFrame(loop); };
    resize(); draw(); if (!reduce) loop();

    const onResize = () => resize();
    const onMove = (e) => {
      const rect = wrap.getBoundingClientRect();
      mouse.x = e.clientX - rect.left; mouse.y = e.clientY - rect.top; mouse.on = true;
      // hit-test topmost (largest first)
      let found = -1, bestR = 1e9;
      for (let i = 0; i < S.length; i++) {
        const dx = S[i].x - mouse.x, dy = S[i].y - mouse.y;
        if (dx * dx + dy * dy < (S[i].r + 4) * (S[i].r + 4) && S[i].r < bestR) { found = i; bestR = S[i].r; }
      }
      hover = found;
      wrap.style.cursor = found >= 0 ? "pointer" : "default";
    };
    const onLeave = () => { mouse.on = false; mouse.x = -9999; mouse.y = -9999; hover = -1; };

    window.addEventListener("resize", onResize);
    wrap.addEventListener("pointermove", onMove);
    wrap.addEventListener("pointerleave", onLeave);

    const io = new IntersectionObserver((ents) => {
      ents.forEach((en) => {
        if (en.isIntersecting && !reduce) { if (!running) { running = true; loop(); } }
        else { running = false; cancelAnimationFrame(raf); }
      });
    }, { threshold: 0.04 });
    io.observe(wrap);

    return () => {
      running = false; cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      wrap.removeEventListener("pointermove", onMove);
      wrap.removeEventListener("pointerleave", onLeave);
      io.disconnect();
    };
  }, []);

  return (
    <div
      ref={wrapRef}
      className="relative h-full w-full"
      role="img"
      aria-label="An interactive influence network: Congress at the center linked to market sectors, company tickers, politicians, and financial institutions."
    >
      <canvas ref={canvasRef} className="block h-full w-full" />
    </div>
  );
}
