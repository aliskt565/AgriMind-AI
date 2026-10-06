"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { AmbientBackground } from "@/components/AmbientBackground";
import { ClickableCard, Badge, HealthStatusBadge, AIBadge } from "@/components/ui/Card";
import { PageHeader, EmptyState, ErrorState, SkeletonCardGrid } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { api, ApiError } from "@/lib/api";
import { stagger } from "@/lib/motion";
import type { Field, Crop, CropIntelligenceResponse, WeatherResponse } from "@/lib/types";

export default function FieldDetailPage() {
  const params = useParams<{ farmId: string; fieldId: string }>();
  const [field, setField] = useState<Field | null>(null);
  const [crops, setCrops] = useState<Crop[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [showForm, setShowForm] = useState(false);
  const [cropType, setCropType] = useState("");
  const [variety, setVariety] = useState("");
  const [plantingDate, setPlantingDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [editingField, setEditingField] = useState(false);
  const [editName, setEditName] = useState("");
  const [editArea, setEditArea] = useState("");
  const [editSoil, setEditSoil] = useState("UNKNOWN");
  const [editIrrigation, setEditIrrigation] = useState("UNKNOWN");
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [advisorResult, setAdvisorResult] = useState<CropIntelligenceResponse | null>(null);
  const [advisorLoading, setAdvisorLoading] = useState(false);
  const [advisorError, setAdvisorError] = useState<string | null>(null);

  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [weatherError, setWeatherError] = useState<string | null>(null);

  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [scanLoading, setScanLoading] = useState(false);

  const load = () => {
    setIsLoading(true);
    setError(null);
    Promise.all([
      api.get<Field>(`/fields/${params.fieldId}`),
      api.get<Crop[]>(`/fields/${params.fieldId}/crops`),
    ])
      .then(([fieldRes, cropsRes]) => {
        setField(fieldRes);
        setCrops(cropsRes);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this field."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [params.fieldId]);

  useEffect(() => {
    api
      .get<WeatherResponse>(`/weather/fields/${params.fieldId}`)
      .then(setWeather)
      .catch((err) => setWeatherError(err instanceof ApiError ? err.message : "Weather is unavailable right now."));
  }, [params.fieldId]);

  const runRiskScan = async () => {
    setScanLoading(true);
    setScanMessage(null);
    try {
      const findings = await api.post<{ risk_type: string }[]>(`/risk/fields/${params.fieldId}/scan`);
      setScanMessage(
        findings.length === 0
          ? "No risks detected for this field right now."
          : `${findings.length} active risk${findings.length === 1 ? "" : "s"} found -- check the Dashboard for details.`
      );
    } catch (err) {
      setScanMessage(err instanceof ApiError ? err.message : "Risk scan failed. Please try again.");
    } finally {
      setScanLoading(false);
    }
  };

  const startFieldEdit = () => {
    if (!field) return;
    setEditName(field.name);
    setEditArea(field.area_acres?.toString() ?? "");
    setEditSoil(field.soil_type);
    setEditIrrigation(field.irrigation_type);
    setEditError(null);
    setEditingField(true);
  };

  const handleFieldEdit = async (e: FormEvent) => {
    e.preventDefault();
    setEditSubmitting(true);
    setEditError(null);
    try {
      await api.patch(`/fields/${params.fieldId}`, {
        name: editName,
        area_acres: editArea ? Number(editArea) : undefined,
        soil_type: editSoil,
        irrigation_type: editIrrigation,
      });
      setEditingField(false);
      load();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Could not update this field.");
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      await api.post(`/fields/${params.fieldId}/crops`, {
        crop_type: cropType, variety: variety || undefined, planting_date: plantingDate || undefined,
      });
      setCropType("");
      setVariety("");
      setShowForm(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create the crop.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const requestAdvisor = async () => {
    setAdvisorLoading(true);
    setAdvisorError(null);
    setAdvisorResult(null);
    try {
      const result = await api.post<CropIntelligenceResponse>(
        `/ai/crop-intelligence/fields/${params.fieldId}`,
        { season: "Rabi" }
      );
      setAdvisorResult(result);
    } catch (err) {
      setAdvisorError(err instanceof ApiError ? err.message : "AI Crop Advisor is unavailable right now.");
    } finally {
      setAdvisorLoading(false);
    }
  };

  return (
    <AppShell>
      <AmbientBackground variant="advisor" />
      <PageHeader
        title={field ? field.name : "Field"}
        description={field ? `${field.soil_type} soil · ${field.irrigation_type} irrigation` : undefined}
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={runRiskScan} isLoading={scanLoading}>
              Run risk scan
            </Button>
            <Button variant="secondary" size="sm" onClick={requestAdvisor} isLoading={advisorLoading}>
              Ask AI Crop Advisor
            </Button>
            <Button variant="secondary" size="sm" onClick={startFieldEdit}>Edit field</Button>
            <Button onClick={() => setShowForm((s) => !s)} size="sm">
              {showForm ? "Cancel" : "Add crop"}
            </Button>
          </div>
        }
      />

      {scanMessage && (
        <p className="animate-in mb-6 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
          {scanMessage}
        </p>
      )}

      {weather && !weatherError && (
        <div className="animate-in mb-6 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4 shadow-[var(--shadow-sm)]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-4 text-sm">
              <span className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                {weather.temperature_celsius !== null ? `${weather.temperature_celsius}°C` : "—"}
              </span>
              <span className="text-[var(--color-text-muted)]">
                Humidity {weather.humidity_percent ?? "—"}% · Rain (24h) {weather.rainfall_mm_last_24h ?? "—"}mm
              </span>
            </div>
            <span className="text-xs text-[var(--color-text-muted)]">
              {weather.is_stale ? "Stale · " : ""}Source: {weather.source} · {new Date(weather.fetched_at).toLocaleString()}
            </span>
          </div>
          {weather.forecast_summary && <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{weather.forecast_summary}</p>}
          {weather.extreme_weather_alert && (
            <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-[var(--color-status-at-risk)]">
              <span aria-hidden style={{ animation: "pulseGlow 2s ease-in-out infinite" }}>⚠</span> {weather.extreme_weather_alert}
            </p>
          )}
        </div>
      )}

      {advisorError && <div className="mb-6"><ErrorState message={advisorError} onRetry={requestAdvisor} /></div>}

      {advisorResult && (
        <div className="animate-in mb-6 rounded-[var(--radius-md)] border border-[var(--color-ai-accent)]/30 bg-[var(--color-ai-accent-soft)] p-5 shadow-[var(--shadow-glow-ai)]">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium text-[var(--color-text-primary)]">AI Crop Advisor suggestions</h3>
            <AIBadge label={advisorResult.is_mock ? "AI generated · mock model" : "AI generated"} />
          </div>
          <div className="flex flex-col gap-3">
            {advisorResult.candidates.slice(0, 3).map((c, i) => (
              <div
                key={c.crop_type}
                className="stagger-item rounded-[var(--radius-sm)] bg-[var(--color-surface-raised)] p-3 shadow-[var(--shadow-sm)]"
                style={stagger(i)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-[var(--color-text-primary)]">{c.crop_type}</span>
                  <span className="text-sm text-[var(--color-text-muted)]">
                    Suitability {c.suitability_score}/100 · Confidence {c.confidence}
                  </span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--color-border)]">
                  <div
                    className="h-full rounded-full bg-[var(--color-ai-accent)] transition-[width] duration-[var(--duration-emphasis)] ease-[var(--ease-out)]"
                    style={{ width: `${c.suitability_score}%` }}
                  />
                </div>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{c.explanation}</p>
                {c.risk_note && <p className="mt-1 text-xs text-[var(--color-status-monitoring)]">Risk: {c.risk_note}</p>}
              </div>
            ))}
          </div>
          {advisorResult.important_assumptions.length > 0 && (
            <ul className="mt-3 list-disc pl-5 text-xs text-[var(--color-text-muted)]">
              {advisorResult.important_assumptions.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {editingField && (
        <form onSubmit={handleFieldEdit} className="animate-in mb-6 flex flex-col gap-4 rounded-[var(--radius-md)] border border-[var(--color-ai-accent)]/25 bg-[var(--color-surface-raised)] p-5 shadow-[var(--shadow-md)] sm:max-w-md">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Edit field</h2>
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditingField(false)}>Cancel</Button>
          </div>
          {editError && <ErrorState message={editError} />}
          <Input label="Field name" required value={editName} onChange={(e) => setEditName(e.target.value)} />
          <Input label="Area (acres)" type="number" min="0" step="0.1" value={editArea} onChange={(e) => setEditArea(e.target.value)} />
          <Select label="Soil type" value={editSoil} onChange={(e) => setEditSoil(e.target.value)}>
            {["UNKNOWN", "LOAMY", "CLAY", "SANDY", "SILTY", "PEATY", "CHALKY"].map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
          <Select label="Irrigation type" value={editIrrigation} onChange={(e) => setEditIrrigation(e.target.value)}>
            {["UNKNOWN", "RAINFED", "CANAL", "TUBEWELL", "DRIP", "FLOOD", "SPRINKLER", "OTHER"].map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
          <Button type="submit" isLoading={editSubmitting} size="sm">Save changes</Button>
        </form>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="animate-in mb-6 flex flex-col gap-4 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5 shadow-[var(--shadow-md)] sm:max-w-md">
          {formError && <ErrorState message={formError} />}
          <Input label="Crop type" required value={cropType} onChange={(e) => setCropType(e.target.value)} placeholder="e.g. Wheat" />
          <Input label="Variety (optional)" value={variety} onChange={(e) => setVariety(e.target.value)} />
          <Input label="Planting date" type="date" value={plantingDate} onChange={(e) => setPlantingDate(e.target.value)} />
          <Button type="submit" isLoading={isSubmitting} size="sm">
            Create crop
          </Button>
        </form>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {isLoading && !error && <SkeletonCardGrid />}

      {crops && crops.length === 0 && !isLoading && (
        <EmptyState
          title="No crops yet"
          description="Add a crop manually, or ask the AI Crop Advisor for suggestions first."
          actionLabel={showForm ? undefined : "Add crop"}
          onAction={() => setShowForm(true)}
        />
      )}

      {crops && crops.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {crops.map((crop, i) => (
            <div key={crop.id} className="stagger-item" style={stagger(i)}>
              <ClickableCard href={`/farms/${params.farmId}/fields/${params.fieldId}/crops/${crop.id}`}>
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-medium text-[var(--color-text-primary)]">
                    {crop.crop_type}
                    {crop.variety ? ` · ${crop.variety}` : ""}
                  </h3>
                  <HealthStatusBadge status={crop.health_status} />
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Badge>{crop.stage.replace("_", " ")}</Badge>
                  {crop.source === "AI_SUGGESTION" && <AIBadge label="From AI suggestion" />}
                </div>
              </ClickableCard>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
