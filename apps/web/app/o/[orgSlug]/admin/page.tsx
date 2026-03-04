import { prisma } from "@/lib/prisma";
import { requireOrg } from "@/lib/authz";

export default async function AdminLandingPage({ params }: { params: { orgSlug: string } }) {
  const org = await requireOrg(params.orgSlug);

  const [memberStats, resourceCount, activePolicyCount] = await Promise.all([
    prisma.membership.groupBy({
      by: ["status"],
      where: { orgId: org.id },
      _count: { _all: true }
    }),
    prisma.resource.count({ where: { orgId: org.id } }),
    prisma.policyVersion.count({ where: { orgId: org.id, isActive: true } })
  ]);

  const statusCounts = memberStats.reduce<Record<string, number>>((acc, item) => {
    acc[item.status] = item._count._all;
    return acc;
  }, {});

  const totalMembers = Object.values(statusCounts).reduce((sum, count) => sum + count, 0);

  return (
    <section style={{ display: "grid", gap: "1rem" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "0.75rem"
        }}
      >
        <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "0.9rem" }}>
          <h3 style={{ margin: "0 0 0.4rem 0", fontSize: "0.95rem", color: "#334155" }}>Total Members</h3>
          <strong style={{ fontSize: "1.25rem" }}>{totalMembers}</strong>
        </article>
        <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "0.9rem" }}>
          <h3 style={{ margin: "0 0 0.4rem 0", fontSize: "0.95rem", color: "#334155" }}>Active</h3>
          <strong style={{ fontSize: "1.25rem" }}>{statusCounts.ACTIVE ?? 0}</strong>
        </article>
        <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "0.9rem" }}>
          <h3 style={{ margin: "0 0 0.4rem 0", fontSize: "0.95rem", color: "#334155" }}>Banned</h3>
          <strong style={{ fontSize: "1.25rem" }}>{statusCounts.BANNED ?? 0}</strong>
        </article>
        <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "0.9rem" }}>
          <h3 style={{ margin: "0 0 0.4rem 0", fontSize: "0.95rem", color: "#334155" }}>Resources</h3>
          <strong style={{ fontSize: "1.25rem" }}>{resourceCount}</strong>
        </article>
        <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "0.9rem" }}>
          <h3 style={{ margin: "0 0 0.4rem 0", fontSize: "0.95rem", color: "#334155" }}>Active Policies</h3>
          <strong style={{ fontSize: "1.25rem" }}>{activePolicyCount}</strong>
        </article>
      </div>
      <p style={{ color: "#475569", marginTop: 0 }}>
        Use the tabs above to manage members, content, and policy versions.
      </p>
    </section>
  );
}
