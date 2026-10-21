import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  // Project Pages serves the site from /megs-bedtime-stories/. Local dev stays at /.
  base: process.env.GITHUB_ACTIONS ? "/megs-bedtime-stories/" : "/",
  plugins: [react(), tailwindcss()],
})
