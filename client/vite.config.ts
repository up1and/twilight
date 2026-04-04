import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true
      },
      "/tiles": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true
      },
      "/snapshots": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
        ws: false,
        headers: {
          "Access-Control-Allow-Origin": "*"
        }
      }
    }
  }
});
