Below is a **comprehensive implementation blueprint**. It’s written as a **single-repo, multi-tenant app** (Burning Man + Ren Faire) sharing one codebase, with **Discord OAuth login**, **Discord guild membership checks**, **optional role-gating**, **member profiles + privacy controls**, **member directory**, **resources hub (Markdown/links/files)**, **policy acknowledgements**, and **admin tools**.

---

# 0) North Star + Scope

## MVP (must ship)

* One web app serving two orgs (“burningman”, “renfaire”) via `/o/{slug}` routes
* Discord OAuth login (SSO)
* Verify user is a member of the org’s Discord guild (required)
* Member profile wizard + privacy controls
* Member directory (search + visibility enforcement)
* Resources hub (articles/links/files) with categories/tags
* Bylaws / code of conduct pages + versioned acknowledgement
* Admin panel: manage members, approve/ban (optional), manage resources, view/export directory (privacy filtered)

## Optional (Phase 2)

* Role-gating: require a Discord role for “active member”
* Announcements mirroring from Discord #announcements
* Events / shifts / equipment signup

---

# 1) Tech Stack (opinionated, small-team friendly)

**Frontend/Backend:** Next.js 14+ (App Router) + TypeScript
**Auth:** Auth.js (NextAuth v5) w/ Discord provider
**DB:** Postgres (local via Docker; prod via Supabase/Neon)
**ORM:** Prisma
**Storage:** S3-compatible or Supabase Storage (MVP can skip uploads and use links)
**UI:** TailwindCSS + shadcn/ui
**Validation:** Zod
**Testing:** Playwright (smoke) + Vitest (unit)
**Rate limiting:** Upstash Redis (optional) or simple in-memory dev limiter

---

# 2) Repo Layout

```
guild-sites/
  apps/web/
    app/
      (marketing)/
      o/[orgSlug]/
      api/
    components/
    lib/
    prisma/
    public/
  packages/
    ui/              # optional if you want shared UI later
  docker/
    postgres/
  scripts/
  .env.example
  docker-compose.yml
  package.json
  README.md
```

If you want to keep it simpler: keep everything under `apps/web/` only.

---

# 3) Local Setup (what CODEX should implement)

## 3.1 Docker Postgres

`docker-compose.yml`

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16
    container_name: guildsites_pg
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: guildsites
      POSTGRES_PASSWORD: guildsites
      POSTGRES_DB: guildsites
    volumes:
      - ./docker/postgres/data:/var/lib/postgresql/data
```

## 3.2 .env.example

```bash
# Database
DATABASE_URL="postgresql://guildsites:guildsites@localhost:5432/guildsites?schema=public"

# Auth.js
AUTH_SECRET="replace-with-long-random"
AUTH_TRUST_HOST=true
NEXTAUTH_URL="http://localhost:3000"

# Discord OAuth
DISCORD_CLIENT_ID="..."
DISCORD_CLIENT_SECRET="..."
DISCORD_REDIRECT_URI="http://localhost:3000/api/auth/callback/discord"

# Discord API (for guild membership checks)
DISCORD_BOT_TOKEN=""  # optional if you choose bot-based guild checks
# If not using bot token, you'll use user access token from OAuth and /users/@me/guilds

