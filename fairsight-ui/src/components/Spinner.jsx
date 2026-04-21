/** Simple accessible spinner — no libraries needed. */
export default function Spinner({ size = 20, label = 'Loading…' }) {
  return (
    <span role="status" aria-label={label} className="inline-flex items-center gap-2">
      <svg
        style={{ width: size, height: size }}
        viewBox="0 0 24 24"
        fill="none"
        className="animate-spin text-accent"
        aria-hidden="true"
      >
        <circle
          cx="12" cy="12" r="10"
          stroke="currentColor"
          strokeWidth="3"
          strokeOpacity="0.25"
        />
        <path
          d="M22 12a10 10 0 0 1-10 10"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      <span className="sr-only">{label}</span>
    </span>
  )
}
