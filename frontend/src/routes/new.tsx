import { createFileRoute } from "@tanstack/react-router";
import { NewEvaluation } from "@/components/visionguard/workspace";
export const Route = createFileRoute("/new")({
  head: () => ({ meta: [
    { title: "VisionGuard — New Evaluation" },
    { name: "description", content: "VisionGuard new evaluation for object-detection model reliability evaluation." },
    { property: "og:title", content: "VisionGuard — New Evaluation" },
    { property: "og:description", content: "Inspect model reliability using clean and corrupted image evaluation evidence." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: NewEvaluation,
});

