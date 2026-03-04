import type { ReactNode } from "react";
import { requireAdmin, requireMemberAccess } from "@/lib/authz";
import { AdminNav } from "@/components/admin-nav";

export default async function AdminLayout({
  children,
  params
}: {
  children: ReactNode;
  params: { orgSlug: string };
}) {
  const access = await requireMemberAccess(params.orgSlug, `/o/${params.orgSlug}/admin`);

  requireAdmin(access.membership.role, params.orgSlug);

  return (
    <main style={{ maxWidth: 1000, margin: "0 auto" }}>
      <header style={{ marginBottom: "0.5rem" }}>
        <h2 style={{ marginBottom: "0.25rem" }}>Admin Portal</h2>
        <p style={{ marginTop: 0, color: "#475569" }}>Manage members, resources, and policies for {access.org.name}.</p>
      </header>
      <AdminNav orgSlug={params.orgSlug} />
      {children}
    </main>
  );
}
