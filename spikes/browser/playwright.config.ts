import { defineConfig } from "@playwright/test";

// E2E_BASE_URL=https://<project>.pages.dev runs the same specs against the deployed site.
const remote = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "e2e",
  webServer: remote
    ? undefined
    : {
        command: "pnpm build && pnpm preview",
        url: "http://localhost:4173",
        reuseExistingServer: true,
      },
  use: { baseURL: remote ?? "http://localhost:4173" },
});