# Multi-org config (JSON string or individual env vars)
ORG_CONFIG='{
  "burningman": {
    "name": "Camp Whatever",
    "guildId": "DISCORD_GUILD_ID_1",
    "requiredRoleIds": ["OPTIONAL_ROLE_ID"],
    "inviteUrl": "https://discord.gg/xxxx"
  },
  "renfaire": {
    "name": "Guild Whatever",
    "guildId": "DISCORD_GUILD_ID_2",
    "requiredRoleIds": [],
    "inviteUrl": "https://discord.gg/yyyy"
  }
}'
```

**Note:** You have two approaches for membership checks:

* **OAuth-only:** call Discord API using user access token to list guilds (`/users/@me/guilds`). Easy, no bot.
* **Bot-assisted:** use a bot token to check guild member + roles precisely (`/guilds/{guildId}/members/{userId}`). More control, needs bot in server.

Blueprint below supports both; MVP can do OAuth-only membership checks and add bot later.

---

# 4) Data Model + RBAC

## 4.1 Roles

* **MEMBER:** normal logged-in user
* **ADMIN:** org admin (manage members/resources)
* **OWNER:** top admin (optional)
* **BANNED:** cannot access
* **PENDING:** if you enable approval workflow

## 4.2 Privacy levels (per field)

* `PRIVATE` (only me)
* `MEMBERS` (any org member)
* `ADMINS` (org admins)

## 4.3 Prisma schema (apps/web/prisma/schema.prisma)

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

enum MembershipStatus {
  PENDING
  ACTIVE
  BANNED
}

enum OrgRole {
  MEMBER
  ADMIN
  OWNER
}

enum Visibility {
  PRIVATE
  MEMBERS
  ADMINS
}

model Org {
  id        String   @id @default(cuid())
  slug      String   @unique
  name      String
  guildId   String   // discord guild id
  inviteUrl String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  memberships Membership[]
  resources   Resource[]
  policies    PolicyVersion[]
}

model User {
  id           String   @id @default(cuid())
  discordId    String   @unique
  email        String?
  displayName  String?
  avatarUrl    String?
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt

  memberships Membership[]
  sessions    Session[]
  accounts    Account[]
}

model Membership {
  id         String           @id @default(cuid())
  userId     String
  orgId      String
  status     MembershipStatus @default(ACTIVE)
  role       OrgRole          @default(MEMBER)

  // Discord snapshot (optional)
  discordUsername String?
  discordGlobalName String?
  discordRoles  String[] @default([])

  profile     Profile?
  acknowledgements Acknowledgement[]

  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt

  user User @relation(fields: [userId], references: [id])
  org  Org  @relation(fields: [orgId], references: [id])

  @@unique([userId, orgId])
  @@index([orgId, status, role])
}

model Profile {
  id           String   @id @default(cuid())
  membershipId String   @unique

  phone        String?
  phoneVis     Visibility @default(PRIVATE)

  emergencyContactName String?
  emergencyContactNameVis Visibility @default(ADMINS)

  emergencyContactPhone String?
  emergencyContactPhoneVis Visibility @default(ADMINS)

  playaName    String?
  playaNameVis Visibility @default(MEMBERS)

  region       String?
  regionVis    Visibility @default(MEMBERS)

  bio          String?
  bioVis       Visibility @default(MEMBERS)

  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt

  membership Membership @relation(fields: [membershipId], references: [id])
}

enum ResourceType {
  ARTICLE
  LINK
  FILE
}

model Resource {
  id        String       @id @default(cuid())
  orgId     String
  type      ResourceType
  title     String
  slug      String
  summary   String?
  contentMd String?      // for ARTICLE
  url       String?      // for LINK/FILE
  tags      String[]     @default([])
  category  String?
  isPublic  Boolean      @default(false)

  createdAt DateTime     @default(now())
  updatedAt DateTime     @updatedAt

  org Org @relation(fields: [orgId], references: [id])

  @@unique([orgId, slug])
  @@index([orgId, isPublic, category])
}

model PolicyVersion {
  id        String   @id @default(cuid())
  orgId     String
  key       String   // "bylaws", "code_of_conduct", etc
  version   Int
  title     String
  contentMd String
  isActive  Boolean  @default(true)
  createdAt DateTime @default(now())

  org Org @relation(fields: [orgId], references: [id])

  @@unique([orgId, key, version])
  @@index([orgId, key, isActive])
}

model Acknowledgement {
  id            String   @id @default(cuid())
  membershipId  String
  policyId      String
  acknowledgedAt DateTime @default(now())

  membership Membership @relation(fields: [membershipId], references: [id])
  policy     PolicyVersion @relation(fields: [policyId], references: [id])

  @@unique([membershipId, policyId])
}

//
// Auth.js Prisma Adapter models (minimal)
//
model Account {
  id                String  @id @default(cuid())
  userId            String
  type              String
  provider          String
  providerAccountId String
  access_token      String?
  token_type        String?
  scope             String?
  expires_at        Int?
  refresh_token     String?
  id_token          String?
  session_state     String?

  user User @relation(fields: [userId], references: [id])

  @@unique([provider, providerAccountId])
}

model Session {
  id           String   @id @default(cuid())
  sessionToken String   @unique
  userId       String
  expires      DateTime

  user User @relation(fields: [userId], references: [id])
}

model VerificationToken {
  identifier String
  token      String   @unique
  expires    DateTime

  @@unique([identifier, token])
}
```

