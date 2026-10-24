# VisionGuard Design System

> **Product:** VisionGuard — AI-powered computer vision reliability testing  
> **File:** `design.md`  
> **Version:** 1.0  
> **Status:** Proposed design system for the hackathon MVP  
> **Primary platforms:** Desktop web first; responsive support for smaller screens  
> **Visual direction:** Technical, trustworthy, analytical, and calm

---

## 1. Purpose

This document defines the visual language and interaction patterns for VisionGuard. It is intended to help the team build a consistent interface across the dashboard, image upload flow, corruption laboratory, comparison views, reliability analytics, failure explorer, and test reports.

The system prioritizes readable evidence and clear comparisons over decoration. It should help users understand what was tested, what changed, and why a result matters.

## 2. Product Design Principles

### 2.1 Evidence before decoration
Prioritize images, detections, metrics, and test settings. Visual styling should support interpretation rather than compete with the results.

### 2.2 Make comparisons effortless
Keep clean and corrupted images visually aligned and clearly labeled. Use consistent ordering and metric definitions so users can compare conditions quickly.

### 2.3 Explain the meaning of metrics
Do not show a number without a label and context. Provide short definitions, units, and a clear indication of whether ground-truth labels are required.

### 2.4 Distinguish status from severity
Use color, text, icons, and shape together to communicate status. Never rely on color alone to indicate a failure or success.

### 2.5 Progressive disclosure
Keep the main workflow simple. Show essential controls first and place advanced settings, thresholds, and metadata in expandable details.

### 2.6 Trustworthy, not overconfident
Avoid visual language that implies VisionGuard certifies a model as safe or production-ready. Results describe the tested images and settings, not all possible real-world conditions.

### 2.7 Consistent and predictable
Reuse the same spacing, button hierarchy, form patterns, labels, and error behavior across the product.

### 2.8 Accessible by default
Aim for WCAG 2.2 AA contrast, keyboard usability, visible focus states, semantic labels, and readable text. Verify contrast for final color combinations during implementation.

---

## 3. Brand and Visual Direction

### Personality
- **Technical:** precise layouts, clear data hierarchy, restrained visual effects.
- **Trustworthy:** transparent metrics, visible test settings, honest limitations.
- **Focused:** minimize distractions during analysis.
- **Approachable:** plain-language labels and useful empty states.

### Recommended visual style
- Light, neutral application canvas with dark navy text.
- Blue as the primary action color.
- Teal or green for positive/retained outcomes.
- Amber for warnings and degraded results.
- Red for failures and errors.
- Subtle borders and restrained shadows.
- Rounded cards and controls, but avoid excessive pill-shaped layouts.

### Layout philosophy
Use a dashboard-style application shell:
- Persistent sidebar on desktop for main sections.
- Top bar for page title, run status, and global actions.
- Main content area for analysis and comparison.
- Optional right-side details panel for selected detections or failures.

---

## 4. Color Palette

Color values below are proposed design tokens. Check final foreground/background pairs for accessible contrast before release.

### 4.1 Core colors

| Token | Hex | Intended use |
|---|---|---|
| `color-brand-900` | `#10233F` | Deep navy, sidebar and high-emphasis text |
| `color-brand-800` | `#17365D` | Dark brand surfaces |
| `color-brand-700` | `#1D4ED8` | Primary brand/action blue |
| `color-brand-600` | `#2563EB` | Primary buttons and active controls |
| `color-brand-100` | `#DBEAFE` | Selected states and subtle blue surfaces |
| `color-brand-50` | `#EFF6FF` | Soft information backgrounds |
| `color-canvas` | `#F6F8FC` | Application background |
| `color-surface` | `#FFFFFF` | Cards, dialogs, panels |
| `color-surface-subtle` | `#F8FAFC` | Secondary panel background |
| `color-border` | `#E2E8F0` | Standard borders and dividers |
| `color-border-strong` | `#CBD5E1` | Emphasized borders |
| `color-text-primary` | `#0F172A` | Primary body and heading text |
| `color-text-secondary` | `#475569` | Supporting text |
| `color-text-muted` | `#64748B` | Hints and metadata; verify contrast at small sizes |
| `color-white` | `#FFFFFF` | Text on dark/primary surfaces when contrast passes |

### 4.2 Semantic colors

