import { Workspace } from "@/components/workspace";

export default async function ComparisonPage({ params }: { params: Promise<{ comparisonId: string }> }) {
  const { comparisonId } = await params;
  return <Workspace section="comparisons" initialComparisonId={comparisonId} />;
}