---

# 5) Multi-Org Config Strategy

## 5.1 Seed orgs in DB

Implement `prisma/seed.ts`:

* Reads `ORG_CONFIG`
* Upserts `Org` records by slug
* Creates initial `PolicyVersion` for each org (bylaws, conduct) from markdown files in `/content/{orgSlug}/policies/*.md`
* Creates sample resources

Seed command:

```bash
pnpm prisma db push
pnpm prisma db seed
```

---

# 6) Auth + Discord Integration (core logic)

## 6.1 Auth.js config (apps/web/app/api/auth/[...nextauth]/route.ts)

* Discord Provider
* Prisma Adapter
* In callbacks:

  * On sign-in: ensure `User.discordId` matches
  * Store access token in `Account.access_token` (Auth.js adapter already supports storing)
  * After sign-in: create or upsert `Membership` for an org **when user visits that org** (not global at login)

## 6.2 Enforcing org access

When a user hits `/o/{orgSlug}/...`:

1. Require session
2. Lookup org by slug
3. Verify Discord guild membership:

   * **OAuth-only MVP:** use user access token and call `/users/@me/guilds` to confirm `guildId` exists
   * **Bot-based option:** call `/guilds/{guildId}/members/{discordUserId}` with bot token
4. If not in guild → show “Join Discord” page with invite link
5. If in guild → ensure `Membership` exists; update discord snapshot (username, roles if available)

### Discord API helpers (apps/web/lib/discord.ts)

Implement:

* `getUserGuilds(accessToken): Promise<{id,name}[]>`
* `getGuildMemberWithBot(guildId, discordId, botToken): Promise<{roles:string[]}>`
* `userIsInGuild(org, session): boolean` logic (OAuth-only)
* `userHasRequiredRole(org, roles): boolean` (if you enable role gating)

---

# 7) Route Map + Pages

## 7.1 Public marketing

* `/` (choose org)
* `/o/{orgSlug}` (org home)
* `/o/{orgSlug}/join` (how to join + Discord link)
* `/o/{orgSlug}/resources/public` (public resources)

## 7.2 Members area (auth required + guild check)

* `/o/{orgSlug}/member` (dashboard)
* `/o/{orgSlug}/member/profile` (wizard)
* `/o/{orgSlug}/member/directory`
* `/o/{orgSlug}/member/resources`
* `/o/{orgSlug}/member/policies` (active policy versions + acknowledgement)

## 7.3 Admin area

* `/o/{orgSlug}/admin` (overview)
* `/o/{orgSlug}/admin/members`
* `/o/{orgSlug}/admin/resources`
* `/o/{orgSlug}/admin/policies`
* `/o/{orgSlug}/admin/export` (CSV export endpoint)

---

# 8) Middleware + Guards

## 8.1 Middleware (optional but clean)

Use Next middleware to protect `/o/*/member/*` and `/o/*/admin/*` by requiring session.
Guild membership checks should happen server-side in layout/load to access org context.

## 8.2 Server helpers

Create `lib/authz.ts`:

* `requireSession()`
* `requireOrg(orgSlug)`
* `requireMembership(orgId, userId)`
* `requireAdmin(membership)`
* `enforceGuildMembership(org, userAccessToken, userDiscordId)`
* `enforceRoleGateIfEnabled(org, roles)`

---

# 9) Key Features Implementation Details

## 9.1 Member Profile + Privacy

### Profile form fields

* phone (+ visibility)
* emergency contact name/phone (Admin-only by default)
* playaName (Members by default)
* region (Members)
* bio (Members)

**Visibility enforcement**:

* Directory query must filter/transform output based on viewer’s role:

  * Admin sees all `ADMINS` and `MEMBERS` fields; private stays private unless owner of profile
  * Member sees `MEMBERS` fields; not `ADMINS`
  * Owner sees everything

Implementation pattern:

* Fetch full profile server-side
* Map to “view model” per viewer role before rendering

## 9.2 Directory

* Search by displayName/playaName/region
* Pagination (simple offset/limit)
* Output view model with redacted fields based on access
* Add rate limit on directory search endpoint (optional)

## 9.3 Resources Hub

Resource types:

* ARTICLE: store markdown in DB (`contentMd`)
* LINK: store `url`
* FILE: store `url` (later: upload)

