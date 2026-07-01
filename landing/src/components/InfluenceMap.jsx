import { useEffect, useRef } from "react";

/**
 * Interactive influence network (item 1): a live bubble/node graph on canvas.
 * Nodes drift continuously with a gentle spring back toward their home slot, the
 * connecting edges pulse, and the whole field reacts to the cursor (nodes are
 * repelled and jiggle as the pointer passes). Lightweight 2D canvas, no WebGL.
 * Pauses when offscreen; renders a static graph under prefers-reduced-motion.
 */

// Home positions in normalized 0..1 space, sized to the container at runtime.
const NODES = [
  { id: "congress", hx: 0.5, hy: 0.5, r: 30, label: "Congress", kind: "hub" },
  { id: "law", hx: 0.5, hy: 0.16, r: 22, label: "The law", kind: "hub" },
  { id: "defense", hx: 0.19, hy: 0.3, r: 19, label: "Defense", kind: "sector" },
  { id: "pharma", hx: 0.82, hy: 0.3, r: 19, label: "Pharma", kind: "sector" },
  { id: "tech", hx: 0.16, hy: 0.66, r: 19, label: "Tech", kind: "sector" },
  { id: "energy", hx: 0.84, hy: 0.66, r: 19, label: "Energy", kind: "sector" },
  { id: "contracts", hx: 0.31, hy: 0.86, r: 15, label: "Contracts", kind: "leaf" },
  { id: "trades", hx: 0.5, hy: 0.9, r: 16, label: "Trades", kind: "leaf" },
  { id: "lobby", hx: 0.69, hy: 0.86, r: 15, label: "Lobbying", kind: "leaf" },
];

const EDGES = [
  ["law", "congress"], ["congress", "defense"], ["congress", "pharma"],
  ["congress", "tech"], ["congress", "energy"], ["congress", "trades"],
  ["defense", "contracts"], ["energy", "lobby"], ["pharma", "lobby"],
  ["tech", "contracts"], ["law", "defense"], ["law", "pharma"],
];

const STYLE = {
  hub: { fill: "rgba(56,189,248,0.16)", stroke: "#38BDF8", text: "#E6F6FF", fs: 12 },
  sector: { fill: "rgba(56,189,248,0.09)", stroke: "rgba(56,189,248,0.6)", text: "#CBE9FB", fs: 10.5 },
  leaf: { fill: "rgba(148,163,184,0.10)", stroke: "rgba(148,163,184,0.5)", text: "#AFC0D4", fs: 10 },
};

export default function InfluenceMap() {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let W = 0, H = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
    const idx = Object.fromEntries(NODES.map((n, i) => [n.id, i]));
    // working state per node
    const S = NODES.map((n) => ({ ...n, x: 0, y: 0, vx: 0, vy: 0 }));
    const mouse = { x: -9999, y: -9999, on: false };
    let t = 0;

    function resize() {
      const rect = wrap.getBoundingClientRect();
      W = rect.width; H = rect.height;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      canvas.style.width = W + "px";
      canvas.style.height = H + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // seed positions from home
      S.forEach((s) => {
        s.homeX = s.hx * W; s.homeY = s.hy * H;
        if (s.x === 0 && s.y === 0) { s.x = s.homeX; s.y = s.homeY; }
      });
    }

    function step() {
      t += 1;
      ctx.clearRect(0, 0, W, H);

      // edges first
      for (const [a, b] of EDGES) {
        const na = S[idx[a]], nb = S[idx[b]];
        const pulse = 0.18 + 0.22 * (0.5 + 0.5 * Math.sin(t * 0.02 + (na.homeX + nb.homeY) * 0.01));
        ctx.strokeStyle = `rgba(56,189,248,${reduce ? 0.28 : pulse})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(na.x, na.y);
        ctx.lineTo(nb.x, nb.y);
        ctx.stroke();
      }

      for (const s of S) {
        if (!reduce) {
          // gentle drift via slow noise
          s.vx += Math.cos(t * 0.008 + s.homeY) * 0.006;
          s.vy += Math.sin(t * 0.009 + s.homeX) * 0.006;
          // spring back to home
          s.vx += (s.homeX - s.x) * 0.008;
          s.vy += (s.homeY - s.y) * 0.008;
          // cursor repulsion
          if (mouse.on) {
            const dx = s.x - mouse.x, dy = s.y - mouse.y;
            const d2 = dx * dx + dy * dy;
            const R = 120;
            if (d2 < R * R) {
              const d = Math.max(Math.sqrt(d2), 0.001);
              const f = (1 - d / R) * 2.2;
              s.vx += (dx / d) * f;
              s.vy += (dy / d) * f;
            }
          }
          s.vx *= 0.9; s.vy *= 0.9;
          s.x += s.vx; s.y += s.vy;
          // soft containment
          const pad = s.r + 4;
          s.x = Math.max(pad, Math.min(W - pad, s.x));
          s.y = Math.max(pad, Math.min(H - pad, s.y));
        }

        const st = STYLE[s.kind];
        // breathing radius
        const rr = s.r + (reduce ? 0 : Math.sin(t * 0.03 + s.homeX) * 1.2);
        ctx.beginPath();
        ctx.arc(s.x, s.y, rr, 0, Math.PI * 2);
        ctx.fillStyle = st.fill;
        ctx.fill();
        ctx.lineWidth = s.kind === "hub" ? 1.5 : 1;
        ctx.strokeStyle = st.stroke;
        ctx.stroke();
        // label
        ctx.fillStyle = st.text;
        ctx.font = `600 ${st.fs}px Inter, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(s.label, s.x, s.y);
      }
    }

    let raf = 0, running = true;
    function loop() { if (!running) return; step(); raf = requestAnimationFrame(loop); }

    resize();
    step();
    if (!reduce) loop();

    const onResize = () => resize();
    const onMove = (e) => {
      const rect = wrap.getBoundingClientRect();
      mouse.x = e.clientX - rect.left; mouse.y = e.clientY - rect.top; mouse.on = true;
    };
    const onLeave = () => { mouse.on = false; mouse.x = -9999; mouse.y = -9999; };

    window.addEventListener("resize", onResize);
    wrap.addEventListener("pointermove", onMove);
    wrap.addEventListener("pointerleave", onLeave);

    // pause when offscreen
    const io = new IntersectionObserver((ents) => {
      ents.forEach((en) => {
        if (en.isIntersecting && !reduce) { if (!running) { running = true; loop(); } }
        else { running = false; cancelAnimationFrame(raf); }
      });
    }, { threshold: 0.05 });
    io.observe(wrap);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
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
      aria-label="An interactive network linking a law to Congress, market sectors, government contracts, lobbying, and disclosed trades."
    >
      <canvas ref={canvasRef} className="block h-full w-full" />
    </div>
  );
}
