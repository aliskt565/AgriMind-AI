import "@testing-library/jest-dom";

// jsdom does not implement scrollIntoView; this is a well-known gap, and
// polyfilling it here (rather than in each test) matches standard RTL/Next.js
// testing setup guidance.
if (typeof window !== "undefined" && !window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = jest.fn();
}
