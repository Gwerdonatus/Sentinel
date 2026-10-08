# Sentinel 2 interface

Sentinel 2 uses the supplied navy shield/S monogram and turquoise accent as its official identity. The original PNG is preserved in `public/brand/sentinel-logo.png`; shared brand components frame the artwork without modifying its pixels. The wordmark appears on the public site, sign-in and workspace. A matching simplified vector monogram serves as the favicon.

The interface uses Geist typography, warm white surfaces, slate text, navy and turquoise accents, subtle borders and shadows. Severity remains visible through both words and color. Public illustrations explain observation rather than displaying invented operational metrics. Dashboard numbers and recent activity come from the existing authenticated API.

## Navigation

- `/`: product homepage and platform overview.
- `/developers`: integration guide with verified backend paths and links to credentials, audit events and the Python SDK.
- `/api/schema`: development OpenAPI schema from the backend. No credentials are forwarded; environments without an available schema return an explicit error.
- `/status`: fresh frontend/backend liveness view. It explicitly distinguishes these checks from background-service health.
- `/login`: labeled sign-in form with loading and error feedback.
- The workspace includes overview, alerts, audit log, AI agents, API keys, compliance and linked investigation views.

Metric cards and recent events are navigable. Overview refresh reloads its data queries. Alert filters reset the cursor, and previous/next buttons follow the returned pagination links. Forms expose validation and request errors; API key copy shows success or failure.

## Responsive and accessible behavior

The sidebar becomes a labeled menu at phone widths; selecting a destination closes it. Tables scroll within their own containers. Forms become single-column where needed. Links and buttons have visible keyboard focus, scope selectors expose pressed state, and reduced-motion preferences disable decorative transitions. Hidden mobile navigation is removed from layout and keyboard access until opened.

Keep the public brand and workspace surface styles in `src/app/globals.css`, the shared artwork framing in `src/components/brand.tsx`, and API behavior in the existing hooks. New views should use the same spacing, surface and feedback conventions, and must distinguish unavailable data from empty data.
