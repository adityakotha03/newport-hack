export default function Logo({ size = 34 }) {
  return (
    <div className="logo">
      <svg width={size} height={size} viewBox="0 0 100 100" fill="none"
           xmlns="http://www.w3.org/2000/svg" aria-label="Prism logo">
        <defs>
          <linearGradient id="spectrum" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#8c5aff" />
            <stop offset="33%" stopColor="#3b82f6" />
            <stop offset="66%" stopColor="#22d3ee" />
            <stop offset="100%" stopColor="#ec4899" />
          </linearGradient>
        </defs>
        {/* incoming white beam */}
        <line x1="2" y1="50" x2="38" y2="50" stroke="#ffffff" strokeWidth="4" strokeLinecap="round" />
        {/* refracted spectrum */}
        <line x1="56" y1="58" x2="98" y2="30" stroke="#8c5aff" strokeWidth="3" strokeLinecap="round" />
        <line x1="56" y1="60" x2="98" y2="44" stroke="#3b82f6" strokeWidth="3" strokeLinecap="round" />
        <line x1="56" y1="62" x2="98" y2="58" stroke="#22d3ee" strokeWidth="3" strokeLinecap="round" />
        <line x1="56" y1="64" x2="98" y2="72" stroke="#ec4899" strokeWidth="3" strokeLinecap="round" />
        {/* prism */}
        <polygon points="44,20 70,68 18,68" fill="url(#spectrum)" fillOpacity="0.18"
                 stroke="url(#spectrum)" strokeWidth="4" strokeLinejoin="round" />
      </svg>
      <span className="logo-word">Prism</span>
    </div>
  );
}
