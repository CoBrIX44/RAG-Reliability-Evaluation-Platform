"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import Lenis from "lenis";
import { gsap } from "gsap";

/** Finite entrance motion; never animate live result rows or block native nested scrolling. */
export function WorkspaceMotion() {
  const pathname = usePathname();
  useEffect(() => {
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const lenis = new Lenis({
        autoRaf: false,
        anchors: false,
        prevent: node => !!node.closest("[data-lenis-prevent], textarea, select, .sidebar, .annotation-source, pre, .run-table-scroll, .table-scroll"),
      });
      const tick = (time: number) => lenis.raf(time * 1000);
      gsap.ticker.add(tick);
      const context = gsap.context(() => {
        gsap.from(".page-heading > div:first-child", { y: 12, duration: 0.4, ease: "power2.out", clearProps: "all" });
      }, ".app-shell");
      return () => { context.revert(); gsap.ticker.remove(tick); lenis.destroy(); };
    });
    return () => media.revert();
  }, [pathname]);
  return null;
}
