import { HTMLAttributes, ReactNode } from "react";
import Link from "next/link";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Reserved for AI Crop Advisor / Plant Vision / Copilot / AI recommendations only -- not for ordinary data cards. */
  aiAccent?: boolean;
}

export function Card({ children, className = "", aiAccent = false, ...props }: CardProps) {
  return (
    <div
      className={`rounded-[var(--radius-md)] border p-5 shadow-[var(--shadow-sm)] transition-shadow duration-[var(--duration-normal)] ease-[var(--ease-standard)] ${
        aiAccent
          ? "border-[var(--color-ai-accent)]/30 bg-[var(--color-ai-accent-soft)] shadow-[var(--shadow-glow-ai)]"
          : "border-[var(--color-border)] bg-[var(--color-surface-raised)]"
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function ClickableCard({ href, children, className = "" }: { href: string; children: ReactNode; className?: string }) {
  return (
    <Link
      href={href}
      className={`block rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-5 shadow-[var(--shadow-sm)] transition-[transform,box-shadow,border-color] duration-[var(--duration-normal)] ease-[var(--ease-standard)] hover:-translate-y-1 hover:border-[var(--color-border-strong)] hover:shadow-[var(--shadow-md)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-brand-strong)] motion-reduce:hover:translate-y-0 ${className}`}
    >
      {children}
    </Link>
  );
}

type BadgeTone = "neutral" | "ai" | "healthy" | "monitoring" | "at-risk" | "critical";

const badgeToneClasses: Record<BadgeTone, string> = {
  neutral: "bg-[var(--color-brand-soft)] text-[var(--color-brand-strong)]",
  ai: "bg-[var(--color-ai-accent-soft)] text-[var(--color-ai-accent-strong)]",
  healthy: "bg-[var(--color-status-healthy)]/12 text-[var(--color-status-healthy)]",
  monitoring: "bg-[var(--color-status-monitoring)]/12 text-[var(--color-status-monitoring)]",
  "at-risk": "bg-[var(--color-status-at-risk)]/12 text-[var(--color-status-at-risk)]",
  critical: "bg-[var(--color-status-critical)]/12 text-[var(--color-status-critical)]",
};

export function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors duration-[var(--duration-fast)] ${badgeToneClasses[tone]}`}
    >
      {children}
    </span>
  );
}

/** Status indicators are never color-only: an icon/glyph always accompanies the color, per accessibility requirements. */
const healthGlyph: Record<string, { glyph: string; tone: BadgeTone }> = {
  HEALTHY: { glyph: "●", tone: "healthy" },
  MONITORING: { glyph: "◐", tone: "monitoring" },
  AT_RISK: { glyph: "▲", tone: "at-risk" },
  DISEASED: { glyph: "✕", tone: "critical" },
};

export function HealthStatusBadge({ status }: { status: string }) {
  const cfg = healthGlyph[status] || healthGlyph.HEALTHY;
  return (
    <Badge tone={cfg.tone}>
      <span aria-hidden className="mr-1">{cfg.glyph}</span>
      {status.replace("_", " ")}
    </Badge>
  );
}

/** Reserved exclusively for AI-generated content, per the design system rule. */
export function AIBadge({ label = "AI generated" }: { label?: string }) {
  return <Badge tone="ai">✨ {label}</Badge>;
}

/** Severity strip for risk-level content -- gives risk cards a strong left-edge
 * accent so high severity is recognizable at a glance, not just via badge color. */
const severityBorder: Record<string, string> = {
  LOW: "border-l-[var(--color-status-healthy)]",
  MODERATE: "border-l-[var(--color-status-monitoring)]",
  HIGH: "border-l-[var(--color-status-at-risk)]",
  CRITICAL: "border-l-[var(--color-status-critical)]",
};

export function riskSeverityBorderClass(level: string): string {
  return severityBorder[level] || severityBorder.LOW;
}
