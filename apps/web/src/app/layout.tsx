import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Observatory · Reliability workspace",
  description: "Compare retrieval strategies and inspect the evidence behind every answer.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
