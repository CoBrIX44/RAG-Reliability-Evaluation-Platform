import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  devIndicators: false,
  output: process.env.STANDALONE_BUILD === "1" ? "standalone" : undefined,
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  poweredByHeader: false,
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "same-origin" },
        { key: "X-Frame-Options", value: "DENY" },
      ],
    }];
  },
};

export default config;
