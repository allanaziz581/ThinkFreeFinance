import Reveal from "./Reveal.jsx";

/** Consistent label + heading + lead block used across landing sections. */
export default function SectionHead({ label, title, lead, center = false }) {
  return (
    <Reveal className={center ? "text-center" : ""}>
      {label ? <div className="t-label">{label}</div> : null}
      <h2 className="t-h2 mt-3">{title}</h2>
      {lead ? (
        <p className={`t-lead mt-4 ${center ? "mx-auto max-w-2xl" : "max-w-2xl"}`}>{lead}</p>
      ) : null}
    </Reveal>
  );
}
