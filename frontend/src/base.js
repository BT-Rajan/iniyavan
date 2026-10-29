// The folder the site lives under (BASE_PATH on the server, e.g. /zigora), read from where the app was opened: <folder>/app/. Empty at the root.
const p=location.pathname,i=p.lastIndexOf('/app/')
export const ROOT=i>0?p.slice(0,i):''
// a link the server saved as /api/... (pictures, files, interactive pages) reaches it under the folder too
export const at=u=>typeof u==='string'&&u.startsWith('/api/')?ROOT+u:u
export const atHtml=h=>ROOT&&h?h.replace(/(\b(?:src|href)\s*=\s*["']?|url\(\s*["']?)\/api\//gi,'$1'+ROOT+'/api/'):h
