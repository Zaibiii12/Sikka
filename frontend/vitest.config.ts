import {
  defineConfig,
} from "vitest/config";


export default defineConfig({
  test: {
    include: [
      "src/**/*.test.ts",
      "src/**/*.test.tsx",
      "src/**/*.spec.ts",
      "src/**/*.spec.tsx",
    ],

    exclude: [
      "tests/e2e/**",
      "node_modules/**",
      "dist/**",
      "playwright-report/**",
      "test-results/**",
    ],
  },
});
