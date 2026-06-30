import { test, expect } from "@playwright/test";
import { PAGES } from "./pages";

for (const page of PAGES) {
  test.describe(page.title, () => {
    test("loads without console errors", async ({ page: pw }) => {
      const errors: string[] = [];
      pw.on("console", (msg) => {
        if (msg.type() === "error") errors.push(msg.text());
      });
      pw.on("pageerror", (err) => errors.push(err.message));

      await pw.goto(`/${page.slug}`);
      await expect(pw.locator(".sidebar")).toBeVisible();
      await expect(pw.locator(".topbar h1")).toContainText(page.title);
      expect(errors, errors.join("\n")).toEqual([]);
    });

    test("theme toggle flips data-theme and persists", async ({ page: pw }) => {
      await pw.goto(`/${page.slug}`);
      const html = pw.locator("html");
      const before = await html.getAttribute("data-theme");
      await pw.locator("[data-action='toggle-theme']").first().click();
      const after = await html.getAttribute("data-theme");
      expect(after).not.toBe(before);

      // persists across reload
      await pw.reload();
      expect(await html.getAttribute("data-theme")).toBe(after);
    });
  });
}
