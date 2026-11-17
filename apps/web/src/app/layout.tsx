import type { Metadata } from "next";
import { BRAND } from "@/lib/brand";
import "./globals.css";

const siteUrl =
  process.env.SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "12:12 | Valorant match intelligence",
    template: "%s | 12:12",
  },
  description: BRAND.description,
  applicationName: BRAND.name,
  openGraph: {
    title: "12:12 | Valorant match intelligence",
    description: BRAND.description,
    siteName: BRAND.name,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "12:12 | Valorant match intelligence",
    description: BRAND.description,
  },
};
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
