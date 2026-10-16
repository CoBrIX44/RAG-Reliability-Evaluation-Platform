import { Workspace } from "@/components/workspace";

export default async function ResultPage({ params }: { params: Promise<{ runId: string; resultId: string }> }) {
  const { runId, resultId } = await params;
  return <Workspace section="experiments" initialRunId={runId} initialResultId={resultId} />;
}
