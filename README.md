# MemberPortal (Guild Sites)

## Prerequisites
- Node.js 20+
- pnpm 9+
- Docker Desktop (or Docker Engine + Compose)
- Discord application credentials for OAuth

## Local setup
1. Start Postgres.
   ```bash
   docker compose up -d
   ```
2. Install dependencies.
   ```bash
   pnpm i
   ```
3. Create local env file.
   ```bash
   cp .env.example .env.local
   ```
   Fill `DISCORD_CLIENT_ID_<ORG>` / `DISCORD_CLIENT_SECRET_<ORG>` for each org slug in `ORG_CONFIG`.
4. Run schema migration and seed.
   ```bash
   pnpm db:migrate
   pnpm db:seed
   ```
5. Start the app.
   ```bash
   pnpm dev
   ```

## Notes
- OAuth membership checks require Discord OAuth scope `guilds`.
- Configure one Discord app per org and add each app callback URL:
  - `http://localhost:3000/api/auth/callback/discord-burningman`
  - `http://localhost:3000/api/auth/callback/discord-renfaire`
- Optional role-gating uses `DISCORD_BOT_TOKEN` and Discord member API.
