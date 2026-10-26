import { createFileRoute } from "@tanstack/react-router";
import { Landing } from "@/components/visionguard/landing";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "VisionGuard — AI Model Reliability" },
      {
        name: "description",
        content:
          "VisionGuard evaluates object-detection reliability across clean and corrupted images.",
      },
      { property: "og:title", content: "VisionGuard — AI Model Reliability" },
      {
        property: "og:description",
        content: "Configure evaluations, compare detection reliability, and investigate failures with evidence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return <Landing />;
}
