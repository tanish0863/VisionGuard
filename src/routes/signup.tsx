import { createFileRoute } from "@tanstack/react-router";
import { Login } from "@/components/visionguard/login";

export const Route = createFileRoute("/signup")({
  head: () => ({
    meta: [
      { title: "Create Account — VisionGuard" },
      {
        name: "description",
        content: "Create your account to start evaluating object detection and AI model reliability.",
      },
      { property: "og:title", content: "Create Account — VisionGuard" },
    ],
  }),
  component: SignupRouteComponent,
});

function SignupRouteComponent() {
  return <Login initialMode="signup" />;
}
