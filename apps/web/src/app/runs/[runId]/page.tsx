import { notFound } from "next/navigation";
import { Workspace } from "@/components/workspace";

export default async function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(runId)) notFound();
  return <Workspace section="experiments" initialRunId={runId} />;
}
