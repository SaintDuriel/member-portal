import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: [
      "tests/**/*.test.ts",
      "tests/**/*.test.tsx",
      "tests/**/*.spec.ts",
      "tests/**/*.spec.tsx"
    ],
    exclude: [
      "tests/e2e/**",
      "node_modules/**",
      ".next/**",
      "dist/**"
    ],
    passWithNoTests: true
  }
});
