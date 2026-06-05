import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  // required when using Svelte components shipped in node_modules
  // especially @lucide/svelte which exports .svelte files
  ssr: {
    noExternal: ['@lucide/svelte']
  }
});
