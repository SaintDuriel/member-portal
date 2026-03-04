import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { getMembershipContext } from "@/lib/authz";
import { getMissingAcknowledgements } from "@/lib/policies";

export default async function MemberPortalGateLayout({
  children,
  params
}: {
  children: ReactNode;
  params: { orgSlug: string };
}) {
  const { org, membership } = await getMembershipContext(params.orgSlug);
  const missingPolicies = await getMissingAcknowledgements(membership.id, org.id);

  if (missingPolicies.length > 0) {
    redirect(`/o/${params.orgSlug}/member/policies`);
  }

  return <>{children}</>;
}
