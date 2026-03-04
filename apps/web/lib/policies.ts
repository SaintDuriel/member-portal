import { prisma } from "@/lib/prisma";

export async function getPolicyAcknowledgementState(membershipId: string, orgId: string) {
  const [activePolicies, acknowledgements] = await Promise.all([
    prisma.policyVersion.findMany({
      where: { orgId, isActive: true },
      orderBy: [{ key: "asc" }, { version: "desc" }]
    }),
    prisma.acknowledgement.findMany({
      where: {
        membershipId,
        policy: {
          orgId
        }
      }
    })
  ]);

  const ackMap = new Map(acknowledgements.map((ack) => [ack.policyId, ack]));

  return activePolicies.map((policy) => {
    const ack = ackMap.get(policy.id);
    return {
      policy,
      acknowledged: Boolean(ack),
      acknowledgedAt: ack?.acknowledgedAt ?? null
    };
  });
}

export async function getMissingAcknowledgements(membershipId: string, orgId: string) {
  const policyState = await getPolicyAcknowledgementState(membershipId, orgId);
  return policyState.filter((item) => !item.acknowledged).map((item) => item.policy);
}
