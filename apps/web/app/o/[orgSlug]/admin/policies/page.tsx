import { requireOrg } from "@/lib/authz";
import { prisma } from "@/lib/prisma";

export default async function AdminPoliciesPage({ params }: { params: { orgSlug: string } }) {
  const org = await requireOrg(params.orgSlug);

  const policies = await prisma.policyVersion.findMany({
    where: { orgId: org.id },
    orderBy: [{ key: "asc" }, { version: "desc" }],
    take: 200
  });

  return (
    <section style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "0.9rem" }}>
      <h3 style={{ marginTop: 0 }}>Policies</h3>
      <p style={{ color: "#475569", marginTop: 0 }}>Policy keys, versions, and active flags.</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Key</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Version</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Title</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Active</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Created</th>
            </tr>
          </thead>
          <tbody>
            {policies.map((policy) => (
              <tr key={policy.id}>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{policy.key}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{policy.version}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{policy.title}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{policy.isActive ? "Yes" : "No"}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>
                  {policy.createdAt.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
