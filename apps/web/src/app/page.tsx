import type { Metadata } from "next";
import { Landing } from "@/components/landing";
import "./landing.css";


export const metadata: Metadata = {
  title: "RAG Observatory · Answers need evidence",
  description: "Upload technical documents, build evaluation datasets, and compare RAG experiments with evidence you can inspect.",
};

export default function Home() {
  return <Landing />;
}
