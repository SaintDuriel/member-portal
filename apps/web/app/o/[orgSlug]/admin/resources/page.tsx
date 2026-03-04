import { requireOrg } from "@/lib/authz";
import { prisma } from "@/lib/prisma";

export default async function AdminResourcesPage({ params }: { params: { orgSlug: string } }) {
  const org = await requireOrg(params.orgSlug);

  const resources = await prisma.resource.findMany({
    where: { orgId: org.id },
    orderBy: { updatedAt: "desc" },
    take: 100
  });

  return (
    <section style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "0.9rem" }}>
      <h3 style={{ marginTop: 0 }}>Resources</h3>
      <p style={{ color: "#475569", marginTop: 0 }}>Content records and visibility settings.</p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.92rem" }}>
          <thead>
            <tr style={{ background: "#f8fafc", textAlign: "left" }}>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Title</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Type</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Category</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Public</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Tags</th>
              <th style={{ padding: "0.5rem", borderBottom: "1px solid #e2e8f0" }}>Updated</th>
            </tr>
          </thead>
          <tbody>
            {resources.map((resource) => (
              <tr key={resource.id}>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{resource.title}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{resource.type}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{resource.category ?? "-"}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>{resource.isPublic ? "Yes" : "No"}</td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>
                  {resource.tags.length > 0 ? resource.tags.join(", ") : "-"}
                </td>
                <td style={{ padding: "0.5rem", borderBottom: "1px solid #f1f5f9" }}>
                  {resource.updatedAt.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
