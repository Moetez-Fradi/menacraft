import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MENACRAFT Manual Service Console",
  description: "Manual tester for direct classifier endpoint flows",
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
        <div className="border-b border-zinc-300 px-4 py-3 dark:border-zinc-700 md:px-8">
          <nav className="mx-auto flex w-full max-w-6xl items-center gap-4 text-sm">
            <Link className="font-medium hover:underline" href="/">
              Home
            </Link>
            <Link className="font-medium hover:underline" href="/analyze">
              Analyze Endpoint
            </Link>
            <Link className="font-medium hover:underline" href="/context">
              Context Endpoint
            </Link>
            <Link className="font-medium hover:underline" href="/source-credibility">
              Source Credibility
            </Link>
            <Link className="font-medium hover:underline" href="/truth-retrieval">
              Truth Retrieval
            </Link>
          </nav>
        </div>
        {children}
      </body>
    </html>
  );
}
