"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { AmbientBackground } from "@/components/AmbientBackground";

export default function RootPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    router.replace(user ? "/dashboard" : "/login");
  }, [isLoading, user, router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-[var(--color-text-muted)]">
      <AmbientBackground variant="default" />
      Loading AgriMind AI…
    </div>
  );
}
