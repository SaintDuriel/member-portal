import Link from "next/link";
import { Prisma } from "@prisma/client";
import { getMembershipContext } from "@/lib/authz";
import { redactProfileForViewer } from "@/lib/directory";
import { prisma } from "@/lib/prisma";

const PAGE_SIZE = 20;

type DirectoryPageProps = {
  params: { orgSlug: string };
  searchParams?: { q?: string | string[]; page?: string | string[] };
};

function getParamValue(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }
  return value ?? "";
}

function buildDirectoryHref(orgSlug: string, query: string, page: number): string {
  const params = new URLSearchParams();
  if (query.trim().length > 0) {
    params.set("q", query.trim());
  }
  if (page > 1) {
    params.set("page", String(page));
  }

  const queryString = params.toString();
  return queryString.length > 0 ? `/o/${orgSlug}/member/directory?${queryString}` : `/o/${orgSlug}/member/directory`;
}

export default async function MemberDirectoryPage({ params, searchParams }: DirectoryPageProps) {
  const { org, membership } = await getMembershipContext(params.orgSlug);

  const query = getParamValue(searchParams?.q).trim();
  const requestedPage = Number.parseInt(getParamValue(searchParams?.page), 10);

  const where: Prisma.MembershipWhereInput = {
    orgId: org.id,
    status: "ACTIVE"
  };

  if (query.length > 0) {
    where.OR = [
      { user: { displayName: { contains: query, mode: "insensitive" } } },
      { profile: { playaName: { contains: query, mode: "insensitive" } } },
      { profile: { region: { contains: query, mode: "insensitive" } } }
    ];
  }

  const totalCount = await prisma.membership.count({ where });
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const page = Number.isFinite(requestedPage) && requestedPage > 0 ? Math.min(requestedPage, totalPages) : 1;
  const skip = (page - 1) * PAGE_SIZE;

  const memberships = await prisma.membership.findMany({
    where,
    include: {
      user: {
        select: {
          displayName: true,
          avatarUrl: true
        }
      },
      profile: true
    },
    orderBy: [{ role: "desc" }, { updatedAt: "desc" }],
    skip,
    take: PAGE_SIZE
  });

  const viewer = {
    membershipId: membership.id,
    role: membership.role
  };

  return (
    <section style={{ display: "grid", gap: "1rem" }}>
      <header style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "1rem" }}>
        <h3 style={{ marginTop: 0, marginBottom: "0.4rem" }}>Member Directory</h3>
        <p style={{ marginTop: 0, color: "#475569", marginBottom: "0.75rem" }}>
          Search by display name, playa name, or region. Visibility controls are enforced per field.
        </p>
        <form method="get" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          <input
            type="text"
            name="q"
            defaultValue={query}
            placeholder="Search members"
            style={{ minWidth: 240, padding: "0.5rem", borderRadius: 6, border: "1px solid #cbd5e1" }}
          />
          <button
            type="submit"
            style={{
              padding: "0.5rem 0.85rem",
              borderRadius: 8,
              border: "1px solid #0f172a",
              background: "#0f172a",
              color: "#f8fafc",
              cursor: "pointer"
            }}
          >
            Search
          </button>
          {query.length > 0 ? (
            <Link
              href={`/o/${params.orgSlug}/member/directory`}
              style={{
                padding: "0.5rem 0.85rem",
                borderRadius: 8,
                border: "1px solid #cbd5e1",
                color: "#0f172a",
                textDecoration: "none"
              }}
            >
              Clear
            </Link>
          ) : null}
        </form>
      </header>

      <article style={{ background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "1rem" }}>
        <p style={{ marginTop: 0, color: "#475569" }}>
          Showing {memberships.length} of {totalCount} result{totalCount === 1 ? "" : "s"}.
        </p>

        <div style={{ display: "grid", gap: "0.75rem" }}>
          {memberships.map((item) => {
            const profile = redactProfileForViewer(item.profile, item.id, viewer);
            const isYou = item.id === membership.id;
            const name = item.user.displayName ?? "Unnamed Member";

            return (
              <div
                key={item.id}
                style={{
                  border: "1px solid #e2e8f0",
                  borderRadius: 8,
                  padding: "0.75rem",
                  background: "#f8fafc"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
                  <strong>{name}</strong>
                  <span style={{ color: "#475569" }}>
                    {item.role}
                    {isYou ? " - You" : ""}
                  </span>
                </div>
                <p style={{ marginTop: "0.4rem", marginBottom: 0, color: "#334155" }}>
                  Playa Name: {profile.playaName ?? "Hidden"}
                </p>
                <p style={{ marginTop: "0.25rem", marginBottom: 0, color: "#334155" }}>
                  Region: {profile.region ?? "Hidden"}
                </p>
                <p style={{ marginTop: "0.25rem", marginBottom: 0, color: "#334155" }}>
                  Phone: {profile.phone ?? "Hidden"}
                </p>
                <p style={{ marginTop: "0.25rem", marginBottom: 0, color: "#334155" }}>
                  Emergency Contact Name: {profile.emergencyContactName ?? "Hidden"}
                </p>
                <p style={{ marginTop: "0.25rem", marginBottom: 0, color: "#334155" }}>
                  Emergency Contact Phone: {profile.emergencyContactPhone ?? "Hidden"}
                </p>
                <p style={{ marginTop: "0.25rem", marginBottom: 0, color: "#334155" }}>
                  Bio: {profile.bio ?? "Hidden"}
                </p>
              </div>
            );
          })}
        </div>

        {totalCount === 0 ? <p style={{ marginTop: "0.75rem", color: "#475569" }}>No members matched this search.</p> : null}
      </article>

      <footer style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
        {page > 1 ? (
          <Link
            href={buildDirectoryHref(params.orgSlug, query, page - 1)}
            style={{ border: "1px solid #cbd5e1", borderRadius: 8, padding: "0.45rem 0.8rem", textDecoration: "none" }}
          >
            Previous
          </Link>
        ) : (
          <span style={{ border: "1px solid #e2e8f0", color: "#94a3b8", borderRadius: 8, padding: "0.45rem 0.8rem" }}>
            Previous
          </span>
        )}
        <span style={{ color: "#475569" }}>
          Page {page} of {totalPages}
        </span>
        {page < totalPages ? (
          <Link
            href={buildDirectoryHref(params.orgSlug, query, page + 1)}
            style={{ border: "1px solid #cbd5e1", borderRadius: 8, padding: "0.45rem 0.8rem", textDecoration: "none" }}
          >
            Next
          </Link>
        ) : (
          <span style={{ border: "1px solid #e2e8f0", color: "#94a3b8", borderRadius: 8, padding: "0.45rem 0.8rem" }}>
            Next
          </span>
        )}
      </footer>
    </section>
  );
}
