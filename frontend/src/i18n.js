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
// sentences the server builds (focus reasons, deadlines, what needs attention): an exact match first, then these shapes, with the numbers and
// names carried into the translation. Anything else is shown as it came.
const SRV=[
  [/^Test not tried yet · (?<n>\d+) questions$/,'Test not tried yet · {n} questions'],[/^Quiz not tried yet · (?<n>\d+) questions$/,'Quiz not tried yet · {n} questions'],
  [/^Best so far (?<best>\d+)%, pass mark (?<pass>\d+)%$/,'Best so far {best}%, pass mark {pass}%'],[/^You scored (?<p>\d+)% on questions about this$/,'You scored {p}% on questions about this'],
  [/^Overdue by 1 day$/,'Overdue by 1 day'],[/^Overdue by (?<n>\d+) days$/,'Overdue by {n} days'],[/^Due in (?<n>\d+) days$/,'Due in {n} days'],
  [/^1 draft topic not yet visible to students$/,'1 draft topic not yet visible to students'],[/^(?<n>\d+) draft topics not yet visible to students$/,'{n} draft topics not yet visible to students'],
  [/^1 course has no units yet: (?<names>.*)$/,'1 course has no units yet: {names}'],[/^(?<n>\d+) courses have no units yet: (?<names>.*)$/,'{n} courses have no units yet: {names}'],
  [/^1 course has no owner, so only admins can edit: (?<names>.*)$/,'1 course has no owner, so only admins can edit: {names}'],[/^(?<n>\d+) courses have no owner, so only admins can edit: (?<names>.*)$/,'{n} courses have no owner, so only admins can edit: {names}'],
  [/^1 active student is not placed in a program and semester or year, so they see nothing$/,'1 active student is not placed in a program and semester or year, so they see nothing'],
  [/^(?<n>\d+) active students are not placed in a program and semester or year, so they see nothing$/,'{n} active students are not placed in a program and semester or year, so they see nothing'],
  [/^1 semester has no semester number \(set it under Programs\)$/,'1 semester has no semester number (set it under Programs)'],[/^(?<n>\d+) semesters have no semester number \(set it under Programs\)$/,'{n} semesters have no semester number (set it under Programs)'],
  [/^1 active student has never opened a topic$/,'1 active student has never opened a topic'],[/^(?<n>\d+) active students have never opened a topic$/,'{n} active students have never opened a topic'],
  [/^Owner (?<name>.+) is no longer faculty$/,'Owner {name} is no longer faculty'],[/^Owner (?<name>.+) is disabled$/,'Owner {name} is disabled']]
export function srv(s){
  if(typeof s!=='string'||!s)return s
  const d=DICTS[lang];if(!d)return s;if(d[s])return d[s]
  for(const [re,key] of SRV){const m=re.exec(s);if(m&&d[key])return t(key,m.groups||{})}
  return s}
