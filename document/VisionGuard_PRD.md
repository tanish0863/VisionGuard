# VisionGuard — Product Requirements Document (PRD)

> **Product:** VisionGuard  
> **Document type:** Product Requirements Document  
> **Status:** Hackathon MVP proposal  
> **Primary audience:** Product, engineering, design, and hackathon judges  
> **Target build window:** 24-hour hackathon  
> **Version:** 1.0

---

## 1. Product Overview

**VisionGuard** is an AI-powered web application that evaluates the reliability of computer vision models under imperfect, real-world image conditions. It lets users run object detection on a clean image, apply controlled image corruptions—such as blur, low brightness, noise, rotation, compression, and partial obstruction—and compare the model's predictions before and after each change.

The platform makes model weaknesses easier to see and measure through side-by-side comparisons, reliability metrics, a failure explorer, and a reproducible test summary.

**Product promise:** VisionGuard does not magically improve a model; it helps teams discover, measure, and document model weaknesses before deployment.

### 1.1 Value proposition

- Stress-test a pretrained object detection model without building a testing pipeline from scratch.
- See which detections disappear, change class, or lose confidence under altered conditions.
- Compare results across controlled corruption types and severity levels.
- Produce repeatable evidence that can inform model selection and further testing.

---

## 2. Problem Statement

Computer vision models can perform well on clean benchmark images but behave less reliably in real environments. Lighting changes, motion or focus blur, sensor noise, image rotation, compression artifacts, and objects being partially hidden can affect detections.

Developers and ML teams need a practical way to test these conditions, understand where failures occur, and compare model behavior. Without a repeatable workflow, identifying these weaknesses can require manual image editing, separate scripts, and time-consuming inspection.

**Problem statement:** There is no simple, unified workflow in the proposed project for applying controlled image corruptions, comparing clean and altered predictions, measuring performance degradation, and reviewing failures in one place.

---

## 3. Product Goals and Non-Goals

### 3.1 Goals

1. Let a user upload an image and run a pretrained object detection model.
2. Establish a clean-image baseline for comparison.
3. Apply several configurable image transformations at different severity levels.
4. Compare baseline and altered predictions in a visual interface.
5. Calculate clear, appropriately defined reliability metrics.
6. Help users inspect individual failures and understand the conditions associated with them.
7. Save enough run configuration and model metadata to make a test reproducible.
8. Deliver a polished, dependable end-to-end demo within the 24-hour hackathon window.

### 3.2 Non-goals for the MVP

- Training or fine-tuning computer vision models.
- Claiming that the tool certifies a model as safe or production-ready.
- Guaranteeing performance on all real-world environments based on a small test set.
- Supporting every model architecture or every computer vision task.
- Building enterprise user management, advanced permissions, or collaboration.
- Video testing, unless all required MVP features are complete.
- Treating confidence scores or detection retention as equivalent to accuracy.

---

## 4. Target Users

| User segment | Need | How VisionGuard helps |
|---|---|---|
| Computer vision developers | Quickly check model behavior outside ideal image conditions | Run controlled transformations and inspect changed detections |
| ML engineers | Evaluate robustness and compare model versions | Review metrics and preserve model/test configuration |
| AI researchers and students | Explore how image corruption affects predictions | Run repeatable experiments and compare conditions |
| Industrial inspection teams | Understand possible detection weaknesses before deployment | Review failures under simulated image-quality issues |

### Primary MVP persona

**A computer vision developer** who has a pretrained object detection model and a small collection of test images, and wants to understand how image quality changes affect its detections without writing a custom evaluation pipeline.

---

## 5. User Needs and Jobs to Be Done

- When I upload an image, I want to see the model's baseline detections so I can establish a reference.
- When I alter image conditions, I want to see whether the model still detects the same objects.
- When a prediction changes or disappears, I want to inspect the original and altered images side by side.
- When I compare conditions, I want metrics with clear definitions so I can interpret the results correctly.
- When I revisit a test, I want its settings and model version recorded so I can reproduce it.
- When I present findings, I want a concise report of the conditions tested and the observed outcomes.

