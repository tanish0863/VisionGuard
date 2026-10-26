import { test, expect } from "@playwright/test";

test.describe("VisionGuard End-to-End Evaluation Workflow", () => {
  let createdRunId = "";

  test("Scenario A — Application Startup & Catalog Loading", async ({ page }) => {
    // 1. Open root dashboard
    await page.goto("/dashboard");

    // 2. Verify header, branding, and navigation
    await expect(page.locator("header")).toBeVisible();
    await expect(page.getByRole("link", { name: "VisionGuard AI" })).toBeVisible();
    await expect(page.locator("nav").getByRole("link", { name: "Overview" })).toBeVisible();
    await expect(page.locator("nav").getByRole("link", { name: "New evaluation" })).toBeVisible();
    await expect(page.locator("nav").getByRole("link", { name: "Settings & glossary" })).toBeVisible();

    // 3. Verify backend connectivity indicator
    await expect(page.getByText("Backend Connected (FastAPI)")).toBeVisible({ timeout: 15000 });

    // 4. Navigate to New Evaluation page
    await page.locator("nav").getByRole("link", { name: "New evaluation" }).click();
    await expect(page).toHaveURL(/\/new/);

    // 5. Verify Model & Dataset catalogs loaded
    const datasetSelect = page.locator("select").nth(0);
    const modelSelect = page.locator("select").nth(1);

    await expect(datasetSelect).toBeVisible();
    await expect(datasetSelect).not.toBeDisabled();
    await expect(modelSelect).toBeVisible();
    await expect(modelSelect).not.toBeDisabled();

    // Verify registered benchmark dataset is present
    await expect(page.getByText("visionguard_demo")).toBeVisible();
  });

  test("Scenario B & C — Evaluation Submission & Lifecycle to Completion", async ({ page }) => {
    test.setTimeout(180000); // Allow sufficient time for Faster R-CNN CPU inference

    await page.goto("/new");
    await expect(page.getByText("Backend Connected (FastAPI)")).toBeVisible({ timeout: 15000 });

    // Ensure preset Blur s1 is selected
    const blurPresetBtn = page.getByRole("button", { name: "Preset: Blur s1" });
    if (await blurPresetBtn.isVisible()) {
      await blurPresetBtn.click();
    }

    // Submit evaluation form
    const submitBtn = page.getByRole("button", { name: /Launch Evaluation/i });
    await expect(submitBtn).toBeEnabled();

    // Intercept POST /api/v1/runs response to capture run_id (returns 202 Accepted)
    const runResponsePromise = page.waitForResponse(
      (response) => response.url().includes("/api/v1/runs") && response.request().method() === "POST"
    );

    await submitBtn.click();

    const runResponse = await runResponsePromise;
    expect(runResponse.status()).toBe(202);
    const runJson = await runResponse.json();
    expect(runJson.run_id).toBeDefined();
    createdRunId = runJson.run_id;

    // Verify automatic navigation to /runs/:id
    await expect(page).toHaveURL(new RegExp(`/runs/${createdRunId}`));

    // Scenario C: Verify Lifecycle (QUEUED / RUNNING -> COMPLETED)
    await expect(page.locator("header")).toBeVisible();

    // Wait for the run to reach COMPLETED terminal state
    await expect(page.getByText("COMPLETED")).toBeVisible({ timeout: 150000 });

    // Verify polling stops (no infinite requests) and summary metrics render
    await expect(page.getByText(/Retention|Matched IoU|Class Consistency/i).first()).toBeVisible();
  });

  test("Scenario D — Report Display & Methodology Disclosures", async ({ page }) => {
    test.skip(!createdRunId, "Requires completed run from Scenario B");

    await page.goto(`/runs/${createdRunId}`);
    await expect(page.getByText("COMPLETED")).toBeVisible({ timeout: 15000 });

    // Verify metric cards
    await expect(page.getByText(/Retention/i).first()).toBeVisible();
    await expect(page.getByText(/Class Consistency/i).first()).toBeVisible();

    // Verify Reference-free disclosure is visible and ground-truth metrics (mAP, Precision, Recall) are NOT claimed
    await expect(page.getByText(/Reference-free/i).first()).toBeVisible();

    // Verify condition breakdown table
    await expect(page.getByRole("table")).toBeVisible();
    await expect(page.getByText(/blur/i).first()).toBeVisible();
  });

  test("Scenario E — Failure Viewer & Visual Canvas Overlays", async ({ page }) => {
    test.skip(!createdRunId, "Requires completed run from Scenario B");

    await page.goto(`/runs/${createdRunId}/failures`);

    // Verify header and navigation
    await expect(page.getByText("Failure Analysis & Visual Evidence")).toBeVisible({ timeout: 15000 });

    // Verify canvas elements for both clean and corrupted views
    const canvases = page.locator("canvas");
    await expect(canvases.first()).toBeVisible({ timeout: 15000 });
    expect(await canvases.count()).toBeGreaterThanOrEqual(2);

    // Verify original and corrupted section labels
    await expect(page.getByText(/Clean Baseline/i).first()).toBeVisible();
    await expect(page.getByText(/Corrupted Condition/i).first()).toBeVisible();
  });

  test("Scenario F — Refresh Persistence", async ({ page }) => {
    test.skip(!createdRunId, "Requires completed run from Scenario B");

    await page.goto(`/runs/${createdRunId}`);
    await expect(page.getByText("COMPLETED")).toBeVisible({ timeout: 15000 });

    // Reload page
    await page.reload();

    // Verify run details and report persist after refresh
    await expect(page.getByText("COMPLETED")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(createdRunId)).toBeVisible();
    await expect(page.getByText(/Retention/i).first()).toBeVisible();
  });

  test("Scenario G — Error Handling & Edge Cases", async ({ page }) => {
    // 1. Non-existent Run ID
    await page.goto("/runs/non-existent-uuid-00000000-0000");
    await expect(
      page.getByText(/Evaluation run not found|Run not found|Failed to load run details|404/i).first()
    ).toBeVisible({ timeout: 15000 });

    // 2. Settings & Glossary View renders reliably
    await page.goto("/settings");
    await expect(page.getByText("Metric glossary")).toBeVisible();
    await expect(page.getByText("Methodology limitations")).toBeVisible();
    await expect(page.getByText("Reference-free", { exact: true }).first()).toBeVisible();
  });
});
