import type { Metadata } from "next";
import localFont from "next/font/local";
import Script from "next/script";
import { instrument, ostrich } from "./fonts";
import "lenis/dist/lenis.css";
import "./globals.css";
import "./workspace-editorial.css";

const plex = localFont({ src: [
  { path: "./fonts/ibm-plex-mono-400.woff2", weight: "400", style: "normal" },
  { path: "./fonts/ibm-plex-mono-500.woff2", weight: "500", style: "normal" },
], variable: "--font-code", display: "swap", preload: false });

export const metadata: Metadata = {
  title: "RAG Observatory · Reliability workspace",
  description: "Compare retrieval strategies and inspect the evidence behind every answer.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${instrument.variable} ${ostrich.variable} ${plex.variable}`} suppressHydrationWarning><body>
    <Script id="workspace-theme" strategy="beforeInteractive">{`try{var t=localStorage.getItem("rag-observatory-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch{}`}</Script>
    {children}</body></html>;
}
