import Link from "next/link";

export default function NotFound() {
  return <main className="standalone"><p className="eyebrow">404 · UNKNOWN PAGE</p>
    <h1>This page is outside the workspace.</h1>
    <p>Return to experiments to continue.</p><Link className="button primary" href="/experiments">Open experiments</Link>
  </main>;
}
