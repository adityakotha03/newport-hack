import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const allowedHosts = ["prism.adityakotha.xyz", ".adityakotha.xyz"];

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true, allowedHosts },
  preview: { port: 4173, host: true, allowedHosts },
});
