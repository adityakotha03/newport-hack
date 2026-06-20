import { useRef, useState } from "react";

/** Draggable before/after slider for images. */
export function ImageCompare({ before, after }) {
  const [pos, setPos] = useState(50);
  const ref = useRef(null);

  const move = (clientX) => {
    const r = ref.current.getBoundingClientRect();
    const p = ((clientX - r.left) / r.width) * 100;
    setPos(Math.max(0, Math.min(100, p)));
  };

  return (
    <div
      className="cmp"
      ref={ref}
      onMouseMove={(e) => e.buttons === 1 && move(e.clientX)}
      onClick={(e) => move(e.clientX)}
      onTouchMove={(e) => move(e.touches[0].clientX)}
    >
      <img className="cmp-img" src={after} alt="after" draggable="false" />
      <div className="cmp-clip" style={{ width: `${pos}%` }}>
        <img className="cmp-img" src={before} alt="before" draggable="false" style={{ width: `${10000 / pos}%` }} />
        <span className="cmp-tag cmp-tag-before">Before</span>
      </div>
      <span className="cmp-tag cmp-tag-after">After · AI</span>
      <div className="cmp-handle" style={{ left: `${pos}%` }}>
        <span className="cmp-knob">⟷</span>
      </div>
    </div>
  );
}

/** Side-by-side before/after videos that play together. */
export function VideoCompare({ before, after }) {
  return (
    <div className="vid-compare">
      <figure>
        <video src={before} muted loop autoPlay playsInline />
        <figcaption>Before</figcaption>
      </figure>
      <figure>
        <video src={after} muted loop autoPlay playsInline />
        <figcaption>After · AI</figcaption>
      </figure>
    </div>
  );
}
