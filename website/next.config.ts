import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for Cloud Run — outputs a self-contained Node.js server
  // in .next/standalone that doesn't need node_modules at runtime
  output: "standalone",
};

export default nextConfig;
