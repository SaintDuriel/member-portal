import { requireMemberAccess } from "@/lib/authz";
import { getPolicyAcknowledgementState } from "@/lib/policies";
import { acknowledgePolicy } from "./actions";

type PoliciesPageProps = {
  params: { orgSlug: string };
  searchParams?: { saved?: string; error?: string };
};

export default async function MemberPoliciesPage({ params, searchParams }: PoliciesPageProps) {
  const access = await requireMemberAccess(params.orgSlug, `/o/${params.orgSlug}/member/policies`);

  const state = await getPolicyAcknowledgementState(access.membership.id, access.org.id);
  const missingCount = state.filter((item) => !item.acknowledged).length;
  const completedCount = state.length - missingCount;
  const total = state.length;

  return (
    <section style={{ display: "grid", gap: "1rem" }}>
      <header style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "1rem" }}>
        <h3 style={{ marginTop: 0, marginBottom: "0.45rem" }}>Policies and Acknowledgements</h3>
        <p style={{ marginTop: 0, color: "#475569" }}>
          {completedCount} of {total} active policies acknowledged.
        </p>
        {missingCount > 0 ? (
          <p style={{ marginBottom: 0, color: "#9a3412" }}>
            You must acknowledge all active policies before accessing dashboard tools.
          </p>
        ) : (
          <p style={{ marginBottom: 0, color: "#166534" }}>All active policies are acknowledged.</p>
        )}
      </header>

      {searchParams?.saved === "1" ? (
        <p style={{ background: "#dcfce7", border: "1px solid #86efac", padding: "0.65rem", borderRadius: 8 }}>
          Acknowledgement saved.
        </p>
      ) : null}
      {searchParams?.error === "policy_not_found" ? (
        <p style={{ background: "#fee2e2", border: "1px solid #fca5a5", padding: "0.65rem", borderRadius: 8 }}>
          The selected policy could not be acknowledged.
        </p>
      ) : null}

      {state.map((item) => {
        const action = acknowledgePolicy.bind(null, params.orgSlug, item.policy.id);

        return (
          <article
            key={item.policy.id}
            style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "1rem" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
              <div>
                <h4 style={{ marginTop: 0, marginBottom: "0.35rem" }}>
                  {item.policy.title} ({item.policy.key} v{item.policy.version})
                </h4>
                <p style={{ marginTop: 0, color: "#475569" }}>
                  Status: {item.acknowledged ? "Acknowledged" : "Pending acknowledgement"}
                </p>
              </div>
              {item.acknowledged ? (
                <span
                  style={{
                    alignSelf: "flex-start",
                    background: "#dcfce7",
                    border: "1px solid #86efac",
                    borderRadius: 999,
                    padding: "0.2rem 0.55rem"
                  }}
                >
                  Acknowledged
                </span>
              ) : (
                <form action={action}>
                  <button
                    type="submit"
                    style={{
                      alignSelf: "flex-start",
                      padding: "0.5rem 0.9rem",
                      borderRadius: 8,
                      border: "1px solid #0f172a",
                      background: "#0f172a",
                      color: "#f8fafc",
                      fontWeight: 600,
                      cursor: "pointer"
                    }}
                  >
                    Acknowledge
                  </button>
                </form>
              )}
            </div>
            <div
              style={{
                marginTop: "0.75rem",
                padding: "0.75rem",
                background: "#f8fafc",
                borderRadius: 8,
                border: "1px solid #e2e8f0",
                whiteSpace: "pre-wrap",
                lineHeight: 1.45
              }}
            >
              {item.policy.contentMd}
            </div>
          </article>
        );
      })}
    </section>
  );
}
