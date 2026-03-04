import { expect, test } from "@playwright/test";

const ORG_SLUG = "burningman";
const interactiveAuthEnabled = process.env.E2E_DISCORD_INTERACTIVE === "1";

test.describe("Member profile flow", () => {
  test("automated flow reaches Discord OAuth handoff from site entry", async ({ page }) => {
    await test.step("Navigate to home", async () => {
      await page.goto("/");
      await expect(page.getByRole("heading", { name: "Guild Sites" })).toBeVisible();
    });

    await test.step("Select org and enter member area", async () => {
      await page.getByRole("link", { name: "Camp Whatever" }).click();
      await expect(page).toHaveURL(`/o/${ORG_SLUG}`);

      await page.getByRole("link", { name: "Member area" }).click();
      await expect(page).toHaveURL(new RegExp(`/o/${ORG_SLUG}/login\\?mode=member`));
    });

    await test.step("Validate Discord login handoff link", async () => {
      const memberLoginLink = page.getByRole("link", { name: "Continue as Member" });
      await expect(memberLoginLink).toBeVisible();

      const href = await memberLoginLink.getAttribute("href");
      expect(href).toContain("/api/auth/signin?provider=discord-burningman");
      expect(href).toContain(`callbackUrl=%2Fo%2F${ORG_SLUG}%2Fmember`);
    });
  });

  test("interactive flow can continue from Discord OAuth to profile tools", async ({ page }) => {
    test.skip(!interactiveAuthEnabled, "Set E2E_DISCORD_INTERACTIVE=1 to run manual Discord login flow.");

    await page.goto(`/o/${ORG_SLUG}/login?mode=member&callback=%2Fo%2F${ORG_SLUG}%2Fmember`);
    await page.getByRole("link", { name: "Continue as Member" }).click();

    await expect(page).toHaveURL(/discord\.com\/oauth2\/authorize/);

    // Manual checkpoint: complete Discord auth in the opened browser, then resume test.
    await page.pause();

    await page.goto(`/o/${ORG_SLUG}/member/policies`);

    const policyHeading = page.getByRole("heading", { name: /Policies and Acknowledgements/i });
    await expect(policyHeading).toBeVisible();

    // Acknowledge any pending policies so profile route becomes accessible.
    const acknowledgeButtons = page.getByRole("button", { name: "Acknowledge" });
    while ((await acknowledgeButtons.count()) > 0) {
      await acknowledgeButtons.first().click();
      await page.waitForLoadState("networkidle");
    }

    await page.goto(`/o/${ORG_SLUG}/member/profile`);
    await expect(page.getByRole("heading", { name: /Profile Wizard/i })).toBeVisible();
  });
});
