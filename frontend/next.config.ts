import type { NextConfig } from "next";

// Where this server forwards /api/* (the FastAPI backend). Read at build time for the Docker
// image (frontend/Dockerfile sets http://api:8000) and at dev-server start locally.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
const dev = process.env.NODE_ENV !== "production";

// Content Security Policy: only this site's own scripts, styles, fonts and API. Next.js needs
// inline scripts for hydration; dev mode also needs eval and a websocket for hot reload.
// Google sign-in is a full-page redirect, so no Google script is ever loaded here.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src 'self'${dev ? " ws: wss:" : ""}`,
  "frame-ancestors 'none'",
  "form-action 'self' https://accounts.google.com",
  "base-uri 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // `npm run build:check` builds into .next-check so it can run while `npm run dev` uses .next.
  // (Building into the dev server's folder breaks it with "Cannot find module './NNN.js'".)
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Self-contained server for the Docker image (frontend/Dockerfile).
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/health", destination: `${API_URL}/health` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
