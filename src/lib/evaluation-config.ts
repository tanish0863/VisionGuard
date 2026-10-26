export const CORRUPTIONS = ["Gaussian blur", "Low light", "Gaussian noise"] as const;
export function validateConditions(count: number) {
  return Number.isInteger(count) && count >= 1 && count <= 24;
}
export function validateThreshold(value: number) {
  return Number.isFinite(value) && value >= 0 && value <= 1;
}