Permissions:

* `isPublic` true → accessible without login at `/resources/public`
* else → members only

UI:

* Categories sidebar
* Tags
* Search

## 9.4 Policies + Acknowledgements

* `PolicyVersion` key + version
* Show active versions for each key
* “Acknowledge” button logs `Acknowledgement`
* Block access to directory until key policies acknowledged (configurable):

  * Example: require `bylaws` and `code_of_conduct` acknowledgement

Enforcement:

* In `/o/{orgSlug}/member/layout.tsx`, check outstanding acknowledgements and route user to `/policies` until completed.

## 9.5 Admin Panel

Admin capabilities:

* Promote/demote membership role
* Set status ACTIVE/PENDING/BANNED
* Create/edit resources
* Create new policy version (auto increments version; set active; optionally deactivate previous)

CSV export:

* Only includes fields visible to admins (`ADMINS` + `MEMBERS`, excluding `PRIVATE` unless owner)
* Log export event (optional table `AuditLog` in Phase 2)

---

# 10) API / Server Actions Design

Prefer **Server Actions** for forms and CRUD (Next.js App Router). For export, use a route handler.

## 10.1 Server actions (suggested)

* `actions/upsertProfile(orgSlug, data)`
* `actions/acknowledgePolicy(orgSlug, policyId)`
* `actions/admin/updateMember(orgSlug, membershipId, patch)`
* `actions/admin/upsertResource(orgSlug, resourceData)`
* `actions/admin/upsertPolicy(orgSlug, key, title, contentMd)`

## 10.2 Route handler for CSV export

`/o/[orgSlug]/admin/export/route.ts`

* require admin
* query memberships + profiles
* apply admin-view redaction rules
* return CSV response with correct headers

---

# 11) UI Components List (shadcn-friendly)

* `OrgShell` (top nav w org switcher)
* `MemberNav` / `AdminNav`
* `PolicyCard` + acknowledgement button
* `ProfileForm` (Zod schema + controlled inputs)
* `VisibilitySelect`
* `DirectoryTable` + `MemberCard` (mobile)
* `ResourceList`, `ResourceEditor`, `MarkdownViewer`
* `RequireDiscordMembership` gate page

---

# 12) Content Structure (Markdown in repo)

```
apps/web/content/
  burningman/
    policies/
      bylaws.md
      code_of_conduct.md
    resources/
      acculturation.md
      packing-list.md
  renfaire/
    policies/
      bylaws.md
      code_of_conduct.md
    resources/
      etiquette.md
      garb-guide.md
```

Seed reads these files and inserts into DB.

---

# 13) Implementation Steps (ordered “tickets” for CODEX)

## Ticket 1 — Scaffold

* Create Next.js app (App Router, TS, Tailwind)
* Install deps:

  * `next`, `react`, `typescript`
  * `tailwindcss`, `postcss`, `autoprefixer`
  * `prisma`, `@prisma/client`
  * `next-auth` (Auth.js), `@auth/prisma-adapter`
  * `zod`
  * shadcn/ui setup
* Docker compose for Postgres
* Basic README with setup commands

## Ticket 2 — Prisma schema + seed

* Add schema from above
* Implement seed reading `ORG_CONFIG` + markdown files
* `pnpm prisma migrate dev` (or db push for MVP)

## Ticket 3 — Auth.js Discord login

* Configure Discord provider
* Prisma adapter
* Session includes `user.id`, `discordId`, `avatarUrl`
* Store access token on account

## Ticket 4 — Org context + guild check

* Implement `/o/[orgSlug]/layout.tsx` server layout:

  * load org
  * require session for member/admin routes
  * implement OAuth-based guild membership check
  * upsert membership record
* Add “Join Discord” gate page

## Ticket 5 — Member dashboard + profile wizard

* Profile page with form + privacy selects
* Server action upserts `Profile`
* Dashboard shows completion state

## Ticket 6 — Policies + acknowledgement

* Policies page lists active policy versions
* Acknowledge action
* Enforce acknowledgement gate in member layout

## Ticket 7 — Directory

* Directory page
* Server-side query memberships + profile
* Redaction mapping based on viewer role
* Search + pagination

## Ticket 8 — Resources hub

* Members resources index + view
* Public resources index + view
* Admin resources editor CRUD

