import { describe, expect, it } from "vitest";
import { validateConditions, validateThreshold } from "../lib/evaluation-config";
describe("Evaluation configuration", () => {
  it("requires between 1 and 24 conditions", () => {
    expect(validateConditions(0)).toBe(false);
    expect(validateConditions(1)).toBe(true);
    expect(validateConditions(24)).toBe(true);
    expect(validateConditions(25)).toBe(false);
  });
  it("uses confidence values from 0 to 1", () => {
    expect(validateThreshold(-0.01)).toBe(false);
    expect(validateThreshold(0)).toBe(true);
    expect(validateThreshold(1)).toBe(true);
    expect(validateThreshold(1.01)).toBe(false);
  });
});