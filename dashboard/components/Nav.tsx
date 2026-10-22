"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  ["/", "Overview"],
  ["/map/", "Map"],
  ["/schools/", "Find a school"],
  ["/districts/", "Districts"],
  ["/kilns/", "Kilns near schools"],
  ["/method/", "Method & accuracy"],
  ["/edit/", "Edit"],
] as const;

export default function Nav() {
  const path = usePathname() || "/";
  const norm = path.endsWith("/") ? path : path + "/";
  return (
    <header style={{ borderBottom: "1px solid var(--line)", background: "var(--panel)" }}>
      <nav className="mx-auto flex max-w-[1120px] flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 text-sm">
        <Link href="/" className="mr-2 text-base font-semibold" style={{ color: "var(--accent)" }}>
          KilnWatch
        </Link>
        {ITEMS.map(([href, label]) => {
          const active = href === "/" ? norm === "/" : norm.startsWith(href);
          return (
            <Link key={href} href={href} aria-current={active ? "page" : undefined}
                  style={{ color: active ? "var(--fg)" : "var(--muted)", fontWeight: active ? 600 : 400 }}>
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
