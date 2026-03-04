import { type Membership, type Org, type OrgRole } from "@prisma/client";
import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { getGuildMemberWithBot, getUserGuilds, userHasRequiredRole, userIsInGuild } from "@/lib/discord";
import { getDiscordProviderIdForOrg, getOrgFromConfig } from "@/lib/org-config";
import { prisma } from "@/lib/prisma";

export type AccessFailureReason =
  | "NO_SESSION"
  | "WRONG_AUTH_PROVIDER"
  | "NO_ACCESS_TOKEN"
  | "NOT_IN_GUILD"
  | "BANNED"
  | "ROLE_REQUIRED"
  | "ROLE_CHECK_UNAVAILABLE";

interface AccessBase {
  org: Org;
}

interface AccessSuccess extends AccessBase {
  allowed: true;
  membership: Membership;
}

interface AccessFailure extends AccessBase {
  allowed: false;
  reason: AccessFailureReason;
  membership?: Membership;
}

export type OrgAccessResult = AccessSuccess | AccessFailure;

function toAuthBaseUrl(path: string): string {
  const base = process.env.NEXTAUTH_URL?.replace(/\/+$/, "");
  return base ? `${base}${path}` : path;
}

export function getOrgSignInPath(orgSlug: string, callbackPath: string): string {
  const mode = callbackPath.includes("/admin") ? "admin" : "member";
  return toAuthBaseUrl(`/o/${orgSlug}/login?mode=${mode}&callback=${encodeURIComponent(callbackPath)}`);
}

export function getDirectDiscordSignInPath(orgSlug: string, callbackPath: string): string {
  const providerId = getDiscordProviderIdForOrg(orgSlug);
  return toAuthBaseUrl(
    `/api/auth/signin?provider=${encodeURIComponent(providerId)}&callbackUrl=${encodeURIComponent(callbackPath)}`
  );
}

export async function requireSession() {
  const session = await auth();
  if (!session?.user?.id) {
    redirect("/api/auth/signin");
  }

  return session;
}

export async function requireOrg(orgSlug: string): Promise<Org> {
  const existingOrg = await prisma.org.findUnique({ where: { slug: orgSlug } });
  if (existingOrg) {
    return existingOrg;
  }

  const configuredOrg = getOrgFromConfig(orgSlug);
  if (!configuredOrg) {
    redirect("/");
  }

  return prisma.org.create({
    data: {
      slug: configuredOrg.slug,
      name: configuredOrg.name,
      guildId: configuredOrg.guildId,
      inviteUrl: configuredOrg.inviteUrl
    }
  });
}

export async function enforceGuildMembership(orgSlug: string): Promise<OrgAccessResult> {
  const org = await requireOrg(orgSlug);
  const session = await auth();

  if (!session?.user?.id) {
    return { allowed: false, org, reason: "NO_SESSION" };
  }

  const providerId = getDiscordProviderIdForOrg(orgSlug);

  const account = await prisma.account.findFirst({
    where: {
      userId: session.user.id,
      provider: providerId
    }
  });

  if (!account) {
    return { allowed: false, org, reason: "WRONG_AUTH_PROVIDER" };
  }

  if (!account?.access_token) {
    return { allowed: false, org, reason: "NO_ACCESS_TOKEN" };
  }

  const guilds = await getUserGuilds(account.access_token);
  if (!userIsInGuild(guilds, org.guildId)) {
    return { allowed: false, org, reason: "NOT_IN_GUILD" };
  }

  const membership = await prisma.membership.upsert({
    where: {
      userId_orgId: {
        userId: session.user.id,
        orgId: org.id
      }
    },
    update: {
      status: "ACTIVE"
    },
    create: {
      userId: session.user.id,
      orgId: org.id,
      status: "ACTIVE",
      role: "MEMBER"
    }
  });

  if (membership.status === "BANNED") {
    return { allowed: false, org, membership, reason: "BANNED" };
  }

  const configuredOrg = getOrgFromConfig(orgSlug);
  const requiredRoleIds = configuredOrg?.requiredRoleIds ?? [];

  if (requiredRoleIds.length > 0) {
    const botToken = process.env.DISCORD_BOT_TOKEN;
    const discordId = session.user.discordId;

    if (!botToken || !discordId) {
      return { allowed: false, org, membership, reason: "ROLE_CHECK_UNAVAILABLE" };
    }

    const guildMember = await getGuildMemberWithBot(org.guildId, discordId, botToken);
    if (!guildMember || !userHasRequiredRole(requiredRoleIds, guildMember.roles)) {
      return { allowed: false, org, membership, reason: "ROLE_REQUIRED" };
    }
  }

  return { allowed: true, org, membership };
}

export function redirectForAccessFailure(orgSlug: string, callbackPath: string, reason: AccessFailureReason): never {
  if (reason === "NO_SESSION" || reason === "WRONG_AUTH_PROVIDER" || reason === "NO_ACCESS_TOKEN") {
    redirect(getOrgSignInPath(orgSlug, callbackPath));
  }

  if (reason === "BANNED") {
    redirect(`/o/${orgSlug}/banned`);
  }

  redirect(`/o/${orgSlug}/join?reason=${reason.toLowerCase()}`);
}

export async function requireMemberAccess(orgSlug: string, callbackPath: string): Promise<AccessSuccess> {
  const access = await enforceGuildMembership(orgSlug);
  if (!access.allowed) {
    redirectForAccessFailure(orgSlug, callbackPath, access.reason);
  }

  return access;
}

export async function getMembershipContext(orgSlug: string): Promise<{
  org: Org;
  membership: Membership;
  userId: string;
}> {
  const session = await requireSession();
  const org = await requireOrg(orgSlug);

  const membership = await prisma.membership.findUnique({
    where: {
      userId_orgId: {
        userId: session.user.id,
        orgId: org.id
      }
    }
  });

  if (!membership) {
    redirect(`/o/${orgSlug}/join?reason=membership_missing`);
  }

  if (membership.status === "BANNED") {
    redirect(`/o/${orgSlug}/banned`);
  }

  return {
    org,
    membership,
    userId: session.user.id
  };
}

export function requireAdmin(membershipRole: OrgRole, orgSlug: string): void {
  if (membershipRole !== "ADMIN" && membershipRole !== "OWNER") {
    redirect(`/o/${orgSlug}/member`);
  }
}
