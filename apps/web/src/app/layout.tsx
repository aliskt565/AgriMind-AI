import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";

export const metadata: Metadata = {
  title: "AgriMind AI",
  description: "AI-Powered Smart Agriculture & Farm Intelligence Platform",
};

// Runs before paint to avoid a flash of the wrong theme. Reads the persisted
// preference; defaults to dark (the primary, designed-for experience).
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = window.localStorage.getItem("agrimind-theme");
    document.documentElement.setAttribute("data-theme", stored === "light" ? "light" : "dark");
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "dark");
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
