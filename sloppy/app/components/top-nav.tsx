"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const leftLinks = [
  { href: "/analyze", label: "Analyze" },
  { href: "/context", label: "Check" },
];

const rightLinks = [
  { href: "/source-credibility", label: "Eval" },
  { href: "/truth-retrieval", label: "Truth" },
];

export function TopNav() {
  const pathname = usePathname();

  const itemClass = (href: string) => {
    const active = pathname === href || pathname.startsWith(`${href}/`);

    return `rounded-lg border px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition ${
      active
        ? "border-[#9D4EDD]/70 bg-[#2A0A3D]/80 text-[#E0AAFF]"
        : "border-[#2A2A2A] bg-[#121212] text-[#C77DFF] hover:border-[#6A0DAD]/70 hover:bg-[#2A0A3D]/65 hover:text-[#E0AAFF]"
    }`;
  };

  return (
    <header className="sticky top-0 z-50 border-b border-[#2A2A2A] bg-[#0D0D0D]/92 backdrop-blur-xl">
      <nav className="mx-auto flex w-full max-w-6xl items-center justify-center px-4 py-3 md:px-8">
        <div className="grid w-full max-w-3xl grid-cols-[1fr_auto_1fr] items-center gap-2">
          <div className="flex items-center justify-end gap-2">
            {leftLinks.map((link) => (
              <Link key={link.href} className={itemClass(link.href)} href={link.href}>
                {link.label}
              </Link>
            ))}
          </div>

          <Link
            className="rounded-xl border border-[#6A0DAD]/50 bg-[#2A0A3D]/75 px-4 py-1.5 text-sm font-semibold uppercase tracking-[0.18em] text-[#E0AAFF] transition hover:border-[#9D4EDD] hover:bg-[#6A0DAD]/50"
            href="/"
          >
            sloppy
          </Link>

          <div className="flex items-center justify-start gap-2">
            {rightLinks.map((link) => (
              <Link key={link.href} className={itemClass(link.href)} href={link.href}>
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </nav>
    </header>
  );
}
