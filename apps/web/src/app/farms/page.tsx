"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AmbientBackground } from "@/components/AmbientBackground";
import { ClickableCard } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Card";
import { PageHeader, EmptyState, ErrorState, SkeletonCardGrid } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { api, ApiError } from "@/lib/api";
import { stagger } from "@/lib/motion";
import type { Farm } from "@/lib/types";

export default function FarmsPage() {
  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [area, setArea] = useState("");
  const [location, setLocation] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [editingFarm, setEditingFarm] = useState<Farm | null>(null);
  const [editName, setEditName] = useState("");
  const [editArea, setEditArea] = useState("");
  const [editLocation, setEditLocation] = useState("");
  const [isEditing, setIsEditing] = useState(false);

  const load = () => {
    setIsLoading(true);
    setError(null);
    api
      .get<Farm[]>("/farms")
      .then(setFarms)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load your farms."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      await api.post("/farms", {
        name,
        total_area_acres: area ? Number(area) : undefined,
        location: location || undefined,
      });
      setName("");
      setArea("");
      setLocation("");
      setShowForm(false);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create the farm.");
    } finally {
      setIsSubmitting(false);
    }
  };


  const startEdit = (farm: Farm) => {
    setEditingFarm(farm);
    setEditName(farm.name);
    setEditArea(farm.total_area_acres?.toString() ?? "");
    setEditLocation(farm.location ?? "");
    setFormError(null);
  };

  const handleEdit = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingFarm) return;
    setFormError(null);
    setIsEditing(true);
    try {
      await api.patch(`/farms/${editingFarm.id}`, {
        name: editName,
        total_area_acres: editArea ? Number(editArea) : undefined,
        location: editLocation || undefined,
      });
      setEditingFarm(null);
      load();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not update the farm.");
    } finally {
      setIsEditing(false);
    }
  };

  return (
    <AppShell>
      <AmbientBackground variant="farms" />
      <PageHeader
        title="Farms"
        description="Manage your properties and the fields within them."
        action={
          <Button onClick={() => setShowForm((s) => !s)} size="sm">
            {showForm ? "Cancel" : "Add farm"}
          </Button>
        }
      />


      {editingFarm && (
        <form onSubmit={handleEdit} className="animate-in mb-6 flex flex-col gap-4 rounded-[var(--radius-md)] border border-[var(--color-ai-accent)]/25 bg-[var(--color-surface-raised)] p-5 shadow-[var(--shadow-md)] sm:max-w-md">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-[var(--color-text-primary)]">Edit farm</h2>
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditingFarm(null)}>Cancel</Button>
          </div>
          {formError && <ErrorState message={formError} />}
          <Input label="Farm name" required value={editName} onChange={(e) => setEditName(e.target.value)} />
          <Input label="Total area (acres)" type="number" min="0" step="0.1" value={editArea} onChange={(e) => setEditArea(e.target.value)} />
          <Input label="Location" value={editLocation} onChange={(e) => setEditLocation(e.target.value)} />
          <Button type="submit" isLoading={isEditing} size="sm">Save changes</Button>
        </form>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="animate-in mb-6 flex flex-col gap-4 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5 shadow-[var(--shadow-md)] sm:max-w-md">
          {formError && <ErrorState message={formError} />}
          <Input label="Farm name" required value={name} onChange={(e) => setName(e.target.value)} />
          <Input label="Total area (acres)" type="number" min="0" step="0.1" value={area} onChange={(e) => setArea(e.target.value)} />
          <Input label="Location" value={location} onChange={(e) => setLocation(e.target.value)} />
          <Button type="submit" isLoading={isSubmitting} size="sm">
            Create farm
          </Button>
        </form>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {isLoading && !error && <SkeletonCardGrid />}

      {farms && farms.length === 0 && !isLoading && (
        <EmptyState
          title="No farms yet"
          description="Add your first farm to start tracking fields and crops."
          actionLabel={showForm ? undefined : "Add farm"}
          onAction={() => setShowForm(true)}
        />
      )}

      {farms && farms.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {farms.map((farm, i) => (
            <div key={farm.id} className="stagger-item" style={stagger(i)}>
              <ClickableCard href={`/farms/${farm.id}`}>
                <div className="flex items-start justify-between">
                  <h3 className="font-medium text-[var(--color-text-primary)]">{farm.name}</h3>
                  <Badge>{farm.field_count} field{farm.field_count === 1 ? "" : "s"}</Badge>
                </div>
                <p className="mt-2 text-sm text-[var(--color-text-muted)]">
                  {farm.location || "No location set"}
                  {farm.total_area_acres ? ` · ${farm.total_area_acres} acres` : ""}
                </p>
              </ClickableCard>
              <div className="mt-2 flex justify-end">
                <Button variant="ghost" size="sm" onClick={() => startEdit(farm)}>Edit</Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
