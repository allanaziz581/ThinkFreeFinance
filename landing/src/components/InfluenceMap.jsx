import { motion, useReducedMotion } from "framer-motion";

/**
 * The signature visual: a living influence network. Pure SVG (no canvas, no
 * external libs beyond Framer) so it stays crisp at any size, respects
 * prefers-reduced-motion, and adds nothing to the landing CSP. Node positions
 * are fixed and deterministic; only opacity/scale animate, which keeps it cheap.
 */

// viewBox space is 0..400 x 0..300.
const NODES = [
  { id: "law", x: 200, y: 48, r: 22, label: "The law", kind: "hub" },
  { id: "congress", x: 200, y: 150, r: 26, label: "Congress", kind: "hub" },
  { id: "defense", x: 78, y: 96, r: 16, label: "Defense", kind: "sector" },
  { id: "pharma", x: 322, y: 96, r: 16, label: "Pharma", kind: "sector" },
  { id: "tech", x: 60, y: 200, r: 16, label: "Tech", kind: "sector" },
  { id: "energy", x: 340, y: 200, r: 16, label: "Energy", kind: "sector" },
  { id: "contracts", x: 120, y: 256, r: 13, label: "Contracts", kind: "leaf" },
  { id: "trades", x: 200, y: 268, r: 14, label: "Trades", kind: "leaf" },
  { id: "lobby", x: 280, y: 256, r: 13, label: "Lobbying", kind: "leaf" },
];

const EDGES = [
  ["law", "congress"],
  ["congress", "defense"],
  ["congress", "pharma"],
  ["congress", "tech"],
  ["congress", "energy"],
  ["congress", "trades"],
  ["defense", "contracts"],
  ["energy", "lobby"],
  ["pharma", "lobby"],
  ["tech", "contracts"],
  ["law", "defense"],
  ["law", "pharma"],
];

const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));

const KIND_STYLE = {
  hub: { fill: "rgba(56,189,248,0.16)", stroke: "#38BDF8", text: "#E6F6FF" },
  sector: { fill: "rgba(56,189,248,0.08)", stroke: "rgba(56,189,248,0.55)", text: "#CBE9FB" },
  leaf: { fill: "rgba(148,163,184,0.10)", stroke: "rgba(148,163,184,0.45)", text: "#AFC0D4" },
};

export default function InfluenceMap() {
  const reduce = useReducedMotion();

  return (
    <svg
      viewBox="0 0 400 300"
      className="h-full w-full"
      role="img"
      aria-label="A network linking a law to Congress, market sectors, government contracts, lobbying, and disclosed trades."
    >
      {/* flat panel: no ambient glow fill behind the graph */}

      {/* edges */}
      <g strokeLinecap="round">
        {EDGES.map(([a, b], i) => {
          const na = byId[a];
          const nb = byId[b];
          return (
            <motion.line
              key={`${a}-${b}`}
              x1={na.x}
              y1={na.y}
              x2={nb.x}
              y2={nb.y}
              stroke="#38BDF8"
              strokeWidth={1}
              initial={{ opacity: reduce ? 0.4 : 0.22 }}
              animate={reduce ? undefined : { opacity: [0.18, 0.6, 0.18] }}
              transition={
                reduce
                  ? undefined
                  : { duration: 3.4, repeat: Infinity, ease: "easeInOut", delay: (i % 6) * 0.45 }
              }
            />
          );
        })}
      </g>

      {/* traveling pulses along a couple of key edges (the "money trail") */}
      {!reduce &&
        [
          ["law", "congress"],
          ["congress", "trades"],
        ].map(([a, b], i) => {
          const na = byId[a];
          const nb = byId[b];
          return (
            <motion.circle
              key={`pulse-${i}`}
              r={2.6}
              fill="#7DD3FC"
              initial={{ cx: na.x, cy: na.y, opacity: 0 }}
              animate={{
                cx: [na.x, nb.x],
                cy: [na.y, nb.y],
                opacity: [0, 1, 1, 0],
              }}
              transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut", delay: i * 1.1 }}
            />
          );
        })}

      {/* nodes */}
      {NODES.map((n, i) => {
        const s = KIND_STYLE[n.kind];
        return (
          <motion.g
            key={n.id}
            initial={{ opacity: 0, scale: 0.6 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: reduce ? 0 : 0.06 * i, ease: "easeOut" }}
            style={{ transformOrigin: `${n.x}px ${n.y}px` }}
          >
            <motion.circle
              cx={n.x}
              cy={n.y}
              r={n.r}
              fill={s.fill}
              stroke={s.stroke}
              strokeWidth={n.kind === "hub" ? 1.5 : 1}
              animate={reduce ? undefined : { r: [n.r, n.r + 1.4, n.r] }}
              transition={
                reduce ? undefined : { duration: 4, repeat: Infinity, ease: "easeInOut", delay: i * 0.3 }
              }
            />
            <text
              x={n.x}
              y={n.y + (n.kind === "leaf" ? 3 : 3.5)}
              textAnchor="middle"
              fontSize={n.kind === "hub" ? 10 : 8}
              fontWeight="600"
              fill={s.text}
            >
              {n.label}
            </text>
          </motion.g>
        );
      })}
    </svg>
  );
}
