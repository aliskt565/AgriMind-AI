"use client";

import { ChangeEvent, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AmbientBackground } from "@/components/AmbientBackground";
import { Card, Badge, AIBadge } from "@/components/ui/Card";
import { PageHeader, ErrorState } from "@/components/ui/States";
import { api, ApiError } from "@/lib/api";
import type { QuickScanResponse } from "@/lib/types";

// Must match SUPPORTED_CROP_TYPES in plant_vision_cnn.py
const CROP_OPTIONS = [
  { value: "Corn", emoji: "🌽", diseases: "Common Rust, Gray Leaf Spot, Northern Leaf Blight" },
  { value: "Potato", emoji: "🥔", diseases: "Early Blight, Late Blight" },
] as const;

type CropValue = (typeof CROP_OPTIONS)[number]["value"];

const RESULT_TONE: Record<string, "healthy" | "at-risk" | "monitoring" | "neutral" | "critical"> = {
  success: "at-risk",
  rejected: "monitoring",
  error: "critical",
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.min(Math.max(value, 0), 100);
  const colour =
    pct >= 85 ? "var(--color-status-at-risk)"
    : pct >= 68 ? "var(--color-status-monitoring)"
    : "var(--color-border-strong)";
  return (
    <div
      className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--color-border)]"
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{ width: `${pct}%`, backgroundColor: colour }}
      />
    </div>
  );
}

