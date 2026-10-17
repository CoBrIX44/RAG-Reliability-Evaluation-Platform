"use client";

import { useSyncExternalStore } from "react";

type Theme = "system" | "light" | "dark";
const key = "rag-observatory-theme";
const changed = "rag-theme-changed";

function preference(): Theme {
  try {
    const stored = localStorage.getItem(key);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    const current = document.documentElement.dataset.theme;
    return current === "light" || current === "dark" ? current : "system";
  }
}

function subscribe(update: () => void) {
  const sync = () => {
    document.documentElement.dataset.theme = preference();
    update();
  };
  sync();
  window.addEventListener(changed, sync);
  window.addEventListener("storage", sync);
  return () => { window.removeEventListener(changed, sync); window.removeEventListener("storage", sync); };
}

export function ThemeControl() {
  const theme = useSyncExternalStore(subscribe, preference, () => "system" as const);
  return <label className="theme-control">Appearance
    <select aria-label="Color theme" value={theme} onChange={event => {
      const value = event.target.value;
      document.documentElement.classList.add("theme-changing");
      document.documentElement.dataset.theme = value;
      try { localStorage.setItem(key, value); } catch { /* Theme still applies for this page. */ }
      window.dispatchEvent(new Event(changed));
      requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.remove("theme-changing")));
    }}>
      <option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option>
    </select>
  </label>;
}
