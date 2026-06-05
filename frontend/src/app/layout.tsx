import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/shared/AppShell";
import { Toaster } from "@/components/ui/sonner";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Pharmasense | Enterprise Drug Demand Forecasting",
  description: "Predicting drug shortages before outbreaks happen.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="scroll-smooth">
      <body
        className={`${inter.variable} font-sans tracking-tight text-[#333333] bg-[#fafafa] antialiased`}
      >
        <AppShell>
          {children}
        </AppShell>
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
