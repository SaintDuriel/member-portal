import { getOrgFromConfig } from "@/lib/org-config";
import { notFound } from "next/navigation";

export default function JoinDiscordPage({ params }: { params: { orgSlug: string } }) {
  const org = getOrgFromConfig(params.orgSlug);
  if (!org) {
    notFound();
  }

  return (
    <main>
      <h2>Join {org.name} Discord</h2>
      <p>You need Discord membership to access member tools.</p>
      {org.inviteUrl ? <a href={org.inviteUrl}>Join server</a> : <p>No invite link configured.</p>}
    </main>
  );
}