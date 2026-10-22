import type { NextConfig } from "next";

// Static export: the dashboard is plain files served by GitHub Pages from docs/dashboard/.
// In production it lives under /kilnwatch/dashboard; locally (npm run dev) at the root.
const isProd = process.env.NODE_ENV === "production";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? (isProd ? "/kilnwatch/dashboard" : "");

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  images: { unoptimized: true },
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};

export default nextConfig;