| Token | Hex | Meaning | Example use |
|---|---|---|---|
| `color-success-700` | `#15803D` | Positive / retained | Successful processing, matched detection |
| `color-success-50` | `#F0FDF4` | Positive subtle surface | Success alert background |
| `color-warning-700` | `#B45309` | Warning / degraded | Noticeable degradation, caution |
| `color-warning-50` | `#FFFBEB` | Warning subtle surface | Warning banner background |
| `color-danger-700` | `#B91C1C` | Failure / error | Missing detection, failed request |
| `color-danger-50` | `#FEF2F2` | Failure subtle surface | Error alert background |
| `color-info-700` | `#0369A1` | Informational | Explanatory notices |
| `color-info-50` | `#F0F9FF` | Informational subtle surface | Metric guidance |

### 4.3 Data visualization colors

Use a consistent series mapping across all charts. Keep charts limited to a few series and pair colors with labels, markers, or patterns.

| Token | Hex | Suggested meaning |
|---|---|---|
| `chart-baseline` | `#64748B` | Clean-image baseline |
| `chart-blur` | `#2563EB` | Blur condition |
| `chart-brightness` | `#D97706` | Brightness / low-light condition |
| `chart-noise` | `#7C3AED` | Noise condition |
| `chart-rotation` | `#0891B2` | Rotation condition |
| `chart-occlusion` | `#DB2777` | Occlusion condition |
| `chart-retained` | `#15803D` | Retained/matched detections |
| `chart-failed` | `#B91C1C` | Missing/failed detections |

**Chart rules**
- Label both axes and include units where relevant.
- Use a zero baseline where appropriate and avoid misleading scales.
- Show tooltips with exact values and test configuration.
- Do not use red/green as the only way to distinguish series.
- Do not imply that illustrative or demo data is measured output.

---

## 5. Typography

### 5.1 Font family

