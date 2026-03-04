"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireMemberAccess } from "@/lib/authz";
import { prisma } from "@/lib/prisma";

export async function acknowledgePolicy(orgSlug: string, policyId: string): Promise<void> {
  const access = await requireMemberAccess(orgSlug, `/o/${orgSlug}/member/policies`);

  const policy = await prisma.policyVersion.findFirst({
    where: {
      id: policyId,
      orgId: access.org.id,
      isActive: true
    }
  });

  if (!policy) {
    redirect(`/o/${orgSlug}/member/policies?error=policy_not_found`);
  }

  await prisma.acknowledgement.upsert({
    where: {
      membershipId_policyId: {
        membershipId: access.membership.id,
        policyId
      }
    },
    update: {},
    create: {
      membershipId: access.membership.id,
      policyId
    }
  });

  revalidatePath(`/o/${orgSlug}/member`);
  revalidatePath(`/o/${orgSlug}/member/policies`);
  redirect(`/o/${orgSlug}/member/policies?saved=1`);
}
