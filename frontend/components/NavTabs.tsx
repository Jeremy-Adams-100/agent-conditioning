"use client";

import Link from "next/link";

interface NavTabsProps {
  current: "explore" | "interact" | "share";
}

export default function NavTabs({ current }: NavTabsProps) {
  const tabs = [
    { key: "explore", label: "Explore", href: "/explore" },
    { key: "interact", label: "Interact", href: "/interact" },
    { key: "share", label: "Share", href: "/share" },
  ] as const;

  return (
    <nav className="flex gap-1">
      {tabs.map((tab) => (
        <Link
          key={tab.key}
          href={tab.href}
          className={`px-2 py-1 text-xs font-medium transition-colors ${
            current === tab.key
              ? "text-gray-100 border-b-2 border-gray-100"
              : "text-gray-400 hover:text-gray-300"
          }`}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
