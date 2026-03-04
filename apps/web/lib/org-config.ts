import { z } from "zod";

const orgConfigSchema = z.record(
  z.object({
    name: z.string().min(1),
    guildId: z.string().min(1),
    requiredRoleIds: z.array(z.string()).default([]),
    inviteUrl: z.string().url().optional(),
    authProviderId: z.string().min(1).optional()
  })
);

export type OrgConfig = z.infer<typeof orgConfigSchema>;
export type OrgConfigEntry = OrgConfig[string] & { slug: string; authProviderId: string };

let cachedConfig: OrgConfig | null = null;

export function getOrgConfig(): OrgConfig {
  if (cachedConfig) {
    return cachedConfig;
  }

  const raw = process.env.ORG_CONFIG;
  if (!raw) {
    throw new Error("ORG_CONFIG env var is required");
  }

  const parsed = orgConfigSchema.parse(JSON.parse(raw));
  cachedConfig = parsed;
  return parsed;
}

export function getOrgFromConfig(orgSlug: string): OrgConfigEntry | null {
  const config = getOrgConfig();
  const org = config[orgSlug];

  if (!org) {
    return null;
  }

  return {
    ...org,
    slug: orgSlug,
    requiredRoleIds: org.requiredRoleIds ?? [],
    authProviderId: org.authProviderId ?? `discord-${orgSlug}`
  };
}

export function getDiscordProviderIdForOrg(orgSlug: string): string {
  const org = getOrgFromConfig(orgSlug);
  if (!org) {
    throw new Error(`Organization "${orgSlug}" was not found in ORG_CONFIG`);
  }

  return org.authProviderId;
}

function toEnvSlugKey(orgSlug: string): string {
  return orgSlug
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toUpperCase();
}

export function getDiscordCredentialEnvVarNames(orgSlug: string): {
  clientIdVar: string;
  clientSecretVar: string;
} {
  const envKey = toEnvSlugKey(orgSlug);
  return {
    clientIdVar: `DISCORD_CLIENT_ID_${envKey}`,
    clientSecretVar: `DISCORD_CLIENT_SECRET_${envKey}`
  };
}