---

## 6. Core Features — MVP

### 6.1 Image Upload and Model Inference — P0

**Description:** Accept a supported image and run a pretrained object detection model.

**Requirements**
- Accept common image formats such as JPG, JPEG, and PNG.
- Validate file type, size, and successful image decoding.
- Show a useful error for invalid or unsupported files.
- Display the image with predicted bounding boxes, class labels, and confidence scores.
- Record inference latency for the baseline run.
- Identify the model name/version used for the run.

**Acceptance criteria**
- A valid image can be uploaded and analyzed end to end.
- Baseline detections and inference time are shown to the user.
- An invalid file produces a clear error rather than an unhandled failure.

### 6.2 Image Corruption Laboratory — P0

**Description:** Generate altered copies of the uploaded image using controlled transformations.

**MVP transformations**
1. Blur
2. Brightness adjustment (including low-light simulation)
3. Gaussian noise
4. Rotation
5. Partial occlusion

Compression can be added if time permits.

**Requirements**
- Allow the user to select one or more transformations.
- Provide a severity control for supported transformations.
- Preserve the clean image as the baseline.
- Display each altered image and identify the transformation and severity applied.
- Make transformation settings available in the saved run metadata.

**Acceptance criteria**
- At least three transformations work reliably; the target is three to five.
- The UI clearly labels each transformed image and its settings.
- The clean baseline remains unchanged throughout the test.

### 6.3 Clean-versus-Altered Prediction Comparison — P0

**Description:** Run inference on altered images and compare their predictions with the clean baseline.

**Requirements**
- Run the same selected model on the clean and altered images.
- Match detections using class labels and intersection-over-union (IoU), with a documented matching threshold.
- Identify detections that remain matched, disappear, or change class.
- Show baseline and altered predictions side by side.
- Make comparison behavior consistent for repeated runs with the same configuration, subject to model/runtime determinism.

**Acceptance criteria**
- Users can inspect clean and altered predictions in one comparison view.
- The interface distinguishes matched detections from missing or changed detections.
- Matching rules and thresholds are documented in the result details.

### 6.4 Reliability Analytics — P0

**Description:** Summarize changes in model behavior using interpretable metrics.

**Minimum metrics**
- **Detection retention:** proportion of baseline detections that are matched after corruption.
- **Confidence change:** difference in confidence for matched detections, with the sign convention shown.
- **Inference latency:** time required for inference on each image.
- **Failure rate by condition:** proportion of tested samples that meet a defined failure rule, when multiple samples are available.

Precision and recall may be added when ground-truth annotations are available and an evaluation protocol is defined.

**Requirements**
- Display metric values with labels, units where applicable, and brief explanations.
- Compare metrics across selected corruption types or severity levels.
- Clearly distinguish metrics computed from model predictions from metrics requiring ground-truth labels.
- Do not present confidence or detection retention as proof of correctness.

**Acceptance criteria**
- At least three meaningful metrics are displayed.
- Every metric uses a documented calculation.
- Metrics that require ground-truth labels are omitted or marked unavailable when labels are absent; they are not fabricated.

### 6.5 Failure Explorer — P0

**Description:** Let users inspect prediction changes at the image and detection level.

**Requirements**
- Highlight baseline detections that are not matched in the altered image.
- Identify new detections and class changes where the comparison logic supports them.
- Show the relevant clean and altered images, transformation settings, and associated metric changes.
- Provide a concise failure category for each identified case.

**Acceptance criteria**
- Users can select a reported failure and inspect the associated image comparison.
- Failure categories follow the documented matching logic.
- The interface does not label a detection as objectively incorrect unless ground-truth data supports that conclusion.

### 6.6 Run History and Reproducibility — P1, simplified for MVP

**Description:** Preserve the information required to review and repeat a test.

