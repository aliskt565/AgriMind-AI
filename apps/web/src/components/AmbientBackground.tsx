/**
 * Reusable, application-wide animated background.
 *
 * Pure CSS: two blurred, slowly-drifting gradient orbs plus a faint dot-grid
 * texture, layered behind all content (z-index: -1, pointer-events: none).
 * No JS animation loop, no canvas -- CSS transforms + opacity only, so it's
 * GPU-friendly and fully inert under `prefers-reduced-motion` (handled
 * globally in globals.css).
 *
 * `variant` tunes the orb colors/positions per page so each area of the app
 * has a subtle, distinct atmosphere while staying part of one visual
 * language (see globals.css --ambient-a / --ambient-b for the base hues).
 */
type Variant = "dashboard" | "farms" | "field" | "advisor" | "vision" | "copilot" | "auth" | "default";

const VARIANT_STYLE: Record<Variant, { a: string; b: string }> = {
  // AI + data + agriculture balance
  dashboard: { a: "rgba(63,138,84,0.30) 0%, transparent 70%", b: "rgba(139,123,250,0.22) 0%, transparent 70%" },
  // Natural, earthy green landscape atmosphere
  farms: { a: "rgba(63,138,84,0.34) 0%, transparent 70%", b: "rgba(178,138,95,0.16) 0%, transparent 70%" },
  // Agricultural depth and growth
  field: { a: "rgba(79,212,132,0.24) 0%, transparent 70%", b: "rgba(63,138,84,0.20) 0%, transparent 70%" },
  // AI accent glow, futuristic
  advisor: { a: "rgba(139,123,250,0.30) 0%, transparent 70%", b: "rgba(168,155,255,0.18) 0%, transparent 70%" },
  // Vision / scanning atmosphere
  vision: { a: "rgba(168,155,255,0.26) 0%, transparent 70%", b: "rgba(79,212,132,0.16) 0%, transparent 70%" },
  // Subtle AI intelligence glow
  copilot: { a: "rgba(139,123,250,0.28) 0%, transparent 70%", b: "rgba(63,138,84,0.14) 0%, transparent 70%" },
  auth: { a: "rgba(63,138,84,0.30) 0%, transparent 70%", b: "rgba(139,123,250,0.20) 0%, transparent 70%" },
  default: { a: "var(--ambient-a) 0%, transparent 70%", b: "var(--ambient-b) 0%, transparent 70%" },
};

export function AmbientBackground({ variant = "default" }: { variant?: Variant }) {
  const colors = VARIANT_STYLE[variant];
  return (
    <div className="ambient-background" aria-hidden="true" data-atmosphere={variant}>
      <div
        className="ambient-orb ambient-orb--a"
        style={{
          width: "42vw",
          height: "42vw",
          top: "-10%",
          left: "-8%",
          background: `radial-gradient(circle, ${colors.a})`,
        }}
      />
      <div
        className="ambient-orb ambient-orb--b"
        style={{
          width: "36vw",
          height: "36vw",
          bottom: "-12%",
          right: "-6%",
          background: `radial-gradient(circle, ${colors.b})`,
        }}
      />
    </div>
  );
}
