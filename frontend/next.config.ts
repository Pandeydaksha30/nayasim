import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // `npm run build:check` builds into .next-check so it can run while `npm run dev` uses .next.
  // (Building into the dev server's folder breaks it with "Cannot find module './NNN.js'".)
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
