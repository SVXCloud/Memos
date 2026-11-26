import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "subpath.spec.ts",
  workers: 1,
  reporter: "list",
  outputDir: "../../node_modules/.cache/subpath-browser-results",
  use: {
    browserName: "chromium",
    baseURL: process.env.MEMOS_SMOKE_ORIGIN,
    launchOptions: { executablePath: process.env.MEMOS_SMOKE_CHROMIUM },
  },
});
