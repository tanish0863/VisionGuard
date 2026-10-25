import { createFileRoute } from "@tanstack/react-router";
import { Dashboard } from "@/components/visionguard/workspace";
export const Route = createFileRoute("/dashboard")({
  head: () => ({ meta: [
    { title: "VisionGuard — Model Reliability Overview" },
    { name: "description", content: "VisionGuard model reliability overview for object-detection model reliability evaluation." },
    { property: "og:title", content: "VisionGuard — Model Reliability Overview" },
    { property: "og:description", content: "Inspect model reliability using clean and corrupted image evaluation evidence." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: Dashboard,
});

