import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe("Scenario H — Independent Worker Mode Workflow", () => {
  test("Decoupled Worker claims, executes, and completes run", async ({ page }) => {
    test.setTimeout(90000);

    const repoRoot = path.resolve(__dirname, "../..");
    const venvPython = path.join(repoRoot, ".venv-gpu", "Scripts", "python.exe");
    const pythonExe = fs.existsSync(venvPython) ? venvPython : "python";

    // 1. Queue a run directly via Python simulating worker dispatcher mode
    const runId = `e2e-worker-${Date.now()}`;
    const insertScript = `
import sys
from pathlib import Path
repo = r"${repoRoot}"
if repo not in sys.path:
    sys.path.insert(0, repo)

from datetime import datetime, timezone
from backend.app.database import RunDatabase

db = RunDatabase("sqlite:///D:/Projects/VisionGuard/scratch/test_e2e.db")
now = datetime.now(timezone.utc)
db.create_run({
    "run_id": "${runId}",
    "status": "QUEUED",
    "model_id": "fasterrcnn_resnet50_fpn",
    "dataset_id": "visionguard_demo",
    "config": {
        "model_id": "fasterrcnn_resnet50_fpn",
        "dataset_id": "visionguard_demo",
        "corruptions": [{"kind": "blur", "severities": [1]}],
        "seed": 42
    },
    "created_at": now,
    "updated_at": now,
})
db.dispose()
print("QUEUED ${runId}")
`;

    execSync(`"${pythonExe}" -`, {
      cwd: repoRoot,
      input: insertScript,
      encoding: "utf-8",
    });

    // 2. Open frontend run details view — verify it renders in QUEUED state
    await page.goto(`/runs/${runId}`);
    await expect(page.locator("header")).toBeVisible();
    await expect(page.getByText("Queued", { exact: true })).toBeVisible({ timeout: 10000 });

    // 3. Trigger worker execution for this specific run ID via CLI
    const workerOutput = execSync(
      `"${pythonExe}" -m backend.app.worker ${runId}`,
      {
        cwd: repoRoot,
        env: {
          ...process.env,
          TEST_DATABASE_URL: "sqlite:///D:/Projects/VisionGuard/scratch/test_e2e.db",
        },
        encoding: "utf-8",
      }
    );

    // 4. Verify frontend detects COMPLETED status and displays report metrics
    await expect(page.getByText("COMPLETED")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Retention|Matched IoU|Class Consistency/i).first()).toBeVisible();
  });
});
