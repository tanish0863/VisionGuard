import { createFileRoute } from "@tanstack/react-router";
import { Login } from "@/components/visionguard/login";

export const Route = createFileRoute("/login")({
  validateSearch: (search: Record<string, unknown>): { mode?: "signin" | "signup" | undefined } => {
    return {
      mode: search["mode"] === "signup" ? "signup" : undefined,
    };
  },
  head: () => ({
    meta: [
      { title: "Sign In & Sign Up — VisionGuard" },
      {
        name: "description",
        content: "Sign in or create an account to access your VisionGuard evaluations, runs, and failure analytics.",
      },
      { property: "og:title", content: "Sign In & Sign Up — VisionGuard" },
    ],
  }),
  component: LoginRouteComponent,
});

function LoginRouteComponent() {
  const { mode } = Route.useSearch();
  return <Login initialMode={mode} />;
}


