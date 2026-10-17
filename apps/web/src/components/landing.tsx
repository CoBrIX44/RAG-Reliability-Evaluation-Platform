"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import Lenis from "lenis";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Icon } from "@/components/icon";
import { ThemeControl } from "@/components/theme-control";

const methods = [
  { name: "Lexical", title: "Start with the words.", text: "Find passages that share terms with a question. A transparent baseline for technical names, commands, and exact vocabulary.", detail: "Keyword retrieval" },
  { name: "Dense", title: "Look beyond the wording.", text: "Search local sentence embeddings for related meaning. Inspect the returned passages to see where semantic similarity helps—and where it misses.", detail: "Local embeddings · cosine search" },
  { name: "Hybrid", title: "Bring both rankings together.", text: "Combine lexical and dense rankings with reciprocal rank fusion. Compare the same questions and corpus to understand what the combination changes.", detail: "Reciprocal rank fusion" },
  { name: "Reranking", title: "Give the shortlist a closer read.", text: "Score retrieved question–passage pairs with a local cross-encoder. Measure the added latency alongside changes in evidence retrieval.", detail: "Local cross-encoder" },
];

export function Landing() {
  const root = useRef<HTMLElement>(null);
  const [method, setMethod] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const lenis = new Lenis({ autoRaf: false, anchors: true });
      const update = () => ScrollTrigger.update();
      const tick = (time: number) => lenis.raf(time * 1000);
      lenis.on("scroll", update);
      gsap.ticker.add(tick);
      const context = gsap.context(() => {
        gsap.from(".landing-hero [data-enter]", { y: 28, opacity: 0, duration: 0.85, stagger: 0.1, ease: "power2.out", clearProps: "all" });
        gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach(element => {
          gsap.from(element, { y: 28, opacity: 0, duration: 0.7, ease: "power2.out", clearProps: "all", scrollTrigger: { trigger: element, start: "top 92%", once: true } });
        });
      }, root);
      return () => { context.revert(); gsap.ticker.remove(tick); lenis.off("scroll", update); lenis.destroy(); };
    });
    return () => media.revert();
  }, []);

  return <main className="landing" ref={root}>
    <a className="landing-skip" href="#landing-content">Skip to content</a>
    <header className="landing-nav">
      <Link href="/" className="landing-brand" aria-label="RAG Observatory home"><span className="landing-mark" aria-hidden="true">◉</span> RAG Observatory</Link>
      <button className="landing-menu" aria-expanded={menuOpen} aria-controls="landing-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? "Close" : "Menu"}<Icon name="menu" /></button>
      <nav id="landing-navigation" aria-label="Landing navigation" className={menuOpen ? "is-open" : ""}>
        <a href="#workflow" onClick={() => setMenuOpen(false)}>The workflow</a>
        <a href="#methods" onClick={() => setMenuOpen(false)}>The methods</a>
        <ThemeControl />
        <Link href="/experiments" className="landing-nav-cta">Open workspace <Icon name="arrow" /></Link>
      </nav>
    </header>

    <section className="landing-hero landing-width" id="landing-content">
      <div className="landing-hero-copy">
        <p className="landing-kicker" data-enter>Document in. Evidence out.</p>
        <h1 data-enter>Answers need<br /><em>evidence.</em></h1>
        <p className="landing-intro" data-enter>A workspace for testing how reliably AI answers questions from your technical documents.</p>
        <div className="landing-actions" data-enter>
          <Link href="/experiments" className="landing-cta">Open workspace <Icon name="arrow" /></Link>
          <Link href="/demo" className="landing-text-link">Explore the demo <Icon name="arrow" /></Link>
        </div>
      </div>
      <aside className="landing-hero-note" data-enter>
        <div className="landing-evidence-art" aria-hidden="true"><span>Question</span><i /><span>Source</span><i /><span>Answer</span><b>?</b></div>
        <p>A convincing answer is a beginning.<br />Trace it back to what the source actually says.</p>
        <a href="#workflow" className="landing-down">Follow the evidence <span aria-hidden="true">↓</span></a>
      </aside>
    </section>

    <section className="landing-product landing-width" aria-label="Product preview">
      <div className="landing-product-heading"><span>Inside the observatory</span><Link href="/demo">Inspect the demo <Icon name="arrow" /></Link></div>
      <Link href="/demo" className="landing-preview" aria-label="Open the read-only synthetic demo"><Image src="/landing/workspace-demo.jpg" alt="Actual read-only demo showing a question trace and a context-clipping example" width={1120} height={900} priority /></Link>
      <p className="landing-caption">Read-only demo. Synthetic evidence, not measured research results.</p>
    </section>

    <section id="workflow" className="landing-workflow landing-width">
      <div className="landing-section-intro" data-reveal><p className="landing-kicker">A question deserves a trail</p><h2>From a document<br />to a defensible comparison.</h2><p>Keep the source, the question, and the experiment connected. Then look closely at what changed.</p></div>
      <div className="landing-steps">
        <article data-reveal><Icon name="documents" /><div><h3>Build your source of truth.</h3><p>Upload technical documents. Inspect extracted sections and publish a versioned corpus.</p><Link href="/documents">Start with documents <Icon name="arrow" /></Link></div></article>
        <article data-reveal><Icon name="datasets" /><div><h3>Ask questions worth testing.</h3><p>Curate questions, reference answers, and source evidence. Keep review provenance and dataset versions visible.</p><Link href="/datasets">Explore datasets <Icon name="arrow" /></Link></div></article>
        <article data-reveal><Icon name="comparisons" /><div><h3>Compare. Inspect. Repeat.</h3><p>Run retrieval strategies against frozen inputs. Follow a failure down to the passage, context, and generated answer.</p><Link href="/comparisons">See comparisons <Icon name="arrow" /></Link></div></article>
      </div>
    </section>

    <section id="methods" className="landing-methods landing-width" data-reveal>
      <div className="landing-method-heading"><p className="landing-kicker">Different routes to the same evidence</p><h2>Change the method.<br />Keep the question.</h2></div>
      <div className="landing-method-controls" role="group" aria-label="Retrieval methods">{methods.map((item, index) => <button key={item.name} aria-pressed={method === index} onClick={() => setMethod(index)}>{item.name}<span aria-hidden="true">↗</span></button>)}</div>
      <div className="landing-method-description" aria-live="polite" aria-atomic="true"><span>{methods[method].detail}</span><h3>{methods[method].title}</h3><p>{methods[method].text}</p></div>
    </section>

    <section className="landing-measure landing-width" data-reveal><p className="landing-kicker">Make the limits visible</p><h2>See what was retrieved.<br />Know what was measured.</h2><div><p>Inspect retrieval precision and recall, context coverage, and latency. Keep answer assessments separate, with their scoring provenance.</p><p>Missing scores stay unavailable. Versions and traces stay attached. Export the evidence behind a comparison so others can inspect it.</p></div></section>

    <footer className="landing-footer landing-width"><div data-reveal><p className="landing-kicker">Your documents. Your questions.</p><h2>Put the answer<br />under observation.</h2><Link href="/experiments" className="landing-cta">Open workspace <Icon name="arrow" /></Link></div><div className="landing-footer-bottom"><Link href="/" className="landing-brand">RAG Observatory</Link><p>Built for careful questions.</p><Link href="/demo">Read-only demo <Icon name="arrow" /></Link></div></footer>
  </main>;
}
