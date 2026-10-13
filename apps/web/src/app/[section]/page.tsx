import { notFound } from "next/navigation";
import { Workspace } from "@/components/workspace";
import { sections } from "@/lib/workspace";

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const match = sections.find((item) => item.id === section);
  if (!match) notFound();
  return <Workspace section={match.id} />;
}
