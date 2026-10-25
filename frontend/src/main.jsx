import {createRoot} from 'react-dom/client'; import App from './App.jsx'
createRoot(document.getElementById('root')).render(<App/>)
if('serviceWorker' in navigator&&import.meta.env.PROD)addEventListener('load',()=>navigator.serviceWorker.register(import.meta.env.BASE_URL+'sw.js',{scope:import.meta.env.BASE_URL}))
