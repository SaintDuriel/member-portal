export interface DiscordGuild {
  id: string;
  name: string;
}

export interface DiscordGuildMember {
  roles: string[];
}

export async function getUserGuilds(accessToken: string): Promise<DiscordGuild[]> {
  const response = await fetch("https://discord.com/api/users/@me/guilds", {
    headers: {
      Authorization: `Bearer ${accessToken}`
    },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch guilds from Discord (${response.status})`);
  }

  return (await response.json()) as DiscordGuild[];
}

export async function getGuildMemberWithBot(
  guildId: string,
  discordId: string,
  botToken: string
): Promise<DiscordGuildMember | null> {
  const response = await fetch(`https://discord.com/api/guilds/${guildId}/members/${discordId}`, {
    headers: {
      Authorization: `Bot ${botToken}`
    },
    cache: "no-store"
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch guild member from Discord (${response.status})`);
  }

  return (await response.json()) as DiscordGuildMember;
}

export function userIsInGuild(guilds: DiscordGuild[], guildId: string): boolean {
  return guilds.some((guild) => guild.id === guildId);
}

export function userHasRequiredRole(requiredRoleIds: string[], roles: string[]): boolean {
  if (requiredRoleIds.length === 0) {
    return true;
  }

  return requiredRoleIds.some((roleId) => roles.includes(roleId));
}