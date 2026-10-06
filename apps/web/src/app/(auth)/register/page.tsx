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

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [location, setLocation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register({ email, password, full_name: fullName, location: location || undefined });
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
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">Create your farmer account</p>
        </div>
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-6 shadow-[var(--shadow-lg)]"
        >
          {error && <ErrorState message={error} />}
          <Input label="Full name" required value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
          <Input label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <Input
            label="Password"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
          <Input label="Location (optional)" value={location} onChange={(e) => setLocation(e.target.value)} />
          <Button type="submit" isLoading={isSubmitting} className="mt-2">
            Create account
          </Button>
          <p className="text-center text-sm text-[var(--color-text-muted)]">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-[var(--color-brand-strong)] transition-colors duration-[var(--duration-fast)] hover:text-[var(--color-ai-accent-strong)]">
              Log in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
