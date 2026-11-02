// The owner's L mark for the top bar: an L-shaped flood gauge, its upper stem pale and its lower stem and foot water blue.
// app/brand/lusot-mark.svg is the master; this is its drawing (cropped to the mark, as the boot screen in index.html crops
// it), with the colours as the brand tokens' fill utilities. Layout.test.tsx holds its paths to the master's. It is
// decoration beside the "Lusot" wordmark, so screen readers skip it.
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg data-brand-mark="" viewBox="126 95 263 320" aria-hidden="true" focusable="false" className={className}>
      <defs>
        <clipPath id="lusot-bar-mark-clip">
          <path d="M130.7 120.4A21.2 21.2 0 0 1 151.9 99.2H197.6A32.7 32.7 0 0 1 230.3 131.9V324.6H356.8A27.8 27.8 0 0 1 384.6 352.4V383A27.8 27.8 0 0 1 356.8 410.7H204.1A73.5 73.5 0 0 1 130.7 337.3V216.6H164.3A7.3 7.3 0 0 0 164.3 201.9H130.7V158.6H164.3A7.3 7.3 0 0 0 164.3 143.9H130.7Z" />
        </clipPath>
      </defs>
      <g clipPath="url(#lusot-bar-mark-clip)">
        <rect x="120" y="95" width="270" height="320" className="fill-brand-pale" />
        <path
          d="M122.5 260.8L130.7 261.1C138 262.2 142.9 262.9 147.4 262.9C173.5 262.9 173.9 252.2 200.1 252.2C212.3 252.2 222.5 255.6 230.3 258.9L236.8 259.2H390V416.5H122.5Z"
          className="fill-brand-water"
        />
      </g>
    </svg>
  )
}
