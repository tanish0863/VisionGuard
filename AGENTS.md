<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->


## Architecture
- Preserve the static Porthole Voyage experience in public/portholevoyage and embed it at the index route; this retains the reference animation and styling.
- Keep the VisionGuard workspace in shared React presentation components with TanStack leaf routes; reuse the template palette through scoped semantic tokens.
- Treat absent evaluation API contracts as unavailable integrations, never simulate runs or invent response types; local images are previews only.
- Use an un-nested failure route so the full-page evaluation detail does not swallow its failure analysis view.
