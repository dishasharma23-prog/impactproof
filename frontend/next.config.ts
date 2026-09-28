import type { NextConfig } from "next";

// The browser talks only to Next.js; /api and /media are forwarded to FastAPI.
// This keeps everything on one address, so a single https tunnel works for phone demos.
const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Checking a photo (upload + AI analysis) can take 10 to 30 seconds.
  experimental: { proxyTimeout: 120_000 },
  // Lets phones open the dev server through a Cloudflare or ngrok tunnel.
  allowedDevOrigins: ["*.trycloudflare.com", "*.ngrok-free.app", "*.ngrok.app"],
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
      { source: "/media/:path*", destination: `${BACKEND_URL}/media/:path*` },
    ];
  },
};

export default nextConfig;
