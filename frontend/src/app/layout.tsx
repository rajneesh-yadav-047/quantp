import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Axon — Quantitative Trading Platform",
  description: "Strategy workspace, backtesting engine, research lab, and live trading for Indian equity markets (NSE/BSE) via SmartAPI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col font-space" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