Recommended stack:
- **Primary:** Inter
- **Fallback:** `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
- **Code/technical values:** `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`

Use a locally available or bundled font where possible so the interface remains consistent offline. Do not make the app depend on a live font CDN for the hackathon demo.

### 5.2 Type scale

| Token | Size | Line height | Weight | Use |
|---|---:|---:|---:|---|
| `text-xs` | 12px | 16px | 400–500 | Dense metadata, chart annotations |
| `text-sm` | 14px | 20px | 400–500 | Secondary UI, labels, table cells |
| `text-base` | 16px | 24px | 400 | Default body text and form controls |
| `text-lg` | 18px | 28px | 500–600 | Card headings and emphasized text |
| `text-xl` | 20px | 28px | 600 | Section headings |
| `text-2xl` | 24px | 32px | 600–700 | Page headings |
| `text-3xl` | 30px | 36px | 700 | Dashboard headline or key summary |
| `text-4xl` | 36px | 40px | 700 | Optional landing-page hero only |

### 5.3 Typography rules
- Use sentence case for headings and buttons.
- Use concise labels such as “Detection retention” and “Inference time.”
- Use tabular numerals for metric values when supported.
- Keep long explanatory text to a comfortable reading width.
- Avoid using uppercase for long labels; reserve it for small section overlines if needed.
- Do not use tiny text to fit more data; simplify or add spacing instead.

---

## 6. Spacing, Sizing, and Layout

### 6.1 Spacing scale

Use a 4px base unit.

| Token | Value | Typical use |
|---|---:|---|
| `space-1` | 4px | Icon/text gap, tight inline spacing |
| `space-2` | 8px | Compact control spacing |
| `space-3` | 12px | Form field internal spacing |
| `space-4` | 16px | Default component gap |
| `space-5` | 20px | Card padding in compact views |
| `space-6` | 24px | Standard card padding |
| `space-8` | 32px | Section spacing |
| `space-10` | 40px | Large section spacing |
| `space-12` | 48px | Major page group separation |
| `space-16` | 64px | Hero or major layout spacing |

### 6.2 Layout tokens
- Desktop sidebar: approximately 240px wide.
- Top bar: approximately 64px high.
- Main content max width: approximately 1440px.
- Main page padding: 24–32px on desktop, 16px on mobile.
- Standard card radius: 12px.
- Large panel radius: 16px.
- Input/button radius: 8px.
- Standard border: 1px solid `color-border`.
- Shadows: subtle and reserved for floating menus, dialogs, and elevated surfaces.

These are starting values; adjust after implementing the primary screens.

### 6.3 Responsive behavior
- **Desktop (≥ 1024px):** sidebar plus main workspace; side-by-side clean/altered images.
- **Tablet (768–1023px):** collapsible sidebar; use two-column cards only when readable.
- **Mobile (< 768px):** single-column layout; stack image comparisons and metric cards; place filters in a drawer or collapsible panel.
- Never force two image panels into narrow columns if bounding boxes and labels become hard to inspect.

---

## 7. Iconography and Imagery

- Use one consistent outline icon set, such as Lucide, if included in the project dependencies.
- Keep icons simple and recognizable.
- Pair important icons with text labels, especially for status and navigation.
- Use real uploaded/test images in analysis screens.
- Use synthetic placeholders only in empty states and label them as examples.
- Do not use decorative imagery that competes with the model output.
- Bounding boxes should have sufficient contrast against the image and should not obscure labels or key objects.

---

## 8. UI Components

### 8.1 Buttons

**Variants**
- **Primary:** main action, such as “Run analysis.”
- **Secondary:** alternative action, such as “Export report.”
- **Tertiary/Ghost:** low-emphasis actions, such as “View details.”
- **Destructive:** delete or discard actions only when such actions exist.

**States**
- Default, hover, focus-visible, active, disabled, and loading.
- Loading buttons should communicate progress and prevent accidental duplicate submissions.
- Disabled buttons must remain legible and have a clear reason where the state is not obvious.

**Rules**
- One dominant primary action per major panel.
- Use action verbs.
- Do not use color alone to communicate destructive intent.

### 8.2 Text inputs and form controls

Include:
- Text input for numeric thresholds where applicable.
- Select menu for model selection if multiple models are supported.
- Checkbox or toggle for transformation selection.
- Slider plus numeric value for severity.
- File input/dropzone for image upload.

Requirements:
- Every control has a visible label.
- Show units and valid ranges for numeric settings.
- Provide inline validation and explain invalid values.
- Ensure keyboard operation and visible focus.

### 8.3 Image upload dropzone

**Anatomy**
- Upload icon
- Instruction: “Drop an image here or browse files”
- Supported formats and maximum size
- Optional thumbnail and file details after selection

**States**
- Empty
- Drag-over
- Uploading/processing
- Success/ready
- Invalid format
- Too large
- Decode failure

**Behavior**
- Allow keyboard users to open the file picker.
- Show a preview before analysis when practical.
- Do not begin analysis until required configuration is valid.
- Preserve a clear route to replace the image.

### 8.4 Cards and metric cards

Use cards to group related information, not to wrap every individual label.

**Metric card anatomy**
- Metric name
- Main value
- Unit or comparison delta
- Brief definition or tooltip
- Optional status indicator

**Metric card rules**
- Use consistent value formatting and decimal precision.
- Distinguish “0,” “not applicable,” and “not available.”
- Do not invent values for empty states.
- Include the tested condition or comparison baseline when needed.

### 8.5 Badges and status indicators

Recommended statuses:
- Ready
- Running
- Completed
- Warning
- Failed
- Not available

Each status should include a text label and, where useful, an icon. Use semantic colors as defined above.

### 8.6 Alerts and notifications

Variants:
- Information
- Success
- Warning
- Error

An alert should explain what happened and what the user can do next. Errors should be actionable and should not expose stack traces, server paths, or internal details.

### 8.7 Tabs and segmented controls

Use tabs for closely related views such as:
- Overview
- Corruption conditions
- Failures
- Run details

Use segmented controls only when switching a small number of mutually exclusive views. Preserve selected state and support keyboard navigation.

### 8.8 Tables

Use tables for run history, model comparisons, and detailed detection lists.

Rules:
- Keep column headings clear and stable.
- Align numeric values consistently.
- Include units in headings or cells.
- Support horizontal scrolling on small screens rather than crushing text.
- Provide a clear empty state when no runs or detections exist.

### 8.9 Tooltips and metric explanations

Use tooltips for short definitions and units. For essential interpretation—such as the distinction between detection retention and accuracy—provide visible helper text or a details panel rather than hiding all context in a tooltip.

### 8.10 Dialogs and drawers

Use dialogs for focused confirmation or short tasks. Use drawers for secondary settings or details that should not replace the analysis view.

Requirements:
- Provide a clear title and close control.
- Keep keyboard focus inside modal dialogs while open.
- Return focus to the triggering control when closed.
- Avoid dialogs for routine, non-destructive actions.

### 8.11 Charts

Recommended charts:
- Bar chart: retention by corruption type.
- Line chart: metric change across severity levels.
- Horizontal bar chart: failure counts by category.

Requirements:
- Include a title, labels, units, and a short interpretation where useful.
- Show the test sample count when it affects interpretation.
- Use tooltips for exact values.
- Provide a table or textual summary when a chart alone is inaccessible.
- Clearly label sample or illustrative data; production/demo output should come from actual calculations.

### 8.12 Bounding boxes and detection labels

- Use a consistent outline width and label style.
- Keep class labels and confidence values readable at presentation size.
- Use stable class colors where possible across clean and altered views.
- Use separate visual treatment for matched, missing, and new detections.
- Include a legend explaining all detection states.
- Avoid drawing a “correct/incorrect” conclusion unless ground-truth labels support it.

### 8.13 Empty states

Every major section should explain:
1. Why it is empty.
2. What action the user can take next.
3. Whether the data is unavailable or simply not yet generated.

Example: “No analysis yet. Upload an image to establish a clean-image baseline.”

### 8.14 Loading and progress states

- Use a spinner or skeleton only where it clarifies waiting.
- Explain what is running, such as “Running inference on altered images.”
- Show step-level progress when possible.
- Keep the user informed if processing takes longer than expected.
- Prevent duplicate requests while the same analysis is in progress.

---

## 9. Core Screen Specifications

### 9.1 Dashboard / Home

**Purpose:** Start an analysis and provide access to recent runs.

**Elements**
- Sidebar navigation: Dashboard, New analysis, Run history, Settings/about.
- Header: page title and primary action.
- Upload dropzone or “New analysis” card.
- Recent runs table or a first-run empty state.
- Optional compact summary metrics only when real saved data exists.

**Primary action:** “New analysis”

### 9.2 New Analysis / Corruption Laboratory

**Purpose:** Configure and run a test.

**Elements**
- Image upload and preview.
- Model identifier.
- Transformation selection list.
- Severity controls with visible values.
- Run-analysis button.
- Processing status and validation messages.

**Layout:** Configuration panel beside the image preview on desktop; stacked on small screens.

### 9.3 Results Overview

**Purpose:** Communicate the main observed changes.

**Elements**
- Run status, timestamp, and model version.
- Metric cards for detection retention, confidence change, and inference latency.
- Clean-versus-altered image comparison.
- Chart showing results by corruption type/severity.
- Link to failure explorer.
- Note indicating whether ground-truth labels were available.

### 9.4 Failure Explorer

**Purpose:** Inspect individual detection changes.

**Elements**
- Filter by transformation and failure category.
- Failure list with concise summaries.
- Selected case detail panel.
- Aligned clean and altered images.
- Baseline and altered detections.
- Matching/IoU rule and related metric change.

### 9.5 Run Details / Report

**Purpose:** Preserve context and make results shareable.

**Elements**
- Run ID and timestamp.
- Model identifier/version.
- Input image reference.
- Transformation parameters.
- Metric definitions and observed values.
- Failure summary.
- Ground-truth availability and limitations.
- Export action if implemented.

---

## 10. Navigation and Information Architecture

Suggested MVP navigation:

```text
VisionGuard
├── Dashboard
├── New analysis
│   ├── Upload image
│   ├── Configure transformations
│   └── Run analysis
├── Results
│   ├── Overview
│   ├── Corruption comparison
│   └── Failure explorer
├── Run history
└── About / metric definitions
```

If time is limited, keep the interface to three main destinations: **Dashboard**, **New analysis**, and **Run results**. Avoid building a separate settings area unless it is needed for the MVP.

---

## 11. Interaction Patterns

### Analysis lifecycle
`Idle → Image selected → Configured → Running → Completed / Failed`

- The user must be able to distinguish each state.
- The Run action is disabled until required inputs are valid.
- A failed run preserves enough context to retry without starting from scratch.
- A completed run presents results and links to detailed failures.

### Transformation lifecycle
`Unselected → Selected → Severity configured → Applied`

- Severity must have a clear range and visible current value.
- Display the applied settings beside the transformed image.
- Do not silently change settings during analysis.

### Error recovery
- Explain the issue in plain language.
- Preserve user-entered configuration where possible.
- Offer a next step, such as choosing another file or retrying.
- Never report success if only part of the requested analysis completed; clearly identify partial results.

---

## 12. Accessibility Requirements

- Use semantic HTML and meaningful heading hierarchy.
- All interactive controls must be keyboard accessible.
- Provide visible focus indicators.
- Provide labels for inputs and accessible names for icon-only controls.
- Do not rely on color alone for status, charts, or detection states.
- Maintain sufficient text and UI contrast; validate combinations before release.
- Respect reduced-motion preferences.
- Provide textual summaries for charts and key image-comparison findings.
- Keep zoom and responsive layouts usable without loss of essential content.
- Add useful alternative text for images when the image is informative; for complex detection overlays, provide a nearby text summary.

---

## 13. Design Tokens: CSS Custom Properties

The following tokens can be adapted into the frontend theme. Keep the values centralized rather than repeating raw colors throughout components.

```css
:root {
  /* Brand */
  --color-brand-900: #10233F;
  --color-brand-800: #17365D;
  --color-brand-700: #1D4ED8;
  --color-brand-600: #2563EB;
  --color-brand-100: #DBEAFE;
  --color-brand-50: #EFF6FF;

  /* Surfaces and borders */
  --color-canvas: #F6F8FC;
  --color-surface: #FFFFFF;
  --color-surface-subtle: #F8FAFC;
  --color-border: #E2E8F0;
  --color-border-strong: #CBD5E1;

  /* Text */
  --color-text-primary: #0F172A;
  --color-text-secondary: #475569;
  --color-text-muted: #64748B;

  /* Semantic */
  --color-success-700: #15803D;
  --color-success-50: #F0FDF4;
  --color-warning-700: #B45309;
  --color-warning-50: #FFFBEB;
  --color-danger-700: #B91C1C;
  --color-danger-50: #FEF2F2;
  --color-info-700: #0369A1;
  --color-info-50: #F0F9FF;

  /* Typography */
  --font-sans: Inter, ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;

  /* Shape and elevation */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --shadow-card: 0 1px 2px rgb(15 23 42 / 5%);
  --shadow-floating: 0 8px 24px rgb(15 23 42 / 12%);
}
```

---

## 14. Content and Microcopy Guidelines

- Prefer direct, specific language.
- Use “Run analysis,” not “Execute pipeline.”
- Use “Image could not be read,” not “Unexpected image decoder exception.”
- Use “No matched detections” rather than “Model failed” unless the failure rule supports that conclusion.
- Say “Observed on this test set” when describing limited results.
- Explain unavailable metrics rather than displaying fabricated zero values.
- Distinguish “not tested,” “not available,” and “zero.”
- Use consistent terms throughout the app: **clean image**, **altered image**, **transformation**, **severity**, **baseline detection**, **matched detection**, and **failure case**.

---

## 15. Motion and Feedback

- Use short, restrained transitions for menus, tabs, and panels.
- Avoid decorative animations in the analysis workspace.
- Use progress feedback for long-running inference.
- Respect `prefers-reduced-motion`.
- Do not animate charts in a way that delays access to results or changes the apparent meaning of data.

---

## 16. Do / Don't

| Do | Don't |
|---|---|
| Make clean and altered images easy to compare | Use layouts that make the images different sizes without reason |
| Define metrics and thresholds clearly | Present confidence as accuracy |
| Use color plus text/icons for status | Communicate failure only through red |
| Show actual measured results | Invent values for a polished-looking dashboard |
| Keep settings visible in result details | Hide the conditions used to produce a metric |
| Use consistent tokens and component patterns | Add one-off styles for every screen |
| Keep the MVP workflow short | Add optional features before the core flow works |
| State limitations honestly | Imply the tool certifies models for deployment |

---

## 17. MVP Design Checklist

### Foundation
- [ ] Centralize color, typography, spacing, radius, and shadow tokens.
- [ ] Set up global typography and base styles.
- [ ] Confirm contrast for important text, controls, and status colors.
- [ ] Define button, input, card, badge, alert, and dropzone variants.

### Primary workflow
- [ ] Build the upload empty, drag-over, invalid, and ready states.
- [ ] Build transformation controls and visible severity values.
- [ ] Build loading, completed, failed, and partial-result states.
- [ ] Build side-by-side clean/altered image comparison.
- [ ] Build metric cards with definitions and unavailable states.
- [ ] Build failure list and selected-case detail.
- [ ] Make layout responsive without sacrificing image readability.

### Quality
- [ ] Verify keyboard navigation and visible focus.
- [ ] Verify color is not the only status cue.
- [ ] Ensure charts have labels and textual summaries.
- [ ] Ensure displayed data comes from actual analysis results.
- [ ] Test the complete flow at the target presentation resolution.

---

## 18. Implementation Notes

- Treat this file as the source of truth for visual tokens and component behavior.
- Implement shared UI primitives before building individual screens.
- Keep design tokens in CSS variables or a shared Tailwind theme configuration.
- Avoid introducing additional colors without a clear semantic purpose.
- If the team uses a component library, map its theme tokens to this system instead of mixing unrelated defaults.
- Prioritize dashboard, upload/configuration, results comparison, and failure explorer for the hackathon demo.
