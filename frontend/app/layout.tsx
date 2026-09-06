import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/shell/AppShell";

export const metadata: Metadata = {
  title: "National Weather Intelligence & Decision Support Platform | SIH 2026",
  description:
    "National-scale real-time weather big data analytics, AI event classification, spatiotemporal incident clustering, and grounded WeatherGPT decision support.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-textPrimary font-sans antialiased h-screen w-screen overflow-hidden select-none">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
