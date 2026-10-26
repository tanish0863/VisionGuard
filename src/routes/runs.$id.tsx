import { createFileRoute } from "@tanstack/react-router";
import { RunDetails } from "@/components/visionguard/workspace";
export const Route = createFileRoute("/runs/$id")({
  head: () => ({ meta: [
    { title: "VisionGuard — Evaluation Details" },
    { name: "description", content: "VisionGuard evaluation details for object-detection model reliability evaluation." },
    { property: "og:title", content: "VisionGuard — Evaluation Details" },
    { property: "og:description", content: "Inspect model reliability using clean and corrupted image evaluation evidence." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: Page,
});
function Page() { const { id } = Route.useParams(); return <RunDetails id={id} />; }
