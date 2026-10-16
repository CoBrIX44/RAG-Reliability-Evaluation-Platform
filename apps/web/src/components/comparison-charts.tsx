"use client";

import { metricNames } from "@/lib/runs";
import type { Report } from "@/lib/comparisons";

export function ComparisonCharts({ report }: { report: Report }) {
  const rows = Object.entries(report.metrics);
  const x = (value: number) => 510 + value * 200;
  const stages = ["question_wall_ms", "retrieval_wall_ms", "generation_wall_ms"];
  const timing = { baseline: report.accounting.baseline.subgroup_stage_timings ?? report.accounting.baseline.stage_timings, candidate: report.accounting.candidate.subgroup_stage_timings ?? report.accounting.candidate.stage_timings };
  const maximum = Math.max(1, ...stages.flatMap(stage => [timing.baseline[stage]?.p95 ?? 0, timing.candidate[stage]?.p95 ?? 0]));
  const stageNames = ["Question total", "Retrieval total", "Answer generation"];
  return <section className="comparison-charts" aria-label="Comparison charts">
    <figure><figcaption><h3>Paired score differences</h3><p>Candidate minus baseline, in percentage points. Lines show available 95% group-bootstrap intervals; circles show paired means. Blocked values are labeled descriptive. Full values, counts and exclusions are in the tables below.</p></figcaption>
      <div className="chart-scroll" role="region" aria-label="Scrollable paired difference chart" tabIndex={0}><svg viewBox={`0 0 800 ${90 + rows.length * 48}`} role="img" aria-labelledby="quality-chart-title" aria-describedby="quality-chart-desc"><title id="quality-chart-title">Paired differences with available uncertainty</title><desc id="quality-chart-desc">Missing values are labeled unavailable and are not plotted as zero. The paired quality comparison table provides all plotted values and sample counts.</desc>
        {[-100, -50, 0, 50, 100].map(tick => <g key={tick}><line x1={x(tick / 100)} x2={x(tick / 100)} y1={30} y2={40 + rows.length * 48} className={tick === 0 ? "chart-zero" : "chart-grid"} /><text x={x(tick / 100)} y={24} textAnchor="middle">{tick > 0 ? "+" : ""}{tick} pp</text></g>)}
        {rows.map(([name, value], i) => { const y = 62 + i * 48; return <g key={name}><text x={12} y={y + 5}>{metricNames[name] ?? name}</text>{value.difference == null ? <text x={320} y={y + 5}>unavailable</text> : <>{value.interval && value.state === "scored" && <><line className="chart-interval" x1={x(value.interval.low)} x2={x(value.interval.high)} y1={y} y2={y} /><line className="chart-interval" x1={x(value.interval.low)} x2={x(value.interval.low)} y1={y - 6} y2={y + 6} /><line className="chart-interval" x1={x(value.interval.high)} x2={x(value.interval.high)} y1={y - 6} y2={y + 6} /></>}<circle cx={x(value.difference)} cy={y} r={5} className={value.state === "blocked" ? "chart-blocked" : "chart-point"} /><text x={735} y={y + 5}>{value.state === "blocked" ? "descriptive" : `${value.paired_question_count}q / ${value.group_count}g`}</text></>}</g>; })}
      </svg></div><p className="pipeline-scroll-hint muted-text">Scroll the chart horizontally. q = paired questions; g = split groups.</p>
    </figure>
    <figure><figcaption><h3>Observed latency</h3><p>Sample p95 in milliseconds; selected-question timings where recorded, otherwise full-run timings for older reports. Baseline is blue; candidate is amber. Timings include model startup where recorded and do not establish portable performance. The latency tables below contain p50/p95 and sample counts.</p></figcaption><div className="chart-scroll" role="region" aria-label="Scrollable latency chart" tabIndex={0}><svg viewBox="0 0 800 260" role="img" aria-labelledby="latency-chart-title"><title id="latency-chart-title">Baseline and candidate observed p95 latency</title>{stages.map((stage, i) => <g key={stage}><text x={12} y={52 + i * 70}>{stageNames[i]}</text>{(["baseline", "candidate"] as const).map((side, j) => { const value = timing[side][stage]?.p95; const y = 32 + i * 70 + j * 24; return <g key={side}><text x={180} y={y + 14}>{side}</text>{value == null ? <text x={280} y={y + 14}>unavailable</text> : <><rect x={280} y={y} width={value / maximum * 370} height={16} className={`chart-${side}`} /><text x={660} y={y + 14}>{value.toFixed(1)} ms</text></>}</g>; })}</g>)}</svg></div></figure>
  </section>;
}
