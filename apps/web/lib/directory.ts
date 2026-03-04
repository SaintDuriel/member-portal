import type { OrgRole, Profile, Visibility } from "@prisma/client";

export interface DirectoryViewer {
  membershipId: string;
  role: OrgRole;
}

export interface RedactedProfile {
  phone: string | null;
  emergencyContactName: string | null;
  emergencyContactPhone: string | null;
  playaName: string | null;
  region: string | null;
  bio: string | null;
}

function isAdminRole(role: OrgRole): boolean {
  return role === "ADMIN" || role === "OWNER";
}

function canSeeVisibility(visibility: Visibility, viewer: DirectoryViewer, isOwner: boolean): boolean {
  if (isOwner) {
    return true;
  }

  if (visibility === "PRIVATE") {
    return false;
  }

  if (visibility === "MEMBERS") {
    return true;
  }

  if (visibility === "ADMINS") {
    return isAdminRole(viewer.role);
  }

  return false;
}

export function redactProfileForViewer(
  profile: Profile | null,
  targetMembershipId: string,
  viewer: DirectoryViewer
): RedactedProfile {
  if (!profile) {
    return {
      phone: null,
      emergencyContactName: null,
      emergencyContactPhone: null,
      playaName: null,
      region: null,
      bio: null
    };
  }

  const isOwner = viewer.membershipId === targetMembershipId;

  const readField = (value: string | null, visibility: Visibility): string | null => {
    if (!value) {
      return null;
    }

    return canSeeVisibility(visibility, viewer, isOwner) ? value : null;
  };

  return {
    phone: readField(profile.phone, profile.phoneVis),
    emergencyContactName: readField(profile.emergencyContactName, profile.emergencyContactNameVis),
    emergencyContactPhone: readField(profile.emergencyContactPhone, profile.emergencyContactPhoneVis),
    playaName: readField(profile.playaName, profile.playaNameVis),
    region: readField(profile.region, profile.regionVis),
    bio: readField(profile.bio, profile.bioVis)
  };
}
