"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <main className="standalone"><p className="eyebrow">WORKSPACE ERROR</p>
    <h1>The page could not load.</h1><p>Your browser can retry the request.</p>
    <button className="button primary" onClick={reset}>Try again</button>
  </main>;
}
