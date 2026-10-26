# VisionGuard AI Model Reliability

The original Porthole Voyage template is preserved with VisionGuard branding, text, imagery, colors and animation. The workspace includes overview, evaluation configuration, run details, failure analysis, and settings/glossary.

## Run locally

Install Bun, then run `bun install` and `bun run dev`. The Vite development URL is printed in the terminal. Use `bun run build` to produce the deployment output and `bun run test` to run tests.

## Pages

- `/`: original animated template adapted to VisionGuard
- `/dashboard`: Model Reliability Overview
- `/new`: evaluation configuration and local image preview
- `/runs/$id`: evaluation details
- `/runs/$id/failures`: failure analysis
- `/settings`: settings and metric glossary

## Integration status

No evaluation backend, API base URL, OpenAPI types, authentication contracts, or model/dataset/report responses were present in the supplied project. No endpoints are called or invented. Run history, model status, reports, artifacts, severity options, presets, exports, cancellation, uploads, persistent settings, and execution remain unavailable pending real API contracts. Local file selection never uploads or evaluates images. The UI does not display simulated results.

The animated template loads General Sans, Three.js and GSAP from external CDNs, so internet access is required. Original images are included under public/portholevoyage/assets. Technology: TanStack Start, React, TypeScript, Tailwind CSS.
