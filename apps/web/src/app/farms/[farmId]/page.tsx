"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { AmbientBackground } from "@/components/AmbientBackground";
import { ClickableCard, Badge } from "@/components/ui/Card";
import { PageHeader, EmptyState, ErrorState, SkeletonCardGrid } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { api, ApiError } from "@/lib/api";
import { stagger } from "@/lib/motion";
import type { Farm, Field } from "@/lib/types";

const SOIL_TYPES = ["UNKNOWN", "LOAMY", "CLAY", "SANDY", "SILTY", "PEATY", "CHALKY"];
const IRRIGATION_TYPES = ["UNKNOWN", "RAINFED", "CANAL", "TUBEWELL", "DRIP", "FLOOD", "SPRINKLER", "OTHER"];
const COMMON_CROPS = ["Wheat", "Rice", "Corn", "Potato", "Sugarcane"];

export default function FarmDetailPage() {
  const params = useParams<{ farmId: string }>();
  const [farm, setFarm] = useState<Farm | null>(null);
  const [fields, setFields] = useState<Field[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [soilType, setSoilType] = useState("UNKNOWN");
  const [irrigationType, setIrrigationType] = useState("UNKNOWN");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [initialCrops, setInitialCrops] = useState<string[]>([]);

  const load = () => {
    setIsLoading(true);
    setError(null);
    Promise.all([api.get<Farm>(`/farms/${params.farmId}`), api.get<Field[]>(`/farms/${params.farmId}/fields`)])
      .then(([farmRes, fieldsRes]) => {
        setFarm(farmRes);
        setFields(fieldsRes);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this farm."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [params.farmId]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      await api.post(`/farms/${params.farmId}/fields`, { name, soil_type: soilType, irrigation_type: irrigationType, initial_crop_types: initialCrops });
      setName("");
      setInitialCrops([]);
      setShowForm(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create the field.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppShell>
      <AmbientBackground variant="field" />
      <PageHeader
        title={farm ? farm.name : "Farm"}
        description={farm ? farm.location || undefined : undefined}
        action={
          <Button onClick={() => setShowForm((s) => !s)} size="sm">
            {showForm ? "Cancel" : "Add field"}
          </Button>
        }
      />

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="animate-in mb-6 flex flex-col gap-4 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5 shadow-[var(--shadow-md)] sm:max-w-md"
        >
          {formError && <ErrorState message={formError} />}
          <Input label="Field name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Select label="Soil type" value={soilType} onChange={(e) => setSoilType(e.target.value)}>
            {SOIL_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
          <Select label="Irrigation type" value={irrigationType} onChange={(e) => setIrrigationType(e.target.value)}>
            {IRRIGATION_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
          <div>
            <p className="mb-2 text-sm font-medium text-[var(--color-text-secondary)]">Initial crops (optional)</p>
            <div className="grid grid-cols-2 gap-2">
              {COMMON_CROPS.map((crop) => {
                const checked = initialCrops.includes(crop);
                return (
                  <label key={crop} className="flex cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface)]/40 px-3 py-2 text-sm text-[var(--color-text-secondary)]">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => setInitialCrops((current) => checked ? current.filter((c) => c !== crop) : [...current, crop])}
                    />
                    {crop}
                  </label>
                );
              })}
            </div>
          </div>
          <Button type="submit" isLoading={isSubmitting} size="sm">
            Create field
          </Button>
        </form>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {isLoading && !error && <SkeletonCardGrid />}

      {fields && fields.length === 0 && !isLoading && (
        <EmptyState
          title="No fields yet"
          description="Add a field to start recording soil, irrigation, and crops for this farm."
          actionLabel={showForm ? undefined : "Add field"}
          onAction={() => setShowForm(true)}
        />
      )}

      {fields && fields.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {fields.map((field, i) => (
            <div key={field.id} className="stagger-item" style={stagger(i)}>
              <ClickableCard href={`/farms/${params.farmId}/fields/${field.id}`}>
                <div className="flex items-start justify-between">
                  <h3 className="font-medium text-[var(--color-text-primary)]">{field.name}</h3>
                  <Badge>{field.crop_count} crop{field.crop_count === 1 ? "" : "s"}</Badge>
                </div>
                <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                  {field.soil_type} soil · {field.irrigation_type} irrigation
                </p>
              </ClickableCard>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
