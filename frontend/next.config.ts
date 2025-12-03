import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['localhost'],
  },
  // Enable standalone output for Docker
  output: 'standalone',
};

export default nextConfig;
