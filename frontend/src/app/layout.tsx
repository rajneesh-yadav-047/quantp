import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Axon — Quantitative Trading Platform",
  description: "Options strategy builder, backtesting engine, and live trading for Indian markets (NSE/BSE) via SmartAPI",
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
