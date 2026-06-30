import { defineConfig, devices } from "@playwright/test";

const PORT = 4173;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  reporter: process.env.CI ? "list" : "html",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
  },
  webServer: {
    command: `python3 -m http.server ${PORT}`,
    port: PORT,
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
    },
  ],
});
