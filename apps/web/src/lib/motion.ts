import type { CSSProperties } from "react";

/**
 * Reusable stagger utility -- pairs with the `.stagger-item` class in
 * globals.css. Pass the item's index; each item's entrance animation
 * delay is derived from it via a CSS custom property, so no per-list
 * animation code needs to be written by hand.
 *
 * Usage: <li className="stagger-item" style={stagger(i)}>
 */
export function stagger(index: number): CSSProperties {
  return { "--stagger-i": index } as CSSProperties;
}
