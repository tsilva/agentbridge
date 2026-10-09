import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  base: '/dashboard/assets/',
  build: {
    outDir: '../agentbridge/static/dashboard',
    emptyOutDir: true,
  },
});
