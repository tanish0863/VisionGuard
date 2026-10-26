import { createFileRoute } from "@tanstack/react-router";
import { Failures } from "@/components/visionguard/workspace";
export const Route = createFileRoute("/runs/$id_/failures")({
  head: () => ({ meta: [
    { title: "VisionGuard — Failure Analysis" },
    { name: "description", content: "VisionGuard failure analysis for object-detection model reliability evaluation." },
    { property: "og:title", content: "VisionGuard — Failure Analysis" },
    { property: "og:description", content: "Inspect model reliability using clean and corrupted image evaluation evidence." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary_large_image" },
  ] }),
  component: Page,
});
function Page() { const { id } = Route.useParams(); return <Failures id={id} />; }
