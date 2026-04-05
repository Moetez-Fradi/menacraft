import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { TopNav } from "./components/top-nav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "sloppy analysis hub",
  description: "User-friendly portal for analyzing claims, context, source credibility, and truth signals",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <TopNav />
        <div className="pointer-events-none fixed inset-0 -z-10 opacity-70 [background:radial-gradient(800px_circle_at_0%_0%,rgba(99,102,241,0.14),transparent_55%),radial-gradient(700px_circle_at_100%_100%,rgba(14,165,233,0.12),transparent_55%)]" />
        {children}
      </body>
    </html>
  );
}
