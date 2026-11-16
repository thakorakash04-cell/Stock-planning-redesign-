import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {inlineComponent} from './inline-component';
export default defineConfig({plugins:[react(),inlineComponent()],base:'./',build:{outDir:'../frontend_dist',emptyOutDir:true,sourcemap:false,rolldownOptions:{output:{codeSplitting:false}}}});
