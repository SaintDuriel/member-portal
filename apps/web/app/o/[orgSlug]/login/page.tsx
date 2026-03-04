import Link from "next/link";
import { notFound } from "next/navigation";
import { getDirectDiscordSignInPath } from "@/lib/authz";
import { getOrgFromConfig } from "@/lib/org-config";

type LoginPageProps = {
  params: { orgSlug: string };
  searchParams?: { mode?: string; callback?: string };
};

function normalizeCallback(orgSlug: string, callback: string | undefined, fallback: string): string {
  if (!callback) {
    return fallback;
  }

  try {
    const decoded = decodeURIComponent(callback);
    if (decoded.startsWith(`/o/${orgSlug}/`)) {
      return decoded;
    }
  } catch {
    return fallback;
  }

  return fallback;
}

export default function OrgLoginPage({ params, searchParams }: LoginPageProps) {
  const org = getOrgFromConfig(params.orgSlug);
  if (!org) {
    notFound();
  }

  const mode = searchParams?.mode === "admin" ? "admin" : "member";
  const callback = searchParams?.callback;

  const memberCallback = mode === "member" ? normalizeCallback(params.orgSlug, callback, `/o/${params.orgSlug}/member`) : `/o/${params.orgSlug}/member`;
  const adminCallback = mode === "admin" ? normalizeCallback(params.orgSlug, callback, `/o/${params.orgSlug}/admin`) : `/o/${params.orgSlug}/admin`;

  const memberSignInPath = getDirectDiscordSignInPath(params.orgSlug, memberCallback);
  const adminSignInPath = getDirectDiscordSignInPath(params.orgSlug, adminCallback);

  return (
    <main style={{ maxWidth: 860, margin: "0 auto", padding: "2rem 1rem" }}>
      <header style={{ marginBottom: "1rem" }}>
        <h1 style={{ marginBottom: "0.35rem" }}>Sign In to {org.name}</h1>
        <p style={{ marginTop: 0, color: "#475569" }}>Use Discord to access member and admin tools.</p>
      </header>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "0.9rem"
        }}
      >
        <article
          style={{
            border: `1px solid ${mode === "member" ? "#0ea5e9" : "#cbd5e1"}`,
            borderRadius: 10,
            background: "#ffffff",
            padding: "1rem"
          }}
        >
          <h2 style={{ marginTop: 0, marginBottom: "0.35rem", fontSize: "1.05rem" }}>Member Login</h2>
          <p style={{ marginTop: 0, color: "#475569" }}>Access profile wizard, policy acknowledgements, and directory.</p>
          <a
            href={memberSignInPath}
            style={{
              display: "inline-block",
              border: "1px solid #0f172a",
              borderRadius: 8,
              padding: "0.5rem 0.85rem",
              background: "#0f172a",
              color: "#f8fafc",
              textDecoration: "none",
              fontWeight: 600
            }}
          >
            Continue as Member
          </a>
        </article>

        <article
          style={{
            border: `1px solid ${mode === "admin" ? "#0ea5e9" : "#cbd5e1"}`,
            borderRadius: 10,
            background: "#ffffff",
            padding: "1rem"
          }}
        >
          <h2 style={{ marginTop: 0, marginBottom: "0.35rem", fontSize: "1.05rem" }}>Admin Login</h2>
          <p style={{ marginTop: 0, color: "#475569" }}>Access member management, resources, policies, and exports.</p>
          <a
            href={adminSignInPath}
            style={{
              display: "inline-block",
              border: "1px solid #0f172a",
              borderRadius: 8,
              padding: "0.5rem 0.85rem",
              background: "#0f172a",
              color: "#f8fafc",
              textDecoration: "none",
              fontWeight: 600
            }}
          >
            Continue as Admin
          </a>
        </article>
      </section>

      <p style={{ marginTop: "1rem", color: "#475569" }}>
        Need server access first?{" "}
        <Link href={`/o/${params.orgSlug}/join`} style={{ textDecoration: "underline" }}>
          Join Discord
        </Link>
        .
      </p>
    </main>
  );
}
