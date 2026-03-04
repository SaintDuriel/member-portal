import { Visibility } from "@prisma/client";
import { getMembershipContext } from "@/lib/authz";
import { prisma } from "@/lib/prisma";
import { upsertProfile } from "./actions";

type ProfilePageProps = {
  params: { orgSlug: string };
  searchParams?: { saved?: string; error?: string };
};

function sectionStyle() {
  return { background: "#ffffff", border: "1px solid #dbeafe", borderRadius: 10, padding: "1rem", marginBottom: "1rem" };
}

const visibilityOptions: Array<{ value: Visibility; label: string }> = [
  { value: "PRIVATE", label: "Private (only me)" },
  { value: "MEMBERS", label: "Members" },
  { value: "ADMINS", label: "Admins" }
];

function VisibilitySelect({ name, defaultValue }: { name: string; defaultValue: Visibility }) {
  return (
    <select name={name} defaultValue={defaultValue} style={{ padding: "0.4rem", borderRadius: 6, border: "1px solid #cbd5e1" }}>
      {visibilityOptions.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export default async function MemberProfilePage({ params, searchParams }: ProfilePageProps) {
  const { membership } = await getMembershipContext(params.orgSlug);

  const profile = await prisma.profile.findUnique({
    where: { membershipId: membership.id }
  });

  const action = upsertProfile.bind(null, params.orgSlug);
  const saveSuccess = searchParams?.saved === "1";
  const saveError = searchParams?.error === "invalid";

  return (
    <section>
      <header style={{ marginBottom: "1rem" }}>
        <h3 style={{ marginBottom: "0.35rem" }}>Profile Wizard</h3>
        <p style={{ marginTop: 0, color: "#475569" }}>
          Complete your profile details and choose visibility per field.
        </p>
      </header>

      {saveSuccess ? (
        <p style={{ background: "#dcfce7", border: "1px solid #86efac", padding: "0.65rem", borderRadius: 8 }}>
          Profile saved.
        </p>
      ) : null}
      {saveError ? (
        <p style={{ background: "#fee2e2", border: "1px solid #fca5a5", padding: "0.65rem", borderRadius: 8 }}>
          Please correct the submitted values and try again.
        </p>
      ) : null}

      <form action={action}>
        <div style={sectionStyle()}>
          <h4 style={{ marginTop: 0 }}>Basic Contact</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "0.75rem", alignItems: "end" }}>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <span>Phone</span>
              <input
                type="text"
                name="phone"
                defaultValue={profile?.phone ?? ""}
                style={{ padding: "0.45rem", borderRadius: 6, border: "1px solid #cbd5e1" }}
              />
            </label>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <span>Phone Visibility</span>
              <VisibilitySelect name="phoneVis" defaultValue={profile?.phoneVis ?? "PRIVATE"} />
            </label>
          </div>
        </div>

        <div style={sectionStyle()}>
          <h4 style={{ marginTop: 0 }}>Emergency Contact</h4>
          <div style={{ display: "grid", gap: "0.8rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "0.75rem", alignItems: "end" }}>
              <label style={{ display: "grid", gap: "0.35rem" }}>
                <span>Emergency Contact Name</span>
                <input
                  type="text"
                  name="emergencyContactName"
                  defaultValue={profile?.emergencyContactName ?? ""}
                  style={{ padding: "0.45rem", borderRadius: 6, border: "1px solid #cbd5e1" }}
                />
              </label>
              <label style={{ display: "grid", gap: "0.35rem" }}>
                <span>Name Visibility</span>
                <VisibilitySelect
                  name="emergencyContactNameVis"
                  defaultValue={profile?.emergencyContactNameVis ?? "ADMINS"}
                />
              </label>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "0.75rem", alignItems: "end" }}>
              <label style={{ display: "grid", gap: "0.35rem" }}>
                <span>Emergency Contact Phone</span>
                <input
                  type="text"
                  name="emergencyContactPhone"
                  defaultValue={profile?.emergencyContactPhone ?? ""}
                  style={{ padding: "0.45rem", borderRadius: 6, border: "1px solid #cbd5e1" }}
                />
              </label>
              <label style={{ display: "grid", gap: "0.35rem" }}>
                <span>Phone Visibility</span>
                <VisibilitySelect
                  name="emergencyContactPhoneVis"
                  defaultValue={profile?.emergencyContactPhoneVis ?? "ADMINS"}
                />
              </label>
            </div>
          </div>
        </div>

        <div style={sectionStyle()}>
          <h4 style={{ marginTop: 0 }}>Identity and Region</h4>
          <div style={{ display: "grid", gap: "0.8rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "0.75rem", alignItems: "end" }}>
              <label style={{ display: "grid", gap: "0.35rem" }}>
                <span>Playa Name</span>
                <input
                  type="text"
                  name="playaName"
                  defaultValue={profile?.playaName ?? ""}
                  style={{ padding: "0.45rem", borderRadius: 6, border: "1px solid #cbd5e1" }}
                />
              </label>
              <label style={{ display: "grid", gap: "0.35rem" }}>
                <span>Playa Name Visibility</span>
                <VisibilitySelect name="playaNameVis" defaultValue={profile?.playaNameVis ?? "MEMBERS"} />
              </label>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "0.75rem", alignItems: "end" }}>
              <label style={{ display: "grid", gap: "0.35rem" }}>
                <span>Region</span>
                <input
                  type="text"
                  name="region"
                  defaultValue={profile?.region ?? ""}
                  style={{ padding: "0.45rem", borderRadius: 6, border: "1px solid #cbd5e1" }}
                />
              </label>
              <label style={{ display: "grid", gap: "0.35rem" }}>
                <span>Region Visibility</span>
                <VisibilitySelect name="regionVis" defaultValue={profile?.regionVis ?? "MEMBERS"} />
              </label>
            </div>
          </div>
        </div>

        <div style={sectionStyle()}>
          <h4 style={{ marginTop: 0 }}>Bio</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 220px", gap: "0.75rem", alignItems: "end" }}>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <span>Short Bio</span>
              <textarea
                name="bio"
                defaultValue={profile?.bio ?? ""}
                rows={5}
                style={{ padding: "0.45rem", borderRadius: 6, border: "1px solid #cbd5e1", resize: "vertical" }}
              />
            </label>
            <label style={{ display: "grid", gap: "0.35rem" }}>
              <span>Bio Visibility</span>
              <VisibilitySelect name="bioVis" defaultValue={profile?.bioVis ?? "MEMBERS"} />
            </label>
          </div>
        </div>

        <button
          type="submit"
          style={{
            padding: "0.55rem 0.95rem",
            borderRadius: 8,
            border: "1px solid #0f172a",
            background: "#0f172a",
            color: "#f8fafc",
            fontWeight: 600,
            cursor: "pointer"
          }}
        >
          Save Profile
        </button>
      </form>
    </section>
  );
}
