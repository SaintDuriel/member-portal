import { PrismaClient } from "@prisma/client";
import { promises as fs } from "node:fs";
import path from "node:path";

type OrgConfig = Record<
  string,
  {
    name: string;
    guildId: string;
    requiredRoleIds?: string[];
    inviteUrl?: string;
  }
>;

const prisma = new PrismaClient();

function parseOrgConfig(raw: string | undefined): OrgConfig {
  if (!raw) {
    throw new Error("ORG_CONFIG is required for seeding");
  }

  try {
    const parsed = JSON.parse(raw) as OrgConfig;
    return parsed;
  } catch (error) {
    throw new Error(`Failed to parse ORG_CONFIG JSON: ${(error as Error).message}`);
  }
}

async function readMarkdownFiles(dir: string): Promise<Array<{ file: string; content: string }>> {
  try {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    const mdFiles = entries.filter((entry) => entry.isFile() && entry.name.endsWith(".md"));

    const files = await Promise.all(
      mdFiles.map(async (file) => {
        const filePath = path.join(dir, file.name);
        const content = await fs.readFile(filePath, "utf8");
        return { file: file.name, content };
      })
    );

    return files;
  } catch {
    return [];
  }
}

function toSlug(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function titleFromMarkdown(fileName: string, content: string): string {
  const heading = content
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("#"));

  if (heading) {
    return heading.replace(/^#+\s*/, "").trim();
  }

  return fileName.replace(/\.md$/i, "").replace(/[-_]+/g, " ");
}

async function seedPolicies(orgId: string, orgSlug: string): Promise<void> {
  const policyDir = path.join(process.cwd(), "content", orgSlug, "policies");
  const policyFiles = await readMarkdownFiles(policyDir);

  for (const policyFile of policyFiles) {
    const key = toSlug(policyFile.file.replace(/\.md$/i, ""));
    const title = titleFromMarkdown(policyFile.file, policyFile.content);

    const existingVersions = await prisma.policyVersion.findMany({
      where: { orgId, key },
      orderBy: { version: "desc" }
    });

    const latest = existingVersions[0];

    if (!latest) {
      await prisma.policyVersion.create({
        data: {
          orgId,
          key,
          version: 1,
          title,
          contentMd: policyFile.content,
          isActive: true
        }
      });
      continue;
    }

    if (latest.contentMd !== policyFile.content) {
      await prisma.$transaction([
        prisma.policyVersion.updateMany({
          where: { orgId, key },
          data: { isActive: false }
        }),
        prisma.policyVersion.create({
          data: {
            orgId,
            key,
            version: latest.version + 1,
            title,
            contentMd: policyFile.content,
            isActive: true
          }
        })
      ]);
    }
  }
}

async function seedResources(orgId: string, orgSlug: string): Promise<void> {
  const resourceDir = path.join(process.cwd(), "content", orgSlug, "resources");
  const resourceFiles = await readMarkdownFiles(resourceDir);

  for (const resourceFile of resourceFiles) {
    const baseName = resourceFile.file.replace(/\.md$/i, "");
    const slug = toSlug(baseName);
    const title = titleFromMarkdown(resourceFile.file, resourceFile.content);

    await prisma.resource.upsert({
      where: { orgId_slug: { orgId, slug } },
      update: {
        title,
        contentMd: resourceFile.content,
        type: "ARTICLE",
        isPublic: true
      },
      create: {
        orgId,
        slug,
        title,
        type: "ARTICLE",
        contentMd: resourceFile.content,
        category: "general",
        isPublic: true
      }
    });
  }
}

async function main(): Promise<void> {
  const config = parseOrgConfig(process.env.ORG_CONFIG);

  for (const [slug, orgData] of Object.entries(config)) {
    const org = await prisma.org.upsert({
      where: { slug },
      update: {
        name: orgData.name,
        guildId: orgData.guildId,
        inviteUrl: orgData.inviteUrl
      },
      create: {
        slug,
        name: orgData.name,
        guildId: orgData.guildId,
        inviteUrl: orgData.inviteUrl
      }
    });

    await seedPolicies(org.id, slug);
    await seedResources(org.id, slug);
  }
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (error) => {
    console.error(error);
    await prisma.$disconnect();
    process.exit(1);
  });