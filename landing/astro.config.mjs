// @ts-check
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  site: 'https://thethundergods.github.io',
  base: '/free-lyric-video-creator',
  vite: {
    plugins: [tailwindcss()]
  }
});
