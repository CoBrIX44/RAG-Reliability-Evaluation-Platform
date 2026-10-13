import type { Section } from "@/lib/workspace";

type Name = Section | "arrow" | "refresh" | "book" | "check" | "menu";
const paths: Record<Name, React.ReactNode> = {
  experiments: <><path d="M9 3h6M10 3v6l-6 10a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2L14 9V3M8 15h8" /></>,
  documents: <><path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8zM14 3v5h5M9 12h6M9 16h6" /></>,
  datasets: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7" /></>,
  comparisons: <><path d="M4 20V4M4 20h17M8 16v-4M13 16V7M18 16v-7" /></>,
  settings: <><path d="M4 7h16M4 17h16" /><circle cx="8" cy="7" r="2" /><circle cx="16" cy="17" r="2" /></>,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  refresh: <><path d="M20 11a8 8 0 1 0-2 6M20 4v7h-7" /></>,
  book: <><path d="M12 5v16M12 5C9 3 5 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 1" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
};

export function Icon({ name, className = "" }: { name: Name; className?: string }) {
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
