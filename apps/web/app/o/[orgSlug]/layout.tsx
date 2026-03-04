import type { ReactNode } from "react";
import { notFound } from "next/navigation";
import { getOrgFromConfig } from "@/lib/org-config";

export default function OrgLayout({
  children,
  params
}: {
  children: ReactNode;
  params: { orgSlug: string };
}) {
  const org = getOrgFromConfig(params.orgSlug);
  if (!org) {
    notFound();
  }

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ margin: 0 }}>{org.name}</h1>
        <small>/{org.slug}</small>
      </header>
      {children}
    </div>
  );
}