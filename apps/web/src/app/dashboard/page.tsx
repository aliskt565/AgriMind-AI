"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { AmbientBackground } from "@/components/AmbientBackground";
import { Card, Badge, AIBadge, riskSeverityBorderClass } from "@/components/ui/Card";
import { PageHeader, ErrorState, Skeleton, EmptyState } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import { stagger } from "@/lib/motion";
import type { DashboardSummary, RiskFinding, Recommendation } from "@/lib/types";

function KpiCard({ label, value, index }: { label: string; value: number | string; index: number }) {
  return (
    <Card className="stagger-item" style={stagger(index)}>
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">{value}</p>
    </Card>
  );
}

const RISK_TONE: Record<string, "healthy" | "monitoring" | "at-risk" | "critical"> = {
  LOW: "healthy",
  MODERATE: "monitoring",
  HIGH: "at-risk",
  CRITICAL: "critical",
};

const PRIORITY_TONE: Record<string, "healthy" | "monitoring" | "at-risk"> = {
  LOW: "healthy",
  MEDIUM: "monitoring",
  HIGH: "at-risk",
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [risks, setRisks] = useState<RiskFinding[] | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);

  const load = () => {
    setIsLoading(true);
    setError(null);
    Promise.all([
      api.get<DashboardSummary>("/dashboard/summary"),
      api.get<RiskFinding[]>("/risk"),
      api.get<Recommendation[]>("/recommendations"),
    ])
      .then(([summaryRes, riskRes, recRes]) => {
        setSummary(summaryRes);
        setRisks(riskRes);
        setRecommendations(recRes);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your dashboard."))
      .finally(() => setIsLoading(false));
  };

  const refreshRecommendations = async () => {
    setIsGenerating(true);
    try {
      const recs = await api.post<Recommendation[]>("/recommendations/generate");
      setRecommendations(recs);
    } catch {
      // Non-critical background action -- the existing list stays visible on failure.
    } finally {
      setIsGenerating(false);
    }
  };

  const dismissRecommendation = async (id: string) => {
    await api.post(`/recommendations/${id}/dismiss`);
    setRecommendations((prev) => (prev ? prev.filter((r) => r.id !== id) : prev));
  };

  useEffect(() => {
    if (user) load();
  }, [user]);

  return (
    <AppShell>
      <AmbientBackground variant="dashboard" />
      <PageHeader title="Welcome back" description="What's happening with your farm, and what needs your attention." />

      {error && <ErrorState message={error} onRetry={load} />}

      {isLoading && !error && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      )}

      {summary && !isLoading && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <KpiCard label="Farms" value={summary.farm_count} index={0} />
          <KpiCard label="Fields" value={summary.field_count} index={1} />
          <KpiCard label="Active crops" value={summary.active_crop_count} index={2} />
          <KpiCard label="Active risks" value={summary.active_risk_count} index={3} />
          <KpiCard label="Recommendations" value={summary.active_recommendation_count} index={4} />
        </div>
      )}

      {summary && summary.farm_count === 0 && !isLoading && (
        <div className="mt-8">
          <Card className="animate-in text-center">
            <p className="text-sm font-medium text-[var(--color-text-primary)]">No farms yet</p>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              Add your first farm to start getting AI-backed crop suggestions and farm intelligence.
            </p>
            <Link
              href="/farms"
              className="mt-4 inline-flex items-center justify-center rounded-[var(--radius-sm)] bg-[var(--color-brand)] px-4 py-2 text-sm font-medium text-white shadow-[var(--shadow-sm)] transition-[transform,box-shadow,background-color] duration-[var(--duration-fast)] ease-[var(--ease-standard)] hover:-translate-y-px hover:bg-[var(--color-brand-strong)] hover:shadow-[var(--shadow-glow-brand)]"
            >
              Go to Farms
            </Link>
          </Card>
        </div>
      )}

      {summary && summary.farm_count > 0 && !isLoading && (
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card className="animate-in">
            <h3 className="mb-3 text-sm font-medium text-[var(--color-text-primary)]">Active risks</h3>
            {risks && risks.length === 0 && (
              <EmptyState title="No active risks" description="Run a risk scan from a field page to check for issues." />
            )}
            {risks && risks.length > 0 && (
              <ul className="flex flex-col gap-2">
                {risks.slice(0, 5).map((risk, i) => (
                  <li
                    key={risk.id}
                    className={`stagger-item rounded-[var(--radius-sm)] border border-l-[3px] border-[var(--color-border)] bg-[var(--color-surface)]/40 p-3 ${riskSeverityBorderClass(risk.risk_level)}`}
                    style={stagger(i)}
                  >
                    <div className="mb-1 flex items-center gap-2">
                      <Badge tone={RISK_TONE[risk.risk_level]}>{risk.risk_level}</Badge>
                      <span className="text-xs text-[var(--color-text-muted)]">{risk.risk_type.replace("_", " ")} · Confidence {risk.confidence}</span>
                    </div>
                    <p className="text-sm text-[var(--color-text-secondary)]">{risk.reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card aiAccent className="animate-in">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-medium text-[var(--color-text-primary)]">Recommendations</h3>
                <AIBadge label="AI generated" />
              </div>
              <Button size="sm" variant="secondary" onClick={refreshRecommendations} isLoading={isGenerating}>
                Refresh
              </Button>
            </div>
            {recommendations && recommendations.length === 0 && (
              <EmptyState
                title="No recommendations right now"
                description="Recommendations appear here once there's a real signal to act on -- nothing is generated without a reason."
              />
            )}
            {recommendations && recommendations.length > 0 && (
              <ul className="flex flex-col gap-2">
                {recommendations.map((rec, i) => (
                  <li
                    key={rec.id}
                    className="stagger-item rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-3"
                    style={stagger(i)}
                  >
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <Badge tone={PRIORITY_TONE[rec.priority]}>{rec.priority}</Badge>
                      <button
                        onClick={() => dismissRecommendation(rec.id)}
                        className="text-xs font-medium text-[var(--color-text-muted)] transition-colors duration-[var(--duration-fast)] hover:text-[var(--color-text-primary)]"
                      >
                        Dismiss
                      </button>
                    </div>
                    <p className="text-sm text-[var(--color-text-primary)]">{rec.text}</p>
                    <p className="mt-1 text-xs text-[var(--color-text-muted)]">{rec.trigger_reason}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </AppShell>
  );
}
