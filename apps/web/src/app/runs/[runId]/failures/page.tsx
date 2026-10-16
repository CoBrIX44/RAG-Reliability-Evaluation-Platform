import { Workspace } from "@/components/workspace";

export default async function FailuresPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <Workspace section="experiments" failureRunId={runId} />;
}