**Requirements**
- Save run ID, timestamp, model identifier/version, transformation settings, severity, and calculated results.
- Use SQLite for the MVP.
- Allow a user to retrieve a run by its ID.
- Record enough metadata to explain how each result was produced.

**Acceptance criteria**
- A completed run can be retrieved during the demo.
- Saved metadata identifies the model and transformation configuration.
- If persistence threatens core delivery, prioritize in-session results and add durable run history only after the end-to-end flow works.

### 6.7 Report Export — P1, if time permits

**Description:** Export a concise summary of the test.

**Report contents**
- Run identifier and timestamp
- Model identifier/version
- Input image or sample reference
- Transformations and severity levels
- Metrics and their definitions
- Failure summary
- Known limitations and whether ground-truth labels were used

**Acceptance criteria**
- A report can be downloaded and corresponds to the displayed run.
- The report does not invent benchmark results or imply broad guarantees from limited testing.

---

## 7. Prioritization

| Priority | Scope |
|---|---|
| **P0 — Must have** | Image upload, pretrained inference, 3–5 transformations, clean/altered comparison, at least 3 meaningful metrics, failure visualization, polished dashboard, working live demo |
| **P1 — Should have** | Basic run persistence, reproducibility metadata, downloadable report |
| **P2 — Could have** | Two-model comparison, compression corruption, expanded run history, PDF export, video testing, accounts and advanced permissions |
| **Out of scope** | Model training, automated model repair, production certification, broad enterprise access controls |

**Scope rule:** Complete one reliable end-to-end workflow before adding optional features.

---

## 8. User Flow

1. The user opens VisionGuard.
2. The user uploads a supported image.
3. VisionGuard validates and preprocesses the image.
4. The selected pretrained detector runs on the clean image.
5. The user selects corruption types and severity levels.
6. VisionGuard generates altered images and runs inference on each.
7. The system matches baseline and altered detections.
8. The dashboard presents images, detections, metrics, and failures.
9. The user opens a failure to inspect the relevant comparison.
10. The user reviews or exports the run summary, if report export is implemented.

---

## 9. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Upload and validate a supported image | P0 |
| FR-02 | Run a pretrained object detector on the clean image | P0 |
| FR-03 | Display labels, bounding boxes, confidence scores, and inference time | P0 |
| FR-04 | Apply configurable image transformations | P0 |
| FR-05 | Run inference on transformed images | P0 |
| FR-06 | Match baseline and altered detections using documented rules | P0 |
| FR-07 | Calculate and display at least three defined metrics | P0 |
| FR-08 | Highlight missing, new, and changed detections where identifiable | P0 |
| FR-09 | Handle invalid input and inference errors gracefully | P0 |
| FR-10 | Save run settings and result metadata | P1 |
| FR-11 | Retrieve a saved run by ID | P1 |
| FR-12 | Export a report for a completed run | P1 |

---

## 10. Non-Functional Requirements

### Reliability
- Invalid uploads and inference failures should return understandable errors.
- The app should complete the primary workflow without requiring internet access after dependencies and model weights have been prepared locally.
- Repeated tests should preserve the same configuration; document any sources of nondeterminism.

### Performance
- Show progress or a loading state during inference and batch transformations.
- Avoid blocking the interface while a test is running.
- Record measured inference latency rather than displaying assumed values.
- Set a reasonable upload-size limit appropriate to the demo environment.

### Usability
- Keep the main workflow discoverable: upload → configure → run → compare → inspect.
- Use clear labels for transformations, severity, metric definitions, and errors.
- Ensure comparison views remain readable on the presentation screen.

### Security and data handling
- Validate uploads by content and supported format, not filename alone.
- Avoid executing or serving uploaded files as active content.
- Use temporary storage or clearly defined retention behavior for images.
- Do not expose local file paths or sensitive server details in user-facing errors.

### Maintainability
- Keep inference, transformations, comparison metrics, API routes, and UI components separated.
- Define the API request and response contracts before parallel development.
- Add automated tests for image validation, transformations, metric calculations, and API error cases.

---

