// The reader page the Android app ships (reader.html, src/reader.jsx): built on its own, with relative paths, into dist-reader/reader,
// which the app's build packs into its assets. npm run build:reader
import {defineConfig} from 'vite'; import react from '@vitejs/plugin-react'
export default defineConfig({base:'./',publicDir:false,plugins:[react()],build:{outDir:'dist-reader/reader',emptyOutDir:true,rollupOptions:{input:'reader.html'}}})