export default function ScanPage() {
  const [selectedCrop, setSelectedCrop] = useState<CropValue | null>(null);
  const [result, setResult] = useState<QuickScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleCropSelect = (crop: CropValue) => {
    setSelectedCrop(crop);
    // Clear any previous result when user changes crop selection
    setResult(null);
    setError(null);
  };

  const handleFileSelected = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedCrop) return;

    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    setResult(null);
    setError(null);
    setScanning(true);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("selected_crop", selectedCrop);
      const res = await api.postForm<QuickScanResponse>("/ai/plant-vision/scan", formData);
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scan failed. Please try again.");
    } finally {
      setScanning(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
    if (preview) {
      URL.revokeObjectURL(preview);
      setPreview(null);
    }
  };

  const cropInfo = CROP_OPTIONS.find((c) => c.value === selectedCrop);
  const uploadReady = selectedCrop !== null && !scanning;

  return (
    <AppShell>
      <AmbientBackground variant="vision" />
      <PageHeader
        title="Quick Scan"
        description="Select your crop type, then upload a leaf photo for an instant disease check."
      />

      <div className="mx-auto max-w-xl space-y-4">
        {/* Step 1 — Crop selector */}
        <Card className="animate-in">
          <div className="mb-3 flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--color-brand)] text-xs font-semibold text-white">
              1
            </span>
            <h2 className="text-sm font-medium text-[var(--color-text-primary)]">Select your crop</h2>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3">
            {CROP_OPTIONS.map((crop) => {
              const active = selectedCrop === crop.value;
              return (
                <button
                  key={crop.value}
                  id={`crop-select-${crop.value.toLowerCase()}`}
                  onClick={() => handleCropSelect(crop.value)}
                  className={`group flex flex-col items-center gap-1.5 rounded-[var(--radius-md)] border px-3 py-4 text-center transition-all duration-[var(--duration-fast)] ease-[var(--ease-standard)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-brand)] ${
                    active
                      ? "border-[var(--color-ai-accent)] bg-[var(--color-ai-accent-soft)] shadow-[var(--shadow-glow-ai)]"
                      : "border-[var(--color-border)] bg-[var(--color-surface-raised)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-hover)]"
                  }`}
                  aria-pressed={active}
                >
                  <span className="text-2xl leading-none transition-transform duration-[var(--duration-fast)] group-hover:scale-110">
                    {crop.emoji}
                  </span>
                  <span
                    className={`text-xs font-semibold ${
                      active ? "text-[var(--color-ai-accent-strong)]" : "text-[var(--color-text-primary)]"
                    }`}
                  >
                    {crop.value}
                  </span>
                </button>
              );
            })}
          </div>

          {cropInfo && (
            <p className="mt-3 text-xs text-[var(--color-text-muted)]">
              <span className="font-medium text-[var(--color-text-secondary)]">{cropInfo.value} diseases detected:</span>{" "}
              {cropInfo.diseases}
            </p>
          )}
          <p className="mt-2 text-xs text-[var(--color-text-muted)]">
            V2 Plant Vision currently supports Corn and Potato. Rice, Wheat, and Sugarcane are not yet covered by
            the trained V2 disease model.
          </p>
        </Card>

        {/* Step 2 — Upload zone */}
        <Card className={`transition-opacity duration-300 ${selectedCrop ? "opacity-100" : "pointer-events-none opacity-40"}`}>
          <div className="mb-3 flex items-center gap-2">
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold text-white transition-colors ${
                selectedCrop ? "bg-[var(--color-brand)]" : "bg-[var(--color-border-strong)]"
              }`}
            >
              2
            </span>
            <h2 className="text-sm font-medium text-[var(--color-text-primary)]">
              Upload a {selectedCrop ?? "crop"} leaf photo
            </h2>
            <AIBadge label="V2 CNN · MobileNetV2" />
          </div>

          <label
            htmlFor="scan-upload"
            className={`group relative flex min-h-[160px] flex-col items-center justify-center gap-3 overflow-hidden rounded-[var(--radius-md)] border-2 border-dashed transition-colors duration-[var(--duration-fast)] ${
              uploadReady
                ? "cursor-pointer border-[var(--color-border-strong)] bg-[var(--color-surface)]/30 hover:border-[var(--color-ai-accent)] hover:bg-[var(--color-ai-accent-soft)]"
                : "cursor-not-allowed border-[var(--color-border)] bg-[var(--color-surface)]/10"
            }`}
          >
            {preview && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={preview}
                alt="Selected leaf preview"
                className="absolute inset-0 h-full w-full object-cover opacity-40"
              />
            )}

            {scanning ? (
              <div className="vision-scan-frame relative z-10 flex flex-col items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                <div className="vision-scan-line motion-reduce:hidden" aria-hidden />
                <span aria-hidden className="text-3xl">🔬</span>
                <span>Analyzing {selectedCrop} leaf…</span>
              </div>
            ) : (
              <div className="relative z-10 flex flex-col items-center gap-1.5 text-sm text-[var(--color-text-secondary)] transition-transform duration-[var(--duration-fast)] group-hover:scale-[1.02]">
                <span aria-hidden className="text-3xl">{cropInfo?.emoji ?? "📷"}</span>
                <span className="font-medium text-[var(--color-text-primary)]">
                  {uploadReady ? "Choose or drop a photo" : "Select a crop first"}
                </span>
                <span className="text-xs text-[var(--color-text-muted)]">JPEG · PNG · WEBP · max 8 MB</span>
              </div>
            )}
          </label>

          <input
            ref={fileInputRef}
            id="scan-upload"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileSelected}
            className="sr-only"
            aria-label={`Upload a ${selectedCrop ?? "plant"} photo for disease detection`}
            disabled={!uploadReady}
          />
        </Card>

        {/* Error */}
        {error && (
          <div className="animate-in">
            <ErrorState message={error} onRetry={reset} />
          </div>
        )}

        {/* Result card */}
        {result && !scanning && (
          <Card
            className="animate-in"
            aiAccent={result.status === "success" && result.is_disease && !result.crop_mismatch}
          >
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                {result.crop_mismatch ? (
                  <Badge tone="monitoring">Crop mismatch</Badge>
                ) : (
                  <Badge tone={RESULT_TONE[result.status] ?? "neutral"}>
                    {result.status === "success"
                      ? result.is_disease
                        ? "Disease detected"
                        : "Healthy"
                      : result.status.charAt(0).toUpperCase() + result.status.slice(1)}
                  </Badge>
                )}
                {result.status === "success" && <AIBadge label="AI generated" />}
                {result.selected_crop && (
                  <span className="text-xs text-[var(--color-text-muted)]">
                    Selected: <span className="font-medium">{result.selected_crop}</span>
                  </span>
                )}
              </div>
              <button
                onClick={reset}
                className="shrink-0 text-xs font-medium text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text-primary)]"
              >
                Clear
              </button>
            </div>

            <p className="text-sm text-[var(--color-text-secondary)]">{result.message}</p>

            {result.predicted_class && (
              <p className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">
                {result.predicted_class.replace(/___/g, " · ")}
              </p>
            )}

            {result.confidence_percent > 0 && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                  <span>Model confidence</span>
                  <span className="tabular-nums">{result.confidence_percent.toFixed(1)}%</span>
                </div>
                <ConfidenceBar value={result.confidence_percent} />
              </div>
            )}

            {/* Mismatch warning — higher priority than disease/healthy banners */}
            {result.crop_mismatch && result.mismatch_message && (
              <div className="mt-3 rounded-[var(--radius-sm)] border border-[var(--color-status-monitoring)]/40 bg-[var(--color-status-monitoring)]/8 px-3 py-2">
                <p className="text-xs font-semibold text-[var(--color-status-monitoring)]">
                  ⚠ Crop family mismatch
                </p>
                <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{result.mismatch_message}</p>
              </div>
            )}

            {/* Disease detected — no mismatch */}
            {result.status === "success" && result.is_disease && !result.crop_mismatch && (
              <div className="mt-3 rounded-[var(--radius-sm)] border border-[var(--color-status-at-risk)]/30 bg-[var(--color-status-at-risk)]/5 px-3 py-2">
                <p className="text-xs font-medium text-[var(--color-status-at-risk)]">
                  ⚠ Disease detected — navigate to the specific crop in your farm to run a linked scan
                  and automatically update its health status and risk alerts.
                </p>
              </div>
            )}

            {/* Healthy result */}
            {result.status === "success" && !result.is_disease && !result.crop_mismatch && (
              <div className="mt-3 rounded-[var(--radius-sm)] border border-[var(--color-status-healthy)]/30 bg-[var(--color-status-healthy)]/5 px-3 py-2">
                <p className="text-xs font-medium text-[var(--color-status-healthy)]">
                  ✓ No disease symptoms detected. Continue routine monitoring.
                </p>
              </div>
            )}

            <p className="mt-4 text-xs italic text-[var(--color-text-muted)]">{result.disclaimer}</p>
          </Card>
        )}

        {/* How it works — shown before first scan */}
        {!result && !scanning && !error && (
          <div className="animate-in rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
              How it works
            </h3>
            <ol className="flex flex-col gap-2 text-sm text-[var(--color-text-secondary)]">
              <li>
                <span className="mr-2 font-semibold text-[var(--color-ai-accent)]">1.</span>
                Select your crop type so the model can validate the result against the correct disease family.
              </li>
              <li>
                <span className="mr-2 font-semibold text-[var(--color-ai-accent)]">2.</span>
                Upload a clear, well-lit photo of a leaf. The V2 CNN classifies
                across the current 7-class Corn + Potato V2 taxonomy.
              </li>
              <li>
                <span className="mr-2 font-semibold text-[var(--color-ai-accent)]">3.</span>
                Low-confidence or out-of-distribution images are rejected using the calibrated V2 safety checks, and crop mismatches are flagged.
              </li>
              <li>
                <span className="mr-2 font-semibold text-[var(--color-ai-accent)]">4.</span>
                To update crop health status and trigger risk alerts, use the <strong>Plant Vision</strong> scan
                inside the specific crop&apos;s detail view.
              </li>
            </ol>
          </div>
        )}
      </div>
    </AppShell>
  );
}
