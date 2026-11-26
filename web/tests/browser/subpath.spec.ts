import { expect, test } from "@playwright/test";

test("sign in and reload a deep memo route under /memo", async ({ page }) => {
  await page.goto("/memo/auth?auto_sign_in=false");
  await page.getByRole("textbox", { name: /username/i }).fill(process.env.MEMOS_SMOKE_USERNAME!);
  await page.locator('input[type="password"]').fill(process.env.MEMOS_SMOKE_PASSWORD!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/memo\/?$/);

  await page.goto("/memo/memos/smoke");
  await expect(page.getByText("Subpath browser smoke", { exact: true }).first()).toBeVisible();
  await page.reload();
  await expect(page.getByText("Subpath browser smoke", { exact: true }).first()).toBeVisible();
});

test("complete an OIDC authorization-code callback under /memo", async ({ page }) => {
  await page.goto("/memo/auth?auto_sign_in=false&redirect=%2Fabout");
  await page.getByRole("button", { name: "Continue with Test OIDC" }).click();
  await expect(page).toHaveURL(/\/memo\/about$/);
  const response = await page.request.post("/memo/memos.api.AuthService/RefreshToken", {
    data: {},
    headers: { "Connect-Protocol-Version": "1" },
  });
  expect(response.ok()).toBe(true);
  expect((await response.json()).accessToken).toBeTruthy();
});