## 11. Metrics and Evaluation Method

Use actual results from a fixed, documented test set. Do not invent accuracy, robustness, or performance figures.

### 11.1 Detection retention

For a baseline set of detections and the subset matched after corruption:

`Detection retention = matched baseline detections / total baseline detections`

Define behavior for a baseline with zero detections; in that case, retention should be marked not applicable rather than dividing by zero.

### 11.2 Confidence change

For matched detections:

`Confidence change = altered confidence − baseline confidence`

Report the aggregation method used, such as the mean across matched detections. State clearly that confidence is not the same as correctness.

### 11.3 Inference latency

Measure the elapsed time spent running inference and report the unit (for example, milliseconds). State whether preprocessing and image transformation time are excluded.

### 11.4 Failure rate by condition

When multiple test samples are available and a failure rule has been defined:

`Failure rate = samples meeting the failure rule / total evaluated samples`

Document the failure rule before calculating the metric. For example, a test may count a sample as a failure if baseline detections fall below a defined retention threshold.

### 11.5 Precision and recall

Calculate these only when ground-truth labels are available and the team has defined the detection-matching protocol and evaluation threshold. Do not infer ground-truth correctness from model confidence alone.

---

## 12. Proposed Technical Architecture

### 12.1 Technology stack

| Layer | Proposed technology |
|---|---|
| Frontend | React, TypeScript, Tailwind CSS |
| Backend API | Python, FastAPI |
| Image processing | OpenCV, Pillow |
| Model inference | PyTorch, pretrained YOLO nano model |
| Metrics | NumPy; scikit-learn where applicable |
| Database | SQLite for MVP; PostgreSQL only if needed later |
| Charts | Recharts |
| Testing | Pytest plus frontend/API tests |
| Deployment | Docker Compose |

### 12.2 High-level flow

```text
React frontend
    |
    | Upload image + test configuration
    v
FastAPI backend
    |
    +--> Validate and preprocess image
    |
    +--> Run inference on clean image
    |
    +--> Generate corrupted variants (OpenCV / Pillow)
    |
    +--> Run inference on altered images
    |
    +--> Match detections and calculate metrics
    |
    +--> Save run metadata and results (SQLite)
    |
    v
Dashboard, comparison view, failure explorer, report
```

### 12.3 Initial API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/analyze` | Accept an image and test configuration; run analysis |
| `GET` | `/api/runs/{id}` | Retrieve a saved test run |
| `GET` | `/api/health` | Check API health |

The final request/response schema, upload limits, error format, and inference timeout should be agreed upon before parallel implementation.

---

## 13. Data Requirements

- A set of representative images for the live demonstration.
- A pretrained object detection model and locally available model weights.
- Optional ground-truth annotations if precision or recall will be shown.
- Fixed transformation parameters and severity definitions for repeatable comparisons.
- Recorded model identifier/version and test configuration for every run.

The demo images should contain clearly visible objects that the selected model is expected to recognize. Include examples that make changes under blur or low light easy to observe, but present only outcomes actually measured during the run.

---

## 14. Success Criteria

### MVP delivery success
- The primary workflow runs end to end on the demo machine.
- Users can upload an image and see baseline detections.
- At least three image transformations work.
- The system compares clean and altered predictions.
- At least three correctly calculated metrics are displayed.
- Users can inspect at least one category of prediction failure.
- The demo is repeatable and does not rely on an external network connection once set up.

### Product usefulness signals
- A new user can complete the basic test flow with minimal explanation.
- The results make it clear which condition was applied and how predictions changed.
- The report or run details allow another person to understand the test configuration.
- The team can explain metric definitions and limitations to judges.

No numeric robustness target is assumed in advance. Establish baselines from the selected model and actual demo dataset.

---

