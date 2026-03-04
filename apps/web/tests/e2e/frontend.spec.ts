import { expect, test } from "@playwright/test";

test.describe("Frontend smoke checks", () => {
  test("home page renders org links", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Guild Sites" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Camp Whatever" })).toHaveAttribute("href", "/o/burningman");
    await expect(page.getByRole("link", { name: "Guild Whatever" })).toHaveAttribute("href", "/o/renfaire");
  });

  test("org landing page renders member/admin entry links", async ({ page }) => {
    await page.goto("/o/burningman");

    await expect(page.getByRole("heading", { name: "Organization: burningman" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Member area" })).toHaveAttribute("href", "/o/burningman/member");
    await expect(page.getByRole("link", { name: "Admin area" })).toHaveAttribute("href", "/o/burningman/admin");
  });

  test("org join page shows discord join guidance", async ({ page }) => {
    await page.goto("/o/burningman/join");

    await expect(page.getByRole("heading", { name: /Join .* Discord/i })).toBeVisible();
    await expect(page.getByRole("link", { name: "Join server" })).toBeVisible();
  });

  test("member route redirects to org login page", async ({ page }) => {
    await page.goto("/o/burningman/member");

    await expect(page).toHaveURL(/\/o\/burningman\/login\?mode=member/);
    await expect(page.getByRole("heading", { name: /Sign In to/i })).toBeVisible();
  });

  test("admin route redirects to org login page in admin mode", async ({ page }) => {
    await page.goto("/o/burningman/admin");

    await expect(page).toHaveURL(/\/o\/burningman\/login\?mode=admin/);
    await expect(page.getByRole("heading", { name: /Sign In to/i })).toBeVisible();
  });

  test("login page exposes member/admin auth links with provider and callback", async ({ page }) => {
    await page.goto("/o/burningman/login?mode=member&callback=%2Fo%2Fburningman%2Fmember");

    const memberAuthLink = page.getByRole("link", { name: "Continue as Member" });
    const adminAuthLink = page.getByRole("link", { name: "Continue as Admin" });

    const memberHref = await memberAuthLink.getAttribute("href");
    const adminHref = await adminAuthLink.getAttribute("href");

    expect(memberHref).toContain("/api/auth/signin?provider=discord-burningman");
    expect(memberHref).toContain("callbackUrl=%2Fo%2Fburningman%2Fmember");

    expect(adminHref).toContain("/api/auth/signin?provider=discord-burningman");
    expect(adminHref).toContain("callbackUrl=%2Fo%2Fburningman%2Fadmin");
  });
});
