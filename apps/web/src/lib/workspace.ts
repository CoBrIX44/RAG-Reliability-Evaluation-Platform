import { z } from "zod";

export const workspaceSchema = z.object({
  stage: z.enum(["foundation", "documents", "datasets"]),
  api: z.literal("ready"),
  database: z.object({
    status: z.enum(["ready", "unavailable"]),
    code: z.enum(["ok", "database_unavailable", "schema_mismatch", "vector_unavailable"]),
    message: z.string(),
    worker_status: z.enum(["ready", "stale", "unavailable"]),
  }),
  capabilities: z.array(z.string()),
  generation_configured: z.boolean(),
  judge_configured: z.boolean(),
});

export type WorkspaceStatus = z.infer<typeof workspaceSchema>;
export type Section = "experiments" | "documents" | "datasets" | "comparisons" | "settings";

export const sections: { id: Section; label: string; href: string }[] = [
  { id: "experiments", label: "Experiments", href: "/" },
  { id: "documents", label: "Documents", href: "/documents" },
  { id: "datasets", label: "Datasets", href: "/datasets" },
  { id: "comparisons", label: "Comparisons", href: "/comparisons" },
  { id: "settings", label: "Settings", href: "/settings" },
];
