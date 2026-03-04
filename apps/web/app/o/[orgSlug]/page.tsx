import { notFound } from "next/navigation";

const supportedOrgs = new Set(["burningman", "renfaire"]);

export default function OrgHomePage({ params }: { params: { orgSlug: string } }) {
  if (!supportedOrgs.has(params.orgSlug)) {
    notFound();
  }

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: "2rem 1rem" }}>
      <h1>Organization: {params.orgSlug}</h1>
      <p>Member and admin areas will be added in subsequent tickets.</p>
      <ul>
        <li>
          <a href={`/o/${params.orgSlug}/member`}>Member area</a>
        </li>
        <li>
          <a href={`/o/${params.orgSlug}/admin`}>Admin area</a>
        </li>
      </ul>
    </main>
  );
}