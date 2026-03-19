import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Interact queries can take 10+ minutes (Wolfram simulations).
  // Default proxy timeout (~2min) is too short.
  experimental: {
    proxyTimeout: 3600_000, // 1 hour in milliseconds
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
