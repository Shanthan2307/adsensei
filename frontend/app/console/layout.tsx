"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { clearToken } from "@/lib/auth";

export default function ConsoleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();

  const handleSignOut = () => {
    clearToken();
    router.push("/");
  };

  return (
    <div className="h-screen w-full overflow-hidden bg-background flex flex-col">
      <nav className="shrink-0 z-50 bg-background">
        <div className="w-full px-8 flex items-center justify-between h-14">
          <Link
            href="/"
            className="cursor-pointer text-sm font-medium tracking-widest uppercase hover:opacity-70 transition-opacity"
          >
            ADAPT
          </Link>
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-foreground/2 font-mono text-[9px] uppercase tracking-widest text-muted">
              <span>Powered by</span>
              <a
                href="https://tokenrouter.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-foreground hover:text-[#6366f1] transition-colors"
              >
                TokenRouter
              </a>
              <span className="text-muted/40">·</span>
              <a
                href="https://www.agenthansa.com/experts/adsensei"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-foreground hover:text-[#6366f1] transition-colors"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#6366f1] animate-pulse" />
                AgentHansa
              </a>
            </div>
            <button
              onClick={handleSignOut}
              className="cursor-pointer font-mono text-[11px] uppercase tracking-widest text-muted hover:text-foreground transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </nav>

      <main className="flex-1 min-h-0 overflow-hidden">
        {children}
      </main>
    </div>
  );
}
