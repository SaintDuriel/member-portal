import NextAuth from "next-auth";
import Discord from "next-auth/providers/discord";
import { PrismaAdapter } from "@auth/prisma-adapter";
import { getDiscordCredentialEnvVarNames, getDiscordProviderIdForOrg, getOrgConfig, getOrgFromConfig } from "@/lib/org-config";
import { prisma } from "@/lib/prisma";

function buildDiscordProviders() {
  const orgConfig = getOrgConfig();
  const orgSlugs = Object.keys(orgConfig);

  if (orgSlugs.length === 0) {
    throw new Error("ORG_CONFIG must contain at least one organization");
  }

  return orgSlugs.map((orgSlug) => {
    const org = getOrgFromConfig(orgSlug);
    if (!org) {
      throw new Error(`Organization "${orgSlug}" missing in ORG_CONFIG`);
    }

    const { clientIdVar, clientSecretVar } = getDiscordCredentialEnvVarNames(orgSlug);
    const clientId = process.env[clientIdVar];
    const clientSecret = process.env[clientSecretVar];

    if (!clientId || !clientSecret) {
      throw new Error(
        `Missing Discord OAuth credentials for org "${orgSlug}". Set ${clientIdVar} and ${clientSecretVar}.`
      );
    }

    return Discord({
      id: getDiscordProviderIdForOrg(orgSlug),
      name: `${org.name} Discord`,
      clientId,
      clientSecret,
      allowDangerousEmailAccountLinking: true,
      authorization: {
        params: {
          scope: "identify email guilds"
        }
      }
    });
  });
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  adapter: PrismaAdapter(prisma),
  session: {
    strategy: "database"
  },
  providers: buildDiscordProviders(),
  callbacks: {
    async signIn({ account, profile, user }) {
      if (!account?.provider?.startsWith("discord")) {
        return true;
      }

      if (!user.id) {
        return false;
      }

      const discordId = profile?.id?.toString();
      if (!discordId) {
        return false;
      }

      const displayName = profile?.global_name?.toString() ?? profile?.username?.toString() ?? null;
      const avatarUrl = profile?.image_url?.toString() ?? user.image ?? null;
      const normalizedEmail = user.email ?? null;

      const existingByDiscord = await prisma.user.findUnique({
        where: { discordId }
      });

      if (existingByDiscord) {
        await prisma.user.update({
          where: { id: existingByDiscord.id },
          data: {
            displayName,
            avatarUrl,
            email: normalizedEmail ?? existingByDiscord.email
          }
        });

        if (existingByDiscord.id !== user.id) {
          await prisma.account.updateMany({
            where: {
              provider: account.provider,
              providerAccountId: account.providerAccountId
            },
            data: {
              userId: existingByDiscord.id
            }
          });
        }

        return true;
      }

      await prisma.user.upsert({
        where: { id: user.id },
        update: {
          discordId,
          displayName,
          avatarUrl,
          email: normalizedEmail
        },
        create: {
          id: user.id,
          discordId,
          displayName,
          avatarUrl,
          email: normalizedEmail
        }
      });

      return true;
    },
    async session({ session, user }) {
      if (session.user) {
        const dbUser = await prisma.user.findUnique({
          where: { id: user.id },
          select: { discordId: true }
        });

        session.user.id = user.id;
        session.user.discordId = dbUser?.discordId ?? "";
      }
      return session;
    }
  }
});
