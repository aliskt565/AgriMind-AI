"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { AmbientBackground } from "@/components/AmbientBackground";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <AmbientBackground variant="auth" />
      <div className="animate-in w-full max-w-sm">
        <div className="mb-8 text-center">
          <span aria-hidden className="mb-2 inline-block text-2xl text-[var(--color-ai-accent-strong)]">✦</span>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">AgriMind AI</h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            AI-Powered Smart Agriculture &amp; Farm Intelligence Platform
          </p>
        </div>
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6 shadow-[var(--shadow-lg)]"
        >
          <h2 className="text-sm font-medium text-[var(--color-text-primary)]">Log in to your account</h2>
          {error && <ErrorState message={error} />}
          <Input label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <Input
            label="Password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
          <Button type="submit" isLoading={isSubmitting} className="mt-2">
            Log in
          </Button>
          <p className="text-center text-sm text-[var(--color-text-muted)]">
            New to AgriMind AI?{" "}
            <Link href="/register" className="font-medium text-[var(--color-brand-strong)] transition-colors duration-[var(--duration-fast)] hover:text-[var(--color-ai-accent-strong)]">
              Create an account
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
