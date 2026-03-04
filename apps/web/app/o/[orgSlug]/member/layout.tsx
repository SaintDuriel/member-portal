import type { ReactNode } from "react";
import { MemberNav } from "@/components/member-nav";
import { requireMemberAccess } from "@/lib/authz";

export default async function MemberLayout({
  children,
  params
}: {
  children: ReactNode;
  params: { orgSlug: string };
}) {
  const access = await requireMemberAccess(params.orgSlug, `/o/${params.orgSlug}/member`);

  return (
    <main style={{ maxWidth: 1000, margin: "0 auto" }}>
      <header style={{ marginBottom: "0.5rem" }}>
        <h2 style={{ marginBottom: "0.25rem" }}>Member Portal</h2>
        <p style={{ marginTop: 0, color: "#475569" }}>Welcome to {access.org.name}.</p>
      </header>
      <MemberNav orgSlug={params.orgSlug} />
      {children}
    </main>
  );
}
