"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface AdminNavProps {
  orgSlug: string;
}

const links = [
  { key: "overview", label: "Overview", path: "" },
  { key: "members", label: "Members", path: "members" },
  { key: "resources", label: "Resources", path: "resources" },
  { key: "policies", label: "Policies", path: "policies" }
];

function isActive(currentPath: string, href: string): boolean {
  if (href.endsWith("/admin")) {
    return currentPath === href;
  }
  return currentPath === href || currentPath.startsWith(`${href}/`);
}

export function AdminNav({ orgSlug }: AdminNavProps) {
  const pathname = usePathname();

  return (
    <nav style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1.25rem" }}>
      {links.map((link) => {
        const href = link.path ? `/o/${orgSlug}/admin/${link.path}` : `/o/${orgSlug}/admin`;
        const active = isActive(pathname, href);

        return (
          <Link
            key={link.key}
            href={href}
            style={{
              padding: "0.45rem 0.8rem",
              borderRadius: 8,
              border: `1px solid ${active ? "#0f172a" : "#cbd5e1"}`,
              background: active ? "#0f172a" : "#ffffff",
              color: active ? "#f8fafc" : "#0f172a",
              fontSize: "0.9rem"
            }}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