## 15. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Model weights or dependencies are unavailable offline | Live demo may fail | Download and test all required assets before the event; keep a verified local setup |
| Pretrained model behaves inconsistently on demo images | Failure may be hard to demonstrate | Test several candidate images and choose a reproducible example without fabricating outcomes |
| Too many features are attempted | Core flow remains unfinished | Enforce P0/P1/P2 priorities and integrate early |
| Detection matching produces misleading results | Metrics may be misunderstood | Document class/IoU matching rules and inspect edge cases |
| Small test set is overinterpreted | Unsupported reliability claims | Label the scope and size of the test set; avoid broad guarantees |
| Frontend/backend integration is delayed | End-to-end demo fails | Agree on API contracts and integrate a thin vertical slice early |
| Ground-truth labels are absent | Accuracy metrics cannot be calculated | Report prediction-consistency metrics and mark ground-truth metrics unavailable |

---

## 16. 24-Hour Hackathon Execution Plan

### Phase 1 — Agree and scaffold
- Confirm API contracts, request/response examples, and repository structure.
- Set up frontend, backend, environment, and dependency installation.
- Confirm model weights load locally.

### Phase 2 — Build the core pipeline
- Implement clean-image inference.
- Implement at least three transformations.
- Implement detection matching and metric calculations.
- Add input validation and meaningful error responses.

### Phase 3 — Integrate the experience
- Build image upload and test configuration.
- Add side-by-side visual comparison.
- Add metric cards/charts and the failure explorer.
- Connect the frontend to the real backend.

### Phase 4 — Stabilize and present
- Add basic persistence/report export if time allows.
- Test invalid files, API failures, and repeated runs.
- Rehearse the full demonstration on the actual presentation machine.
- Keep a fallback demo image and locally available model weights.

### Suggested division for a five-person team

| Member | Responsibility |
|---|---|
| 1 | Frontend UI, upload flow, charts, comparison screens |
| 2 | FastAPI endpoints, validation, database |
| 3 | Model inference and image transformations |
| 4 | Integration, architecture, API contracts, Git workflow |
| 5 | Metrics, automated tests, reports, deployment, documentation |

**Coordination rule:** Agree on API contracts and sample inputs before parallel development. Integrate a basic end-to-end version early rather than waiting for every module to be complete.

---

## 17. Demonstration Script

1. Open VisionGuard and upload an image containing several recognizable objects.
2. Run the clean-image baseline and point out the detected labels, bounding boxes, and confidence scores.
3. Apply blur or low-light transformations at increasing severity.
4. Run analysis and show the clean-versus-altered predictions.
5. Review actual changes in detection retention, confidence, and inference latency.
6. Open a failure case and explain the matching rule used to identify it.
7. Show the test settings and export the report if implemented.
8. Close with the value proposition: VisionGuard makes model weaknesses measurable, visible, and reproducible before deployment.

---

## 18. Open Questions and Assumptions

### Assumptions
- The first version focuses on image-based object detection.
- A pretrained YOLO nano model is suitable for the MVP, subject to local compatibility and license checks.
- The hackathon build window is approximately 24 hours.
- A fixed set of demo images will be prepared in advance.

### Open questions
- What are the official hackathon problem statement and judging criteria?
- Which model version and class set will be used for the demo?
- What maximum image size and upload limit are practical for the target machine?
- What IoU threshold and matching policy will be used?
- Will labeled ground-truth data be available?
- Is report export required for judging, or is a dashboard sufficient?
- What is the final data-retention policy for uploaded images and saved runs?

**Important:** This PRD is based on the supplied VisionGuard project brief. It is a proposed project specification, not confirmation that VisionGuard matches an official HackFusion 2.0 challenge. Verify the official problem statement and judging criteria before final submission.

---

## 19. Release Definition

The hackathon MVP is considered ready when a team member can, on the target machine:

1. Start the application using the documented setup.
2. Upload a valid image.
3. Run clean-image inference.
4. apply at least three transformations and analyze the altered images.
5. Review side-by-side predictions and at least three correctly calculated metrics.
6. Inspect a reported failure.
7. Explain the run configuration, metric definitions, and limitations.

The team should prioritize a complete, trustworthy demonstration over a larger feature set.
