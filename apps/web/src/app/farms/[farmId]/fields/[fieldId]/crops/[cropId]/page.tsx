"use client";

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { AmbientBackground } from "@/components/AmbientBackground";
import { Card, Badge, HealthStatusBadge, AIBadge } from "@/components/ui/Card";
import { PageHeader, EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { api, ApiError } from "@/lib/api";
import { stagger } from "@/lib/motion";
import type {
  Crop,
  CropActivity,
  ActivityType,
  PlantVisionDetectResponse,
  HealthStatus,
} from "@/lib/types";

const ACTIVITY_TYPES: ActivityType[] = [
  "PLANTING", "IRRIGATION", "FERTILIZATION", "SPRAYING", "OBSERVATION", "HARVEST", "CUSTOM",
];

const RESULT_TONE: Record<string, "healthy" | "monitoring" | "at-risk" | "critical" | "neutral"> = {
  HEALTHY: "healthy",
  HIGH_CONFIDENCE: "at-risk",
  LOW_CONFIDENCE: "monitoring",
  REJECTED_LOW_QUALITY: "neutral",
  REJECTED_NON_PLANT: "neutral",
  UNSUPPORTED_CROP: "neutral",
  SERVICE_FAILURE: "critical",
};

const PRIORITY_TONE: Record<string, "healthy" | "monitoring" | "at-risk"> = {
  LOW: "healthy",
  MEDIUM: "monitoring",
  HIGH: "at-risk",
};

const V2_PLANT_VISION_CROPS = new Set(["Corn", "Potato"]);

export default function CropDetailPage() {
  const params = useParams<{ farmId: string; fieldId: string; cropId: string }>();
  const [crop, setCrop] = useState<Crop | null>(null);
  const [activities, setActivities] = useState<CropActivity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [showActivityForm, setShowActivityForm] = useState(false);
  const [activityType, setActivityType] = useState<ActivityType>("IRRIGATION");
  const [activityDate, setActivityDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [isSubmittingActivity, setIsSubmittingActivity] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);

  // Vision scan state — note: uses PlantVisionDetectResponse (includes side-effects)
  const [visionResult, setVisionResult] = useState<PlantVisionDetectResponse | null>(null);
  const [visionLoading, setVisionLoading] = useState(false);
  const [visionError, setVisionError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Inline health-status notification from scan side-effects
  const [healthBanner, setHealthBanner] = useState<{ status: HealthStatus; message: string } | null>(null);

  const load = () => {
    setIsLoading(true);
    setError(null);
    Promise.all([
      api.get<Crop>(`/crops/${params.cropId}`),
      api.get<CropActivity[]>(`/crops/${params.cropId}/activities`),
    ])
      .then(([cropRes, activitiesRes]) => {
        setCrop(cropRes);
        setActivities(activitiesRes);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this crop."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [params.cropId]);

  const handleLogActivity = async (e: FormEvent) => {
    e.preventDefault();
    setActivityError(null);
    setIsSubmittingActivity(true);
    try {
      await api.post(`/crops/${params.cropId}/activities`, {
        activity_type: activityType,
        activity_date: activityDate,
        notes: notes || undefined,
      });
      setNotes("");
      setShowActivityForm(false);
      load();
    } catch (err) {
      setActivityError(err instanceof ApiError ? err.message : "Could not log this activity.");
    } finally {
      setIsSubmittingActivity(false);
    }
  };

  const handleImageSelected = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setVisionLoading(true);
    setVisionError(null);
    setVisionResult(null);
    setHealthBanner(null);

    try {
      const formData = new FormData();
      formData.append("image", file);
      const result = await api.postForm<PlantVisionDetectResponse>(
        `/ai/plant-vision/crops/${params.cropId}/detect`,
        formData,
      );
      setVisionResult(result);

      // --- Side-effect: update local crop health status if escalated ---
      if (result.health_status_updated && result.updated_health_status) {
        const newStatus = result.updated_health_status as HealthStatus;
        // Optimistically update the crop badge shown in the page header
        setCrop((prev) => prev ? { ...prev, health_status: newStatus } : prev);

        const statusLabel: Record<string, string> = {
          AT_RISK: "At Risk",
          DISEASED: "Diseased",
          MONITORING: "Monitoring",
          HEALTHY: "Healthy",
        };
        setHealthBanner({
          status: newStatus,
          message: `Crop health updated to "${statusLabel[newStatus] ?? newStatus}" based on this scan.`,
        });
      }
    } catch (err) {
      setVisionError(err instanceof ApiError ? err.message : "Plant Vision is unavailable right now.");
    } finally {
      setVisionLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <AppShell>
      <AmbientBackground variant="vision" />
      {isLoading && (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-32" />
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}

      {crop && !isLoading && (
        <>
          <PageHeader
            title={`${crop.crop_type}${crop.variety ? ` · ${crop.variety}` : ""}`}
            description={`Stage: ${crop.stage.replace(/_/g, " ")}`}
            action={<HealthStatusBadge status={crop.health_status} />}
          />

          {/* Health escalation banner — appears immediately after a disease scan */}
          {healthBanner && (
            <div
              className="animate-in mb-5 flex items-start gap-3 rounded-[var(--radius-md)] border border-[var(--color-status-at-risk)]/40 bg-[var(--color-status-at-risk)]/8 px-4 py-3"
              role="alert"
            >
              <span aria-hidden className="mt-0.5 text-base" style={{ animation: "pulseGlow 2s ease-in-out infinite" }}>
                ⚠
              </span>
              <div className="flex-1">
                <p className="text-sm font-medium text-[var(--color-status-at-risk)]">{healthBanner.message}</p>
                <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                  Risk alerts and recommendations have been updated — check your Dashboard for details.
                </p>
              </div>
              <button
                onClick={() => setHealthBanner(null)}
                className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
                aria-label="Dismiss alert"
              >
                ✕
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Plant Vision */}
            <Card aiAccent={!!visionResult} className="animate-in">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-medium text-[var(--color-text-primary)]">Plant Vision</h3>
                {visionResult && (
                  <AIBadge label={visionResult.is_mock ? "AI generated · mock model" : "AI generated · CNN"} />
                )}
              </div>
              <p className="mb-3 text-sm text-[var(--color-text-muted)]">
                Upload a photo of this crop to check for visible disease symptoms. A confirmed disease will
                automatically update this crop&apos;s health status and create risk alerts.
              </p>

              {V2_PLANT_VISION_CROPS.has(crop.crop_type) ? (
                <>
                  <label
                    htmlFor="plant-vision-upload"
                    className="flex cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] border border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface)]/40 px-3 py-2 text-sm text-[var(--color-text-secondary)] transition-colors duration-[var(--duration-fast)] hover:border-[var(--color-ai-accent)] hover:text-[var(--color-text-primary)]"
                  >
                    <span aria-hidden>📷</span>
                    {visionLoading ? "Analyzing…" : "Choose a photo…"}
                  </label>
                  <input
                    ref={fileInputRef}
                    id="plant-vision-upload"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleImageSelected}
                    className="sr-only"
                    aria-label="Upload a plant photo for disease detection"
                    disabled={visionLoading}
                  />
                </>
              ) : (
                <div className="rounded-[var(--radius-sm)] border border-[var(--color-status-monitoring)]/30 bg-[var(--color-status-monitoring)]/5 px-3 py-3">
                  <p className="text-xs font-medium text-[var(--color-status-monitoring)]">
                    V2 Plant Vision does not yet cover {crop.crop_type}.
                  </p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    The current trained V2 model supports Corn and Potato only. Rice, Wheat, and Sugarcane will
                    be enabled after their dedicated datasets are added and evaluated.
                  </p>
                </div>
              )}

              {visionLoading && (
                <div className="vision-scan-frame mt-3 flex flex-col items-center gap-2 rounded-[var(--radius-sm)] border border-[var(--color-ai-accent)]/25 bg-[var(--color-ai-accent-soft)] px-3 py-6 text-sm text-[var(--color-text-secondary)]">
                  <div className="vision-scan-line motion-reduce:hidden" aria-hidden />
                  <span aria-hidden className="text-2xl">🔬</span>
                  Analyzing image…
                </div>
              )}

              {visionError && (
                <div className="mt-3">
                  <ErrorState message={visionError} />
                </div>
              )}

              {visionResult && !visionLoading && (
                <div className="animate-in mt-4 flex flex-col gap-3">
                  {/* Detection result */}
                  <div className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-3">
                    <div className="mb-2 flex items-center gap-2">
                      <Badge tone={RESULT_TONE[visionResult.result_type] ?? "neutral"}>
                        {visionResult.result_type.replace(/_/g, " ")}
                      </Badge>
                      {visionResult.confidence !== null && (
                        <span className="text-xs text-[var(--color-text-muted)]">
                          Confidence {Math.round(visionResult.confidence * 100)}%
                        </span>
                      )}
                    </div>
                    {visionResult.predicted_disease && (
                      <p className="text-sm font-medium text-[var(--color-text-primary)]">
                        {visionResult.predicted_disease}
                      </p>
                    )}
                    {visionResult.guidance_text && (
                      <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{visionResult.guidance_text}</p>
                    )}
                    {visionResult.rejection_reason && (
                      <p className="mt-1 text-sm text-[var(--color-status-monitoring)]">{visionResult.rejection_reason}</p>
                    )}
                  </div>

                  {/* Triggered recommendations — only shown when side-effects fired */}
                  {(visionResult.triggered_recommendations?.length ?? 0) > 0 && (
                    <div className="rounded-[var(--radius-sm)] border border-[var(--color-ai-accent)]/25 bg-[var(--color-ai-accent-soft)] p-3">
                      <div className="mb-2 flex items-center gap-2">
                        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                          New recommendations
                        </p>
                        <AIBadge label="AI generated" />
                      </div>
                      <ul className="flex flex-col gap-2">
                        {visionResult.triggered_recommendations.map((rec, i) => (
                          <li
                            key={rec.id}
                            className="stagger-item rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-3 py-2"
                            style={stagger(i)}
                          >
                            <div className="mb-1 flex items-center gap-2">
                              <Badge tone={PRIORITY_TONE[rec.priority] ?? "neutral"}>{rec.priority}</Badge>
                              <span className="text-xs text-[var(--color-text-muted)]">{rec.category.replace(/_/g, " ")}</span>
                            </div>
                            <p className="text-sm text-[var(--color-text-primary)]">{rec.text}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <p className="text-xs italic text-[var(--color-text-muted)]">{visionResult.disclaimer}</p>
                </div>
              )}
            </Card>

            {/* Activities */}
            <Card className="animate-in">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-medium text-[var(--color-text-primary)]">Activity log</h3>
                <Button size="sm" variant="secondary" onClick={() => setShowActivityForm((s) => !s)}>
                  {showActivityForm ? "Cancel" : "Log activity"}
                </Button>
              </div>

              {showActivityForm && (
                <form onSubmit={handleLogActivity} className="animate-in mb-4 flex flex-col gap-3">
                  {activityError && <ErrorState message={activityError} />}
                  <Select label="Activity type" value={activityType} onChange={(e) => setActivityType(e.target.value as ActivityType)}>
                    {ACTIVITY_TYPES.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </Select>
                  <Input label="Date" type="date" required value={activityDate} onChange={(e) => setActivityDate(e.target.value)} />
                  <Input label="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
                  <Button type="submit" size="sm" isLoading={isSubmittingActivity}>
                    Save activity
                  </Button>
                </form>
              )}

              {activities && activities.length === 0 && (
                <EmptyState title="No activities logged yet" description="Log irrigation, fertilization, or other actions as they happen." />
              )}

              {activities && activities.length > 0 && (
                <ul className="flex flex-col gap-2">
                  {activities.map((a, i) => (
                    <li
                      key={a.id}
                      className="stagger-item flex items-center justify-between rounded-[var(--radius-sm)] border border-[var(--color-border)] px-3 py-2 text-sm"
                      style={stagger(i)}
                    >
                      <span className="font-medium text-[var(--color-text-primary)]">{a.activity_type}</span>
                      <span className="text-[var(--color-text-muted)]">{a.activity_date}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </AppShell>
  );
}
