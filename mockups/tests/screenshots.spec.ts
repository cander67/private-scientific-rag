import { test } from "@playwright/test";
import { PAGES } from "./pages";

// Generates the review screenshot matrix:
//   screenshots/<project>/<page>-<theme>.png
// where <project> is desktop or mobile (from playwright.config.ts).
for (const page of PAGES) {
  for (const theme of ["light", "dark"] as const) {
    test(`${page.title} — ${theme}`, async ({ page: pw }, testInfo) => {
      await pw.goto(`/${page.slug}`);
      await pw.evaluate((t) => {
        localStorage.setItem("mml-theme", t);
        document.documentElement.setAttribute("data-theme", t);
      }, theme);
      await pw.waitForTimeout(150);

      const name = page.slug.replace(".html", "");
      await pw.screenshot({
        path: `screenshots/${testInfo.project.name}/${name}-${theme}.png`,
        fullPage: true,
      });
    });
  }
}
