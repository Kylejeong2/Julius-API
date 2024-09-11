import type { Page } from "playwright-core";

export const waitForReload = async (
  page: Page,
  selector: string,
  numAttempts = 3,
) => {
  try {
    await page.waitForSelector(selector, { timeout: 10000 });
  } catch (e) {
    await page.reload();
    await waitForReload(page, selector, numAttempts - 1);
  }
  return;
};
