import {defineConfig} from 'vite'; import react from '@vitejs/plugin-react'
// built with relative paths, so the same build works at /app/ and under a folder of the site (BASE_PATH, e.g. /zigora/app/)
export default defineConfig(({command})=>({base:command==='build'?'./':'/app/',plugins:[react()],server:{host:true,proxy:{'/api':'http://localhost:8000'}}}))
