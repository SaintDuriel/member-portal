"use server";

import { Visibility } from "@prisma/client";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";
import { requireMemberAccess } from "@/lib/authz";
import { prisma } from "@/lib/prisma";

const visibilitySchema = z.nativeEnum(Visibility);

const profileSchema = z.object({
  phone: z.string().max(80).optional(),
  phoneVis: visibilitySchema,
  emergencyContactName: z.string().max(120).optional(),
  emergencyContactNameVis: visibilitySchema,
  emergencyContactPhone: z.string().max(80).optional(),
  emergencyContactPhoneVis: visibilitySchema,
  playaName: z.string().max(120).optional(),
  playaNameVis: visibilitySchema,
  region: z.string().max(120).optional(),
  regionVis: visibilitySchema,
  bio: z.string().max(1200).optional(),
  bioVis: visibilitySchema
});

function normalizeOptional(value: FormDataEntryValue | null): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export async function upsertProfile(orgSlug: string, formData: FormData): Promise<void> {
  const access = await requireMemberAccess(orgSlug, `/o/${orgSlug}/member/profile`);

  const parsed = profileSchema.safeParse({
    phone: normalizeOptional(formData.get("phone")),
    phoneVis: formData.get("phoneVis"),
    emergencyContactName: normalizeOptional(formData.get("emergencyContactName")),
    emergencyContactNameVis: formData.get("emergencyContactNameVis"),
    emergencyContactPhone: normalizeOptional(formData.get("emergencyContactPhone")),
    emergencyContactPhoneVis: formData.get("emergencyContactPhoneVis"),
    playaName: normalizeOptional(formData.get("playaName")),
    playaNameVis: formData.get("playaNameVis"),
    region: normalizeOptional(formData.get("region")),
    regionVis: formData.get("regionVis"),
    bio: normalizeOptional(formData.get("bio")),
    bioVis: formData.get("bioVis")
  });

  if (!parsed.success) {
    redirect(`/o/${orgSlug}/member/profile?error=invalid`);
  }

  await prisma.profile.upsert({
    where: { membershipId: access.membership.id },
    update: parsed.data,
    create: {
      membershipId: access.membership.id,
      ...parsed.data
    }
  });

  revalidatePath(`/o/${orgSlug}/member`);
  revalidatePath(`/o/${orgSlug}/member/profile`);
  redirect(`/o/${orgSlug}/member/profile?saved=1`);
}
