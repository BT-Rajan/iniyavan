// The app's screens in English, Arabic (right to left) or Tamil. Text is written in English in the code and looked up in the dictionaries
// (locales/ar.json, locales/ta.json) by its English wording; anything not translated yet shows in English. {name} marks a value filled in
// when the text is shown, and stays in the translation wherever the language puts it.
const DICTS={},LOAD={ar:()=>import('./locales/ar.json'),ta:()=>import('./locales/ta.json')}  // each dictionary is downloaded only when someone picks it
export async function loadLang(l){if(LOAD[l]&&!DICTS[l])DICTS[l]=(await LOAD[l]()).default}
export const LANGS=[['en','English'],['ar','العربية'],['ta','தமிழ்']]
let lang='en'
const TERMS=new Set(['Semester','Semesters','Year','Years','Grade','Grades','Term','Terms','semester','semesters','year','years','grade','grades','term','terms'])
export const getLang=()=>lang
export const locale=()=>lang==='ar'?'ar-u-nu-latn':lang==='ta'?'ta-IN':undefined  // dates in the language, with the usual digits
export function t(s,vars){
  const d=DICTS[lang];let out=(d&&d[s])||s
  if(vars)out=out.replace(/\{(\w+)\}/g,(m,k)=>vars[k]==null?m:TERMS.has(vars[k])?t(vars[k]):vars[k])  // term words filled in are translated too; names never are
  return out}
export function applyLang(l){
  lang=l==='ar'||l==='ta'?l:'en'
  const r=document.documentElement;r.lang=lang;r.dir=lang==='ar'?'rtl':'ltr'
  try{localStorage.lang=lang}catch{/* private mode: the choice lasts until the page closes */}
  return lang}
export function firstLang(){  // a choice made on this device, else the browser's language
  try{if(localStorage.lang)return localStorage.lang}catch{/* no storage */}
  const n=(navigator.language||'').slice(0,2);return LOAD[n]?n:'en'}
// a table of labels (an object or array, nested) whose text is translated each time it is read, so tables made once at start still follow the language
export const L=o=>new Proxy(o,{get(x,k){const v=x[k];return typeof v==='string'?t(v):v&&typeof v==='object'?L(v):v}})
