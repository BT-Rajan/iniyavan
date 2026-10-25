import {defineConfig} from 'vite'; import react from '@vitejs/plugin-react'
export default defineConfig({base:'/app/',plugins:[react()],server:{host:true,proxy:{'/api':'http://localhost:8000'}}})