## Ticket 9 — Admin: members management

* Members list
* Update role/status actions
* Ban logic blocks access

## Ticket 10 — CSV export

* Admin-only export route
* Redaction rules applied
* Download response

## Ticket 11 — Optional: role gating

* If `requiredRoleIds` present in ORG_CONFIG:

  * Use bot-based check for roles (recommended)
  * Otherwise, skip role gating or use manual admin approval

## Ticket 12 — Smoke tests

* Playwright: login flow stub (can skip OAuth in CI by feature flag)
* Directory access requires acknowledgement

---

# 14) Core Algorithms (pseudocode you can paste to CODEX)

## 14.1 Membership enforcement (server)

```ts
async function ensureOrgAccess({ orgSlug, userId, discordId, accessToken }) {
  const org = await db.org.findUnique({ where: { slug: orgSlug } });
  if (!org) throw notFound();

  // 1) verify guild membership
  const inGuild = await discordUserInGuild(accessToken, org.guildId);
  if (!inGuild) return { org, allowed: false, reason: "NOT_IN_DISCORD" };

  // 2) upsert membership
  const membership = await db.membership.upsert({
    where: { userId_orgId: { userId, orgId: org.id } },
    update: { status: "ACTIVE" },
    create: { userId, orgId: org.id, status: "ACTIVE", role: "MEMBER" },
    include: { profile: true }
  });

  if (membership.status === "BANNED") return { org, allowed: false, reason: "BANNED" };

  return { org, membership, allowed: true };
}
```

## 14.2 Directory redaction mapping

```ts
function redactProfileForViewer(profile, viewer) {
  const isOwner = viewer.membershipId === profile.membershipId;
  const isAdmin = viewer.role === "ADMIN" || viewer.role === "OWNER";

  const canSee = (vis) =>
    vis === "MEMBERS" ? true :
    vis === "ADMINS" ? isAdmin :
    false;

  const getField = (value, vis) => (isOwner || isAdmin && vis !== "PRIVATE" || canSee(vis) || (isOwner && vis==="PRIVATE")) ? value : null;

  return {
    phone: getField(profile.phone, profile.phoneVis),
    emergencyContactName: isOwner || isAdmin ? profile.emergencyContactName : null,
    emergencyContactPhone: isOwner || isAdmin ? profile.emergencyContactPhone : null,
    playaName: getField(profile.playaName, profile.playaNameVis),
    region: getField(profile.region, profile.regionVis),
    bio: getField(profile.bio, profile.bioVis),
  };
}
```

## 14.3 Policy gating check

```ts
async function getMissingAcknowledgements(membershipId, orgId) {
  const activePolicies = await db.policyVersion.findMany({
    where: { orgId, isActive: true },
  });
  const acks = await db.acknowledgement.findMany({ where: { membershipId } });
  const ackSet = new Set(acks.map(a => a.policyId));
  return activePolicies.filter(p => !ackSet.has(p.id));
}
```

---

# 15) Discord API Implementation Notes

## OAuth-only guild membership check (MVP)

* Use stored `access_token` from Auth account record
* Call:

  * `GET https://discord.com/api/users/@me/guilds`
  * Verify `guildId` exists in returned list

This requires the scope `guilds` on the Discord OAuth app.

## Bot-based role checks (recommended for Phase 2)

* Create Discord bot, add to both servers
* Use:

  * `GET /guilds/{guildId}/members/{userId}`
  * Check roles for required role ids
* Needs `GUILD_MEMBERS` privileged intent depending on approach; many servers can still query member endpoint if bot has permission and member is cached, but for reliability you typically enable the intent.

---

# 16) “CODEX Handoff Prompt” (copy/paste)

Use this prompt as your instruction block to CODEX:

```text
Implement the blueprint in this repo as a Next.js 14 App Router TypeScript project with Prisma+Postgres and Auth.js Discord OAuth. Follow the provided Prisma schema exactly. Create multi-tenant org routes at /o/[orgSlug]. Add guild membership checks using OAuth token and /users/@me/guilds with scope guilds. Require Discord membership to access /member and /admin routes. Implement membership upsert on first org visit. Build member profile wizard with privacy controls, resources hub (article/link), policy acknowledgement gate, member directory with redaction mapping, and admin CRUD for members/resources/policies plus CSV export. Seed orgs/policies/resources from content markdown folders using ORG_CONFIG env var. Provide a README with local docker postgres setup, prisma migrate, seed, and dev run steps. Keep code clean and well-typed with Zod validation.
```

