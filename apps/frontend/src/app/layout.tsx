import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  title: {
    template: "%s | Sentinel",
    default: "Sentinel — Security & Audit Intelligence",
  },
  description:
    "Event-driven security, audit trail, and risk intelligence platform for financial systems.",
  robots: {
    index: false, // Internal platform — do not index
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body
        className={`${geistSans.variable} ${geistMono.variable} h-full bg-gray-950 font-sans text-gray-100 antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
