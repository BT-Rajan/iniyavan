const V='et-v1'
self.addEventListener('install',e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(['/','/manifest.json','/icon-192.png'])));self.skipWaiting()})
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==V).map(x=>caches.delete(x)))));self.clients.claim()})
self.addEventListener('fetch',e=>{const r=e.request,u=new URL(r.url)
  if(r.method!=='GET'||u.pathname.startsWith('/api'))return
  if(r.mode==='navigate'){e.respondWith(fetch(r).catch(()=>caches.match('/')));return}
  e.respondWith(caches.match(r).then(h=>h||fetch(r).then(x=>{const c=x.clone();caches.open(V).then(k=>k.put(r,c));return x})))})
