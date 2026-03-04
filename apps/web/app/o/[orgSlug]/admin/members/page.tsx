import { requireOrg } from "@/lib/authz";
import { prisma } from "@/lib/prisma";

export default async function AdminMembersPage({ params }: { params: { orgSlug: string } }) {
  const org = await requireOrg(params.orgSlug);

  const memberships = await prisma.membership.findMany({
    where: { orgId: org.id },
    include: {
      user: {
        select: {
          id: true,
          displayName: true,
          email: true,
          discordId: true
        }
      }
    },
    orderBy: [{ role: "desc" }, { updatedAt: "desc" }],
    take: 100
  });

  return (
    <section style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "0.9rem" }}>
      <h3 style={{ marginTop: 0 }}>Members</h3>
      <p style={{ color: "#475569", marginTop: 0 }}>Current org membership roster (first 100 records).</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Name</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Email</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Role</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Status</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Discord ID</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Updated</th>
            </tr>
          </thead>
          <tbody>
            {memberships.map((membership) => (
              <tr key={membership.id}>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>
                  {membership.user.displayName ?? "Unnamed User"}
                </td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{membership.user.email ?? "-"}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{membership.role}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{membership.status}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9", fontFamily: "monospace" }}>
                  {membership.user.discordId}
                </td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>
                  {membership.updatedAt.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
