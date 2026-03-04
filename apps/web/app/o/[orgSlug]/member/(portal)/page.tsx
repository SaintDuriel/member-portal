import Link from "next/link";
import { getMembershipContext } from "@/lib/authz";
import { prisma } from "@/lib/prisma";

export default async function MemberLandingPage({ params }: { params: { orgSlug: string } }) {
  const { membership } = await getMembershipContext(params.orgSlug);

  const profile = await prisma.profile.findUnique({
    where: { membershipId: membership.id }
  });

  const checklist = [
    { label: "Phone", complete: Boolean(profile?.phone) },
    { label: "Emergency Contact Name", complete: Boolean(profile?.emergencyContactName) },
    { label: "Emergency Contact Phone", complete: Boolean(profile?.emergencyContactPhone) },
    { label: "Playa Name", complete: Boolean(profile?.playaName) },
    { label: "Region", complete: Boolean(profile?.region) },
    { label: "Bio", complete: Boolean(profile?.bio) }
  ];

  const completedCount = checklist.filter((item) => item.complete).length;
  const completionPercent = Math.round((completedCount / checklist.length) * 100);

  return (
    <section style={{ display: "grid", gap: "1rem" }}>
      <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "1rem" }}>
        <h3 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Profile Completion</h3>
        <p style={{ marginTop: 0, color: "#334155" }}>
          {completedCount} of {checklist.length} fields complete ({completionPercent}%)
        </p>
        <div
          style={{
            width: "100%",
            height: 10,
            background: "#e2e8f0",
            borderRadius: 999,
            overflow: "hidden",
            marginBottom: "0.75rem"
          }}
        >
          <div
            style={{
              width: `${completionPercent}%`,
              height: "100%",
              background: completionPercent === 100 ? "#16a34a" : "#0ea5e9"
            }}
          />
        </div>
        <Link href={`/o/${params.orgSlug}/member/profile`} style={{ color: "#0f172a", textDecoration: "underline" }}>
          Continue profile wizard
        </Link>
      </article>

      <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "1rem" }}>
        <h3 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Checklist</h3>
        <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "#334155" }}>
          {checklist.map((item) => (
            <li key={item.label} style={{ marginBottom: "0.3rem" }}>
              {item.complete ? "Complete" : "Missing"}: {item.label}
            </li>
          ))}
        </ul>
      </article>

      <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "1rem" }}>
        <h3 style={{ marginTop: 0, marginBottom: "0.5rem" }}>Next Steps</h3>
        <p style={{ marginTop: 0, color: "#475569" }}>
          Finish your profile details and visibility settings before directory and policy-based features are enabled.
        </p>
      </article>
    </section>
  );
}
