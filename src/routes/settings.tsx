import { createFileRoute } from "@tanstack/react-router";
import { Settings } from "@/components/visionguard/workspace";
export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [
    { title: "VisionGuard — Settings & Glossary" },
    { name: "description", content: "VisionGuard settings & glossary for object-detection model reliability evaluation." },
    { property: "og:title", content: "VisionGuard — Settings & Glossary" },
    { property: "og:description", content: "Inspect model reliability using clean and corrupted image evaluation evidence." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: Settings,
});