---

# 17) README Skeleton (what CODEX should generate)

Minimum commands:

```bash
# 1) start db
docker compose up -d

# 2) install
pnpm i

# 3) env
cp .env.example .env.local
# fill discord client/secret + ORG_CONFIG

# 4) db
pnpm prisma migrate dev
pnpm prisma db seed

# 5) run
pnpm dev
```

---


---

# 18) Implementation Progress (Live)

Status legend: `[x]` complete, `[~]` in progress, `[ ]` not started

- [x] Ticket 1 - Scaffold
  - Created workspace + app structure under `apps/web`
  - Added root setup files (`package.json`, `pnpm-workspace.yaml`, `.env.example`, `docker-compose.yml`, `README.md`)
  - Added base Next.js/Tailwind TypeScript app shell and org route stubs
- [x] Ticket 2 - Prisma schema + seed
  - Added full Prisma schema in `apps/web/prisma/schema.prisma`
  - Fixed `PolicyVersion` <-> `Acknowledgement` relation for valid Prisma schema sync
  - Implemented seed pipeline in `apps/web/prisma/seed.ts` reading `ORG_CONFIG` and markdown content
  - Added starter markdown policy/resource content for `burningman` and `renfaire`
- [~] Ticket 3 - Auth.js Discord login
  - Added Prisma client helper and Auth.js baseline (`apps/web/lib/prisma.ts`, `apps/web/auth.ts`)
  - Added NextAuth route handler at `apps/web/app/api/auth/[...nextauth]/route.ts`
  - Added per-org Discord OAuth provider support (separate Discord applications per org)
  - Added org login screen with separate Member and Admin sign-in options (`/o/[orgSlug]/login`)
  - Remaining: finalize callback hardening, session protection, and membership upsert flow
- [~] Ticket 4 - Org context + guild check
  - Added org config parser (`apps/web/lib/org-config.ts`)
  - Added Discord API helpers (`apps/web/lib/discord.ts`)
  - Added org layout + join page skeleton
  - Added server-side authz helpers and member/admin route guards (`apps/web/lib/authz.ts`)
  - Added org-specific sign-in redirects to enforce correct Discord application per org
  - Added banned route handling and redirects
- [x] Ticket 5 - Member dashboard + profile wizard
  - Added member portal shell/navigation in member layout
  - Implemented member dashboard with profile completion metrics and checklist
  - Added profile wizard page with field-level visibility controls
  - Added server action to validate and upsert profile data (`/member/(portal)/profile/actions.ts`)
- [x] Ticket 6 - Policies + acknowledgement
  - Added member policies page at `/o/[orgSlug]/member/policies`
  - Added acknowledgement server action and persistence to `Acknowledgement`
  - Added member policy gate layout so dashboard/profile routes redirect until active policies are acknowledged
- [x] Ticket 7 - Directory
  - Added gated member directory page at `/o/[orgSlug]/member/directory`
  - Implemented server-side search by display name, playa name, and region
  - Implemented pagination with previous/next navigation
  - Added visibility redaction mapper (`apps/web/lib/directory.ts`) based on viewer role and profile ownership
- [~] Ticket 8 - Resources hub
  - Added admin resources listing page at `/o/[orgSlug]/admin/resources`
- [~] Ticket 9 - Admin members management
  - Added admin overview dashboard with member/resource/policy counts
  - Added admin members listing page at `/o/[orgSlug]/admin/members`
  - Added admin policies listing page at `/o/[orgSlug]/admin/policies`
  - Added shared admin navigation for portal sections
- [ ] Ticket 10 - CSV export
- [ ] Ticket 11 - Optional role gating
- [~] Ticket 12 - Smoke tests
  - Ran build validation (`pnpm --filter web build`) successfully
  - Ran dev runtime smoke check and confirmed `GET /` returns `200`
  - Added and passed Playwright frontend e2e suite (`apps/web/tests/e2e/frontend.spec.ts`)
  - Added member login-to-profile Playwright flow (`apps/web/tests/e2e/member-profile-flow.spec.ts`) with optional interactive Discord auth mode

