import { useEffect, useRef } from "react";

/**
 * Ethereal light beams background (the ethereal-beams aesthetic, built natively
 * on a 2D canvas so it stays light on mobile). A few soft diagonal beams drift
 * slowly across a dark field, additive and restrained (not glow-spam). Only
 * animates while onscreen; renders a single static frame under reduced-motion.
 */
export default function Beams({ className = "" }) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let W = 0, H = 0, dpr = Math.min(window.devicePixelRatio || 1, 2), t = 0;

    const BEAMS = [
      { x: 0.2, w: 0.16, hue: "56,189,248", a: 0.10, sp: 0.00018 },
      { x: 0.45, w: 0.10, hue: "125,211,252", a: 0.07, sp: 0.00026 },
      { x: 0.72, w: 0.20, hue: "56,189,248", a: 0.08, sp: 0.00015 },
      { x: 0.9, w: 0.12, hue: "233,196,110", a: 0.05, sp: 0.00022 },
    ];

    function resize() {
      const rect = canvas.getBoundingClientRect();
      W = rect.width; H = rect.height;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function draw() {
      t += 1;
      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";
      ctx.save();
      ctx.translate(W / 2, H / 2);
      ctx.rotate(-0.35);
      ctx.translate(-W / 2, -H / 2);
      for (const b of BEAMS) {
        const drift = reduce ? 0 : Math.sin(t * b.sp * 1000) * 0.06;
        const cx = (b.x + drift) * W;
        const bw = b.w * W;
        const g = ctx.createLinearGradient(cx - bw, 0, cx + bw, 0);
        g.addColorStop(0, `rgba(${b.hue},0)`);
        g.addColorStop(0.5, `rgba(${b.hue},${b.a})`);
        g.addColorStop(1, `rgba(${b.hue},0)`);
        ctx.fillStyle = g;
        ctx.fillRect(cx - bw, -H, bw * 2, H * 3);
      }
      ctx.restore();
      ctx.globalCompositeOperation = "source-over";
    }

    let raf = 0, running = true;
    const loop = () => { if (!running) return; draw(); raf = requestAnimationFrame(loop); };
    resize(); draw(); if (!reduce) loop();

    const onResize = () => { resize(); if (reduce) draw(); };
    window.addEventListener("resize", onResize);
    const io = new IntersectionObserver((ents) => {
      ents.forEach((en) => {
        if (en.isIntersecting && !reduce) { if (!running) { running = true; loop(); } }
        else { running = false; cancelAnimationFrame(raf); }
      });
    }, { threshold: 0.01 });
    io.observe(canvas);

    return () => { running = false; cancelAnimationFrame(raf); window.removeEventListener("resize", onResize); io.disconnect(); };
  }, []);

  return <canvas ref={ref} aria-hidden="true" className={`block h-full w-full ${className}`} />;
}
