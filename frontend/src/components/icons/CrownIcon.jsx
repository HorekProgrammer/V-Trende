export default function CrownIcon()
{
  return (
    <svg
      className="crown-icon"
      width="30"
      height="24"
      viewBox="0 0 48 38"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="crownGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#FFE3A3" />
          <stop offset="100%" stopColor="#F2B84B" />
        </linearGradient>
      </defs>
      <path
        d="M5,32 L5,13 L16,22 L24,6 L32,22 L43,13 L43,32 Z"
        fill="url(#crownGrad)"
        stroke="#F2B84B"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <rect x="4" y="31" width="40" height="5" rx="2" fill="url(#crownGrad)" stroke="#F2B84B" strokeWidth="1.2" />
      <circle cx="24" cy="6" r="3.4" fill="#FFEFC9" stroke="#F2B84B" strokeWidth="1.1" />
      <circle cx="16" cy="22" r="2.6" fill="#FFEFC9" stroke="#F2B84B" strokeWidth="1" />
      <circle cx="32" cy="22" r="2.6" fill="#FFEFC9" stroke="#F2B84B" strokeWidth="1" />
    </svg>
  );
}