import {useState,useEffect,useCallback,useRef,createContext,useContext,Children,Fragment,isValidElement,memo} from 'react'
import {createPortal} from 'react-dom'
import Markdown from 'react-markdown'
import remarkMath from 'remark-math'
import remarkGfm from 'remark-gfm'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import 'katex/contrib/mhchem'
// AI answers sometimes arrive with a whole table squeezed onto one line ("| A | B | |---|---| | x | y |"). Put the rows back on their own lines so it renders as a table.
export function fixTables(text){
  return String(text||'').split('\n').map(line=>{
    const t=line.trim(),sep=t.match(/\|\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|/)
    if(!t.startsWith('|')||!sep||t.replace(/[|\s:-]/g,'')==='')return line
    const n=sep[0].split('|').filter(c=>c.trim()).length,cells=t.split('|').slice(1,-1),rows=[];let i=0
    while(i<cells.length){rows.push(cells.slice(i,i+n));i+=n;if(i<cells.length&&cells[i].trim()==='')i++}  // a blank cell marks the end of a row
    if(!n||rows.length<3||rows[1].length!==n||rows[1].some(c=>!/^\s*:?-{3,}:?\s*$/.test(c))||rows.slice(2).some(r=>r.length!==n))return line  // not a squeezed table
    return '\n'+rows.map(r=>'|'+r.join('|')+'|').join('\n')+'\n'
  }).join('\n')
}
const Md=({children})=><Markdown remarkPlugins={[remarkGfm,remarkMath]} rehypePlugins={[rehypeKatex]}>{fixTables(children)}</Markdown>
// a topic's content: Markdown, or HTML from an uploaded file (the server cleans it on every save and every read, so it carries no scripts or styles)
const Body=({text,format})=>format==='html'?<div className="htmlc" dangerouslySetInnerHTML={{__html:text||''}}/>:<Md>{text}</Md>
import {Users as UsersIcon,GraduationCap,Sparkles,BarChart3,Info,LogOut,Menu,X,ArrowUp,ArrowDown,Search,ChevronLeft,ChevronRight,Sun,Moon,Monitor,Upload,Copy,Check,Pencil,Trash2,Bookmark,Link2,Eye,EyeOff,History,TrendingUp,Flame,Clock,AlertTriangle,Play,Target,RotateCcw,ClipboardList,ArrowRight,Archive,ArchiveRestore,Lock,FileText,Bell,BookOpen,Highlighter,Maximize2,Minimize2,Globe} from 'lucide-react'
import '@fontsource/bricolage-grotesque/600.css'
import '@fontsource/bricolage-grotesque/800.css'
import '@fontsource/instrument-sans/400.css'
import '@fontsource/instrument-sans/500.css'
import '@fontsource/instrument-sans/600.css'
import '@fontsource/instrument-sans/700.css'
import '@fontsource/noto-sans-arabic/400.css'
import '@fontsource/noto-sans-arabic/600.css'
import '@fontsource/noto-sans-tamil/400.css'
import '@fontsource/noto-sans-tamil/600.css'
import './styles.css'
import './highlighter.js'
import {t,L,LANGS,locale,applyLang,firstLang,loadLang} from './i18n.js'

const api=async(p,o={})=>{const t=localStorage.t
  const r=await fetch('/api'+p,{...o,headers:{'Content-Type':'application/json',...(t&&{Authorization:'Bearer '+t})},body:o.body&&JSON.stringify(o.body)})
  const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(typeof j.detail==='string'?t(j.detail):t('Something went wrong'));return j}  // the server's messages are looked up like any other text
const TEMPLATE=`program,semester,course,unit,topic,content,question_pattern,sample_content,guideline
B.E. Mechanical Engineering,Semester 3,Thermodynamics,Unit 1: Basic concepts,First law of thermodynamics,"Energy can change form but is never created or destroyed.","2 marks: define. 13 marks: derive and solve a numerical.","Q: State the first law for a closed system.","Introduction, labelled diagram, steps, units, conclusion"
,,,,Zeroth law of thermodynamics,"If A and B are each in equilibrium with C, they are in equilibrium with each other.","2 marks: state the law.","Q: State the zeroth law.","Definition, one example, significance"
`
const COL=['#722f99','#c2464e','#7a6f70','#9a6420','#4e1d6c']
const when=iso=>new Date(iso).toLocaleString(locale(),{day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'})  // shown in the viewer's own time zone
const localInput=iso=>{if(!iso)return '';const d=new Date(iso),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`}
const STATUS=L({not_started:'Not started',in_progress:'In progress',completed:'Completed'})
const doneOf=ts=>t('{done} of {total}',{done:ts.filter(x=>x.status==='completed').length,total:ts.length})  // worked out from each topic's state, never stored
const Mark=({s})=>s==='completed'?<Check className="done" aria-label={t("Completed")}/>:<span className="st" aria-label={STATUS[s]}>{s==='in_progress'?'●':'—'}</span>
const ownerLine=c=>c.mine?'Your course':c.owner_problem||(c.owner?'Owner: '+c.owner:'Owner not assigned')
const useFaculty=on=>{const [l,setL]=useState([]);useEffect(()=>{if(on)api('/admin/users?role=faculty&limit=100').then(r=>setL(r.items.filter(u=>u.active))).catch(()=>{})},[on]);return l}

const firstName=n=>{const w=(n||'').trim().split(/\s+/).filter(Boolean);if(!w.length)return '';if(!/^(dr|prof|mr|mrs|ms|miss)\.?$/i.test(w[0]))return w[0];const rest=w.slice(1).filter(x=>x.replace(/\./g,'').length>1);return rest.length?w[0]+' '+rest[0]:w[0]}  // a title stays with the surname it belongs to ("Dr. A. Kumar" → "Dr. Kumar"), skipping initials
const MAX_FILE_MB=20,tooBig=f=>f.size>MAX_FILE_MB*1024*1024  // the server's limit for one file of study material
const pl=(n,w)=>t(n===1?'{n} '+w:'{n} '+(w==='quiz'?'quizzes':w+'s'),{n})  // "1 topic", "3 topics": each form is its own phrase to translate
const matches=n=>t(n===1?'{n} match':'{n} matches',{n})
const Ctx=createContext({})
const THEMES=L([['system',Monitor,'Auto'],['light',Sun,'Light'],['dark',Moon,'Dark']])
const readTheme=()=>{try{return localStorage.theme||'system'}catch{return 'system'}}
const applyTheme=t=>{const r=document.documentElement;if(t==='light'||t==='dark')r.dataset.theme=t;else delete r.dataset.theme;const dark=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);document.querySelector('meta[name=theme-color]')?.setAttribute('content',dark?'#120e17':'#f6f4f7')}
// the Zigora mark: a Z in cream and coral on plum (the same drawing as public/favicon.svg)
const ZMark=({size=40})=><svg className="zmark" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="#722f99"/><rect x="16" y="15" width="32" height="8" rx="2.5" fill="#fee7c8"/><path d="M38.5 23H48L25.5 41H16Z" fill="#ff9292"/><rect x="16" y="41" width="32" height="8" rx="2.5" fill="#fee7c8"/></svg>
const Logo=({src,size=40})=>src?<img className="logo" src={src} alt="" width={size} height={size} style={{width:size,height:size}}/>:<ZMark size={size}/>
const Lockup=({logo,name,size=40})=><div className="lockup"><Logo src={logo} size={size}/><b>{name}</b></div>
// sign-in, reset and first-password pages: the form, with a brand panel beside it on wide screens
// the language switch: English, Arabic (the whole app turns right to left) or Tamil
const LangSwitch=({lang,pick})=><label className="langsw" title={t("Language")}><Globe size={17} aria-hidden="true"/><select aria-label={t("Language")} value={lang} onChange={e=>pick(e.target.value)}>{LANGS.map(([k,l])=><option key={k} value={k} lang={k}>{l}</option>)}</select></label>
const AuthFrame=({logo,name,children,lang,pick})=><div className="auth"><div className="authlang"><LangSwitch lang={lang} pick={pick}/></div><aside className="authart" aria-hidden="true"><Lockup logo={logo} name={name} size={44}/>
  <div><h2>{t("Learn engineering, one topic at a time.")}</h2><p>{t("Courses, notes, practice tests and progress for every program, semester and student, in one place.")}</p></div>
  <div className="bands"><i style={{background:'#722f99'}}/><i style={{background:'#c5c1c1'}}/><i style={{background:'#fee7c8'}}/><i style={{background:'#ff9292'}}/></div></aside>{children}</div>

export default function App(){
  const [user,setUser]=useState(null),[ready,setReady]=useState(false),[pageSel,setPage]=useState(null),[msg,setMsg]=useState(''),[open,setOpen]=useState(false),[name,setName]=useState('Zigora'),[canReset,setCanReset]=useState(false),[canReg,setCanReg]=useState(false),[resetTok,setResetTok]=useState(()=>(/^#reset=([\w-]+)$/.exec(location.hash)||[])[1]||null),[start,setStart]=useState(null),[logo,setLogo]=useState(null),[theme,setTheme]=useState(readTheme),[ask,setAsk]=useState(null),[studyStart,setStudyStart]=useState(null),[findQ,setFindQ]=useState({q:'',n:0}),[lang,setLangS]=useState(()=>applyLang(firstLang())),picked=useRef(false)
  const confirm=useCallback(o=>new Promise(res=>setAsk({o,res})),[])  // in-app replacement for window.confirm: await confirm({title,body,ok,danger})
  const toast=useCallback(m=>{setMsg(m);setTimeout(()=>setMsg(''),2800)},[])
  const pickLang=useCallback(async l=>{picked.current=true;await loadLang(l).catch(()=>{});setLangS(applyLang(l));api('/me/lang',{method:'PUT',body:{lang:l}}).catch(()=>{/* signed out: kept on this device until sign-in */})},[])
  useEffect(()=>{if(!user)return  // signed in: a language picked just now goes to the account; otherwise the account's language is used
    if(picked.current&&user.lang!==lang)api('/me/lang',{method:'PUT',body:{lang}}).catch(()=>{})
    else if(!picked.current&&user.lang&&user.lang!==lang)loadLang(user.lang).catch(()=>{}).then(()=>setLangS(applyLang(user.lang)))},[user])
  useEffect(()=>{Promise.allSettled([loadLang(lang),api('/config').then(c=>{setName(c.name);setLogo(c.logo||null);setCanReset(!!c.email_reset);setCanReg(!!c.self_registration);document.title=c.name}),localStorage.t?api('/me').then(setUser).catch(()=>localStorage.removeItem('t')):null]).then(()=>setReady(true))},[])
  useEffect(()=>{applyTheme(theme);if(theme!=='system')return;const m=matchMedia('(prefers-color-scheme: dark)'),f=()=>applyTheme('system');m.addEventListener('change',f);return()=>m.removeEventListener('change',f)},[theme])
  const pickTheme=t=>{setTheme(t);try{t==='system'?localStorage.removeItem('theme'):localStorage.theme=t}catch{/* private mode: the choice lasts until the page closes */}}
  useEffect(()=>{const k=e=>e.key==='Escape'&&setOpen(false);addEventListener('keydown',k);return()=>removeEventListener('keydown',k)},[])
  useEffect(()=>{document.body.style.overflow=open?'hidden':''},[open])
  if(!ready)return null
  if(resetTok)return <AuthFrame logo={logo} name={name} lang={lang} pick={pickLang}><ResetPassword token={resetTok} toast={toast} msg={msg} canReset={canReset} appName={name} logo={logo} done={u=>{history.replaceState(null,'',location.pathname);setResetTok(null);setUser(u);toast(t("Password changed. You are signed in."))}} leave={()=>{history.replaceState(null,'',location.pathname);setResetTok(null)}}/></AuthFrame>
  if(!user)return <AuthFrame logo={logo} name={name} lang={lang} pick={pickLang}><Login onIn={setUser} toast={toast} msg={msg} appName={name} logo={logo} canReset={canReset} canReg={canReg}/></AuthFrame>
  if(user.must_change)return <AuthFrame logo={logo} name={name} lang={lang} pick={pickLang}><ChangePassword forced appName={name} logo={logo} toast={toast} msg={msg} done={()=>setUser({...user,must_change:false})} out={()=>{localStorage.removeItem('t');setUser(null)}}/></AuthFrame>
  const student=user.role==='student',page=pageSel||'home',admin=user.role==='admin',go=k=>{if(k==='build')setStudyStart(null);setPage(k);setOpen(false)},openIn=nav=>{setStart(nav);go('learn')},openStudy=t=>{setPage('build');setOpen(false);setStudyStart(t)},find=q=>{setFindQ(f=>({q,n:f.n+1}));go('search')},signOut=()=>{localStorage.removeItem('t');setOpen(false);setPage(null);setUser(null)}
  // the side menu (the logo goes Home; search, change password, theme and sign out are in the header)
  const links=student?[['learn',GraduationCap,'My courses'],['routine',Clock,'My routine'],['progress',TrendingUp,'My progress'],['build',Upload,'Build a course'],['bookmarks',Bookmark,'Bookmarks'],['highlights',Highlighter,'My highlights'],...(user.self_registered?[['aikey',Sparkles,'My AI key']]:[]),['about',Info,'About']]
    :admin?[['programs',GraduationCap,'Programs'],['courses',BookOpen,'Courses'],['users',UsersIcon,'Users'],['reports',BarChart3,'Reports'],['activity',History,'Activity log'],['ai',Sparkles,'Settings'],['about',Info,'About']]
    :[['learn',BookOpen,'Courses'],['bookmarks',Bookmark,'Bookmarks'],['highlights',Highlighter,'My highlights'],['reports',BarChart3,'Reports'],...(user.self_registered?[['aikey',Sparkles,'My AI key']]:[]),['about',Info,'About']]
  return <Ctx.Provider value={{menu:()=>setOpen(true),appName:name,confirm}}>
    <TopBar user={user} lang={lang} pickLang={pickLang} theme={theme} pickTheme={pickTheme} onMenu={()=>setOpen(true)} onHome={()=>go('home')} onAccount={()=>go('password')} onOut={signOut} onNote={()=>go('home')} page={page}/>
    {page!=='search'&&<GlobalSearch key={findQ.n} onFind={find}/>}
    <div id="pageslot"/>
    {page==='home'&&student&&<Dashboard user={user} toast={toast} onOpen={openIn} onSearch={()=>go('search')} onStudy={openStudy} onRoutine={()=>go('routine')}/>}
    {page==='routine'&&student&&<RoutinePage toast={toast} done={()=>go('home')}/>}
    {page==='home'&&!student&&<StaffHome user={user} toast={toast} open={openIn}/>}
    {page==='search'&&<SearchPage key={findQ.n} initial={findQ.q} user={user} toast={toast}/>}{page==='learn'&&<Learn key={String(start)} start={start} user={user} toast={toast} appName={name}/>}
    {page==='progress'&&user.role==='student'&&<Insights toast={toast} role={user.role}/>}
    {page==='build'&&user.role==='student'&&<StudyHome key={JSON.stringify(studyStart)} start={studyStart} toast={toast}/>}
    {page==='bookmarks'&&!admin&&<Bookmarks toast={toast} role={user.role}/>}{page==='highlights'&&!admin&&<MyHighlights toast={toast} role={user.role}/>}
    {page==='users'&&admin&&<Users toast={toast} me={user}/>}{page==='courses'&&admin&&<AdminCourses toast={toast} onOpen={openIn}/>}{page==='programs'&&admin&&<Programs toast={toast} onOpen={openIn}/>}
    {page==='ai'&&admin&&<AiConfig toast={toast} onBrand={()=>api('/config').then(c=>{setName(c.name);setLogo(c.logo||null);document.title=c.name})}/>}{page==='reports'&&(admin||user.role==='faculty')&&<Reports role={user.role} toast={toast}/>}{page==='activity'&&admin&&<Activity/>}{page==='aikey'&&user.self_registered&&<MyAiKey toast={toast}/>}{page==='password'&&<ChangePassword toast={toast} done={()=>go('learn')}/>}{page==='about'&&<About user={user}/>}
    <div className={'drawer'+(open?' open':'')}><div className="dscrim" onClick={()=>setOpen(false)}/>
      <nav className="panel" aria-label={t("Main menu")}>
        <div className="dhead"><button className={'homebtn'+(page==='home'?' on':'')} aria-label={t("{name}, home",{name:name})} aria-current={page==='home'?'page':undefined} onClick={()=>go('home')}><Logo src={logo} size={36}/><span><b>{name}</b><small>{user.name}, {user.role}</small></span></button><button className="ic" aria-label={t("Close menu")} onClick={()=>setOpen(false)}><X/></button></div>
        {links.map(([k,I,l])=><button key={k} className={'dlink'+(page===k?' on':'')} onClick={()=>{if(k==='learn')setStart(null);go(k)}}><I size={20}/>{t(l)}</button>)}
      </nav></div>
    <footer className="foot"><span>{t("© {v} {name}. All rights reserved.",{v:new Date().getFullYear(),name:name})}</span></footer>
    <Toast msg={msg}/>
    {ask&&<Confirm o={ask.o} answer={ok=>{ask.res(ok);setAsk(null)}}/>}
  </Ctx.Provider>}

function Login({onIn,toast,msg,appName,logo,canReset,canReg}){
  const [f,setF]=useState({email:'',password:''}),[b,setB]=useState(false),[mode,setMode]=useState('in'),[sent,setSent]=useState('')
  const go=async()=>{setB(true);try{const r=await api('/login',{method:'POST',body:f});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  const forgot=async()=>{setB(true);try{setSent((await api('/forgot',{method:'POST',body:{email:f.email}})).message)}catch(e){toast(e.message)}setB(false)}
  if(mode==='register')return <Register onIn={onIn} toast={toast} msg={msg} appName={appName} logo={logo} back={()=>setMode('in')}/>
  if(mode==='forgot')return <div className="login"><Lockup logo={logo} name={appName}/><h1>{t("Forgot your password?")}</h1>{sent?<p>{sent}</p>:<><p>{t("Enter your account email and we will send a link to choose a new one.")}</p>
    <label>{t("Email")}</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})} onKeyDown={e=>e.key==='Enter'&&forgot()}/>
    <button className="btn" disabled={b||!f.email} onClick={forgot}>{t("Send reset link")}</button></>}
    <button className="btn ghost" onClick={()=>{setMode('in');setSent('')}}>{t("Back to sign in")}</button><Toast msg={msg}/></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>{t("Sign in")}</h1><p>{t("Use the account your institution created for you.")}</p>
    <label>{t("Email")}</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})}/>
    <label>{t("Password")}</label><input type="password" autoComplete="current-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>{t("Sign in")}</button>
    {canReset?<button className="btn ghost" onClick={()=>setMode('forgot')}>{t("Forgot password?")}</button>:<p className="known">{t("Forgot your password? Ask your admin to reset it.")}</p>}{canReg&&<button className="btn ghost" onClick={()=>setMode('register')}>{t("Create an account")}</button>}<Toast msg={msg}/></div>}

function Register({onIn,toast,msg,appName,logo,back}){
  const [f,setF]=useState({name:'',institution:'',id_number:'',email:'',phone:'',password:''}),[stage,setStage]=useState('form'),[code,setCode]=useState(''),[b,setB]=useState(false),[wait,setWait]=useState(0),[info,setInfo]=useState(''),[st,setSt]=useState({domains:[]})
  useEffect(()=>{api('/register/status').then(setSt).catch(()=>{})},[])
  useEffect(()=>{if(wait<=0)return;const t=setTimeout(()=>setWait(wait-1),1000);return()=>clearTimeout(t)},[wait])
  const set=k=>e=>setF({...f,[k]:e.target.value}),ok=Object.values(f).every(v=>v.trim())
  const start=async()=>{setB(true);try{const r=await api('/register/start',{method:'POST',body:f});setInfo(r.message);setStage('code');setWait(30)}catch(e){toast(e.message)}setB(false)}
  const verify=async()=>{setB(true);try{const r=await api('/register/verify',{method:'POST',body:{email:f.email,code}});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  const resend=async()=>{try{await api('/register/resend',{method:'POST',body:{email:f.email}});toast(t("A new code is on its way"));setWait(30);setCode('')}catch(e){toast(e.message)}}
  if(stage==='code')return <div className="login"><Lockup logo={logo} name={appName}/><h1>{t("Enter the code")}</h1><p>{info}</p>
    <label htmlFor="otp">{t("6-digit code")}</label><input id="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} onKeyDown={e=>e.key==='Enter'&&code.length===6&&verify()} style={{letterSpacing:'.4em',fontSize:22,textAlign:'center'}}/>
    <button className="btn" disabled={b||code.length!==6} onClick={verify}>{t("Verify and create my account")}</button>
    <button className="btn ghost" disabled={wait>0} onClick={resend}>{wait>0?t("Send a new code in {wait}s",{wait:wait}):t("Send a new code")}</button>
    <button className="btn ghost" onClick={()=>{setStage('form');setCode('')}}>{t("Change my details")}</button><Toast msg={msg}/></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>{t("Create an account")}</h1><p>{t("We will email you a code to confirm your address.")}{st.domains.length>0&&t(" Use your institution email ({domains}).",{domains:st.domains.map(d=>'@'+d).join(', ')})}</p>
    <label htmlFor="rn">{t("Full name")}</label><input id="rn" autoComplete="name" value={f.name} onChange={set('name')}/>
    <label htmlFor="ri">{t("Institution")}</label><input id="ri" autoComplete="organization" value={f.institution} onChange={set('institution')}/>
    <label htmlFor="rid">{t("ID number")}</label><input id="rid" value={f.id_number} onChange={set('id_number')} placeholder={t("Roll or employee number")}/>
    <label htmlFor="re">{t("Email")}</label><input id="re" type="email" autoComplete="email" value={f.email} onChange={set('email')}/>
    <label htmlFor="rp">{t("Phone")}</label><input id="rp" type="tel" autoComplete="tel" value={f.phone} onChange={set('phone')} placeholder="+91 98765 43210"/>
    <label htmlFor="rw">{t("Password")}</label><input id="rw" type="password" autoComplete="new-password" value={f.password} onChange={set('password')} onKeyDown={e=>e.key==='Enter'&&ok&&start()}/>
    <p className="known">{t("At least 8 characters. AI help on this account uses your own DeepSeek API key, which you add after signing in.")}</p>
    <button className="btn" disabled={b||!ok} onClick={start}>{t("Send me a code")}</button><button className="btn ghost" onClick={back}>{t("Back to sign in")}</button><Toast msg={msg}/></div>}

function MyAiKey({toast}){
  const confirm=useConfirm()
  const [d,setD]=useState(null),[key,setKey]=useState(''),[b,setB]=useState(false)
  const load=()=>api('/me/ai-key').then(setD).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  const save=async()=>{setB(true);try{await api('/me/ai-key',{method:'PUT',body:{key}});setKey('');toast(t("Key saved. AI help is on."));load()}catch(e){toast(e.message)}setB(false)}
  const del=async()=>{if(!await confirm({title:t("Remove your key?"),body:t("AI help turns off for you until you add one again."),ok:t("Remove key"),danger:true}))return;try{await api('/me/ai-key',{method:'DELETE'});toast(t("Key removed"));load()}catch(e){toast(e.message)}}
  return <><Bar title={t("My AI key")} sub={d?.key_set?t("AI is on · key {key_hint}",{key_hint:d.key_hint}):t("AI is off · no key yet")}/><div className="main">
    <p className="known">{t("AI explanations on your account use your own DeepSeek API key, so any usage is billed to your DeepSeek account. Create a key at platform.deepseek.com, paste it here and save. We check it with DeepSeek first, then store it encrypted. It is never shown again in full.")}</p>
    <label htmlFor="k">{t("DeepSeek API key")}</label><input id="k" type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder={d?.key_set?t("Paste a new key to replace the current one"):t("sk-…")}/>
    <button className="btn" disabled={b||!key.trim()} onClick={save}>{b?t("Checking the key…"):t("Save key")}</button>
    {d?.key_set&&<button className="btn ghost" onClick={del}>{t("Remove my key")}</button>}</div></>}

function PromptEditor({toast}){
  const confirm=useConfirm()
  const [items,setItems]=useState(null),[draft,setDraft]=useState({}),[busy,setBusy]=useState('')
  const load=()=>api('/admin/prompts').then(r=>{setItems(r.items);setDraft({})}).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  if(!items)return <div className="sk"/>
  const save=async x=>{const text=draft[x.kind];if(x.saved_answers>0&&!await confirm({title:t("Save this prompt?"),body:t("Saving discards the {n} written with the old prompt, so students get fresh ones.",{n:pl(x.saved_answers,'saved answer')}),ok:t("Save prompt")}))return
    setBusy(x.kind);try{const r=await api('/admin/prompts/'+x.kind,{method:'PUT',body:{text}});toast(t("Prompt saved{v}",{v:r.cleared?` · ${pl(r.cleared,'saved answer')} cleared`:''}));load()}catch(e){toast(e.message)}setBusy('')}
  const reset=async x=>{if(!await confirm({title:t("Go back to the built-in prompt?"),body:x.saved_answers?t("This also discards {n}.",{n:pl(x.saved_answers,'saved answer')}):null,ok:t("Reset to built-in")}))return
    setBusy(x.kind);try{await api('/admin/prompts/'+x.kind,{method:'DELETE'});toast(t("Back to the built-in prompt"));load()}catch(e){toast(e.message)}setBusy('')}
  return <><p className="known">{t("These are the instructions the AI gets before it answers. Change the tone, depth, language or format to suit your students. Saving a prompt discards the saved answers it wrote, so the new wording applies from the next question (that costs tokens again).")}</p>
    {items.map(x=>{const v=draft[x.kind]??x.text,dirty=v.trim()!==x.text.trim()
      return <div key={x.kind} className="qbox"><b>{x.label}{x.custom&&<span className="chip" style={{marginLeft:8}}>{t("Edited")}</span>}</b><p className="known" style={{margin:'4px 0 8px'}}>{x.help}</p>
        <textarea aria-label={t("{label} prompt",{label:x.label})} rows={9} value={v} maxLength={4000} onChange={e=>setDraft({...draft,[x.kind]:e.target.value})}/>
        <small className="known">{v.length}{" "}{t("/ 4000 characters")}</small>
        <div className="two"><button className="btn" disabled={!dirty||busy===x.kind||v.trim().length<20} onClick={()=>save(x)}>{t("Save prompt")}</button><button className="btn ghost" disabled={busy===x.kind||(!x.custom&&!dirty)} onClick={()=>x.custom?reset(x):setDraft({...draft,[x.kind]:x.default})}>{x.custom?t("Reset to built-in"):t("Undo changes")}</button></div></div>})}</>}

function SelfReg({cfg,run}){
  const [dom,setDom]=useState(null);const on=!!cfg.self_registration,shown=dom??cfg.allowed_domains??''
  return <><p className="known">{on?t("On. The sign-in page shows “Create an account”. People confirm their email with a code, then you place them in a program and semester or year from Users (they show as Self-registered)."):t("Off. Only admins can create accounts.")} {!cfg.mail_on&&t("Emailing codes needs SMTP set up first (see the email section below), so registration stays closed until it is.")} {cfg.self_registered_users>0&&t("{self_registered_users} people have registered themselves so far.",{self_registered_users:cfg.self_registered_users})}</p>
    <label className="chk"><input type="checkbox" checked={on} onChange={e=>run(()=>api('/admin/settings',{method:'PUT',body:{self_registration:e.target.checked}}),e.target.checked?'Self-registration is on':'Self-registration is off')}/>{" "}{t("Allow people to register themselves")}</label>
    <label htmlFor="dom">{t("Only these email domains (optional)")}</label><input id="dom" value={shown} onChange={e=>setDom(e.target.value)} placeholder={t("college.edu, mail.college.edu")}/>
    <button className="btn ghost" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{allowed_domains:shown}}).then(()=>setDom(null)),'Domains saved')}>{t("Save domains")}</button>
    <p className="known">{t("Self-registered people always use their own DeepSeek key, never yours.")}</p></>}

function ResetPassword({token,toast,msg,done,leave,canReset,appName,logo}){
  const [ok,setOk]=useState(null),[f,setF]=useState({password:'',again:''}),[b,setB]=useState(false)
  useEffect(()=>{api('/reset/check',{method:'POST',body:{token}}).then(r=>setOk(r.valid)).catch(()=>setOk(false))},[token])
  const go=async()=>{if(f.password.length<8)return toast(t("Use at least 8 characters"));if(f.password!==f.again)return toast(t("The passwords don't match"))
    setB(true);try{const r=await api('/reset',{method:'POST',body:{token,new_password:f.password}});localStorage.t=r.token;done(r.user)}catch(e){toast(e.message)}setB(false)}
  if(ok===null)return null
  if(!ok)return <div className="login"><Lockup logo={logo} name={appName}/><h1>{t("This link has expired")}</h1><p>{t("Reset links work once and only for a short time.")}{canReset?t(" Ask for a new one from the sign-in page."):t(" Ask your admin to reset your password.")}</p><button className="btn" onClick={leave}>{t("Go to sign in")}</button></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>{t("Choose a new password")}</h1><p>{t("Use at least 8 characters.")}</p>
    <label>{t("New password")}</label><input type="password" autoComplete="new-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})}/>
    <label>{t("Repeat new password")}</label><input type="password" autoComplete="new-password" value={f.again} onChange={e=>setF({...f,again:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>{t("Save and sign in")}</button><Toast msg={msg}/></div>}

function ChangePassword({forced,appName,logo,toast,msg,done,out}){
  const [f,setF]=useState({current:'',password:'',again:''}),[b,setB]=useState(false),set=k=>e=>setF({...f,[k]:e.target.value})
  const go=async()=>{if(f.password.length<8)return toast(t("Use at least 8 characters"));if(f.password!==f.again)return toast(t("The new passwords don't match"))
    setB(true);try{const d=await api('/me/password',{method:'POST',body:{current:f.current,new_password:f.password}});if(d.token)localStorage.t=d.token;toast(t("Password changed"));done()}catch(e){toast(e.message)}setB(false)}
  const form=<><label>{forced?t("Password your admin gave you"):t("Current password")}</label><input type="password" autoComplete="current-password" value={f.current} onChange={set('current')}/>
    <label>{t("New password (8+ characters)")}</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/>
    <label>{t("Repeat new password")}</label><input type="password" autoComplete="new-password" value={f.again} onChange={set('again')} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>{t("Change password")}</button></>
  if(forced)return <div className="login"><Lockup logo={logo} name={appName}/><h1>{t("Choose your own password")}</h1><p>{t("Your admin set a temporary password. Pick a new one to continue.")}</p>{form}<button className="btn ghost" onClick={out}>{t("Sign out")}</button><Toast msg={msg}/></div>
  return <><Bar title={t("Change password")}/><div className="main">{form}</div></>}

const Bar=({title,sub,back,right})=><div className="bar">{back&&<button className="ic" aria-label={t("Back")} onClick={back}><ChevronLeft/></button>}
  <h1>{title}{sub&&<small>{sub}</small>}</h1>{right}</div>
// the header on every signed-in page: menu (phone), notifications, theme, the signed-in user (opens Change password) and sign out at the far right
const initials=n=>(n||'?').trim().split(/\s+/).filter(w=>!/^(dr|prof|mr|mrs|ms|miss)\.?$/i.test(w)).slice(0,2).map(w=>w[0]).join('').toUpperCase()||'?'
function TopBar({user,lang,pickLang,theme,pickTheme,onMenu,onHome,onAccount,onOut,onNote,page}){
  const {appName}=useContext(Ctx),i=THEMES.findIndex(t=>t[0]===theme),[,ThemeIcon,themeLabel]=THEMES[i<0?0:i],nextTheme=THEMES[(i+1)%THEMES.length]
  return <header className="top"><button className="ic menu" aria-label={t("Open menu")} onClick={onMenu}><Menu/></button><button className="topname" onClick={onHome}>{appName}</button>
    <span className="topgap"/>
    <Notifications onOpen={onNote} page={page}/>
    <LangSwitch lang={lang} pick={pickLang}/>
    <button className="ic" aria-label={t("Theme: {themeLabel}. Switch to {v}",{themeLabel:themeLabel,v:nextTheme[2]})} title={t("Theme: {themeLabel}",{themeLabel:themeLabel})} onClick={()=>pickTheme(nextTheme[0])}><ThemeIcon size={19}/></button>
    <button className={'who'+(page==='password'?' on':'')} onClick={onAccount} title={t("Change password")}><span className="av" aria-hidden="true">{initials(user.name)}</span><span className="whotx"><b>{user.name}</b><small>{user.role}</small></span></button>
    <button className="ic" aria-label={t("Sign out")} title={t("Sign out")} onClick={onOut}><LogOut size={19}/></button></header>}
// what needs doing: staff get the overview's attention list, students their overdue and due-soon topics and untried or failed tests
// what needs doing (worked out by the server): staff get the overview's attention list, students their deadlines and tests. The badge counts
// only the ones not seen yet; opening the list marks them seen. Where the server can send email, a daily summary can be switched on here.
function Notifications({onOpen,page}){
  const [d,setD]=useState(null),[open,setOpen]=useState(false),box=useRef(null)
  const load=useCallback(()=>api('/me/notifications').then(setD).catch(()=>setD({items:[]})),[])
  useEffect(()=>{load()},[load,page])
  useEffect(()=>{const t=setInterval(load,120000),f=()=>document.visibilityState==='visible'&&load();document.addEventListener('visibilitychange',f);return()=>{clearInterval(t);document.removeEventListener('visibilitychange',f)}},[load])  // fresh every 2 minutes, and on coming back to the tab
  useEffect(()=>{if(!open)return;const f=e=>{if(!box.current?.contains(e.target))setOpen(false)},k=e=>e.key==='Escape'&&setOpen(false);addEventListener('pointerdown',f);addEventListener('keydown',k);return()=>{removeEventListener('pointerdown',f);removeEventListener('keydown',k)}},[open])
  const items=d?.items||[],n=items.filter(x=>x.unread).length
  const toggle=async()=>{if(open){setOpen(false);load();return}  // closing: the bold ones are seen now
    setOpen(true);try{const r=await api('/me/notifications');setD(r);const keys=r.items.filter(x=>x.unread).map(x=>x.key)  // what is shown now is what gets marked seen
      if(keys.length)await api('/me/notifications/seen',{method:'POST',body:{keys}})}catch{/* the list stays as it was */}}
  const digest=async on=>{try{const r=await api('/me/notifications/settings',{method:'PUT',body:{digest:on}});setD(x=>({...x,digest:r.digest}))}catch(e){alert(e.message)}}
  return <div className="notes" ref={box}><button className="ic" aria-label={n?t("Notifications, {n} new",{n:n}):t("Notifications")} aria-expanded={open} onClick={toggle}><Bell size={19}/>{n>0&&<em className="badge">{n>9?'9+':n}</em>}</button>
    {open&&<div className="pop" role="dialog" aria-label={t("Notifications")}><b className="poph">{t("Notifications")}{n>0&&<small>{" "}{t("· {n} new",{n:n})}</small>}</b>
      {d===null?<Skeleton/>:items.length?items.map(x=><button key={x.key} className={'note'+(x.unread?' new':'')} onClick={()=>{setOpen(false);load();onOpen()}}><span>{x.text}</span>{x.sub&&<small>{x.sub}</small>}</button>):<p className="known">{t("You're all caught up.")}</p>}
      {d?.mail&&<label className="chk notemail"><input type="checkbox" checked={!!d.digest} onChange={e=>digest(e.target.checked)}/>{" "}{t("Email me a daily summary of new ones")}</label>}</div>}</div>}
// the search box under the header on every page: Enter opens Search with the query
function GlobalSearch({onFind}){
  const [q,setQ]=useState('')
  return <form className="gsearch" role="search" onSubmit={e=>{e.preventDefault();if(q.trim().length>=2)onFind(q.trim())}}><div className="search"><Search size={18}/><input type="search" aria-label={t("Search topics")} placeholder={t("Search topics, or ask a question")} value={q} maxLength={200} onChange={e=>setQ(e.target.value)}/></div></form>}

const ARCHIVE_WHAT=L({programs:'every semester or year, course, unit, topic and quiz in it',semesters:'every course, unit, topic and quiz in it',courses:'its units, topics and quizzes',units:'its topics and quizzes',topics:'this topic'})
const ONE=L({programs:'program',semesters:'semester or year',courses:'course',units:'unit',topics:'topic'})
function ArchiveSheet({a,close,done,toast}){  // archive or restore one item; archiving takes everything under it along, nothing is deleted
  const [busy,setBusy]=useState(false)
  const go=async()=>{setBusy(true);try{await api(`/${a.kind}/${a.id}/archive`,{method:'PUT',body:{archived:a.on}});toast(a.on?t("Archived"):t("Restored"));done()}catch(e){toast(e.message);setBusy(false)}}
  return <Sheet close={close}><h3>{a.on?t("Archive"):t("Restore")} “{a.name}”?</h3>
    <p className="known">{a.on?t("This hides the {v} and {v2} from students, who see “unavailable right now” instead. Nothing is deleted and reading progress and quiz results are kept. You can restore it any time.",{v:ONE[a.kind],v2:ARCHIVE_WHAT[a.kind]})
      :t("This brings back the {v} and everything that was archived along with it. Anything you archived on its own inside it stays archived until you restore that too.",{v:ONE[a.kind]})}</p>
    <button className={'btn'+(a.on?' danger':'')} disabled={busy} onClick={go}>{busy?t("Working…"):a.on?t("Archive"):t("Restore")}</button><button className="btn ghost" onClick={close}>{t("Cancel")}</button></Sheet>}
const ArchPill=({x})=>x.archived?<span className="pill off sm">{x.archived_self?t("Archived"):t("Archived with its parent")}</span>:null
function Learn({user,toast,appName,start}){
  const isAdmin=user.role==='admin',staff=user.role!=='student'
  const [mat,setMat]=useState(false)
  const [bulk,setBulk]=useState(null),[copy,setCopy]=useState(null),[tree,setTree]=useState([]),[nav,setNav]=useState(start||[]),[sheet,setSheet]=useState(null),[cp,setCp]=useState(null),[t,setT]=useState(null),[ed,setEd]=useState(null),[del,setDel]=useState(null),[sh,setSh]=useState(null),[qz,setQz]=useState(null),[qe,setQe]=useState(null),[arch,setArch]=useState(null),[showArch,setShowArch]=useState(false),[qr,setQr]=useState(null),[gb,setGb]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t,ed,qz,qe,sheet,arch,qr])
  const landed=useRef(!!start?.length);useEffect(()=>{if(landed.current||user.role!=='student'||tree.length!==1)return;landed.current=true;const p=tree[0],c=p.semesters.find(x=>x.current)||(p.semesters.length===1?p.semesters[0]:null);setNav(c?[p.id,c.id]:[p.id])},[tree])
  const prog=tree.find(x=>x.id===nav[0]),sem=prog?.semesters.find(x=>x.id===nav[1]),co=sem?.courses.find(x=>x.id===nav[2]),unit=co?.units.find(x=>x.id===nav[3])
  const mayEdit=isAdmin||(user.role==='faculty'&&!!co?.editable)
  useEffect(()=>{setCp(null);if(co&&mayEdit&&!co.shared)api(`/courses/${co.id}/progress`).then(setCp).catch(()=>{})},[co?.id,mayEdit,t])
  if(mat&&co)return <MyMaterial cid={co.id} name={co.name} back={()=>{setMat(false);load()}} toast={toast}/>
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast} role={user.role}/>
  if(qz)return <QuizPlay id={qz} back={()=>setQz(null)} toast={toast} role={user.role}/>
  if(qe)return <QuizEditor {...qe} done={()=>setQe(null)} toast={toast}/>
  if(qr)return <QuizResults id={qr} back={()=>setQr(null)} toast={toast} role={user.role}/>
  if(gb)return <Gradebook cid={gb} back={()=>setGb(null)} toast={toast} role={user.role}/>
  if(ed)return <TopicEditor role={user.role} toast={toast} edit={ed.id?ed:null} unitId={ed.unit_id} done={()=>setEd(null)} cancel={()=>setEd(null)}/>
  const tsub=x=>[x.published===false&&'Draft · students cannot see it',x.learning_due_at?'Due '+when(x.learning_due_at):!staff&&'No deadline',x.overdue&&!staff&&'Overdue',
    cp?.topics[x.id]&&`${cp.topics[x.id].completed}/${cp.students} completed`+(cp.topics[x.id].overdue?` · ${cp.topics[x.id].overdue} overdue`:'')].filter(Boolean).join(' · ')
  const row=(x,kind,one,sub,extra={})=>({id:x.id,n:x.name,sub,kind,archived:x.archived,archived_self:x.archived_self,locked:!staff&&kind==='courses'&&x.archived,can:kind==='programs'||kind==='semesters'?isAdmin:kind==='courses'?(isAdmin||x.mine)&&!x.shared:mayEdit&&!co?.shared,go:()=>setNav([...nav,x.id]),edit:()=>setEd({kind:one,id:x.id,name:x.name,...extra})})
  const drafts=t=>t.filter(x=>x.published===false).length
  const setPub=async(url,published,msg)=>{try{await api(url,{method:'PUT',body:{published}});toast(msg);load()}catch(e){toast(e.message)}}
  const move=async(items,i,d,url)=>{const ids=items.map(x=>x.id),j=i+d;if(j<0||j>=ids.length)return;[ids[i],ids[j]]=[ids[j],ids[i]];try{await api(url,{method:'PUT',body:{ids}});load()}catch(e){toast(e.message)}}
  const list0=unit?unit.topics.map(x=>({id:x.id,n:x.title,s:x.status,b:x.bookmarked,kind:'topics',archived:x.archived,archived_self:x.archived_self,can:mayEdit&&!co.shared,sub:tsub(x),late:x.overdue,draft:x.published===false,go:()=>setT(x.id),edit:()=>setEd({id:x.id}),pub:()=>setPub(`/topics/${x.id}/publish`,x.published===false,x.published===false?'Published':'Moved to drafts')}))
    :co?co.units.map(x=>({...row(x,'units','unit',staff?x.topics.length+' topics'+(mayEdit&&drafts(x.topics)?' · '+drafts(x.topics)+' draft':''):doneOf(x.topics)+' topics completed'),edit:()=>setSheet({type:'unit',un:x,cid:co.id})}))
    :sem?sem.courses.map(x=>({...row(x,'courses','course',(staff?x.units.length+' units':doneOf(x.units.flatMap(n=>n.topics))+' topics completed')+(x.shared?' · shared from '+x.home:x.shared_with?' · shared with '+x.shared_with+' more':'')+(staff?' · '+ownerLine(x):'')),edit:()=>setSheet({type:'course',c:x,pid:prog.id,sid:x.semester_id}),share:()=>setSh({id:x.id,name:x.name,home:x.semester_id,sel:x.link_ids||[]}),unlink:x.shared?{id:x.id,keep:(x.link_ids||[]).filter(i=>i!==sem.id)}:null}))
    :prog?prog.semesters.map(x=>({...row(x,'semesters','semester',(isAdmin?(x.number?prog.term+' no. '+x.number:'No '+prog.term.toLowerCase()+' number set')+' · ':'')+x.courses.length+' courses'),edit:()=>setSheet({type:'semester',sem:x,pid:prog.id})}))
    :tree.map(x=>({...row(x,'programs','program',x.semesters.length+' '+x.term.toLowerCase()+(x.semesters.length===1?'':'s')),edit:()=>setSheet({type:'program',p:x})}))
  const hidden=staff?list0.filter(x=>x.archived).length:0,list=staff&&!showArch?list0.filter(x=>!x.archived):list0,anyArch=staff&&tree.some(p=>p.archived||p.semesters.some(s=>s.archived||s.courses.some(c=>c.archived||c.units.some(n=>n.archived_self||n.topics.some(t=>t.archived_self)))))
  const cur=unit||co||sem||prog,crumbs=[prog,sem,co,unit].filter(Boolean).slice(0,-1).map(x=>x.name).join(' › ')
  const allSems=tree.flatMap(p=>p.semesters.map(s=>({id:s.id,label:p.name+' › '+s.name})))
  const myCourses=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>c.mine&&!c.shared&&(!c.archived||showArch)).map(c=>({p,s,c}))))
  const saveShare=async()=>{try{await api(`/courses/${sh.id}/links`,{method:'PUT',body:{semester_ids:sh.sel}});toast(t("Sharing updated"));setSh(null);load()}catch(e){toast(e.message)}}
  const remove=async()=>{try{if(del.unlink)await api(`/courses/${del.unlink.id}/links`,{method:'PUT',body:{semester_ids:del.unlink.keep}});else await api(`/${del.kind}/${del.id}`,{method:'DELETE'});toast(t("Deleted"));setDel(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={cur?.name||appName} sub={nav.length?crumbs:t("Hi {name}",{name:user.name})} back={nav.length>0&&(()=>setNav(nav.slice(0,-1)))}/>
   <div className="main">{unit&&mayEdit&&drafts(unit.topics)>0&&<button className="btn" style={{marginTop:0,marginBottom:12}} onClick={()=>setPub(`/units/${unit.id}/publish`,true,'All drafts published')}>{t("Publish all {drafts} drafts",{drafts:drafts(unit.topics)})}</button>}{!nav.length&&!(user.role==='faculty'&&myCourses.length>0)&&<div className="hero"><h2>{t("Choose a program")}</h2></div>}
     {staff&&(anyArch||showArch)&&<label className="chk" style={{marginBottom:12}}><input type="checkbox" checked={showArch} onChange={e=>setShowArch(e.target.checked)}/>{" "}{t("Show archived")}{!showArch&&hidden>0?t(" ({hidden} here)",{hidden:hidden}):''}</label>}
     {isAdmin&&!sem&&<button className="btn ghost lead" onClick={()=>setSheet(prog?{type:'semester',sem:{},pid:prog.id}:{type:'program',p:{}})}>{prog?t("Add {term} to {name}",{term:prog.term.toLowerCase(),name:prog.name}):t("New program")}</button>}
     {isAdmin&&sem&&!co&&<button className="btn ghost lead" onClick={()=>setSheet({type:'course',c:{},pid:prog.id,sid:sem.id})}>{t("Add course to")}{" "}{sem.name}</button>}
     {co&&!unit&&!staff&&<p className="known" style={{marginTop:0}}>{doneOf(co.units.flatMap(n=>n.topics))}{" "}{t("topics completed")}</p>}
     {co&&!unit&&!staff&&(()=>{const ts=co.units.flatMap(n=>n.topics),k=ts.filter(x=>x.has_notes).length;return <div className="card"><button className="hit" onClick={()=>setMat(true)}><span className="dot" style={{background:COL[3]}}><FileText size={20}/></span>
       <div><b>{k?t("Your notes in {k} of {length} topics",{k:k,length:ts.length}):t("Bring your own notes")}</b><span>{k?t("Add or update your material"):t("Upload your PDF or Word notes. They are filed under this course's topics, for you only.")}</span></div></button></div>})()}
     {co&&!unit&&staff&&<div className="qbox" style={{marginTop:0}}><p className="known" style={{margin:0}}>{t("Owner:")}{" "}<b>{co.mine?t("You"):co.owner_problem||co.owner||t("Not assigned")}</b>{sem.number?t(" · {term} no. {number}",{term:prog.term,number:sem.number}):''}</p>
       {isAdmin&&!co.shared&&<div className="two"><button className="btn ghost" onClick={()=>setSheet({type:'course',c:co,pid:prog.id,sid:co.semester_id})}>{t("Edit course")}</button><button className="btn ghost" onClick={()=>setSheet({type:'owner',c:co})}>{t("Change owner")}</button></div>}</div>}
     {!nav.length&&user.role==='faculty'&&<><h3 className="sec first">{t("My courses")}</h3>{myCourses.length?myCourses.map(({p,s,c},i)=><div key={c.id} className="card"><button className="hit" onClick={()=>setNav([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div><b>{c.name}<ArchPill x={c}/></b><span>{p.name}{" "}{t("› {name} · {length} units",{name:s.name,length:c.units.length})}</span></div></button></div>)
       :<p className="known">{t("No course is assigned to you yet. An admin makes you the owner of a course.")}</p>}<h3 className="sec">{t("All programs")}</h3></>}
    {mayEdit&&co&&!unit&&!co.shared&&<button className="btn ghost lead" onClick={()=>setSheet({type:'unit',un:{},cid:co.id})}>{t("Add unit")}</button>}
    {mayEdit&&unit&&!co.shared&&<div className="two lead2"><button className="btn ghost" onClick={()=>setEd({unit_id:unit.id})}>{t("Add topic to")}{" "}{unit.name}</button><button className="btn ghost" onClick={()=>setBulk(unit)}><Upload size={16}/>{" "}{t("Upload topic files")}</button></div>}
    {staff&&unit&&<button className="btn ghost lead" onClick={()=>setCopy({kind:'unit',id:unit.id,title:unit.name})}>{t("Copy this unit to another course")}</button>}
    {list.map((x,i)=>x.locked?<div key={x.id} className="card" style={{opacity:.7}}><button className="hit" onClick={()=>toast(t("This course is unavailable right now"))} aria-label={t("{n}, unavailable right now",{n:x.n})}><span className="dot" style={{background:'var(--mut)'}}><Lock size={18}/></span><div><b>{x.n}</b><span>{t("Unavailable right now")}</span></div></button></div>:<div key={x.id} className="card" style={x.archived?{opacity:.75}:undefined}><button className="hit" onClick={x.go}><span className="dot" style={{background:COL[i%5]}}>{x.n[0]}</span><div><b>{x.n}<ArchPill x={x}/></b>{x.sub&&<span>{x.sub}</span>}</div>{(x.s||x.b)&&<span className="marks">{x.b&&<Bookmark className="bm" size={16} fill="currentColor"/>}{x.s&&<Mark s={x.s}/>}</span>}</button>
      <div className="acts">{staff&&x.can&&(x.archived_self||!x.archived)&&<button className="ic sm" aria-label={(x.archived_self?'Restore ':'Archive ')+x.n} onClick={()=>setArch({kind:x.kind,id:x.id,name:x.n,on:!x.archived_self})}>{x.archived_self?<ArchiveRestore size={16}/>:<Archive size={16}/>}</button>}
      {mayEdit&&<>{(x.kind==='units'||x.kind==='topics')&&list.length>1&&[[-1,ArrowUp,'up'],[1,ArrowDown,'down']].map(([d,I,w])=><button key={w} className="ic sm" aria-label={t("Move {n} {w}",{n:x.n,w:w})} disabled={i+d<0||i+d>=list.length} onClick={()=>move(list,i,d,x.kind==='units'?`/courses/${co.id}/units/order`:`/units/${unit.id}/topics/order`)}><I size={16}/></button>)}{x.pub&&<button className="ic sm" aria-label={(x.draft?'Publish ':'Unpublish ')+x.n} onClick={x.pub}>{x.draft?<Eye size={16}/>:<EyeOff size={16}/>}</button>}{x.share&&<button className="ic sm" aria-label={t("Share {n}",{n:x.n})} onClick={x.share}><Link2 size={16}/></button>}<button className="ic sm" aria-label={t("Edit {n}",{n:x.n})} onClick={x.edit}><Pencil size={16}/></button><button className="ic sm" aria-label={t("Delete {n}",{n:x.n})} onClick={()=>setDel(x.unlink?{...x,unlink:x.unlink}:x)}><Trash2 size={16}/></button></>}</div></div>)}
    {co&&!unit&&(co.tests?.length>0||(mayEdit&&!co.shared))&&<><h3 className="sec">{t("MCQ tests")}</h3>
      {co.tests.map((q,i)=><div key={q.id} className="card"><button className="hit" onClick={()=>setQz(q.id)}><span className="dot" style={{background:COL[(i+1)%5]}}><ClipboardList size={18}/></span><div><b>{q.title}</b><span>{q.questions}{" "}{t("questions · pass {pass_percent}%",{pass_percent:q.pass_percent})}{q.best!=null?t(" · best {best}%",{best:q.best}):''}{q.published?'':t(" · Draft")}</span></div>{q.best!=null&&q.best>=q.pass_percent&&<span className="marks"><Check size={16}/></span>}</button>
        {mayEdit&&<><button className="ic sm" aria-label={t("Results of {title}",{title:q.title})} onClick={()=>setQr(q.id)}><BarChart3 size={16}/></button><button className="ic sm" aria-label={t("Edit {title}",{title:q.title})} onClick={()=>setQe({id:q.id,course_id:co.id})}><Pencil size={16}/></button></>}</div>)}
      {mayEdit&&!co.shared&&<button className="btn ghost" onClick={()=>setQe({course_id:co.id,csvFirst:true})}><Upload size={16}/>{" "}{t("New MCQ test from a CSV")}</button>}
      {mayEdit&&<button className="btn ghost" onClick={()=>setGb(co.id)}><BarChart3 size={16}/>{" "}{t("Gradebook: final scores for every test")}</button>}</>}
    {unit&&(unit.quizzes.length>0||mayEdit)&&<><h3 className="sec">{t("Quizzes")}</h3>
      {unit.quizzes.map((q,i)=><div key={q.id} className="card"><button className="hit" onClick={()=>setQz(q.id)}><span className="dot" style={{background:COL[(i+3)%5]}}>?</span><div><b>{q.title}</b><span>{q.questions}{" "}{t("questions · pass {pass_percent}%",{pass_percent:q.pass_percent})}{q.best!=null?t(" · best {best}%",{best:q.best}):''}{q.published?'':t(" · Draft")}</span></div>{q.best!=null&&q.best>=q.pass_percent&&<span className="marks"><Check size={16}/></span>}</button>
        {mayEdit&&<><button className="ic sm" aria-label={t("Results of {title}",{title:q.title})} onClick={()=>setQr(q.id)}><BarChart3 size={16}/></button><button className="ic sm" aria-label={t("Edit {title}",{title:q.title})} onClick={()=>setQe({id:q.id,unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}><Pencil size={16}/></button></>}</div>)}
      {mayEdit&&<button className="btn ghost" onClick={()=>setQe({unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}>{t("Add quiz")}</button>}</>}
    {!list.length&&<p className="known">{(mayEdit&&co)||isAdmin?t("Nothing here yet. Use the button above to add it."):!nav.length&&user.role==='student'?t("You are not enrolled in a program yet. Ask your admin to add you to one."):t("Nothing here yet. Your admin will add it soon.")}</p>}</div>
   {arch&&<ArchiveSheet a={arch} toast={toast} close={()=>setArch(null)} done={()=>setArch(null)}/>}
   {copy&&<CopySheet {...copy} toast={toast} close={()=>{setCopy(null);load()}}/>}{bulk&&<BulkTopics unit={bulk} toast={toast} close={()=>setBulk(null)} done={()=>{setBulk(null);load()}}/>}
   {del&&<Sheet close={()=>setDel(null)}><h3>{del.unlink?t("Remove"):t("Delete")} “{del.n}”{del.unlink?t(" from this {v}",{v:(prog?.term||'semester').toLowerCase()}):''}?</h3>
     <p className="known">{del.unlink?t("It only disappears from this {v}. The course stays where it was created.",{v:(prog?.term||'semester').toLowerCase()}):DELETES[del.kind]}{" "}{t("This can't be undone.")}</p>
     <button className="btn danger" onClick={remove}>{del.unlink?t("Remove"):t("Delete")}</button><button className="btn ghost" onClick={()=>setDel(null)}>{t("Cancel")}</button></Sheet>}
   {sh&&<Sheet page close={()=>setSh(null)}><h3>{t("Share “{name}”",{name:sh.name})}</h3><p className="known">{t("Tick every semester or year that should also show this course. You still edit it in one place.")}</p>
     {allSems.filter(x=>x.id!==sh.home).map(x=><label key={x.id} className="chk"><input type="checkbox" checked={sh.sel.includes(x.id)} onChange={e=>setSh({...sh,sel:e.target.checked?[...sh.sel,x.id]:sh.sel.filter(i=>i!==x.id)})}/> {x.label}</label>)}
     <button className="btn" onClick={saveShare}>{t("Save")}</button><button className="btn ghost" onClick={()=>setSh(null)}>{t("Cancel")}</button></Sheet>}
   {sheet?.type==='program'&&<ProgramSheet p={sheet.p} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
   {sheet?.type==='semester'&&<SemesterSheet sem={sheet.sem} pid={sheet.pid} term={prog?.term} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
   {sheet?.type==='course'&&<CourseSheet c={sheet.c} pid={sheet.pid} sid={sheet.sid} term={prog?.term} sems={tree.flatMap(p=>p.semesters.map(s=>({id:s.id,label:p.name+' › '+s.name})))} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
   {sheet?.type==='unit'&&<UnitSheet un={sheet.un} cid={sheet.cid} courses={isAdmin?tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared).map(c=>({id:c.id,label:`${p.name} › ${s.name} › ${c.name}`})))):null} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
   {sheet?.type==='owner'&&<OwnerSheet c={sheet.c} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
</>}
const DELETES={programs:"This deletes its semesters and courses with their units, topics and quizzes, and the students' reading progress, bookmarks and quiz attempts in them. Enrolled students keep their accounts but lose their program.",
  semesters:"This deletes its courses with their units, topics and quizzes, and the students' reading progress, bookmarks and quiz attempts in them. Courses shared into it from elsewhere are only unlinked.",
  courses:"This deletes its units, topics and quizzes, and the students' reading progress, bookmarks and quiz attempts in them. The owner keeps their account.",
  units:"This deletes its topics and quizzes, and the students' reading progress, bookmarks and quiz attempts in them.",
  topics:"This deletes the topic, its saved AI answers, and the students' reading progress and bookmarks for it."}
function SemesterSheet({sem,pid,term='Semester',close,done,toast}){
  const isNew=!sem.id,[f,setF]=useState({name:sem.name||'',no:sem.number||''}),[busy,setBusy]=useState(false)
  const pickNo=e=>{const no=e.target.value;setF({no,name:!f.name||/^(Semester|Year|Grade) \d+$/.test(f.name)?(no?term+' '+no:''):f.name})}
  const save=async()=>{setBusy(true);try{const body={name:f.name,semester_no:f.no?+f.no:null};await api(isNew?`/programs/${pid}/semesters`:'/semesters/'+sem.id,{method:isNew?'POST':'PUT',body:isNew?body:{...body,program_id:pid}});toast(isNew?t("{term} added",{term:term}):t("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?t("New {term}",{term:term.toLowerCase()}):t("Edit {term}",{term:term.toLowerCase()})}</h3>
    <label>{term}{" "}{t("number")}</label><select value={f.no} onChange={pickNo}><option value="">{t("Choose…")}</option>{upTo(maxOf(term)).map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>{t("Name")}</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder={term+" 3"}/>
    <p className="known" style={{marginTop:10}}>{t("The number sets the order and which students see it: a student in {term} 3 sees {term2}s 1 to 3. Each number is used once per program.",{term:term.toLowerCase(),term2:term.toLowerCase()})}</p>
    <button className="btn" disabled={busy||!f.no||!f.name.trim()} onClick={save}>{isNew?t("Add {term}",{term:term.toLowerCase()}):t("Save changes")}</button></Sheet>}
function CourseSheet({c,pid,sid,sems,term='Semester',close,done,toast}){
  const isNew=!c.id,faculty=useFaculty(true),[f,setF]=useState({name:c.name||'',sem:sid,owner:c.owner_id||''}),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{const owner=String(f.owner)!==String(c.owner_id||'')?{faculty_owner_id:f.owner?+f.owner:null}:{}  // unchanged owners are left alone
    await api(isNew?`/programs/${pid}/semesters/${sid}/courses`:'/courses/'+c.id,{method:isNew?'POST':'PUT',body:isNew?{name:f.name,...owner}:{name:f.name,semester_id:+f.sem,...owner}});toast(isNew?t("Course added"):t("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?t("New course in {v}",{v:sems.find(x=>x.id===sid)?.label||''}):t("Edit course")}</h3>
    <label>{t("Name")}</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder={t("Thermodynamics")}/>
    {!isNew&&<><label>{term}</label><select value={f.sem} onChange={e=>setF({...f,sem:+e.target.value})}>{sems.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></>}
    <label>{t("Owner (faculty)")}</label><select value={f.owner} onChange={e=>setF({...f,owner:e.target.value})}><option value="">{t("Not assigned")}</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner}{" "}{t("(can't edit)")}</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    {!isNew&&+f.sem!==sid&&<p className="known">{t("Moving the course takes its units, topics, quizzes and owner with it. Students placed there will see it.")}</p>}
    <button className="btn" disabled={busy||!f.name.trim()} onClick={save}>{isNew?t("Add course"):t("Save changes")}</button></Sheet>}

const STUDY=L({not_started:'Not opened yet',in_progress:'Opened, not marked completed',completed:'Marked completed'})
const AREA_GROUPS=L([['needs_study','Needs another round of study','Read these topics again, then retake the quiz.'],['getting_there','Getting there',''],['strong','Strong areas','You answered these well.']])
function AreaList({areas,onStudy,staff}){
  return <>{AREA_GROUPS.map(([k,title,hint])=>{const L=areas.filter(a=>a.status===k);if(!L.length)return null
    return <div className={'qbox area '+k} key={k}><b>{title} ({L.length})</b>{hint&&!staff&&<p className="known" style={{margin:'4px 0 8px'}}>{hint}</p>}
      {L.map(a=><div className="arow" key={a.topic_id||'u'+a.unit_id}><div><span>{a.title}</span><small>{a.correct}{" "}{t("of {total} right · {percent}%",{total:a.total,percent:a.percent})}{a.study&&!staff?' · '+STUDY[a.study]:''}{a.course?' · '+a.course:''}</small><Bar2 v={a.percent}/></div>
        {a.topic_id&&onStudy&&<button className="tool" onClick={()=>onStudy(a.topic_id)}>{k==='strong'?t("Review"):t("Study again")}</button>}</div>)}</div>})}</>}
const ATTN_GO={drafts:'drafts',empty_courses:'empty_courses',unowned:'unowned',unenrolled:'unenrolled',semester_numbers:'semester_numbers',never_opened:'never_opened'}
const RS_PAGE=5
function ResultSet({kind,user,back,toast,open}){  // the rows behind a dashboard card: search, sort, 5 per page, and a tap on a row opens its details
  const [q,setQ]=useState(''),[order,setOrder]=useState('name'),[page,setPage]=useState(0),[d,setD]=useState(null),[view,setView]=useState(null),[progs,setProgs]=useState([])
  useEffect(()=>{setPage(0)},[q,order])
  useEffect(()=>{if(view)return;let live=true;const t=setTimeout(()=>api(`/overview/list?kind=${kind}&q=${encodeURIComponent(q)}&order=${order}&limit=${RS_PAGE}&offset=${page*RS_PAGE}`).then(r=>{if(!live)return;if(!r.items.length&&r.total&&page>0)setPage(Math.max(0,Math.ceil(r.total/RS_PAGE)-1));else setD(r)}).catch(e=>toast(e.message)),q?250:0);return()=>{live=false;clearTimeout(t)}},[kind,q,order,page,view])
  useEffect(()=>{if(view?.target.type==='user')api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name,term:p.term})))).catch(()=>{})},[view])
  const shut=()=>setView(null)
  if(view){const t=view.target
    if(t.type==='user')return <UserDetail id={t.id} me={user} progs={progs} back={shut} toast={toast}/>
    if(t.type==='topic')return <Topic id={t.id} back={shut} toast={toast} role={user.role}/>
    if(t.type==='course'&&kind==='courses'){const [p='',sm='']=(view.sub||'').split(' · ');return <StudentReport c={{course_id:t.id,course:view.title,program:p,semester:sm}} back={shut} toast={toast}/>}
    open(t.type==='program'?[t.id]:[t.program_id,t.semester_id,t.id].filter(x=>x!=null));return null}
  const total=d?.total??0,pages=Math.max(1,Math.ceil(total/RS_PAGE)),title=d?.title||'Loading'
  return <><Bar title={title} sub={d?(total+(q?' match'+(total===1?'':'es'):' in total')):''} back={back}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={t("Search {title}",{title:title.toLowerCase()})} placeholder={t("Search")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="qopt"><select aria-label={t("Sort by")} value={order} onChange={e=>setOrder(e.target.value)}><option value="name">{t("Sort: A to Z")}</option><option value="name_desc">{t("Sort: Z to A")}</option><option value="detail">{t("Sort: by details")}</option><option value="newest">{t("Sort: newest first")}</option>{d?.can_recent&&<option value="recent">{t("Sort: last active")}</option>}</select></div>
    {!d&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {d&&d.items.length>0&&<div className="uhead" aria-hidden="true"><span>{t("Name")}</span><span>{t("Details")}</span><span/></div>}
    {d?.items.map(x=><button key={x.id} className="utr" onClick={()=>setView(x)} aria-label={t("Open {title}",{title:x.title})}>
      <span className="nm"><span className="dot" style={{background:COL[x.id%5]}}>{(x.title||'?')[0]}</span><span className="tx"><b>{x.title}</b><small className="sub">{x.sub}</small></span></span>
      <span className="pg">{x.detail||'—'}</span><span className="sn"><ChevronRight size={16}/></span></button>)}
    {d&&!d.items.length&&<p className="known">{q?t("Nothing matches that search."):t("Nothing here. All clear.")}</p>}
    {d&&total>RS_PAGE&&<nav className="pager" aria-label={t("Pages")}><button className="btn ghost" disabled={page===0} onClick={()=>setPage(page-1)}><ChevronLeft size={18}/><span>{t("Previous")}</span></button><small>{t("Page {v} of",{v:page+1})}{" "}{pages}</small><button className="btn ghost" disabled={page+1>=pages} onClick={()=>setPage(page+1)}><span>{t("Next")}</span><ChevronRight size={18}/></button></nav>}
  </div></>}
function StaffHome({user,toast,open}){
  const [o,setO]=useState(null),[list,setList]=useState(null),[rep,setRep]=useState(null)
  useEffect(()=>{if(!list&&!rep)api('/overview').then(setO).catch(e=>toast(e.message))},[toast,list,rep])
  if(rep)return <StudentReport c={rep} back={()=>setRep(null)} toast={toast}/>
  if(list)return <ResultSet kind={list} user={user} back={()=>setList(null)} toast={toast} open={open}/>
  const admin=user.role==='admin',hour=new Date().getHours(),hi=hour<12?'Good morning':hour<17?'Good afternoon':'Good evening'
  const stats=o?(admin?[[o.people.students,'Active students','students'],[o.people.active_week,'Studied this week','active_week'],[o.people.faculty,'Faculty','faculty'],[o.courses,'Courses','courses']]:[[o.courses,'Your courses','courses'],[o.topics,'Topics','topics'],[o.drafts,'Drafts','drafts']]):[]
  return <><Bar title={`${hi}, ${firstName(user.name)}`} sub={admin?t("Across the whole college"):t("Your courses")}/><div className="main">
    {!o&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {o&&<div className="stats">{stats.map(([n,l,k])=><button className="stat" key={l} style={{textAlign:'start',width:'100%'}} onClick={()=>setList(k)} aria-label={t("{v} {l}. Show the list",{v:(n??0).toLocaleString(),l:l})}><b>{(n??0).toLocaleString()}</b>{l}</button>)}</div>}
    {o&&<><h3 className="sec">{t("Needs attention")}</h3>
      {o.attention.length?o.attention.map(x=><button key={x.kind} className="card" style={{textAlign:'start'}} onClick={()=>setList(ATTN_GO[x.kind]||'drafts')}><div style={{flex:1}}><b>{x.text}</b></div><ChevronRight size={18}/></button>)
        :<p className="known">{t("Nothing needs your attention right now.")}</p>}</>}
    {o&&!o.courses&&!admin&&<p className="known">{t("No course is assigned to you yet. An admin makes you the owner of a course.")}</p>}
    {o?.courses>0&&<><h3 className="sec">{admin?t("Courses"):t("Your courses")}</h3><CourseReports toast={toast} onOpen={setRep}/></>}
  </div></>}
const FOCUS=L({overdue:[AlertTriangle,'Overdue','Open it'],due_soon:[Clock,'Due soon','Open it'],weak:[Target,'Needs review','Review'],resume:[Play,'Continue','Continue'],quiz_retake:[RotateCcw,'Retake the quiz','Retake'],quiz_new:[ClipboardList,'Quiz','Take the quiz'],next:[ArrowRight,'Next up','Start']})
function Dashboard({user,toast,onOpen,onSearch,onStudy,onRoutine}){
  const [sme,setSme]=useState(null);useEffect(()=>{api('/study/me').then(setSme).catch(()=>{})},[])
  const [tree,setTree]=useState(null),[ins,setIns]=useState(null),[today,setToday]=useState(null),[planErr,setPlanErr]=useState(''),[topic,setTopic]=useState(null),[sess,setSess]=useState(null)
  useEffect(()=>{if(topic)return;api('/tree').then(setTree).catch(e=>toast(e.message));api('/me/insights').then(setIns).catch(()=>{});api('/me/today').then(r=>{setToday(r);setPlanErr('')}).catch(e=>setPlanErr(e.message))},[topic,toast])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={user.role}/>
  const hour=new Date().getHours(),hi=hour<12?'Good morning':hour<17?'Good afternoon':'Good evening'
  const seen=new Map(),courses=[]
  for(const p of tree||[])for(const s of p.semesters)for(const c of s.courses){const at=seen.get(c.id),item={p,s,c,topics:c.units.flatMap(un=>un.topics.map(t=>({...t,unit:un})))}
    if(at===undefined){seen.set(c.id,courses.length);courses.push(item)}else if(courses[at].c.archived&&!c.archived)courses[at]=item}  // a course shown twice counts once, and a live place wins over an archived one
  const all=courses.flatMap(x=>x.topics.map(t=>({...t,x})))
  const routine=!!sess?.routine,inSession=new Set((sess?.session?.items||[]).filter(x=>x.kind!=='review'&&x.src!=='study').map(x=>x.id))  // today's session already lists these
  const due=all.filter(t=>t.learning_due_at&&t.status!=='completed'&&!inSession.has(t.id)).sort((a,b)=>a.learning_due_at.localeCompare(b.learning_due_at)).slice(0,5)
  const need=ins?.needs_study.slice(0,3)||[],focus=(today?.focus||[]).filter(f=>!inSession.has(f.topic_id)),top=routine?null:focus[0]
  const act=f=>f.topic_id?setTopic(f.topic_id):onOpen(f.nav)
  const sub=!today?'Here is where you are today':today.streak>1?`${today.streak}-day study streak. Keep it going`:today.active_today?'You have studied today. Nice start':focus.length?'Here is what to do next':'Here is where you are today'
  return <><Bar title={`${hi}, ${firstName(user.name)}`} sub={sub}/><div className="main">
    <SessionCard toast={toast} onRoutine={onRoutine} openTopic={setTopic} onStudy={onStudy} refresh={topic} onLoad={setSess}/>
    <button className="search fake" onClick={onSearch} aria-label={t("Search topics")}><Search size={18}/><span>{t("Search any topic")}</span></button>
    {sme&&sme.courses>0&&<><h3 className="sec first">{t("Your own courses")}</h3><LearnCard me={sme} compact onContinue={n=>onStudy({id:n.course_id,topic:n.topic_id})} onReview={cid=>onStudy({review:cid})}/></>}
    {sme&&!sme.courses&&tree&&!courses.length&&<button className="row rowbtn" onClick={()=>onStudy(null)}><span className="dot" style={{background:'var(--acc)'}}><Upload size={18}/></span><div>{t("Build a course from your own notes")}<small>{t("Upload a PDF or Word file and study it with quick checks, quizzes and reviews")}</small></div><ChevronRight size={18}/></button>}
    {!tree&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {tree&&!courses.length&&<p className="known">{user.self_registered&&!user.placed?t("Your account is ready. An admin will place you in your program and semester or year, and your courses will appear here."):t("You are not enrolled in a course yet. Ask your admin to add you to one.")}</p>}
    {planErr&&courses.length>0&&<p className="known" role="alert">{t("Today's plan could not load ({planErr}). Your courses are below. If this keeps happening, tell your admin.",{planErr:planErr})}</p>}
    {today&&courses.length>0&&<><div className="stats dstats">
      <div className="stat"><b><Flame size={20} className={'flame'+(today.streak?' on':'')} aria-hidden="true"/> {today.streak}</b>{t("Day streak")}<small>{today.active_today?t("Studied today"):today.streak?t("Study today to keep it"):t("Start one today")}</small></div>
      <div className="stat"><b>{today.completed_this_week}</b>{t("Done this week")}<small>{pl(today.active_days_week,'active day')}</small></div>
      <div className="stat"><b>{today.percent}%</b>{t("Completed")}<small>{today.topics_completed}{" "}{t("of {topics_total} topics",{topics_total:today.topics_total})}</small></div>
      <div className="stat"><b>{today.quiz_average==null?'–':today.quiz_average+'%'}</b>{t("Quiz average")}<small>{today.quiz_average==null?t("No quizzes yet"):t("best scores")}</small></div></div>
      <div className="week" role="img" aria-label={t("Studied on {length} of the last 7 days",{length:today.week.filter(d=>d.active).length})}>{today.week.map(d=><span key={d.date} className={'wd'+(d.active?' on':'')+(d.today?' now':'')}><i>{d.active&&<Check size={13}/>}</i><small>{d.label}</small></span>)}</div></>}
    {top&&<><h3 className="sec first">{t("Today's focus")}</h3>
      <div className="hero"><small>{top.kind==='overdue'||top.kind==='due_soon'?top.reason:FOCUS[top.kind][1]+' · '+top.reason}</small><h2 style={{fontSize:24}}>{top.title}</h2><p>{top.course} · {top.unit}</p>
        <button className="btn inv" style={{marginTop:14}} onClick={()=>act(top)}>{FOCUS[top.kind][2]}</button></div></>}
    {routine&&focus.length>0&&<h3 className="sec first">{t("Also worth doing")}</h3>}{focus.slice(top?1:0).map((f,i)=>{const [I,,go]=FOCUS[f.kind];return <button key={i} className="frow" onClick={()=>act(f)}><span className={'fic '+f.kind}><I size={18}/></span><span className="ftx"><b>{f.title}</b><small>{f.reason} · {f.course}</small></span><span className="fgo">{go}</span></button>})}
    {today&&courses.length>0&&!focus.length&&!routine&&<div className="qbox" style={{marginTop:6}}><b>{t("You are all caught up")}</b><p className="known" style={{margin:'6px 0 0'}}>{t("Nothing is overdue or waiting. Search a topic you want to revisit, or try a quiz to test yourself.")}</p></div>}
    {courses.length>0&&<><h3 className="sec">{t("My courses")}</h3>{courses.map(({p,s,c,topics},i)=>{const done=topics.filter(t=>t.status==='completed').length,pc=topics.length?Math.round(100*done/topics.length):0,late=topics.filter(t=>t.overdue).length,next=topics.find(t=>t.status==='in_progress')||topics.find(t=>t.status==='not_started')
      if(c.archived)return <div key={c.id} className="card" style={{opacity:.7}}><button className="hit" onClick={()=>toast(t("This course is unavailable right now"))} aria-label={t("{name}, unavailable right now",{name:c.name})}><span className="dot" style={{background:'var(--mut)'}}><Lock size={18}/></span><div><b>{c.name}</b><span>{t("Unavailable right now")}</span></div></button></div>
      return <div key={c.id} className="card" style={{display:'block'}}><button className="hit" style={{width:'100%'}} onClick={()=>onOpen([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div style={{flex:1}}><b>{c.name}{late>0&&<span className="pill off sm">{late}{" "}{t("overdue")}</span>}</b><span>{done}{" "}{t("of {length} topics completed · {pc}%",{length:topics.length,pc:pc})}</span><Bar2 v={pc}/>{next&&<span className="nexts">{next.status==='in_progress'?t("Continue"):t("Next")}: {next.title}</span>}</div></button></div>})}</>}
    {due.length>0&&<><h3 className="sec">{t("Coming up")}</h3>{due.map(t=><button key={t.id} className="row rowbtn" onClick={()=>setTopic(t.id)}><div>{t.title}<small>{t.x.c.name}{" "}{t("· due")}{" "}{new Date(t.learning_due_at).toLocaleDateString(undefined,{weekday:'short',day:'numeric',month:'short'})}</small></div>{t.overdue&&<span className="pill off sm">{t("Overdue")}</span>}<ChevronRight size={18}/></button>)}</>}
    {need.length>0&&<><h3 className="sec">{t("Worth another round of study")}</h3><AreaList areas={need} onStudy={setTopic}/></>}
  </div></>}
const WD=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
const nextStudyDay=days=>{for(let k=1;k<=7;k++){const d=new Date(Date.now()+k*864e5);if(days[(d.getDay()+6)%7]==='1')return k===1?'tomorrow':WD[(d.getDay()+6)%7]}return ''}
function SessionCard({toast,onRoutine,openTopic,onStudy,refresh,onLoad}){  // today's one session, from the student's own routine
  const [v,setV]=useState(null),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/me/session').then(x=>{setV(x);onLoad?.(x)}).catch(()=>{})},[refresh])
  if(!v)return null
  if(!v.routine)return <button className="row rowbtn" onClick={onRoutine}><span className="dot" style={{background:'var(--acc)'}}><Clock size={18}/></span><div>{t("Set your study routine")}<small>{t("Pick your study days and minutes. Each day you get one small session, at your own pace.")}</small></div><ChevronRight size={18}/></button>
  const open=x=>x.kind==='review'?onStudy({review:x.course_id}):x.src==='study'?onStudy({id:x.course_id,topic:x.id}):openTopic(x.id)
  const extra=async()=>{setBusy(true);try{const x=await api('/me/session',{method:'POST'});setV(x);onLoad?.(x)}catch(e){toast(e.message)}setBusy(false)}
  const r=v.routine,ss=v.session,left=ss?.items.filter(x=>!x.done)||[]
  return <div className="hero session"><div className="shead"><small>{t("Today's session · {minutes} min",{minutes:r.minutes})}{r.at?' · '+r.at:''}{v.streak>0?t(" · {streak}-day streak",{streak:v.streak}):''}</small><button className="schip" onClick={onRoutine} aria-label={t("Change my routine")}><Clock size={14}/>{" "}{t("Routine")}</button></div>
    {v.missed>=2&&!v.studied_today&&<p style={{margin:'6px 0 0'}}>{t("Welcome back. Today is just one session, the same as always. No catching up needed.")}</p>}
    {!ss&&<><h2 style={{fontSize:22}}>{t("Rest day")}</h2><p>{t("Your next session is {nextStudyDay}.",{nextStudyDay:nextStudyDay(r.days)})}</p><button className="btn inv" disabled={busy} onClick={extra}>{t("Study anyway")}</button></>}
    {ss&&ss.caught_up&&<><h2 style={{fontSize:22}}>{t("All caught up")}</h2><p>{t("Nothing is left to study right now. Well done.")}</p></>}
    {ss&&!ss.caught_up&&<>{ss.done?<h2 style={{fontSize:22}}><Check size={22}/>{" "}{t("Done for today")}</h2>:<h2 style={{fontSize:22}}>{left.length}{" "}{t("of {length} to go",{length:ss.items.length})}</h2>}
      <ul className="sitems">{ss.items.map((x,i)=><li key={i}><button className={'sitem'+(x.done?' done':'')} onClick={()=>open(x)}><span className="sx">{x.done?<Check size={16}/>:x.kind==='review'?<RotateCcw size={16}/>:<Play size={16}/>}</span><span><b>{x.title}</b><small>{x.course}</small></span></button></li>)}</ul>
      {!ss.done&&<button className="btn inv" onClick={()=>open(left[0])}>{left.length===ss.items.length?t("Start"):t("Continue")}: {left[0].title}</button>}
      {ss.done&&<p>{t("See you {nextStudyDay}.",{nextStudyDay:nextStudyDay(r.days)})}</p>}</>}
    <p className="splan">{v.plan.left?t("{left} topics left · at this pace, done by {v}",{left:v.plan.left,v:new Date(v.plan.finish+'T00:00').toLocaleDateString(undefined,{day:'numeric',month:'short'})}):t("Nothing left in your courses")}{v.plan.late>0?t(" · {late} would miss their deadline. {v}",{late:v.plan.late,v:v.plan.advice||''}):''}</p></div>}
function RoutinePage({toast,done}){
  const confirm=useConfirm()
  const [v,setV]=useState(null),[f,setF]=useState({days:'1111110',minutes:30,at:''}),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/me/session').then(x=>{setV(x);if(x.routine)setF({days:x.routine.days,minutes:x.routine.minutes,at:x.routine.at||''})}).catch(e=>toast(e.message))},[])
  const flip=k=>setF({...f,days:f.days.slice(0,k)+(f.days[k]==='1'?'0':'1')+f.days.slice(k+1)})
  const save=async()=>{setBusy(true);try{setV(await api('/me/routine',{method:'PUT',body:{...f,at:f.at||null}}));toast(t("Routine saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  const stop=async()=>{if(!await confirm({title:t("Stop your routine?"),body:t("Your progress stays. Home goes back to showing what to do next."),ok:t("Stop the routine")}))return;try{await api('/me/routine/stop',{method:'POST'});toast(t("Routine stopped"));done()}catch(e){toast(e.message)}}
  const per={15:1,30:1,45:2,60:3}[f.minutes]
  return <><Bar title={t("My routine")} sub={t("Study at your own pace, a little every day")}/><div className="main">
    <p className="known" style={{marginTop:0}}>{t("Pick the days you study and how long. Each study day you get one session: {v} and any reviews that are due. Miss a day and nothing piles up: the next session is the same size, and your streak only counts the days you picked.",{v:per===1?'one new topic':per+' new topics'})}</p>
    <label>{t("Study days")}</label><div className="chips wrap" role="group" aria-label={t("Study days")}>{WD.map((d,k)=><button key={d} className={'sbtn'+(f.days[k]==='1'?' on':'')} aria-pressed={f.days[k]==='1'} onClick={()=>flip(k)}><span className="lbl">{d}</span></button>)}</div>
    <label htmlFor="mins">{t("Minutes a session")}</label><select id="mins" value={f.minutes} onChange={e=>setF({...f,minutes:+e.target.value})}>{[15,30,45,60].map(m=><option key={m} value={m}>{m}{" "}{t("minutes")}</option>)}</select>
    <label htmlFor="at">{t("Usual time (optional)")}</label><input id="at" type="time" value={f.at} onChange={e=>setF({...f,at:e.target.value})}/>
    {v?.plan&&<p className="known">{v.plan.left?t("With your current routine you would finish the {left} topics left by {v}.",{left:v.plan.left,v:new Date(v.plan.finish+'T00:00').toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'})}):t("Nothing is left to study right now.")}{v.plan.late>0?t(" {late} topics would miss their deadline. {v}",{late:v.plan.late,v:v.plan.advice||''}):''}</p>}
    <button className="btn" disabled={busy||!f.days.includes('1')} onClick={save}>{t("Save routine")}</button>
    {v?.routine&&<button className="btn ghost" onClick={stop}>{t("Stop the routine")}</button>}</div></>}
function SearchPage({user,toast,initial}){
  const [q,setQ]=useState(initial||''),[live,setLive]=useState(null),[asked,setAsked]=useState(''),[ai,setAi]=useState(null),[aiBusy,setAiBusy]=useState(false),[aiErr,setAiErr]=useState(''),[topic,setTopic]=useState(null),[pend,setPend]=useState(false)
  const typed=q.trim()
  useEffect(()=>{if(typed.length<2){setLive(null);return}const t=setTimeout(()=>api('/search?q='+encodeURIComponent(typed)).then(r=>setLive({...r,for:typed})).catch(()=>{}),300);return()=>clearTimeout(t)},[typed])
  const askAi=async(query,refresh)=>{setAiBusy(true);setAiErr('');try{setAi({...await api('/search/ai',{method:'POST',body:{q:query,refresh}}),for:query,fresh:refresh})}catch(e){setAiErr(e.message)}setAiBusy(false)}
  const submit=async()=>{if(typed.length<2)return;setPend(true);setAi(null);setAiErr('')
    try{const r=await api('/search?q='+encodeURIComponent(typed));setLive({...r,for:typed});setAsked(typed);setPend(false)
      if(!r.results.length||!r.confident)await askAi(typed,false)}catch(e){toast(e.message);setPend(false)}}  // nothing good in the app's own notes, so the AI answers
  useEffect(()=>{if(initial)submit()},[])  // once, for a search started from the header
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={user.role}/>
  const res=asked&&live?.for===asked?live:null,aiNote=ai&&res&&res.results.length>0&&!res.confident
  return <><Bar title={t("Search")} sub={t("Find a topic, or ask the AI")}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={t("Search topics")} autoFocus placeholder={t("e.g. temporary hardness of water")} value={q} maxLength={200} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&submit()}/></div>
    <button className="btn" disabled={pend||aiBusy||typed.length<2} onClick={submit}>{pend?t("Searching…"):t("Search")}</button>
    {!asked&&live&&live.results.length>0&&<><h3 className="sec">{t("Topics in your courses")}</h3><p className="known">{t("Press Enter to search properly. If nothing here fits, the AI answers.")}</p>{live.results.slice(0,5).map(x=><Hit key={x.id} x={x} open={setTopic}/>)}</>}
    {!asked&&typed.length>=2&&live&&!live.results.length&&<p className="known">{t("Nothing in your courses matches yet. Press Enter and the AI will answer instead.")}</p>}
    {res&&<>{res.results.length>0?<><h3 className="sec">{aiNote?t("Possible matches in your courses"):t("In your courses")}</h3>{res.results.map(x=><Hit key={x.id} x={x} open={setTopic}/>)}</>
      :<p className="known" style={{marginTop:18}}>{t("Nothing in your courses matches “{asked}”.",{asked:asked})}</p>}
      {!ai&&!aiBusy&&<button className="btn ghost" onClick={()=>askAi(asked,false)}><Sparkles size={16}/>{" "}{t("Not what you wanted? Recheck with AI")}</button>}</>}
    {aiBusy&&<div className="qbox" aria-live="polite"><b>{t("Asking the AI…")}</b><div className="sk"/></div>}
    {aiErr&&<div className="qbox" role="alert"><b>{t("The AI could not answer")}</b><p className="known" style={{margin:'6px 0 0'}}>{aiErr}</p></div>}
    {ai&&!aiBusy&&<><h3 className="sec">{t("AI answer")}</h3><div className="prose">{ai.cached&&<span className="chip">{t("Saved answer · no tokens used")}</span>}<Md>{ai.text}</Md></div>
      <p className="known">{t("AI answers can contain mistakes. Check them against your notes and textbook.")}</p>
      <button className="btn ghost" disabled={aiBusy} onClick={()=>askAi(ai.for,true)}><Sparkles size={16}/>{" "}{t("Not happy? Recheck with AI")}</button></>}</div></>}
function Hit({x,open}){return <button className="hitrow" onClick={()=>open(x.id)}><b>{x.title}{x.in_title&&<span className="chip" style={{marginLeft:8}}>{t("Best match")}</span>}</b><small>{[x.program,x.semester,x.course,x.unit].filter(Boolean).join(' › ')}</small>{x.snippet&&<span className="snip">{x.snippet}</span>}</button>}

function Insights({toast,role}){
  const [d,setD]=useState(null),[topic,setTopic]=useState(null),[sc,setSc]=useState(null)
  useEffect(()=>{if(!topic)api('/me/insights').then(setD).catch(e=>toast(e.message))},[topic])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(sc)return <ScoreCourse c={sc} back={()=>setSc(null)} toast={toast} role={role}/>
  const n=d?d.needs_study.length:0
  return <><Bar title={t("My progress")} sub={t("Your scores, where you shine and what to revisit")}/><div className="main">
    <MyScores onCourse={setSc}/>{d?.courses.length>0&&<h3 className="sec">{t("Strengths and weak areas")}</h3>}
    {!d&&<Skeleton/>}
    {d&&!d.courses.length&&<p className="known">{t("Take a quiz and your strengths and weak spots will show up here.")}</p>}
    {d?.courses.length>0&&<div className="qbox"><b>{n?t("{n} {v} another round of study",{n:n,v:n===1?'area needs':'areas need'}):t("Nothing needs another round of study right now")}</b><p className="known" style={{margin:'4px 0 0'}}>{d.strong.length}{" "}{t("strong · {length} getting there · based on your latest result in {quizzes_taken}",{length:d.getting_there.length,quizzes_taken:d.quizzes_taken})}{" "}{d.quizzes_taken===1?'quiz':'quizzes'}</p></div>}
    {d?.courses.map(c=><section key={c.course_id}><h3 className="sec">{c.course}{" "}{t("· {percent}% right",{percent:c.percent})}</h3><AreaList areas={c.areas} onStudy={setTopic}/></section>)}</div></>}

const uploadImg=async f=>{const r=await fetch('/api/uploads',{method:'POST',headers:{'Content-Type':f.type||'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');return j.url}
// one image place on a question or an answer: shows the image, the file the CSV asked for, or a small "Add image" button
function ImgSlot({url,need,label,onSet,toast,small}){
  const ref=useRef(),[busy,setBusy]=useState(false)
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;setBusy(true);try{onSet(await uploadImg(f))}catch(x){toast(x.message)}setBusy(false)}
  const input=<input ref={ref} type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden onChange={pick}/>
  if(url)return <div className={'islot'+(small?' sm':'')}>{input}<img src={url} alt={label}/><span><button className="tool" onClick={()=>ref.current.click()}>{t("Replace")}</button><button className="tool" onClick={()=>onSet('')}>{t("Remove image")}</button></span></div>
  if(need)return <div className="islot need" role="status">{input}<AlertTriangle size={16}/><span>{t("Needs")}{" "}<b>{need}</b></span><button className="tool" disabled={busy} onClick={()=>ref.current.click()}>{busy?t("Uploading…"):t("Upload")}</button><button className="tool" onClick={()=>onSet('',true)}>{t("Skip")}</button></div>
  return <>{input}<button className="tool" disabled={busy} onClick={()=>ref.current.click()} aria-label={t("Add image to {label}",{label:label})}>{busy?t("Uploading…"):small?t("Image"):t("Add image")}</button></>}
const QImg=({src,alt})=>src?<img className="qimg" src={src} alt={alt} loading="lazy"/>:null
const OptBody=({text,img,k})=><span className="obody">{img&&<img src={img} alt={t("Answer {k}",{k:LET[k]})}/>}{text?<Md>{text}</Md>:!img&&<span>—</span>}</span>
const LET='ABCDEF'
function QuizPlay({id,back,toast,role}){
  const [q,setQ]=useState(null),[ans,setAns]=useState([]),[res,setRes]=useState(null),[busy,setBusy]=useState(false),[topic,setTopic]=useState(null),[view,setView]=useState(null)
  const start=d=>{setQ(d);setAns(d.questions.map(()=>null));setRes(null)}
  useEffect(()=>{api('/quizzes/'+id).then(start).catch(e=>{toast(e.message);back()})},[id])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(view)return view.kind==='attempt'?<AttemptView id={view.id} back={()=>setView(null)} toast={toast} role={role}/>:view.kind==='mine'?<MyAttempts quiz={id} back={()=>setView(null)} toast={toast} role={role}/>:<QuizResults id={id} back={()=>setView(null)} toast={toast} role={role}/>
  if(!q)return <><Bar title={t("Quiz")} back={back}/><div className="main"><Skeleton/></div></>
  const left=ans.filter(a=>a===null).length
  const submit=async()=>{setBusy(true);try{setRes(await api(`/quizzes/${id}/attempt`,{method:'POST',body:{answers:ans}}));window.scrollTo(0,0)}catch(e){toast(e.message)}setBusy(false)}
  return <><Bar title={q.title} sub={t("{length} questions · pass mark {pass_percent}%{v}",{length:q.questions.length,pass_percent:q.pass_percent,v:q.kind==='course'?' · course test':''})} back={back}/><div className="main">
    {!res&&q.can_edit&&<button className="btn ghost" style={{marginTop:0}} onClick={()=>setView({kind:'results'})}><BarChart3 size={16}/>{" "}{t("Results and scores")}</button>}
    {!res&&q.attempts>0&&<p className="known" style={{marginTop:0}}>{t("You have tried this {n}. Best {best}% · latest {latest}%.",{n:pl(q.attempts,'time'),best:q.best,latest:q.latest})}{" "}<button className="tool" onClick={()=>setView({kind:'mine'})}>{t("See your attempts")}</button></p>}
    {res&&<div className="qbox"><h2 style={{margin:0}}>{res.score} / {res.total} · {res.percent}%</h2><p className="known">{res.passed?t("Passed. Well done!"):t("Not there yet. Go back over the topics and try again.")}{res.summary&&' '+res.summary}</p>
      <div className="two"><button className="btn" onClick={()=>setView({kind:'attempt',id:res.attempt_id})}>{t("Review answers")}</button><button className="btn ghost" onClick={()=>start(q)}>{t("Try again")}</button></div><button className="btn ghost" onClick={back}>{t("Back")}</button></div>}
    {res&&res.areas?.length>0&&<><h3 className="sec">{t("What you are good at and what to revisit")}</h3><AreaList areas={res.areas} onStudy={setTopic}/></>}
    {q.questions.map((x,i)=><div className="qbox" key={x.id}><b>{t("Question")}{" "}{i+1}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={t("Picture for question {i}{v}",{i:i,v:1})}/>
      {x.options.map((o,k)=>{const r=res&&res.results[i],cls=r?(k===r.correct||(r.ok&&k===r.chosen)?' ok':k===r.chosen?' bad':''):ans[i]===k?' sel':''
        return <button key={k} className={'opt'+cls} disabled={!!res} aria-pressed={!res&&ans[i]===k} onClick={()=>setAns(ans.map((a,n)=>n===i?k:a))}><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/></button>})}
      {res&&res.results[i].explanation&&<div className="known"><Md>{res.results[i].explanation}</Md></div>}</div>)}
    {!res&&<button className="btn" disabled={busy} onClick={submit}>{busy?t("Checking…"):t("Submit answers")}</button>}
    {!res&&left>0&&<p className="known">{left}{" "}{t("unanswered. Blank answers count as wrong.")}</p>}</div></>}
// one attempt, question by question
function AttemptView({id,back,toast,role}){
  const [d,setD]=useState(null),[topic,setTopic]=useState(null)
  useEffect(()=>{api('/attempts/'+id).then(setD).catch(e=>{toast(e.message);back()})},[id])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(!d)return <><Bar title={t("Attempt")} back={back}/><div className="main"><Skeleton/></div></>
  const staff=role!=='student',right=d.questions.filter(x=>x.ok).length
  return <><Bar title={d.quiz} sub={(staff?d.user+' · ':'')+when(d.at)} back={back}/><div className="main">
    <div className="qbox" style={{marginTop:0}}><h2 style={{margin:0}}>{d.score} / {d.total} · {d.percent}%</h2><p className="known" style={{marginBottom:0}}>{d.passed?t("Passed"):t("Below the pass mark")}{" "}{t("of {pass_percent}%.",{pass_percent:d.pass_percent})}{d.summary&&' '+d.summary}</p></div>
    {d.areas.length>0&&<><h3 className="sec">{staff?t("Strengths and weak areas"):t("What you are good at and what to revisit")}</h3><AreaList areas={d.areas} onStudy={staff?null:setTopic} staff={staff}/></>}
    {d.no_detail&&<p className="known">{t("This attempt was made before answers were kept question by question, so only the score is known.")}</p>}
    {d.changed>0&&<p className="known">{pl(d.changed,'question')}{" "}{t("of this attempt {v} changed or removed since, so {v2} not shown.",{v:d.changed===1?'was':'were',v2:d.changed===1?'it is':'they are'})}</p>}
    {!d.reveal&&d.questions.length>0&&<p className="known">{t("You see which answers were right ({right} of {length}). This quiz does not show the correct answers.",{right:right,length:d.questions.length})}</p>}
    {d.questions.map((x,i)=><div className="qbox" key={x.id}><b>{t("Question {v} ·",{v:i+1})}{" "}{x.ok?t("Right"):t("Wrong")}{x.area?' · '+x.area:''}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={t("Picture for question {i}{v}",{i:i,v:1})}/>
      {x.options.map((o,k)=>{const mine=x.chosen_known&&x.chosen===k,key=d.reveal&&x.correct===k,cls=key||(mine&&x.ok)?' ok':mine?' bad':''
        return <div key={k} className={'opt'+cls}><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/>{(mine||key)&&<span className="otag">{[mine&&(staff?'Their answer':'Your answer'),key&&'Correct answer'].filter(Boolean).join(' · ')}</span>}</div>})}
      {x.chosen_known&&x.chosen==null&&<p className="known">{t("Left blank.")}</p>}
      {x.explanation&&<div className="known"><Md>{x.explanation}</Md></div>}</div>)}</div></>}
function MyAttempts({quiz,user,back,toast,role}){  // a person's attempts at one quiz; staff pass user to see a student's
  const [d,setD]=useState(null),[open,setOpen]=useState(null)
  useEffect(()=>{api(`/quizzes/${quiz}/attempts`+(user?'?user_id='+user:'')).then(setD).catch(e=>{toast(e.message);back()})},[quiz,user])
  if(open)return <AttemptView id={open} back={()=>setOpen(null)} toast={toast} role={role}/>
  return <><Bar title={d?.quiz||t("Attempts")} sub={d?(user?d.user+' · ':'')+pl(d.items.length,'attempt'):''} back={back}/><div className="main">
    {d&&!d.items.length&&<p className="known">{t("No attempts yet.")}</p>}
    {d?.items.map((a,i)=><button key={a.id} className="row rowbtn" onClick={()=>setOpen(a.id)}><div>{a.score} / {a.total} · {a.percent}%<small>{when(a.at)} · {a.passed?t("Passed"):t("Below the pass mark")}{i===0?t(" · latest"):''}</small><Bar2 v={a.percent}/></div><ChevronRight size={18}/></button>)}</div></>}

const MCQ_TEMPLATE=`question,a,b,c,d,correct,explanation,topic,area,question_image,a_image,b_image,c_image,d_image
"Which ion makes water hard?",Na+,Ca2+,Cl-,K+,B,"Calcium and magnesium salts cause hardness.",Water Treatment,,,,,,
"Which boiler is shown in the picture?",Fire tube,Water tube,Electric,Packaged,A,,Boilers,,boiler.png,,,,
"Pick the symbol for a resistor",,,,,C,,,Circuit symbols,,sym-a.png,sym-b.png,sym-c.png,sym-d.png
"What is 15% of 200?",20,30,15,35,30,,,Arithmetic,,,,,
`
const CSV_COLS=[['question','The question. Markdown and $math$ work.'],['a, b, c, d (up to f)','The answer choices. Leave the later ones blank if a question has fewer. A choice can be only an image.'],
  ['correct','The right answer: its letter (B), its number (2) or its exact text.'],['explanation','Optional. Shown after submitting when the test reveals answers.'],
  ['topic','Optional. A topic title from this course; strengths are worked out per topic.'],['area','Optional. A skill or area name for questions not tied to a topic.'],
  ['question_image, a_image … f_image','Optional. Image file names. You upload the files in the preview, matched by name.']]
const blankQ=()=>({text:'',options:['',''],option_images:['',''],correct:0,explanation:'',topic_id:null,area:'',image:'',need:{image:'',options:[]}})
const fromCsv=x=>({text:x.text,options:x.options,option_images:x.option_images.map(v=>v||''),correct:x.correct,explanation:x.explanation||'',topic_id:x.topic_id,area:x.area||'',image:x.image||'',
  need:{image:x.image?'':x.image_name,options:x.option_image_names.map((n,k)=>x.option_images[k]?'':n)}})
const missing=qs=>qs.flatMap((x,i)=>[...(x.need.image&&!x.image?[{i,k:-1,name:x.need.image}]:[]),...x.need.options.map((n,k)=>n&&!x.option_images[k]?{i,k,name:n}:null).filter(Boolean)])
function QuizEditor({id,unit_id,course_id,unitTopics,csvFirst,done,toast}){
  const confirm=useConfirm()
  const [m,setM]=useState({title:'',pass_percent:50,published:false,reveal:false}),[qs,setQs]=useState([blankQ()]),[busy,setBusy]=useState(false),[topics,setTopics]=useState(unitTopics||[]),csvRef=useRef(null),imgRef=useRef(null)
  const [csv,setCsv]=useState(null),[bank,setBank]=useState(false),[btags,setBtags]=useState(''),[stage,setStage]=useState(csvFirst&&!id?'csv':'edit'),[cid,setCid]=useState(course_id)
  const course=!unit_id
  useEffect(()=>{if(id)api('/quizzes/'+id).then(d=>{setM({title:d.title,pass_percent:d.pass_percent,published:d.published,reveal:d.reveal});setCid(d.course_id);setTopics(d.topics||[])
    setQs(d.questions.length?d.questions.map(x=>({text:x.text,options:x.options,option_images:x.options.map((_,k)=>x.option_images[k]||''),correct:x.correct,explanation:x.explanation||'',topic_id:x.topic_id??null,area:x.area||'',image:x.image||'',need:{image:'',options:[]}})):[blankQ()])}).catch(e=>{toast(e.message);done()})
    else if(course&&course_id)api('/courses/'+course_id+'/topics').then(setTopics).catch(()=>{})},[id])
  const upd=(i,p)=>setQs(cur=>cur.map((x,n)=>n===i?{...x,...p}:x))
  const setOpt=(i,k,v)=>upd(i,{options:qs[i].options.map((o,n)=>n===k?v:o)})
  const setOptImg=(i,k,v,skip)=>setQs(cur=>cur.map((x,n)=>n!==i?x:{...x,option_images:x.options.map((_,j)=>j===k?v:x.option_images[j]||''),need:skip||v?{...x.need,options:x.need.options.map((nm,j)=>j===k?'':nm)}:x.need}))
  const setQImg=(i,v,skip)=>setQs(cur=>cur.map((x,n)=>n!==i?x:{...x,image:v,need:skip||v?{...x.need,image:''}:x.need}))
  const delOpt=(i,k)=>{const x=qs[i];upd(i,{options:x.options.filter((_,n)=>n!==k),option_images:x.option_images.filter((_,n)=>n!==k),need:{...x.need,options:x.need.options.filter((_,n)=>n!==k)},correct:x.correct===k?0:x.correct>k?x.correct-1:x.correct})}
  const todo=missing(qs)
  const payload=()=>qs.filter(x=>x.text.trim()||x.image).map(x=>({text:x.text,options:x.options,option_images:x.option_images,correct:x.correct,explanation:x.explanation,topic_id:x.topic_id,area:x.area,image:x.image}))
  const save=async()=>{setBusy(true);try{const body={...(course?{course_id:cid}:{unit_id}),...m,pass_percent:+m.pass_percent},qid=id||(await api('/quizzes',{method:'POST',body})).id
    if(id)await api('/quizzes/'+id,{method:'PUT',body})
    await api(`/quizzes/${qid}/questions`,{method:'PUT',body:{questions:payload()}});toast(course?t("Test saved"):t("Quiz saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  const readCsv=async(f,replace)=>{try{const r=await api('/quizzes/parse-csv',{method:'POST',body:{csv:await f.text(),...(course?{course_id:cid}:{unit_id})}});setCsv(r)
    if(!r.questions.length){toast(t("No questions could be read from the file"));return}
    const got=r.questions.map(fromCsv);setQs(cur=>replace?got:[...cur.filter(x=>x.text.trim()||x.image),...got])
    if(replace&&!m.title)setM(v=>({...v,title:f.name.replace(/\.[^.]+$/,'').replace(/[_-]+/g,' ').slice(0,200)}))
    setStage('edit');toast(t("{n} read. Check them below{v}, then save.",{n:pl(r.questions.length,'question'),v:r.images_needed.length?' and upload the images':''}))}catch(e){toast(e.message)}}
  const importCsv=async e=>{const f=e.target.files[0];e.target.value='';if(f)readCsv(f,stage==='csv')}
  const bulkImages=async e=>{const files=[...e.target.files];e.target.value='';if(!files.length)return;setBusy(true);let used=0;const extra=[];let next=qs
    for(const f of files){const hits=missing(next).filter(s=>s.name.toLowerCase()===f.name.toLowerCase());if(!hits.length){extra.push(f.name);continue}
      try{const url=await uploadImg(f);used++;next=next.map((x,i)=>{const h=hits.filter(s=>s.i===i);if(!h.length)return x
        return {...x,image:h.some(s=>s.k<0)?url:x.image,option_images:x.option_images.map((v,k)=>h.some(s=>s.k===k)?url:v),need:{image:h.some(s=>s.k<0)?'':x.need.image,options:x.need.options.map((n,k)=>h.some(s=>s.k===k)?'':n)}}})}catch(x){toast(f.name+': '+x.message)}}
    setQs(next);setBusy(false);toast(t("{n} matched{v}",{n:pl(used,'image'),v:extra.length?`. Not in the CSV: ${extra.slice(0,3).join(', ')}${extra.length>3?'…':''}`:''}))}
  const addFromBank=picked=>{setQs(cur=>[...cur.filter(x=>x.text.trim()),...picked.map(x=>({...blankQ(),text:x.text,options:x.options,option_images:x.options.map(()=>''),correct:x.correct,explanation:x.explanation||''}))]);setBank(false);toast(t("{n} added. Tie them to topics if you like, then save.",{n:pl(picked.length,'question')}))}
  const toBank=async()=>{const list=qs.filter(x=>x.text.trim());let added=0,skipped=0,bad=0;setBusy(true)
    for(const x of list){if(x.image||x.option_images.some(Boolean)){bad++;continue}try{await api('/bank',{method:'POST',body:{text:x.text,options:x.options,correct:x.correct,explanation:x.explanation,tags:btags,source:m.title}});added++}catch(e){/already in the bank/.test(e.message)?skipped++:bad++}}
    setBusy(false);toast(t("{added} saved to the bank{v}{v2}",{added:added,v:skipped?`, ${skipped} already there`:'',v2:bad?`, ${bad} skipped (incomplete or with images)`:''}))}
  const del=async()=>{if(!await confirm({title:t("Delete this {v}?",{v:course?'test':'quiz'}),body:t("This also deletes every student attempt. This can't be undone."),ok:t("Delete"),danger:true}))return;try{await api('/quizzes/'+id,{method:'DELETE'});toast(t("Deleted"));done()}catch(e){toast(e.message)}}
  const fileInputs=<><input ref={csvRef} type="file" accept=".csv,text/csv,text/plain" hidden onChange={importCsv}/><input ref={imgRef} type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple hidden onChange={bulkImages}/></>
  const csvNotes=csv&&(csv.error_count>0||csv.warnings.length>0)&&<div className="qbox" role="alert">{csv.error_count>0&&<><b>{pl(csv.error_count,'row')}{" "}{t("could not be read and {v} left out",{v:csv.error_count===1?'was':'were'})}</b>{csv.errors.slice(0,10).map((x,i)=><p className="known" style={{margin:'4px 0'}} key={i}>{t("Row {row}:",{row:x.row})}{" "}{x.error}</p>)}{csv.error_count>10&&<p className="known">{t("…and {v} more.",{v:csv.error_count-10})}</p>}</>}
    {csv.warnings.length>0&&<><b style={{display:'block',marginTop:csv.error_count?10:0}}>{t("Worth a look")}</b>{csv.warnings.slice(0,8).map((w,i)=><p className="known" style={{margin:'4px 0'}} key={i}>{w}</p>)}{csv.warnings.length>8&&<p className="known">{t("…and {v} more.",{v:csv.warnings.length-8})}</p>}</>}</div>
  if(stage==='csv')return <><Bar title={t("New MCQ test")} sub={t("Step 1 of 2 · attach the questions CSV")} back={done}/><div className="main">{fileInputs}
    <p className="known" style={{marginTop:0}}>{t("A course test is built from a CSV file with one question per row. In the next step you check every question, upload any pictures for questions and answer choices, then save.")}</p>
    <button className="btn" onClick={()=>csvRef.current.click()}><Upload size={16}/>{" "}{t("Choose the CSV file")}</button><button className="btn ghost" onClick={()=>download('mcq-template.csv',MCQ_TEMPLATE)}>{t("Download the template")}</button>
    {csvNotes}
    <h3 className="sec">{t("Columns")}</h3>{CSV_COLS.map(([c,h])=><div className="row" key={c}><div><code>{c}</code><small>{h}</small></div></div>)}
    <p className="known">{t("The first row names the columns. Comma, semicolon and tab separated files all work. A course test holds up to 200 questions.")}</p></div></>
  return <><Bar title={id?(course?t("Edit test"):t("Edit quiz")):csvFirst?t("New MCQ test"):t("New quiz")} sub={csvFirst&&!id?t("Step 2 of 2 · check, add images, save"):''} back={done}/><div className="main">{fileInputs}
    {csvNotes}
    {todo.length>0&&<div className="qbox need" role="status"><b>{pl(todo.length,'image')}{" "}{t("still to upload")}</b><p className="known" style={{margin:'4px 0 8px'}}>{t("Choose them all at once and they are matched to their questions by file name, or upload each one below.")}{" "}{[...new Set(todo.map(x=>x.name))].slice(0,6).join(', ')}{todo.length>6?'…':''}</p>
      <button className="btn" style={{margin:0}} disabled={busy} onClick={()=>imgRef.current.click()}><Upload size={16}/> {busy?t("Uploading…"):t("Upload images")}</button></div>}
    <label>{t("Title")}</label><input value={m.title} onChange={e=>setM({...m,title:e.target.value})} placeholder={course?t("e.g. Chemistry final MCQ"):t("e.g. Water treatment check")}/>
    <label>{t("Pass mark (%)")}</label><input type="number" min="1" max="100" value={m.pass_percent} onChange={e=>setM({...m,pass_percent:e.target.value})}/>
    <label className="chk"><input type="checkbox" checked={m.published} onChange={e=>setM({...m,published:e.target.checked})}/>{" "}{t("Published (students can take it)")}</label>
    <label className="chk"><input type="checkbox" checked={m.reveal} onChange={e=>setM({...m,reveal:e.target.checked})}/>{" "}{t("Show students the correct answers and explanations after they submit")}</label>
    {qs.map((x,i)=><div className="qbox" key={i}><b>{t("Question")}{" "}{i+1}</b>
      <textarea placeholder={t("Question (Markdown and $math$ work)")} value={x.text} onChange={e=>upd(i,{text:e.target.value})}/>
      <ImgSlot url={x.image} need={x.need.image} label={t("question {i}{v}",{i:i,v:1})} toast={toast} onSet={(v,skip)=>setQImg(i,v,skip)}/>
      {x.options.map((o,k)=><div key={k}><div className="qopt"><input type="radio" name={'c'+i} aria-label={t("Answer {k} is correct",{k:LET[k]})} checked={x.correct===k} onChange={()=>upd(i,{correct:k})}/><b className="olet">{LET[k]}</b><input value={o} placeholder={t("Answer {k}{v}",{k:LET[k],v:x.option_images[k]?' (optional with an image)':''})} onChange={e=>setOpt(i,k,e.target.value)}/>
        {!x.option_images[k]&&!x.need.options[k]&&<ImgSlot small label={t("answer {k}",{k:LET[k]})} toast={toast} onSet={v=>setOptImg(i,k,v)}/>}{x.options.length>2&&<button className="ic sm" aria-label={t("Remove answer {k}",{k:LET[k]})} onClick={()=>delOpt(i,k)}><X size={16}/></button>}</div>
        {(x.option_images[k]||x.need.options[k])&&<div style={{paddingLeft:48}}><ImgSlot small url={x.option_images[k]} need={x.need.options[k]} label={t("answer {k}",{k:LET[k]})} toast={toast} onSet={(v,skip)=>setOptImg(i,k,v,skip)}/></div>}</div>)}
      {x.options.length<6&&<button className="tool" onClick={()=>upd(i,{options:[...x.options,''],option_images:[...x.option_images,'']})}>{t("Add answer")}</button>}
      <label>{t("Topic this tests")}</label><select value={x.topic_id??''} onChange={e=>upd(i,{topic_id:e.target.value?+e.target.value:null})}><option value="">{t("Not tied to one topic")}</option>{topics.map(t=><option key={t.id} value={t.id}>{t.unit?t.unit+' › ':''}{t.title}</option>)}</select>
      {x.topic_id==null&&<><label>{t("Area or skill")}</label><input value={x.area} onChange={e=>upd(i,{area:e.target.value})} placeholder={t("e.g. Arithmetic (used for strengths when there is no topic)")}/></>}
      <textarea placeholder={t("Explanation shown after submitting (optional)")} value={x.explanation} onChange={e=>upd(i,{explanation:e.target.value})}/>
      {qs.length>1&&<button className="tool" onClick={()=>setQs(qs.filter((_,n)=>n!==i))}>{t("Remove question")}</button>}</div>)}
    <p className="known">{t("Tick the radio button beside the correct answer. Tie each question to the topic it tests, or name an area: students then see what they are good at and what needs another round of study.")}</p>
    <button className="btn ghost" onClick={()=>setQs([...qs,blankQ()])}>{t("Add question")}</button>
    <div className="two"><button className="btn ghost" onClick={()=>csvRef.current.click()}><Upload size={16}/>{" "}{t("Add from a CSV")}</button><button className="btn ghost" onClick={()=>download('mcq-template.csv',MCQ_TEMPLATE)}>{t("CSV template")}</button></div>
    <button className="btn ghost" onClick={()=>setBank(true)}>{t("Add from the question bank")}</button>
    <label htmlFor="bt">{t("Share these questions in the bank")}</label><div className="two"><input id="bt" value={btags} onChange={e=>setBtags(e.target.value)} placeholder={t("Tags, e.g. water, hardness (optional)")}/><button className="btn ghost" disabled={busy||!qs.some(x=>x.text.trim())} onClick={toBank}>{t("Save to bank")}</button></div>
    <button className="btn" disabled={busy||todo.length>0} onClick={save}>{busy?t("Saving…"):todo.length?t("Upload {n} first",{n:pl(todo.length,'image')}):id?t("Save changes"):course?t("Create test"):t("Save quiz")}</button>{bank&&<BankSheet close={()=>setBank(false)} onAdd={addFromBank} toast={toast}/>}
    {id&&<button className="btn danger" onClick={del}>{t("Delete")}{" "}{course?'test':'quiz'}</button>}</div></>}

// score spread: one series, so one hue and no legend; every bar has its count as text and a tooltip
const Spread=({rows,pass})=>{const top=Math.max(1,...rows.map(r=>r.count))
  return <figure className="spread" aria-label={t("How many students scored in each band")}><div className="sbars">{rows.map((r,i)=><div key={r.label} className="sbar" title={`${r.label}%: ${pl(r.count,'student')}`}><em>{r.count||''}</em><i style={{height:r.count?Math.max(4,100*r.count/top)+'%':0}} className={i*10+9<pass?'below':''}/></div>)}</div>
    <div className="saxis">{rows.map(r=><span key={r.label}>{r.label.split('–')[0]}</span>)}</div><figcaption>{t("Final score in bands of 10%. Lighter bars are below the {pass}% pass mark.",{pass:pass})}</figcaption></figure>}
const PassPill=({ok})=><span className={'pill sm '+(ok?'okp':'off')}>{ok?t("Passed"):t("Not yet")}</span>
function QuizResults({id,back,toast,role}){
  const [d,setD]=useState(null),[tab,setTab]=useState('overview'),[who,setWho]=useState(null),[sort,setSort]=useState('order')
  useEffect(()=>{api(`/quizzes/${id}/results`).then(setD).catch(e=>{toast(e.message);back()})},[id])
  if(who)return <MyAttempts quiz={id} user={who} back={()=>setWho(null)} toast={toast} role={role}/>
  if(!d)return <><Bar title={t("Results")} back={back}/><div className="main"><Skeleton/></div></>
  const sm=d.summary,qs=sort==='hard'?[...d.questions].sort((a,b)=>(a.percent??101)-(b.percent??101)):d.questions
  return <><Bar title={d.title} sub={t("Results · {took} of {students} students took it",{took:sm.took,students:sm.students})} back={back}/><div className="main">
    <Tabs scroll label={t("Result sections")} items={[['overview','Overview'],['students','Students'],['questions','Questions'],['areas','Strengths']]} value={tab} onChange={setTab}/>
    {tab==='overview'&&<>{!sm.took?<p className="known">{t("Nobody has taken it yet.")}{d.published?'':t(" It is still a draft, so students cannot see it.")}</p>:<>
      <div className="stats">{[['Average final score',sm.average+'%'],['Pass rate',sm.pass_rate+'%',`${sm.passed} of ${sm.took} passed`],['Median',sm.median+'%'],['Highest · lowest',sm.highest+'% · '+sm.lowest+'%'],
        ['Took it',sm.took+' / '+sm.students,sm.not_taken?sm.not_taken+' not yet':'everyone'],['Attempts',sm.attempts,'latest average '+sm.average_latest+'%']].map(([l,v,x])=><div className="stat" key={l}><b>{v}</b>{l}{x&&<small style={{display:'block',color:'var(--mut)'}}>{x}</small>}</div>)}</div>
      <h3 className="sec">{t("Spread of final scores")}</h3><Spread rows={sm.distribution} pass={d.pass_percent}/>
      <p className="known">{t("The final score is each student's best attempt. Strengths and the question analysis use each student's latest attempt, so a retake replaces the earlier result.")}</p></>}
      {d.not_taken.length>0&&<><h3 className="sec">{t("Not taken yet ({not_taken})",{not_taken:sm.not_taken})}</h3><p className="known" style={{margin:0}}>{d.not_taken.map(x=>x.name).join(', ')}{sm.not_taken>d.not_taken.length?'…':''}</p></>}
      <button className="btn ghost" onClick={()=>fetchFile(`/quizzes/${id}/results?format=csv`,'results-'+d.title.replace(/\s+/g,'_')+'.csv',toast)}>{t("Download results CSV")}</button></>}
    {tab==='students'&&<>{!d.students.length&&<p className="known">{t("No results yet.")}</p>}
      {d.students.map(x=><button key={x.user_id} className="row rowbtn" onClick={()=>setWho(x.user_id)}><div>{x.name}<PassPill ok={x.passed}/><small>{t("Final {best}% · latest {latest}% · {n} ·",{best:x.best,latest:x.latest,n:pl(x.attempts,'attempt')})}{" "}{day(x.last_at)}</small>
        {(x.strong.length>0||x.needs_study.length>0)&&<small>{x.strong.length>0&&t("Good at: {strong}",{strong:x.strong.join(', ')})}{x.strong.length>0&&x.needs_study.length>0&&' · '}{x.needs_study.length>0&&t("Revisit: {needs_study}",{needs_study:x.needs_study.join(', ')})}</small>}<Bar2 v={x.best}/></div><ChevronRight size={18}/></button>)}</>}
    {tab==='questions'&&<><div className="seg" style={{gridTemplateColumns:'1fr 1fr',margin:'0 0 12px'}}>{[['order','In test order'],['hard','Hardest first']].map(([k,l])=><button key={k} className={sort===k?'on':''} aria-pressed={sort===k} onClick={()=>setSort(k)}>{l}</button>)}</div>
      {qs.map(x=>{const n=x.picks.reduce((a,b)=>a+b,0)+x.blank
        return <div className="qbox" key={x.id}><b>{t("Question {pos} ·",{pos:x.pos})}{" "}{x.percent==null?t("no answers yet"):t("{percent}% right",{percent:x.percent})}{x.area?' · '+x.area:''}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={t("Picture for question {pos}",{pos:x.pos})}/>
          {x.options.map((o,k)=>{const c=x.picks[k],pc=n?Math.round(100*c/n):0
            return <div key={k} className="pick" title={`${LET[k]}: ${pl(c,'student')}`}><div className="pickh"><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/>{k===x.correct&&<span className="otag ok"><Check size={14}/>{" "}{t("Correct")}</span>}<span className="pickn">{c} · {pc}%</span></div><div className="meter"><i style={{width:pc+'%'}} className={k===x.correct?'ok':''}/></div></div>})}
          {x.picks_known>0&&x.blank>0&&<p className="known" style={{margin:'6px 0 0'}}>{t("Left blank:")}{" "}{x.blank}</p>}
          {x.total>x.picks_known&&<p className="known" style={{margin:'6px 0 0'}}>{x.total-x.picks_known}{" "}{t("older {v} not record which answer was picked.",{v:x.total-x.picks_known===1?'attempt does':'attempts do'})}</p>}</div>})}</>}
    {tab==='areas'&&<>{!d.areas.length?<p className="known">{t("No results yet.")}</p>:<><p className="known" style={{marginTop:0}}>{t("Weakest first, from each student's latest attempt.")}</p>
      {d.areas.map(a=><div className="row" key={a.title+(a.topic_id||'')}><div>{a.title}<small>{a.percent}{t("% right · {strong} strong · {getting_there} getting there · {needs_study} need another round",{strong:a.strong,getting_there:a.getting_there,needs_study:a.needs_study})}{a.unit?' · '+a.unit:''}</small><Bar2 v={a.percent}/></div></div>)}</>}</>}</div></>}
function Gradebook({cid,back,toast,role}){
  const [d,setD]=useState(null),[open,setOpen]=useState(null),[stu,setStu]=useState(null)
  useEffect(()=>{api(`/courses/${cid}/gradebook`).then(setD).catch(e=>{toast(e.message);back()})},[cid])
  if(open)return <QuizResults id={open} back={()=>setOpen(null)} toast={toast} role={role}/>
  if(stu)return stu.quiz?<MyAttempts quiz={stu.quiz} user={stu.id} back={()=>setStu({...stu,quiz:null})} toast={toast} role={role}/>
    :<><Bar title={stu.name} sub={t("{course} · final {v}",{course:d.course,v:stu.final==null?'–':stu.final+'%'})} back={()=>setStu(null)}/><div className="main">{d.tests.map((t,i)=><button key={t.id} className="row rowbtn" disabled={stu.scores[i]==null} onClick={()=>setStu({...stu,quiz:t.id})}><div>{t.title}{stu.scores[i]!=null&&<PassPill ok={stu.scores[i]>=t.pass_percent}/>}<small>{t.unit||t("Course test")}{" "}{t("· {v} · pass {pass_percent}%",{v:stu.scores[i]==null?'not taken':'final '+stu.scores[i]+'%',pass_percent:t.pass_percent})}</small>{stu.scores[i]!=null&&<Bar2 v={stu.scores[i]}/>}</div>{stu.scores[i]!=null&&<ChevronRight size={18}/>}</button>)}</div></>
  if(!d)return <><Bar title={t("Gradebook")} back={back}/><div className="main"><Skeleton/></div></>
  return <><Bar title={t("Gradebook")} sub={d.course+' · '+pl(d.tests.length,'test')} back={back}/><div className="main">
    {!d.tests.length?<p className="known">{t("No published tests or quizzes in this course yet.")}</p>:<>
    <p className="known" style={{marginTop:0}}>{t("Each cell is a student's final (best) score. The final course score is the average of the tests they took. Tap a student or a test to drill down.")}</p>
    <div className="gbwrap"><table className="gb"><thead><tr><th>{t("Student")}</th>{d.tests.map(t=><th key={t.id}><button className="tool" onClick={()=>setOpen(t.id)} title={t.unit||t("Course test")}>{t.title}</button><small>{t("avg {v}%",{v:t.average??'–'})}</small></th>)}<th>{t("Final")}</th></tr></thead>
      <tbody>{d.students.map(r=><tr key={r.user_id}><td><button className="tool" onClick={()=>setStu(r)}>{r.name}</button></td>{r.scores.map((v,i)=><td key={i} className={v==null?'na':v>=d.tests[i].pass_percent?'':'low'}>{v==null?'–':v+'%'}</td>)}<td><b>{r.final==null?'–':r.final+'%'}</b><small>{r.taken}/{d.tests.length}</small></td></tr>)}</tbody></table></div>
    <p className="known">{t("A dash means not taken. Scores below a test's pass mark are marked with a lighter background.")}</p>
    <button className="btn ghost" onClick={()=>fetchFile(`/courses/${cid}/gradebook?format=csv`,'gradebook-'+d.course.replace(/\s+/g,'_')+'.csv',toast)}>{t("Download gradebook CSV")}</button></>}</div></>}
function ScoreCourse({c,back,toast,role}){  // one course of a student's scores: each test, then its attempts
  const [q,setQ]=useState(null)
  if(q)return <MyAttempts quiz={q} back={()=>setQ(null)} toast={toast} role={role}/>
  return <><Bar title={c.course} sub={t("Final score {v} · {taken} of {length} taken",{v:c.final==null?'–':c.final+'%',taken:c.taken,length:c.tests.length})} back={back}/><div className="main">
    {c.tests.map(t=><button key={t.id} className="row rowbtn" disabled={!t.attempts} onClick={()=>setQ(t.id)}><div>{t.title}{t.attempts>0&&<PassPill ok={t.passed}/>}<small>{t.unit||t("Course test")}{" "}{t("· {v} · pass {pass_percent}%",{v:t.attempts?`best ${t.best}% · latest ${t.latest}% · ${pl(t.attempts,'attempt')}`:'not taken yet',pass_percent:t.pass_percent})}</small>{t.attempts>0&&<Bar2 v={t.best}/>}</div>{t.attempts>0&&<ChevronRight size={18}/>}</button>)}
    <p className="known">{t("Your final score in a test is your best attempt. The course score is the average of the tests you have taken.")}</p></div></>}
function MyScores({onCourse}){  // a student's final score per course
  const [d,setD]=useState(null)
  useEffect(()=>{api('/me/scores').then(setD).catch(()=>setD({courses:[]}))},[])
  if(!d||!d.courses.length)return null
  return <><h3 className="sec first">{t("Scores")}</h3>{d.courses.map(x=><button key={x.course_id} className="row rowbtn" onClick={()=>onCourse(x)}><div>{x.course}<small>{x.final==null?t("No tests taken yet"):t("Final score {final}%",{final:x.final})}{" "}{t("· {taken} of {length} taken · {passed} passed",{taken:x.taken,length:x.tests.length,passed:x.passed})}</small>{x.final!=null&&<Bar2 v={x.final}/>}</div><ChevronRight size={18}/></button>)}</>}
// ---- courses students build from their own material ----
const Stars=({n,big})=><span className={'stars'+(big?' big':'')} role="img" aria-label={t("{n} of 3 stars",{n:n})}>{[1,2,3].map(i=><span key={i} className={i<=n?'on':''} aria-hidden="true">★</span>)}</span>
const STAR_HELP='★ topic completed · ★★ quiz passed · ★★★ mastered (90%+ in a quiz)'
// streak, level, this week, reviews due and the next step: the self-learner's "what now?" in one card
function LearnCard({me,onContinue,onReview,compact}){
  if(!me)return null
  const x=me.xp
  return <div className="learn"><div className={'lrow'+(compact?' one':'')}>
      {!compact&&<div className="lstat"><b><Flame size={20} className={'flame'+(me.streak?' on':'')} aria-hidden="true"/> {me.streak}</b><small>{me.active_today?t("day streak · studied today"):me.streak?t("day streak · study today to keep it"):t("day streak · start one today")}</small></div>}
      <div className="lstat"><b><span className="lvl">{t("Lv")}{" "}{x.level}</span>{" "}{t("{total} XP",{total:x.total})}</b><div className="meter" role="progressbar" aria-label={t("Progress to the next level")} aria-valuemin={0} aria-valuemax={x.span} aria-valuenow={x.into}><i style={{width:Math.round(100*x.into/x.span)+'%'}}/></div><small>{x.span-x.into}{" "}{t("XP to level")}{" "}{x.level+1}</small></div></div>
    {!compact&&<div className="week" aria-label={t("Days studied this week")}>{me.week.map(d=><span key={d.date} className={(d.active?'on':'')+(d.today?' today':'')} title={d.date}>{d.label}</span>)}</div>}
    {me.reviews_due>0&&<button className="btn" onClick={()=>onReview(me.review_courses[0].course_id)}><RotateCcw size={16}/>{" "}{t("Review {n} due",{n:pl(me.reviews_due,'topic')})}{me.review_courses.length>1?t(" (start with {course})",{course:me.review_courses[0].course}):''}</button>}
    {me.next&&<button className={'btn'+(me.reviews_due?' ghost':'')} onClick={()=>onContinue(me.next)}><Play size={16}/> {me.next.done?t("Continue"):t("Start")}: {me.next.topic}<small className="sub">{me.next.course}{" "}{t("· {done} of {topics} done",{done:me.next.done,topics:me.next.topics})}</small></button>}</div>}
const STEPS=['Name','Material','Slice','Preview'],AREA_LABEL={strong:'Strong',getting_there:'Getting there',needs_study:'Revisit'}
const Steps=({at})=><ol className="steps" aria-label={t("Setup steps")}>{STEPS.map((s,i)=><li key={s} className={i<at?'done':i===at?'on':''} aria-current={i===at?'step':undefined}><span>{i<at?<Check size={14}/>:i+1}</span>{s}</li>)}</ol>
const NOTES_HINT='Optional. For example: "One topic per verse", "Keep the vocabulary table in one topic", "Units should follow the chapters", "Make topics very short".'
function StudyHome({toast,start}){
  const [d,setD]=useState(null),[me,setMe]=useState(null),[open,setOpen]=useState(start&&start.id?start:null),[make,setMake]=useState(false),[title,setTitle]=useState(''),[busy,setBusy]=useState(false),[rev,setRev]=useState(null)
  const load=()=>{api('/study/courses').then(setD).catch(e=>toast(e.message));api('/study/me').then(setMe).catch(()=>{})}
  useEffect(()=>{if(!open&&!rev)load()},[open,rev])
  const review=async cid=>{try{setRev(await api(`/study/courses/${cid}/review`,{method:'POST'}))}catch(e){toast(e.message)}}
  useEffect(()=>{if(start?.review)review(start.review)},[])  // Home's "Review" button starts the review straight away
  if(rev)return <StudyQuizPlay quiz={rev} toast={toast} back={()=>setRev(null)}/>
  if(open)return open.wizard?<StudyWizard id={open.id} toast={toast} back={()=>setOpen(null)} done={()=>setOpen({id:open.id})}/>:<StudyCourse id={open.id} topic={open.topic} toast={toast} back={()=>setOpen(null)} setup={()=>setOpen({id:open.id,wizard:true})}/>
  const create=async()=>{setBusy(true);try{const r=await api('/study/courses',{method:'POST',body:{title}});setMake(false);setTitle('');setOpen({id:r.id,wizard:true})}catch(e){toast(e.message)}setBusy(false)}
  const card=(c,i)=><button key={c.id} className="row rowbtn" onClick={()=>setOpen({id:c.id,wizard:c.mine&&c.status!=='ready'})}><span className="dot" style={{background:COL[i%5]}}>{c.title[0]}</span>
    <div>{c.title}{c.status!=='ready'&&<span className="pill sm" style={{marginLeft:6}}>{t("Setup not finished")}</span>}{c.mine&&c.share==='program'&&<span className="pill sm okp" style={{marginLeft:6}}>{t("Shared")}</span>}
      <small>{c.status==='ready'?t("{completed} of {topics} topics completed",{completed:c.completed,topics:c.topics}):t("Continue the setup")}{!c.mine?t(" · by {owner}",{owner:c.owner}):''}</small>{c.status==='ready'&&c.topics>0&&<Bar2 v={100*c.completed/c.topics}/>}</div><ChevronRight size={18}/></button>
  return <><Bar title={t("Build a course")} sub={t("Turn your own notes into a course")}/><div className="main">
    {me&&me.courses>0&&<LearnCard me={me} onContinue={n=>setOpen({id:n.course_id,topic:n.topic_id})} onReview={review}/>}
    <p className="known" style={{marginTop:me&&me.courses>0?16:0}}>{t("Upload your notes, textbook chapters or handouts. The AI slices them into units and small topics, you check and adjust the outline, and then you study it with explanations, practice MCQs and quizzes.")}</p>
    <button className="btn lead" onClick={()=>setMake(true)}><Upload size={16}/>{" "}{t("New course from my material")}</button>
    {!d?<Skeleton/>:<>{d.mine.length>0&&<><h3 className="sec">{t("My courses")}</h3>{d.mine.map(card)}</>}
      {d.shared.length>0&&<><h3 className="sec">{t("Shared by classmates")}</h3>{d.shared.map(card)}</>}
      {!d.mine.length&&!d.shared.length&&<p className="known">{t("You have not built a course yet.")}</p>}</>}
    {make&&<Sheet close={()=>setMake(false)}><h3>{t("New course")}</h3><label htmlFor="sct">{t("Course name")}</label><input id="sct" autoFocus value={title} onChange={e=>setTitle(e.target.value)} onKeyDown={e=>e.key==='Enter'&&title.trim()&&create()} placeholder={t("e.g. Islamic Education · Unit 4")}/>
      <button className="btn" disabled={busy||!title.trim()} onClick={create}>{t("Next: add material")}</button><button className="btn ghost" onClick={()=>setMake(false)}>{t("Cancel")}</button></Sheet>}</div></>}
function StudyWizard({id,toast,back,done}){
  const confirm=useConfirm()
  const [c,setC]=useState(null),[step,setStep]=useState(null),[text,setText]=useState(''),[busy,setBusy]=useState(''),[notes,setNotes]=useState(''),[plan,setPlan]=useState(null),[dirty,setDirty]=useState(false),[peek,setPeek]=useState(null),fileRef=useRef()
  const load=async(go)=>{try{const d=await api('/study/courses/'+id);setC(d);setNotes(d.notes);setPlan(d.plan);setDirty(false);setStep(go??(d.plan?3:d.sources.length?2:1));return d}catch(e){toast(e.message);back()}}
  useEffect(()=>{load()},[id]);usePoll(!!c?.reading,()=>api('/study/courses/'+id).then(d=>setC(d)).catch(()=>{}))  // only the file list refreshes; the step and outline stay
  if(!c||step==null)return <><Bar title={t("Set up your course")} back={back}/><div className="main"><Skeleton/></div></>
  const files=async e=>{const fs=[...e.target.files];e.target.value='';for(const f of fs){if(tooBig(f)){toast(t("{name} is over {MAX_FILE_MB} MB. Split it into smaller files.",{name:f.name,MAX_FILE_MB:MAX_FILE_MB}));continue}setBusy('Reading '+f.name+'…')
      try{const r=await fetch(`/api/study/courses/${id}/files?name=${encodeURIComponent(f.name)}`,{method:'POST',headers:{'Content-Type':'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');toast(j.status==='reading'?t("{name} is scanned pages. Reading them now…",{name:f.name}):t("{name}: {n} read",{name:f.name,n:pl(j.words,'word')}))}catch(x){toast(f.name+': '+x.message)}}
    setBusy('');load(1)}
  const paste=async()=>{setBusy('Adding…');try{const r=await api(`/study/courses/${id}/text`,{method:'POST',body:{text}});setText('');toast(t("{n} added",{n:pl(r.words,'word')}))}catch(e){toast(e.message)}setBusy('');load(1)}
  const dropSrc=async i=>{if(!await confirm({title:t("Remove this material?"),body:t("Its text is taken out of the course. Any outline already made is cleared."),ok:t("Remove"),danger:true}))return;try{await api(`/study/courses/${id}/sources/${i}`,{method:'DELETE'});load(1)}catch(e){toast(e.message)}}
  const slice=async method=>{if(dirty&&!await confirm({title:t("Slice again?"),body:t("Your renames, merges and removals in the current outline are replaced."),ok:t("Slice again")}))return
    setBusy(method==='ai'?'The AI is reading your material and slicing it. This can take a minute…':'Slicing by headings…');try{const r=await api(`/study/courses/${id}/slice`,{method:'POST',body:{notes,method}});setPlan(r.plan);setDirty(false);setStep(3);window.scrollTo(0,0)}catch(e){toast(e.message)}setBusy('')}
  // preview edits stay on this screen until Finish (or Save outline) sends them
  const flat=plan?plan.units.flatMap((u,ui)=>u.topics.map((t,ti)=>({...t,ui,ti}))):[]
  const edit=f=>{const p=JSON.parse(JSON.stringify(plan));f(p);p.units=p.units.filter(u=>u.topics.length);setPlan(p);setDirty(true)}
  const rename=(ui,ti,v)=>edit(p=>{if(ti==null)p.units[ui].title=v;else p.units[ui].topics[ti].title=v})
  const merge=(ui,ti)=>edit(p=>{const all=p.units.flatMap((u,a)=>u.topics.map((t,b)=>[a,b])),k=all.findIndex(([a,b])=>a===ui&&b===ti),[na,nb]=all[k+1],nx=p.units[na].topics[nb]
    const t=p.units[ui].topics[ti];t.to=nx.to;t.words=(t.words||0)+(nx.words||0);p.units[na].topics.splice(nb,1)})
  const remove=(ui,ti)=>edit(p=>{p.units[ui].topics.splice(ti,1)})
  const savePlan=async()=>{const r=await api(`/study/courses/${id}/plan`,{method:'PUT',body:{units:plan.units}});setPlan(r.plan);setDirty(false)}
  const finish=async()=>{setBusy('Building your course…');try{if(dirty)await savePlan()
      try{await api(`/study/courses/${id}/finish`,{method:'POST',body:{}})}catch(e){if(!/already has topics/.test(e.message))throw e
        setBusy('');if(!await confirm({title:t("Replace the course's topics?"),body:t("Finishing again builds the topics from this outline. Progress and quiz results on the old topics are removed."),ok:t("Replace topics"),danger:true}))return
        setBusy('Building your course…');await api(`/study/courses/${id}/finish`,{method:'POST',body:{replace:true}})}
      toast(t("Your course is ready"));done()}catch(e){toast(e.message)}setBusy('')}
  const words=c.sources.reduce((a,x)=>a+x.words,0)
  return <><Bar title={c.title} sub={t("Set up · step {step}{v} of 4",{step:step,v:1})} back={back}/><div className="main">
    <Steps at={step}/>
    {busy&&<div className="qbox" role="status" style={{marginTop:0}}><b>{busy}</b></div>}
    {step===1&&<>
      <h3 className="sec first">{t("Add your material")}</h3><p className="known" style={{marginTop:0}}>{t("PDF, Word (.docx), or .txt and .md files, up to {MAX_FILE_MB} MB each. Add several and they are joined in the order you add them. You can also paste text.",{MAX_FILE_MB:MAX_FILE_MB})}{c.ocr_available?t(" Scanned PDFs are read with text recognition, a few seconds a page."):t(" Scanned PDFs can't be read on this server yet.")}</p>
      <input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown" onChange={files}/>
      <button className="btn" disabled={!!busy} onClick={()=>fileRef.current.click()}><Upload size={16}/>{" "}{t("Choose files")}</button>
      <label htmlFor="pst">{t("Or paste text")}</label><textarea id="pst" value={text} onChange={e=>setText(e.target.value)} placeholder={t("Paste notes here. Leave an empty line between paragraphs; lines starting with # become headings.")}/>
      <button className="btn ghost" disabled={!!busy||!text.trim()} onClick={paste}>{t("Add this text")}</button>
      {c.sources.length>0&&<><h3 className="sec">{t("Your material ·")}{" "}{pl(words,'word')}</h3>{c.sources.map((x,i)=><div className="row" key={i}><div>{x.name}<small role={x.status==='reading'?'status':undefined}>{x.status?srcLine(x):<>{x.kind.toUpperCase()} · {pl(x.words,'word')} · {pl(x.paras,'paragraph')}</>}</small></div><div className="acts"><button className="ic sm" aria-label={t("Remove {name}",{name:x.name})} onClick={()=>dropSrc(i)}><Trash2 size={16}/></button></div></div>)}
        <button className="btn" disabled={!!c.reading} onClick={()=>setStep(2)}>{c.reading?t("Reading scanned pages…"):t("Next: slice it into topics")}</button></>}</>}
    {step===2&&<>
      <h3 className="sec first">{t("How should it be sliced?")}</h3><p className="known" style={{marginTop:0}}>{t("The AI groups your {n} into units and the smallest topics that make sense on their own. It keeps your own words; it only decides where each topic starts and ends and what to call it.",{n:pl(c.paragraphs,'paragraph')})}</p>
      <label htmlFor="nts">{t("Notes for the AI")}</label><textarea id="nts" value={notes} onChange={e=>setNotes(e.target.value)} placeholder={NOTES_HINT}/>
      <AiNote o={c}/>
      <button className={'btn'+(c.ai_available&&c.ai_left!==0?'':' ghost')} disabled={!!busy||!c.ai_available||c.ai_left===0} onClick={()=>slice('ai')}><Sparkles size={16}/>{" "}{t("Slice with AI")}</button>
      <button className={'btn'+(c.ai_available&&c.ai_left!==0?' ghost':'')} disabled={!!busy} onClick={()=>slice('headings')}>{t("Slice by headings instead (no AI)")}</button>
      <button className="btn ghost" onClick={()=>setStep(1)}>{t("Back to material")}</button></>}
    {step===3&&plan&&<>
      <h3 className="sec first">{t("Check the outline")}</h3><p className="known" style={{marginTop:0}}>{pl(plan.units.length,'unit')}{t(", {n}{v}. Rename anything, merge a topic into the next one, or remove one you don't need. Not right? Change the notes and slice again.",{n:pl(flat.length,'topic'),v:c.sliced_by==='headings'?' · sliced by headings':''})}</p>
      {plan.units.map((u,ui)=><section key={ui} className="qbox"><label className="sr" htmlFor={'u'+ui}>{t("Unit {v} title",{v:ui+1})}</label><input id={'u'+ui} className="utitle" value={u.title} onChange={e=>rename(ui,null,e.target.value)}/>
        {u.topics.map((t,ti)=>{const last=ui===plan.units.length-1&&ti===u.topics.length-1
          return <div key={t.from} className="ptopic"><label className="sr" htmlFor={`t${ui}-${ti}`}>{t("Topic title")}</label><input id={`t${ui}-${ti}`} value={t.title} onChange={e=>rename(ui,ti,e.target.value)}/>
            <small className="known">{t.summary?t.summary+' · ':''}{pl(t.words||0,'word')}</small><p className="excerpt">{t.excerpt}{t.excerpt&&t.excerpt.length>=280?'…':''}</p>
            <div className="acts"><button className="tool" onClick={async()=>{try{setPeek({title:t.title,...(await api(`/study/courses/${id}/preview?start=${t.from}&end=${t.to}`))})}catch(e){toast(e.message)}}}>{t("Read it all")}</button>
              {!last&&<button className="tool" onClick={()=>merge(ui,ti)}>{t("Merge with next")}</button>}{flat.length>1&&<button className="tool" onClick={()=>remove(ui,ti)}>{t("Remove")}</button>}</div></div>})}</section>)}
      <h3 className="sec">{t("Slice it differently")}</h3><label htmlFor="nts2">{t("Notes for the AI")}</label><textarea id="nts2" value={notes} onChange={e=>setNotes(e.target.value)} placeholder={NOTES_HINT}/>
      <div className="two"><button className="btn ghost" disabled={!!busy} onClick={()=>slice('ai')}><Sparkles size={16}/>{" "}{t("Slice again with AI")}</button><button className="btn ghost" disabled={!!busy} onClick={()=>setStep(1)}>{t("Change material")}</button></div>
      <button className="btn" disabled={!!busy} onClick={finish}><Check size={16}/>{" "}{t("Finish: build my course")}</button>
      {dirty&&<button className="btn ghost" disabled={!!busy} onClick={async()=>{try{await savePlan();toast(t("Outline saved"))}catch(e){toast(e.message)}}}>{t("Save outline and finish later")}</button>}</>}
    {peek&&<Sheet close={()=>setPeek(null)}><h3>{peek.title}</h3><div className="prose"><Md>{peek.content}</Md></div><button className="btn ghost" onClick={()=>setPeek(null)}>{t("Close")}</button></Sheet>}</div></>}
function StudyCourse({id,topic:first,toast,back,setup}){
  const confirm=useConfirm()
  const [c,setC]=useState(null),[p,setP]=useState(null),[topic,setTopic]=useState(first||null),[ren,setRen]=useState(null),[rev,setRev]=useState(null),[find,setFind]=useState('')
  const load=()=>{api('/study/courses/'+id).then(setC).catch(e=>{toast(e.message);back()});api(`/study/courses/${id}/progress`).then(setP).catch(()=>{})}
  useEffect(()=>{if(!topic&&!rev)load()},[id,topic,rev])
  if(rev)return <StudyQuizPlay quiz={rev} toast={toast} back={()=>setRev(null)}/>
  if(topic)return <StudyTopicPage id={topic} toast={toast} back={()=>setTopic(null)} go={setTopic}/>
  if(!c)return <><Bar title={t("Course")} back={back}/><div className="main"><Skeleton/></div></>
  if(c.status!=='ready')return <><Bar title={c.title} back={back}/><div className="main"><p className="known">{t("This course is being set up.")}</p>{c.can_edit&&<button className="btn" onClick={setup}>{t("Continue the setup")}</button>}</div></>
  const all=c.units.flatMap(u=>u.topics),done=all.filter(t=>t.status==='completed').length
  const share=async v=>{try{await api('/study/courses/'+id,{method:'PUT',body:{share:v}});toast(v==='program'?t("Classmates in your program can now study it"):t("Only you can see it now"));load()}catch(e){toast(e.message)}}
  const del=async()=>{if(!await confirm({title:t("Delete “{title}”?",{title:c.title}),body:t("Its topics, your progress and your quiz results are removed. This can't be undone."),ok:t("Delete course"),danger:true}))return;try{await api('/study/courses/'+id,{method:'DELETE'});toast(t("Course deleted"));back()}catch(e){toast(e.message)}}
  const reopen=async()=>{if(!await confirm({title:t("Change the setup?"),body:t("You go back to the outline. Your topics stay as they are until you finish the setup again."),ok:t("Change the setup")}))return;try{await api(`/study/courses/${id}/reopen`,{method:'POST'});setup()}catch(e){toast(e.message)}}
  const next=all.find(t=>t.status!=='completed')
  return <><Bar title={c.title} sub={c.mine?t("Your course"):t("Shared by {owner}",{owner:c.owner})} back={back}/><div className="main">
    <div className="qbox" style={{marginTop:0}}><div className="mast"><div><b>{c.mastery}{t("% mastered")}</b><small>{done}{" "}{t("of {length} topics completed",{length:all.length})}</small></div><Stars n={c.mastery>=90?3:c.mastery>=60?2:c.mastery>0?1:0} big/></div><Bar2 v={c.mastery}/>
      {c.reviews_due>0&&<button className="btn" onClick={async()=>{try{setRev(await api(`/study/courses/${id}/review`,{method:'POST'}))}catch(e){toast(e.message)}}}><RotateCcw size={16}/>{" "}{t("Review {n} due",{n:pl(c.reviews_due,'topic')})}</button>}
      {p&&p.quizzed>0&&<p className="known" style={{margin:'8px 0 0'}}>{t("Quiz average {average}% over {n}.",{average:p.average,n:pl(p.quizzed,'topic')})}{p.summary&&' '+p.summary}</p>}
      {next&&<button className={'btn'+(c.reviews_due?' ghost':'')} onClick={()=>setTopic(next.id)}><Play size={16}/> {done?t("Continue"):t("Start")}: {next.title}</button>}<p className="known" style={{margin:'8px 0 0'}}>{STAR_HELP}</p></div>
    {all.length>12&&<div className="search" style={{marginTop:14}}><Search size={18}/><input type="search" aria-label={t("Find a topic")} placeholder={t("Find a topic")} value={find} onChange={e=>setFind(e.target.value)}/></div>}
    {c.units.map(u=>({...u,topics:u.topics.filter(t=>!find.trim()||(t.title+' '+(t.summary||'')).toLowerCase().includes(find.trim().toLowerCase()))})).filter(u=>u.topics.length).map((u,ui)=><section key={u.id}><h3 className={'sec'+(ui?'':' first')}>{u.title}</h3>
      {u.topics.map(t=><button key={t.id} className="row rowbtn" onClick={()=>setTopic(t.id)}><div>{t.title}{t.due&&<span className="pill sm" style={{marginLeft:6}}>{t("Review due")}</span>}<small>{t.summary||''}{t.best!=null?t("{v}best quiz {best}%",{v:t.summary?' · ':'',best:t.best}):''}</small></div><Stars n={t.stars}/><ChevronRight size={18}/></button>)}</section>)}
    {p&&p.areas.length>0&&<><h3 className="sec">{t("From your quizzes")}</h3><p className="known" style={{marginTop:0}}>{t("Your best quiz score in each topic, weakest first.")}</p>
      {p.areas.map(a=><button key={a.topic_id} className="row rowbtn" onClick={()=>setTopic(a.topic_id)}><div>{a.title}<span className={'pill sm '+(a.status==='strong'?'okp':a.status==='needs_study'?'off':'')} style={{marginLeft:6}}>{AREA_LABEL[a.status]}</span><small>{t("Best quiz {percent}%",{percent:a.percent})}</small><Bar2 v={a.percent}/></div><ChevronRight size={18}/></button>)}</>}
    {c.can_edit&&<><h3 className="sec">{t("Course settings")}</h3>
      <label id="shr">{t("Who can study it")}</label><div className="seg" role="group" aria-labelledby="shr" style={{gridTemplateColumns:'1fr 1fr',margin:'0 0 8px'}}>{[['private','Only me'],['program','My classmates']].map(([k,l])=><button key={k} className={c.share===k?'on':''} aria-pressed={c.share===k} onClick={()=>c.share!==k&&share(k)}>{l}</button>)}</div>
      <p className="known" style={{marginTop:0}}>{c.share==='program'?t("Students in your program can open it and take their own quizzes. Only you can change it."):t("Private: only you can see it.")}</p>
      <div className="two"><button className="btn ghost" onClick={()=>setRen(c.title)}><Pencil size={16}/>{" "}{t("Rename")}</button><button className="btn ghost" onClick={reopen}>{t("Change the setup")}</button></div>
      <button className="btn danger" onClick={del}>{t("Delete course")}</button></>}
    {ren!=null&&<Sheet close={()=>setRen(null)}><h3>{t("Rename course")}</h3><label htmlFor="rnm">{t("Course name")}</label><input id="rnm" autoFocus value={ren} onChange={e=>setRen(e.target.value)}/>
      <button className="btn" disabled={!ren.trim()} onClick={async()=>{try{await api('/study/courses/'+id,{method:'PUT',body:{title:ren}});setRen(null);load()}catch(e){toast(e.message)}}}>{t("Save")}</button><button className="btn ghost" onClick={()=>setRen(null)}>{t("Cancel")}</button></Sheet>}</div></>}
const AiNote=({o})=>!o?null:!o.ai_available?<p className="known" role="note">{o.ai_own_key?t("Add your own DeepSeek API key under “My AI key” in the menu to use explanations, quick checks and quizzes."):t("AI help is switched off right now. Ask your admin to add an AI key.")}</p>
  :o.ai_left!=null&&o.ai_left<=10?<p className="known" role="note">{o.ai_left?t("{n} left today for your own courses.",{n:pl(o.ai_left,'AI request')}):t("You have used today's AI requests for your own courses. Reviews still work; new questions come back tomorrow.")}</p>:null
function StudyTopicPage({id,toast,back,go}){
  const confirm=useConfirm()
  const [t,setT]=useState(null),[tab,setTab]=useState('notes'),[ex,setEx]=useState(null),[busy,setBusy]=useState(''),[quiz,setQuiz]=useState(null),[ed,setEd]=useState(null)
  const load=()=>api('/study/topics/'+id).then(setT).catch(e=>{toast(e.message);back()})
  useEffect(()=>{setT(null);setEx(null);setTab('notes');load();window.scrollTo(0,0)},[id])
  useEffect(()=>{if(!quiz&&t)load()},[quiz])
  if(quiz)return <StudyQuizPlay quiz={quiz} toast={toast} back={()=>setQuiz(null)} again={k=>make(k)} next={t?.next&&{title:t.next.title,go:()=>{setQuiz(null);go(t.next.id)}}}/>
  if(!t)return <><Bar title={t("Topic")} back={back}/><div className="main"><Skeleton/></div></>
  const explain=async()=>{setBusy('explain');try{setEx(await api(`/study/topics/${id}/explain`))}catch(e){toast(e.message)}setBusy('')}
  async function make(kind){setBusy(kind);try{setQuiz(await api(`/study/topics/${id}/quizzes`,{method:'POST',body:{kind}}))}catch(e){toast(e.message)}setBusy('')}
  const done=async on=>{try{await api(`/study/topics/${id}/progress`,{method:'PUT',body:{completed:on}});setT({...t,completed:on});toast(on?t("Marked as completed"):t("Marked as not completed"))}catch(e){toast(e.message)}}
  const saveEd=async()=>{try{await api('/study/topics/'+id,{method:'PUT',body:ed});setEd(null);setEx(null);toast(t("Topic saved"));load()}catch(e){toast(e.message)}}
  const delTopic=async()=>{if(!await confirm({title:t("Delete “{title}”?",{title:t.title}),body:t("The topic, your progress and your checks on it are removed. This can't be undone."),ok:t("Delete topic"),danger:true}))return
    try{await api('/study/topics/'+id,{method:'DELETE'});toast(t("Topic deleted"));back()}catch(e){toast(e.message)}}
  const noAi=!t.ai_available||t.ai_left===0
  return <><Bar title={t.title} sub={t("{course} › {unit} · {position} of {total}",{course:t.course,unit:t.unit,position:t.position,total:t.total})} back={back}/><div className="main">
    <div className="mast" style={{marginBottom:10}}><Stars n={t.stars} big/><small className="known">{['Not started yet','Completed','Quiz passed','Mastered'][t.stars]} · {STAR_HELP}</small></div>
    <Tabs label={t("Topic sections")} items={[['notes','Notes'],['explain','Explain']]} value={tab} onChange={setTab}/>
    {tab==='notes'&&<div className="prose"><Md>{t.content}</Md></div>}
    {tab==='explain'&&(ex?<div className="prose">{ex.cached&&<span className="chip">{t("Saved explanation · no AI request used")}</span>}<Md>{ex.text}</Md></div>
      :t.has_explain||!noAi?<button className="btn" disabled={!!busy} onClick={explain}><Sparkles size={16}/> {busy==='explain'?t("Thinking…"):t("Explain it to me")}</button>:<AiNote o={t}/>)}
    <h3 className="sec">{t("Check yourself")}</h3>
    <AiNote o={t}/>
    <div className="two"><button className="btn" disabled={!!busy||noAi} onClick={()=>make('mcq')}><ClipboardList size={16}/> {busy==='mcq'?t("Writing questions…"):t("Quick check · 5")}</button><button className="btn ghost" disabled={!!busy||noAi} onClick={()=>make('quiz')}><Target size={16}/> {busy==='quiz'?t("Writing the quiz…"):t("Full quiz · 10")}</button></div>
    <p className="known">{t("Quick check: 5 practice MCQs with the answer right after each one; 4 right marks the topic completed. Full quiz: 10 questions scored at the end; pass it for ★★, score 90% for ★★★. New questions every time, and the topic comes back for review before you forget it.")}</p>
    {t.attempts.length>0&&<><h3 className="sec">{t("Your results here")}</h3>{t.attempts.slice(0,5).map(a=><div className="row" key={a.id}><div>{a.kind==='quiz'?t("Quiz"):t("Practice MCQs")} · {a.score} / {a.total} · {a.percent}%<small>{when(a.at)}</small><Bar2 v={a.percent}/></div></div>)}</>}
    <div style={{marginTop:16}}>{t.completed?<button className="btn ghost" onClick={()=>done(false)}>{t("Mark as not completed")}</button>:<button className="btn" onClick={()=>done(true)}><Check size={16}/>{" "}{t("Mark as completed")}</button>}</div>
    <div className="two">{t.prev?<button className="btn ghost" onClick={()=>go(t.prev.id)}><ChevronLeft size={16}/>{" "}{t("Previous")}</button>:<span/>}{t.next&&<button className="btn ghost" onClick={()=>go(t.next.id)}>{t("Next")}{" "}<ChevronRight size={16}/></button>}</div>
    {t.can_edit&&<div className="two"><button className="btn ghost" onClick={()=>setEd({title:t.title,content:t.content})}><Pencil size={16}/>{" "}{t("Edit topic")}</button><button className="btn ghost" onClick={delTopic}><Trash2 size={16}/>{" "}{t("Delete topic")}</button></div>}
    {ed&&<Sheet close={()=>setEd(null)}><h3>{t("Edit topic")}</h3><label htmlFor="ett">{t("Title")}</label><input id="ett" value={ed.title} onChange={e=>setEd({...ed,title:e.target.value})}/>
      <label htmlFor="etc">{t("Text")}</label><textarea id="etc" style={{minHeight:260}} value={ed.content} onChange={e=>setEd({...ed,content:e.target.value})}/>
      <p className="known">{t("Markdown works: # for headings, - for lists, **bold**. Your progress and stars stay.")}</p>
      <button className="btn" disabled={!ed.title.trim()||!ed.content.trim()} onClick={saveEd}>{t("Save")}</button><button className="btn ghost" onClick={()=>setEd(null)}>{t("Cancel")}</button></Sheet>}</div></>}
function StudyQuizPlay({quiz,toast,back,again,next}){
  const mcq=quiz.kind!=='quiz',[ans,setAns]=useState(quiz.questions.map(()=>null)),[fb,setFb]=useState({}),[res,setRes]=useState(null),[busy,setBusy]=useState(false)
  const [flagged,setFlagged]=useState({})
  const flag=async i=>{try{await api(`/study/quizzes/${quiz.id}/flag`,{method:'POST',body:{index:i}});setFlagged(f=>({...f,[i]:true}));toast(t("Thanks. That question won't come back in your reviews."))}catch(e){toast(e.message)}}
  const pick=async(i,k)=>{if(res||(mcq&&fb[i]))return;setAns(a=>a.map((v,n)=>n===i?k:v));if(!mcq)return
    try{const r=await api(`/study/quizzes/${quiz.id}/check`,{method:'POST',body:{index:i,answer:k}});setFb(f=>({...f,[i]:r}))}catch(e){toast(e.message)}}
  const submit=async()=>{setBusy(true);try{setRes(await api(`/study/quizzes/${quiz.id}/attempt`,{method:'POST',body:{answers:ans}}));window.scrollTo(0,0)}catch(e){toast(e.message)}setBusy(false)}
  const left=ans.filter(a=>a==null).length,review=quiz.kind==='review',label=review?'Review':mcq?'Quick check':'Full quiz'
  const cheer=res&&[res.xp.level_up&&`Level ${res.xp.level}!`,res.stars.after>res.stars.before&&['','Topic completed','Quiz passed','Mastered!'][res.stars.after],res.completed_now&&res.stars.after<2&&'Topic completed'].filter((x,i,all)=>x&&all.indexOf(x)===i)
  return <><Bar title={label} sub={quiz.topic+' · '+pl(quiz.questions.length,'question')} back={back}/><div className="main">
    {res&&<div className={'qbox score'+(cheer.length?' win':'')} style={{marginTop:0}} role="status">
      {cheer.length>0&&<div className="cheer"><span aria-hidden="true">🎉</span> {cheer.join(' · ')}</div>}
      <h2 style={{margin:0}}>{res.score} / {res.total} · {res.percent}%</h2>
      <p className="known" style={{margin:'6px 0'}}><b className="xp">{t("+{gained} XP",{gained:res.xp.gained})}</b>{" "}{t("· level")}{" "}{res.xp.level}{res.stars.after>0&&<> · <Stars n={res.stars.after}/></>}</p>
      <p className="known">{review?t("Review done."):mcq?(res.percent>=80?t("Nicely done."):t("Practice done. Read the tricky parts again.")):res.passed?t("Passed. Well done!"):t("Below {pass_percent}%. Read the topic again and try a new quiz.",{pass_percent:res.pass_percent})}{res.summary&&' '+res.summary}{res.next_review&&' '+res.next_review+'.'}</p>
      {next&&<button className="btn" onClick={next.go}>{t("Next topic: {title}",{title:next.title})}{" "}<ChevronRight size={16}/></button>}
      <div className="two">{again&&<button className={'btn'+(next?' ghost':'')} onClick={()=>again(quiz.kind)}>{t("New")}{" "}{mcq?'questions':'quiz'}</button>}<button className={'btn'+(again||next?' ghost':'')} onClick={back}>{review?t("Done"):t("Back to the topic")}</button></div></div>}
    {res&&!mcq&&res.areas.length>0&&<><h3 className="sec">{t("What you know well and what to revisit")}</h3><AreaList areas={res.areas} onStudy={null} staff/></>}
    {quiz.questions.map((x,i)=>{const f=mcq?fb[i]:res&&res.results[i]
      return <div className="qbox" key={i}><b>{t("Question")}{" "}{i+1}{f?(f.ok?t(" · Right"):t(" · Wrong")):''}</b>{x.topic&&<small className="known" style={{display:'block'}}>{x.topic}</small>}<div className="prose"><Md>{x.text}</Md></div>
        {x.options.map((o,k)=>{const cls=f?(k===f.correct?' ok':k===ans[i]?' bad':''):ans[i]===k?' sel':''
          return <button key={k} className={'opt'+cls} disabled={!!f||!!res} aria-pressed={ans[i]===k} onClick={()=>pick(i,k)}><b className="olet">{LET[k]}</b><span className="obody"><Md>{o}</Md></span>{f&&k===f.correct&&<span className="otag ok"><Check size={14}/>{" "}{t("Correct")}</span>}</button>})}
        {f&&f.explanation&&<div className="known"><Md>{f.explanation}</Md></div>}
        {f&&(flagged[i]?<p className="known" style={{margin:'4px 0 0'}}>{t("Reported.")}</p>:<button className="tool" onClick={()=>flag(i)}>{t("This question is wrong")}</button>)}</div>})}
    {!res&&<><button className="btn" disabled={busy||(mcq&&Object.keys(fb).length<quiz.questions.length)} onClick={submit}>{busy?t("Checking…"):mcq?t("See my score"):t("Submit answers")}</button>
      {mcq?<p className="known">{t("Pick an answer to see right away if it is right.")}{Object.keys(fb).length<quiz.questions.length?t(" {v} to go.",{v:quiz.questions.length-Object.keys(fb).length}):''}</p>:left>0&&<p className="known">{left}{" "}{t("unanswered. Blank answers count as wrong.")}</p>}</>}</div></>}
function BankSheet({close,onAdd,toast}){
  const confirm=useConfirm()
  const [q,setQ]=useState(''),[tag,setTag]=useState(''),[mine,setMine]=useState(false),[d,setD]=useState(null),[sel,setSel]=useState({}),[n,setN]=useState(0)
  useEffect(()=>{const t=setTimeout(()=>api('/bank?limit=30&q='+encodeURIComponent(q)+'&tag='+encodeURIComponent(tag)+(mine?'&mine=true':'')).then(setD).catch(e=>toast(e.message)),250);return()=>clearTimeout(t)},[q,tag,mine,n,toast])
  const picked=Object.values(sel),more=async()=>{try{const r=await api('/bank?limit=30&offset='+d.items.length+'&q='+encodeURIComponent(q)+'&tag='+encodeURIComponent(tag)+(mine?'&mine=true':''));setD({...d,items:[...d.items,...r.items]})}catch(e){toast(e.message)}}
  const flip=x=>{const c={...sel};c[x.id]?delete c[x.id]:c[x.id]=x;setSel(c)}
  const del=async x=>{if(!await confirm({title:t("Delete this question from the bank?"),body:t("It disappears for everyone. Quizzes that already use it keep their copy."),ok:t("Delete"),danger:true}))return;try{await api('/bank/'+x.id,{method:'DELETE'});const c={...sel};delete c[x.id];setSel(c);setN(n+1)}catch(e){toast(e.message)}}
  return <Sheet close={close}><h3>{t("Question bank")}</h3><p className="known">{t("Questions shared by every teacher. Adding one puts a copy in this quiz, so later changes to the bank never alter a quiz students are taking.")}</p>
    <div className="search"><Search size={18}/><input type="search" aria-label={t("Search the bank")} placeholder={t("Search questions, tags or source")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label={t("Filter by tag")} value={tag} onChange={e=>setTag(e.target.value)}><option value="">{t("All tags")}</option>{(d?.tags||[]).map(t=><option key={t} value={t}>{t}</option>)}</select>
      <label className="chk" style={{padding:0}}><input type="checkbox" checked={mine} onChange={e=>setMine(e.target.checked)}/>{" "}{t("Only mine")}</label></div>
    {!d?<div className="sk"/>:!d.items.length?<p className="known">{q||tag||mine?t("Nothing matches that."):t("The bank is empty. Use “Save to bank” in any quiz to start it.")}</p>:d.items.map(x=><div key={x.id} className="row"><label className="chk" style={{alignItems:'flex-start',flex:1}}><input type="checkbox" checked={!!sel[x.id]} onChange={()=>flip(x)}/><span><span style={{display:'block'}}>{x.text.length>180?x.text.slice(0,180)+'…':x.text}</span><small>{x.options.length}{" "}{t("answers{v} · by",{v:x.tags.length>0&&' · '+x.tags.join(', ')})}{" "}{x.owner||'someone'}{x.uses>0&&t(" · used {n}",{n:pl(x.uses,'time')})}</small></span></label>{x.can_edit&&<button className="ic sm" aria-label={t("Delete from the bank")} onClick={()=>del(x)}><Trash2 size={16}/></button>}</div>)}
    {d&&d.items.length<d.total&&<ShowMore left={d.total-d.items.length} onClick={more}/>}
    <button className="btn" disabled={!picked.length} onClick={()=>onAdd(picked)}>{picked.length?t("Add {n}",{n:pl(picked.length,'question')}):t("Choose questions to add")}</button><button className="btn ghost" onClick={close}>{t("Cancel")}</button></Sheet>}

function CopySheet({kind,id,title,close,toast}){
  const [tree,setTree]=useState(null),[cid,setCid]=useState(''),[uid,setUid]=useState(''),[wq,setWq]=useState(true),[busy,setBusy]=useState(false),[res,setRes]=useState(null)
  useEffect(()=>{api('/tree').then(setTree).catch(e=>{toast(e.message);close()})},[toast,close])
  const courses=(tree||[]).flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>c.editable&&!c.shared).map(c=>({...c,label:`${p.name} › ${s.name} › ${c.name}`}))))
  const dest=courses.find(c=>String(c.id)===cid)
  const run=async()=>{setBusy(true);try{setRes(await api(`/${kind==='topic'?'topics':'units'}/${id}/copy`,{method:'POST',body:kind==='topic'?{unit_id:+uid}:{course_id:+cid,with_quizzes:wq}}))}catch(e){toast(e.message)}setBusy(false)}
  if(res)return <Sheet close={close}><h3>{t("Copied")}</h3><p className="known">{kind==='topic'?t("“{title}” is a draft in {label} › {name}.",{title:res.title,label:dest.label,name:dest.units.find(u=>u.id===res.unit_id)?.name}):t("“{name}” is in {label} with {n}{v}.",{name:res.name,label:dest.label,n:pl(res.topics,'topic'),v:res.quizzes?` and ${pl(res.quizzes,'quiz')}`:''})}{" "}{t("Everything arrives as a draft, so students see nothing until you publish it.")}</p><button className="btn" onClick={close}>{t("Done")}</button></Sheet>
  return <Sheet close={close}><h3>{t("Copy")}{" "}{kind==='topic'?'topic':'unit'}</h3><p className="known">{t("Makes a copy of “{title}”{v} in a course you can edit. The original is not changed. Reading progress and bookmarks are not copied.",{title:title,v:kind==='unit'?' with its topics'+(' and, if you may edit the original, its quizzes'):''})}</p>
    {!tree?<div className="sk"/>:!courses.length?<p className="known">{t("You do not own a course to copy into. An admin makes you the owner of a course.")}</p>:<>
      <label htmlFor="cc">{t("Copy into course")}</label><select id="cc" value={cid} onChange={e=>{setCid(e.target.value);setUid('')}}><option value="">{t("Choose a course")}</option>{courses.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select>
      {kind==='topic'&&dest&&<><label htmlFor="cu">{t("Unit")}</label><select id="cu" value={uid} onChange={e=>setUid(e.target.value)}><option value="">{t("Choose a unit")}</option>{dest.units.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select>{!dest.units.length&&<p className="known">{t("That course has no units yet. Add a unit first.")}</p>}</>}
      {kind==='unit'&&<label className="chk"><input type="checkbox" checked={wq} onChange={e=>setWq(e.target.checked)}/>{" "}{t("Include its quizzes (as drafts)")}</label>}</>}
    <button className="btn" disabled={busy||!dest||(kind==='topic'&&!uid)} onClick={run}>{busy?t("Copying…"):t("Copy")}</button><button className="btn ghost" onClick={close}>{t("Cancel")}</button></Sheet>}
const FIELD_LABEL=L({title:'Title',content:'Notes',content_format:'Content format',sample_content:'Sample answer',question_pattern:'Question pattern',guideline:'Answer guideline'})
const lineDiff=(a,b)=>{const x=a.split('\n'),y=b.split('\n'),n=x.length,m=y.length
  if(n*m>250000)return [...x.map(t=>({k:'del',t})),...y.map(t=>({k:'add',t}))]  // very long texts: show both rather than spend the time
  const L=Array.from({length:n+1},()=>new Uint16Array(m+1))
  for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)L[i][j]=x[i]===y[j]?L[i+1][j+1]+1:Math.max(L[i+1][j],L[i][j+1])
  const out=[];let i=0,j=0
  while(i<n&&j<m){if(x[i]===y[j]){out.push({k:'same',t:x[i]});i++;j++}else if(L[i+1][j]>=L[i][j+1])out.push({k:'del',t:x[i++]});else out.push({k:'add',t:y[j++]})}
  while(i<n)out.push({k:'del',t:x[i++]});while(j<m)out.push({k:'add',t:y[j++]});return out}
function HistorySheet({tid,close,done,toast}){
  const confirm=useConfirm()
  const [list,setList]=useState(null),[v,setV]=useState(null),[busy,setBusy]=useState(false)
  useEffect(()=>{api(`/topics/${tid}/versions`).then(setList).catch(e=>{toast(e.message);close()})},[tid,toast,close])
  const open=async x=>{try{setV({...(await api('/topic-versions/'+x.id)),current:x.current})}catch(e){toast(e.message)}}
  const restore=async()=>{if(!await confirm({title:t("Put this version back?"),body:t("What is there now stays in the history, so you can undo it."),ok:t("Restore version")}))return;setBusy(true)
    try{await api(`/topic-versions/${v.id}/restore`,{method:'POST'});toast(t("Version restored"));done()}catch(e){toast(e.message);setBusy(false)}}
  if(v){const changed=Object.keys(FIELD_LABEL).filter(k=>v[k]!==v.now[k])
    return <Sheet close={close}><button className="link" onClick={()=>setV(null)}><ChevronLeft size={16}/>{" "}{t("All versions")}</button>
      <h3>{v.saved_at?when(v.saved_at):t("Earlier version")}</h3><p className="known">{v.note}{v.current?t(" · this is the current text"):''}</p>
      {!changed.length&&<p className="known">{t("Same as the current text.")}</p>}
      {changed.map(k=><div key={k} className="qbox"><b>{FIELD_LABEL[k]}</b><p className="known" style={{margin:'2px 0 8px'}}>{t("Red lines are in this version only. Green lines are in the current text.")}</p>
        <div className="diff">{lineDiff(v[k],v.now[k]).map((l,i)=><div key={i} className={'dl '+l.k}>{l.t||'\u00a0'}</div>)}</div></div>)}
      {!v.current&&<button className="btn" disabled={busy} onClick={restore}>{t("Restore this version")}</button>}<button className="btn ghost" onClick={close}>{t("Close")}</button></Sheet>}
  return <Sheet close={close}><h3>{t("Version history")}</h3><p className="known">{t("Every save is kept (the latest {v}). Pick one to compare it with the current text.",{v:100})}</p>
    {!list?<div className="sk"/>:!list.length?<p className="known">{t("No versions recorded yet. They appear the next time this topic is saved.")}</p>
      :list.map(x=><button key={x.id} className="row" style={{width:'100%',textAlign:'start',background:'none'}} onClick={()=>open(x)}><div>{x.saved_at&&!(x.by===null&&x.note.startsWith('Before'))?when(x.saved_at):t("Before history began")}<small>{x.note}{x.by?' · '+x.by:''}</small></div>{x.current&&<span className="pill">{t("Current")}</span>}<ChevronRight size={16}/></button>)}
    <button className="btn ghost" onClick={close}>{t("Close")}</button></Sheet>}
function Topic({id:first,back,toast,role}){
  const [practice,setPractice]=useState(null),[checking,setChecking]=useState(''),[reading,setReading]=useState(false),[hls,setHls]=useState([]),autoRead=useRef(null)
  const [id,setId]=useState(first),[editing,setEditing]=useState(false),[v,setV]=useState(0),[t,setT]=useState(null),[tab,setTab]=useState('notes'),[known,setKnown]=useState([]),[ai,setAi]=useState({}),[aiOk,setAiOk]=useState(null),[ownKey,setOwnKey]=useState(false),[aiMsg,setAiMsg]=useState(''),[busy,setBusy]=useState(false),[bm,setBm]=useState(false),[pv,setPv]=useState(false),[hist,setHist]=useState(false),[cp,setCp]=useState(false),[gone,setGone]=useState('')
  const [mat,setMat]=useState(false),[upNext,setUpNext]=useState(null),opened=useRef(false),jump=nid=>{opened.current=false;setUpNext(null);setGone('');setT(null);setTab('notes');setAi({});setAiMsg('');setKnown([]);setEditing(false);setId(nid);window.scrollTo(0,0)},learn=r=>setT(p=>({...p,status:r.status,overdue:r.overdue,late:r.late,completed_at:r.completed_at}))
  useEffect(()=>{api('/topics/'+id).then(x=>{setT(x);setBm(!!x.bookmarked)
    if(role==='student'&&x.content&&autoRead.current!==id){autoRead.current=id;setReading(true)}  // students land in the full-screen reader
    if(!opened.current){opened.current=true;api(`/topics/${id}/read`,{method:'POST'}).then(r=>{setKnown(r.known);learn(r)}).catch(()=>{})}}).catch(e=>{toast(e.message);if(/unavailable right now/.test(e.message))setGone(e.message)})},[id,v])  // opening starts it, after the page has loaded
  const setDone=async on=>{try{learn(await api(`/topics/${id}/complete`,{method:on?'PUT':'DELETE'}));toast(on?t("Marked as completed"):t("Marked as not completed"))}catch(e){toast(e.message);return}
    setUpNext(null);if(!on||role!=='student')return
    try{const items=(await api('/me/session')).session?.items||[];if(items.some(x=>x.id===id&&x.kind!=='review'&&x.src!=='study'))setUpNext({items,next:items.find(x=>!x.done)})}catch{/* no session today: nothing to lead on to */}}
  useEffect(()=>{api('/ai/status').then(r=>{setAiOk(r.available);setOwnKey(!!r.own_key)}).catch(()=>{})},[id])
  useEffect(()=>{setHls([]);api(`/topics/${id}/highlights`).then(r=>setHls(r.items)).catch(()=>{})},[id,v])
  const dropHl=async h=>{try{await api('/me/highlights/'+h.id,{method:'DELETE'});setHls(l=>l.filter(x=>x.id!==h.id));toast(t("Highlight removed"))}catch(e){toast(e.message)}}
  const ask=async k=>{setBusy(true);setAiMsg('');try{const r=await api(`/topics/${id}/ai/${k}`);setAi(a=>({...a,[k]:r}))}catch(e){setAiMsg(e.message)}setBusy(false)}
  async function practise(kind){setChecking(kind);try{setPractice(await api(`/topics/${id}/practice`,{method:'POST',body:{kind}}))}catch(e){toast(e.message)}setChecking('')}
  if(mat&&t)return <MyMaterial cid={t.course_id} name={t.course} back={()=>{setMat(false);setAi({});setAiMsg('');setV(v+1)}} toast={toast}/>  // clear saved answers: the notes may have changed, so Explain must be asked again
  if(practice)return <StudyQuizPlay quiz={practice} toast={toast} back={()=>setPractice(null)} again={k=>practise(k)}/>
  if(editing)return <TopicEditor role={role} toast={toast} edit={{id}} done={()=>{setEditing(false);setV(v+1)}} cancel={()=>setEditing(false)}/>
  if(gone)return <><Bar title={t("Unavailable")} back={back}/><div className="main"><div className="hero"><h2>{gone}</h2><p>{t("It has been archived. Check back later or ask your teacher.")}</p></div></div></>
  if(!t)return <><Bar title={t("Loading")} back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const flip=async()=>{const on=!bm;setBm(on);try{await api(`/topics/${id}/bookmark`,{method:on?'PUT':'DELETE'});toast(on?t("Bookmarked"):t("Bookmark removed"))}catch(e){setBm(!on);toast(e.message)}}
  const view=k=>ai[k]?<div className="prose">{ai[k].cached&&<span className="chip">{t("Saved answer · no tokens used")}</span>}{ai[k].own_notes&&<span className="chip">{t("Written with your own notes")}</span>}<Md>{ai[k].text}</Md></div>
    :aiOk===false?<p className="known">{ownKey?t("Add your own DeepSeek API key under “My AI key” in the menu to use AI help."):t("AI unavailable. Try again later.")}</p>
    :<><button className="btn" disabled={busy} onClick={()=>ask(k)}><Sparkles size={16}/> {busy?t("Thinking…"):k==='explain'?t("Explain it to me"):t("Show a sample answer")}</button>{t.my_notes&&<p className="known">{t("Uses your own notes too. It counts toward your daily AI requests.")}</p>}{aiMsg&&<p className="known">{aiMsg}</p>}</>
  return <><Bar title={t.title} sub={[t.program,t.semester,t.course,t.unit].filter(Boolean).join(' › ')} back={back} right={role!=='admin'&&<button className={'ic'+(bm?' on':'')} aria-label={bm?t("Remove bookmark"):t("Bookmark this topic")} aria-pressed={bm} onClick={flip}><Bookmark fill={bm?'currentColor':'none'}/></button>}/><div className="main">
    {t.can_edit&&pv&&<div className="qbox" style={{marginTop:0}}><b>{t("Previewing as a student")}</b><p className="known" style={{margin:'4px 0 8px'}}>{t("This is what students see: no editing buttons, and drafts show as unavailable to them.")}</p><button className="btn ghost" style={{marginTop:0}} onClick={()=>setPv(false)}>{t("Back to editing")}</button></div>}
    {t.can_edit&&!pv&&<div className="two" style={{marginBottom:12}}><button className="btn ghost" style={{marginTop:0}} onClick={()=>setEditing(true)}><Pencil size={16}/>{" "}{t("Edit topic")}</button>
      <button className="btn ghost" style={{marginTop:0}} onClick={async()=>{try{await api(`/topics/${id}/publish`,{method:'PUT',body:{published:!t.published}});toast(t.published?t("Moved to drafts"):t("Published"));setV(v+1)}catch(e){toast(e.message)}}}>{t.published?<><EyeOff size={16}/>{" "}{t("Unpublish")}</>:<><Eye size={16}/>{" "}{t("Publish")}</>}</button></div>}
    <div className="qbox" style={{marginTop:0}}><div className="row"><div>{t.learning_due_at?when(t.learning_due_at):t("No deadline")}<small>{t("Learn by")}</small></div>{t.overdue&&role==='student'&&<span className="pill off sm">{t("Overdue")}</span>}</div>
      {role==='student'&&<><div className="row"><div>{STATUS[t.status]}{t.status==='completed'&&t.completed_at&&t(" on {n}{v}",{n:when(t.completed_at),v:t.late?', after the deadline':''})}<small>{t("Your status")}</small></div></div>
        {t.status==='completed'?<button className="btn ghost" onClick={()=>setDone(false)}>{t("Mark as not completed")}</button>:<button className="btn" onClick={()=>setDone(true)}><Check size={16}/>{" "}{t("Mark as completed")}</button>}</>}</div>
    {upNext&&<div className="qbox" role="status"><b>{t("Today's session · {length} of {length2} done",{length:upNext.items.filter(x=>x.done).length,length2:upNext.items.length})}</b>
      {!upNext.next?<p className="known" style={{margin:'4px 0 0'}}>{t("That's today's session done. See you next study day.")}</p>
        :upNext.next.kind!=='review'&&upNext.next.src!=='study'?<button className="btn" onClick={()=>jump(upNext.next.id)}>{t("Next:")}{" "}{upNext.next.title}<ChevronRight size={16}/></button>
        :<button className="btn ghost" onClick={back}>{t("Back for the next part:")}{" "}{upNext.next.title}</button>}</div>}
    {t.can_edit&&!pv&&<><button className="tool" onClick={()=>setPv(true)}><Eye size={14}/>{" "}{t("Preview as student")}</button><button className="tool" onClick={()=>setHist(true)}><History size={14}/>{" "}{t("Version history")}</button></>}
    {role!=='student'&&!pv&&<button className="tool" onClick={()=>setCp(true)}><Copy size={14}/>{" "}{t("Copy to another course")}</button>}
    {cp&&<CopySheet kind="topic" id={id} title={t.title} toast={toast} close={()=>setCp(false)}/>}
    {hist&&<HistorySheet tid={id} toast={toast} close={()=>setHist(false)} done={()=>{setHist(false);setV(v+1)}}/>}
    {t.can_edit&&!t.published&&<p className="known" style={{marginTop:0}}>{t("Draft · students cannot see it")}</p>}
    <Tabs label={t("Topic sections")} items={[['notes','Notes'],['explain','Explain'],['answer','Sample answer']]} value={tab} onChange={setTab}/>
    {known.length>0&&tab==='explain'&&<p className="known">{t("You’ve already covered:")}{" "}{known.join(', ')}</p>}
    {tab==='notes'&&t.content&&<button className="btn lead" onClick={()=>setReading(true)}><Maximize2 size={16}/> {t.content_format==='interactive'?t("Open the interactive page"):t("Read in full screen")}</button>}
    {tab==='notes'&&<div className="prose">{t.content?(t.content_format==='interactive'?<p className="known" style={{margin:0}}>{t("This topic is an interactive page. Open it above to use it and highlight its text.")}</p>:<Body text={t.content} format={t.content_format}/>):!t.my_notes&&<Md>{t("No notes yet.")}</Md>}{t.my_notes&&<>{t.content&&<h3>{t("Your notes")}</h3>}{!t.content&&<span className="chip">{t("Your notes")}</span>}<Md>{t.my_notes}</Md></>}{t.question_pattern&&<><h3>{t("Question pattern")}</h3><Md>{t.question_pattern}</Md></>}{t.guideline&&<><h3>{t("Answer guideline")}</h3><Md>{t.guideline}</Md></>}{role==='student'&&<button className="tool" onClick={()=>setMat(true)}><FileText size={14}/> {t.my_notes?t("Update your notes for this course"):t("Add your own notes for this topic")}</button>}</div>}
    {tab==='notes'&&hls.length>0&&<><h3 className="sec">{t("Your highlights ({length})",{length:hls.length})}</h3>{hls.map(h=><HlItem key={h.id} h={h} toast={toast} onSaved={r=>setHls(l=>l.map(x=>x.id===r.id?r:x))} onDrop={()=>dropHl(h)}/>)}</>}
    {tab==='explain'&&view('explain')}{tab==='answer'&&view('answer')}
    {reading&&<Reader t={t} auto={role==='student'} toast={toast} onList={setHls} close={()=>setReading(false)}/>}
    {role==='student'&&aiOk!==false&&<><h3 className="sec">{t("Check yourself")}</h3><div className="two"><button className="btn ghost" disabled={!!checking} onClick={()=>practise('mcq')}><ClipboardList size={16}/> {checking==='mcq'?t("Writing questions…"):t("Quick check · 5")}</button><button className="btn ghost" disabled={!!checking} onClick={()=>practise('quiz')}><Target size={16}/> {checking==='quiz'?t("Writing the quiz…"):t("Full quiz · 10")}</button></div>
      <p className="known" style={{marginTop:4}}>{t("The AI writes new questions from this topic's notes each time. Quick check: the answer right after each question. Full quiz: scored at the end.")}</p></>}
    {t.nav&&t.nav.total>1&&<nav className="pager" aria-label={t("Topics in this unit")}><button className="btn ghost" disabled={!t.nav.prev} onClick={()=>jump(t.nav.prev.id)} aria-label={t.nav.prev?t("Previous topic: {title}",{title:t.nav.prev.title}):t("No previous topic")}><ChevronLeft size={18}/><span>{t.nav.prev?t.nav.prev.title:t("Previous")}</span></button>
      <small>{t.nav.position}{" "}{t("of")}{" "}{t.nav.total}</small>
      <button className={'btn'+(t.nav.next?'':' ghost')} disabled={!t.nav.next} onClick={()=>jump(t.nav.next.id)} aria-label={t.nav.next?t("Next topic: {title}",{title:t.nav.next.title}):t("No next topic")}><span>{t.nav.next?t.nav.next.title:t("Next")}</span><ChevronRight size={18}/></button></nav>}</div></>}

// a topic's content full screen, with the reader's own highlights: select text to highlight it, tap a highlight to remove it.
// Markdown and HTML are highlighted right here; an interactive page runs in a sandboxed frame (no access to the app or the sign-in) and
// sends its highlight requests here by postMessage, which this page checks and saves for it.
const Content=memo(({text,format})=><Body text={text} format={format}/>)
const HL_COL={coral:'#ff9292',yellow:'#ffd60a',green:'#50c878',blue:'#5aa0ff'}
// one saved highlight: the passage in its colour, where it is (on the list of all of them), the reader's note, and remove
function HlItem({h,where,onGo,onSaved,onDrop,focus,toast}){
  const [ed,setEd]=useState(!!focus),[note,setNote]=useState(h.note||''),ta=useRef(null)
  useEffect(()=>{if(focus)setEd(true)},[focus])
  useEffect(()=>{if(ed)ta.current?.focus()},[ed])
  const save=async()=>{try{onSaved(await api('/me/highlights/'+h.id,{method:'PATCH',body:{note}}));setEd(false)}catch(e){toast(e.message)}}
  return <div className="hlrow" style={{'--hc':HL_COL[h.color]||HL_COL.coral}}><div className="hlbody">
    {onGo?<button className="hltext" onClick={onGo}>{h.text}</button>:<p className="hltext">{h.text}</p>}
    {where&&<small className="hlwhere">{where}</small>}
    {ed?<><textarea ref={ta} className="hlnote" value={note} maxLength={2000} placeholder={t("Your note")} aria-label={t("Your note")} onChange={e=>setNote(e.target.value)}/><div className="tools"><button onClick={save}>{t("Save note")}</button><button onClick={()=>{setNote(h.note||'');setEd(false)}}>{t("Cancel")}</button></div></>
      :h.note?<button className="hlnoted" onClick={()=>setEd(true)} title={t("Edit note")}>{h.note}</button>:<button className="link hladd" onClick={()=>setEd(true)}>{t("Add a note")}</button>}</div>
    <button className="ic sm" aria-label={t("Remove highlight")} title={t("Remove")} onClick={onDrop}><Trash2 size={15}/></button></div>}
function Reader({t,auto,toast,onList,close}){
  const [list,setList]=useState(null),[panel,setPanel]=useState(false),[noteFor,setNoteFor]=useState(null),[fs,setFs]=useState(!!document.fullscreenElement),box=useRef(null),frame=useRef(null),hl=useRef(null),now=useRef([])
  const inter=t.content_format==='interactive',ready=list!==null
  now.current=list||[]
  useEffect(()=>{api(`/topics/${t.id}/highlights`).then(r=>setList(r.items)).catch(e=>{toast(e.message);setList([])})},[t.id,toast])
  useEffect(()=>{if(list)onList?.(list)},[list,onList])
  useEffect(()=>{document.body.style.overflow='hidden';if(auto)document.documentElement.requestFullscreen?.().catch(()=>{/* the browser wants a tap first: the button is there */})
    const f=()=>setFs(!!document.fullscreenElement),k=e=>{if(e.key==='Escape'&&!document.fullscreenElement)close()}
    document.addEventListener('fullscreenchange',f);addEventListener('keydown',k)
    return()=>{document.body.style.overflow='';document.removeEventListener('fullscreenchange',f);removeEventListener('keydown',k);if(document.fullscreenElement)document.exitFullscreen().catch(()=>{})}},[auto,close])
  const save=useCallback(async h=>{const r=await api(`/topics/${t.id}/highlights`,{method:'POST',body:{text:String(h.text||'').slice(0,5000),prefix:String(h.prefix||'').slice(-200),color:h.color||'coral'}});setList(l=>[...l,r]);return r},[t.id])
  const remove=useCallback(async id=>{await api('/me/highlights/'+id,{method:'DELETE'});setList(l=>l.filter(x=>x.id!==+id))},[])
  const recolor=useCallback(async(id,color)=>{const r=await api('/me/highlights/'+id,{method:'PATCH',body:{color}});setList(l=>l.map(x=>x.id===r.id?r:x));return r},[])
  const noteOn=useCallback(id=>{setPanel(true);setNoteFor(+id)},[])
  useEffect(()=>{if(!ready||inter||!box.current||!window.zgHighlighter)return
    const loud=f=>(...a)=>f(...a).catch(e=>{toast(e.message);throw e})
    hl.current=window.zgHighlighter.attach(box.current,{list:now.current,save:loud(save),remove:loud(remove),update:loud((id,c)=>recolor(id,c.color)),note:noteOn})
    return()=>{hl.current?.detach();hl.current=null}},[ready,inter,save,remove,recolor,noteOn,toast])
  useEffect(()=>{if(!ready||!inter)return
    const win=()=>frame.current?.contentWindow,reply=(k,d)=>win()?.postMessage({zg:1,k,...d},'*')
    const on=async e=>{const d=e.data;if(!win()||e.source!==win()||!d||d.zg!==1)return  // only our own frame, and only these requests
      if(d.type==='ready')win().postMessage({zg:1,type:'init',list:now.current.map(({id,text,prefix,color})=>({id,text,prefix,color}))},'*')
      else if(d.type==='save'){try{const h=await save(d);reply(d.k,{id:h.id})}catch(er){toast(er.message);reply(d.k,{error:1})}}
      else if(d.type==='remove'){try{await remove(+d.id);reply(d.k,{})}catch(er){toast(er.message);reply(d.k,{error:1})}}
      else if(d.type==='update'){try{await recolor(+d.id,String(d.color));reply(d.k,{})}catch(er){toast(er.message);reply(d.k,{error:1})}}
      else if(d.type==='note')noteOn(d.id)
      else if(d.type==='store'&&d.data&&typeof d.data==='object'){const data=Object.fromEntries(Object.entries(d.data).filter(([,v])=>typeof v==='string'))  // the page's localStorage, kept for this person
        api(`/topics/${t.id}/store`,{method:'PUT',body:{data}}).catch(er=>toast(er.message))}}
    addEventListener('message',on);return()=>removeEventListener('message',on)},[ready,inter,save,remove,recolor,noteOn,toast,t.id])
  const goTo=id=>{if(inter)frame.current?.contentWindow?.postMessage({zg:1,type:'scroll',id},'*');else hl.current?.scrollTo(id);if(innerWidth<900)setPanel(false)}
  const drop=async id=>{try{await remove(id);if(inter)frame.current?.contentWindow?.postMessage({zg:1,type:'unpaint',id},'*');else hl.current?.remove(id)}catch(e){toast(e.message)}}
  const toggleFs=()=>document.fullscreenElement?document.exitFullscreen().catch(()=>{}):document.documentElement.requestFullscreen?.().catch(()=>toast(t("Full screen is not available here")))
  return <div className="reader" role="dialog" aria-modal="true" aria-label={t.title}>
    <div className="rbar"><button className="ic" aria-label={t("Close")} title={t("Close")} onClick={close}><X size={20}/></button>
      <span className="rtitle"><b>{t.title}</b><small>{[t.course,t.unit].filter(Boolean).join(' › ')}</small></span>
      <span className="rhint">{t("Select text to highlight it")}</span>
      <button className={'tool rhl'+(panel?' on':'')} aria-expanded={panel} onClick={()=>setPanel(!panel)}><Highlighter size={15}/> {list?.length||0}<span className="rlab">{" "}{t("highlight")}{list?.length===1?'':'s'}</span></button>
      <button className="ic" aria-label={fs?t("Exit full screen"):t("Full screen")} title={fs?t("Exit full screen"):t("Full screen")} onClick={toggleFs}>{fs?<Minimize2 size={19}/>:<Maximize2 size={19}/>}</button></div>
    <div className="rmain">
      {inter?(ready&&<iframe ref={frame} className="rframe" title={t.title} src={t.frame_url} sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox allow-modals allow-forms allow-downloads"/>)
        :<div className="rscroll"><div className="prose rtext" ref={box}>{ready?<Content text={t.content} format={t.content_format}/>:<Skeleton/>}</div></div>}
      {panel&&<aside className="rpanel" aria-label={t("Your highlights")}><b>{t("Your highlights")}</b><p className="known">{t("Select text and pick a colour. Tap a highlight to change its colour, add a note or remove it.")}</p>
        {list?.length?list.map(h=><HlItem key={h.id} h={h} toast={toast} focus={noteFor===h.id} onGo={()=>goTo(h.id)} onSaved={r=>{setList(l=>l.map(x=>x.id===r.id?r:x));setNoteFor(null)}} onDrop={()=>drop(h.id)}/>):<p className="known">{t("None yet.")}</p>}</aside>}</div></div>}

const TOPIC_CONFIG_TEMPLATE=`---
title: 1. Introduction and learning objectives
published: no
deadline: 2026-10-20 17:00
---

## Question pattern
- Recite the verses from memory
- Explain the vocabulary

## Sample content
**Q:** Name the three parts of the verses.

**A:** First, verses 28–29 ...

## How an answer should be
- Answer what the verb asks: explain, infer, or give the ruling with the reason.
- Support every answer with the verse or hadith.
`
const FILES_HELP='Pick the content: an HTML file or a Markdown .md file. To keep a page’s JavaScript, first choose HTML + JavaScript as the content format below. You can add a config .md file for the title and the other boxes, and any images the page uses. The form fills in; check it, then save.'
function TopicEditor({role,toast,done,cancel,edit,unitId}){  // edit = {id} of a topic, or null for a new one in unitId
  const confirm=useConfirm()
  const fac=role==='faculty',[prev,setPrev]=useState(false),[up,setUp]=useState(false),fileRef=useRef(null),taRef=useRef(null),filesRef=useRef(null),[busy,setBusy]=useState(false)
  const [tree,setTree]=useState([]),[f,setF]=useState({title:'',unit_id:unitId||'',content:'',content_format:'markdown',sample_content:'',question_pattern:'',guideline:'',published:!fac,due:''}),[cid,setCid]=useState(null)
  const [fromFiles,setFromFiles]=useState(null),[shown,setShown]=useState(''),[imp,setImp]=useState(false)
  useEffect(()=>{api('/tree').then(setTree).catch(()=>{});if(edit)api('/topics/'+edit.id).then(t=>{setCid(t.course_id);setF({title:t.title,unit_id:t.unit_id||'',content:t.content||'',content_format:t.content_format||'markdown',sample_content:t.sample_content||'',question_pattern:t.question_pattern||'',guideline:t.guideline||'',published:t.published!==false,due:localInput(t.learning_due_at)})}).catch(e=>toast(e.message))},[])
  const html=f.content_format==='html',inter=f.content_format==='interactive',[frameUrl,setFrameUrl]=useState('')
  useEffect(()=>{if(!prev||!inter)return;let live=true;setFrameUrl('');api('/topics/frame-preview',{method:'POST',body:{html:f.content}}).then(r=>live&&setFrameUrl(r.url)).catch(e=>toast(e.message));return()=>{live=false}},[prev,inter,f.content])
  useEffect(()=>{if(!prev||!html)return;let live=true;api('/topics/clean-html',{method:'POST',body:{html:f.content}}).then(r=>live&&setShown(r.html)).catch(e=>toast(e.message));return()=>{live=false}},[prev,html,f.content])
  const set=k=>e=>setF({...f,[k]:e.target.value})
  const pickFiles=async e=>{const files=[...e.target.files];e.target.value='';if(!files.length)return
    const ext=x=>(x.name.split('.').pop()||'').toLowerCase(),htmlF=files.filter(x=>['html','htm'].includes(ext(x))),cfgF=files.filter(x=>['md','markdown','txt'].includes(ext(x))),imgs=files.filter(x=>/^image\//.test(x.type))
    if(htmlF.length>1||cfgF.length>1)return toast(t("Choose one HTML file and one config file at a time"))
    if(!htmlF.length&&!cfgF.length)return toast(t("Choose an HTML file, a config .md file, or both"))
    if((f.content.trim()||f.question_pattern.trim()||f.sample_content.trim()||f.guideline.trim())&&!await confirm({title:t("Replace what is in the form?"),body:t("The boxes the files fill in are replaced. Nothing is saved until you save."),ok:t("Fill from files")}))return
    setBusy(true);try{const images={};for(const x of imgs)images[x.name]=await uploadImg(x)
      const r=await api('/topics/from-files',{method:'POST',body:{unit_id:+(f.unit_id||unitId),html:htmlF.length?await htmlF[0].text():'',config:cfgF.length?await cfgF[0].text():'',images,scripts:f.content_format==='interactive'}})
      setF(cur=>({...cur,...['title','content','content_format','question_pattern','sample_content','guideline'].reduce((o,k)=>r[k]!==undefined?{...o,[k]:r[k]}:o,{}),...(r.published!==undefined?{published:r.published}:{}),...(r.learning_due_at?{due:r.learning_due_at}:{})}))
      setFromFiles({names:[...htmlF,...cfgF].map(x=>x.name),warnings:r.warnings,images:r.images_saved+imgs.length});setPrev(!!r.content&&['html','interactive'].includes(r.content_format));toast(t("Filled from {v}. Check it, then save.",{v:[...htmlF,...cfgF].map(x=>x.name).join(' and ')}))}catch(er){toast(er.message)}setBusy(false)}
  const pickImg=async e=>{const file=e.target.files[0];e.target.value='';if(!file)return;if(file.size>3*1024*1024)return toast(t("Image is too large. Keep it under 3 MB."))
    setUp(true);try{const r=await fetch('/api/uploads',{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:file});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Upload failed')
      const pos=taRef.current?.selectionStart??f.content.length,tag=html||inter?`\n<p><img src="${d.url}" alt="Describe the image"></p>\n`:`\n\n![Describe the image](${d.url})\n\n`;setF({...f,content:f.content.slice(0,pos)+tag+f.content.slice(pos)});toast(t("Image added"))}catch(er){toast(er.message)}setUp(false)}
  const all=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared&&c.editable).flatMap(c=>c.units.map(n=>({...n,course_id:c.id,label:`${c.name} › ${n.name}`})))))
  const units=role==='admin'?all:all.filter(n=>n.course_id===cid)  // faculty move a topic only between units of its own course
  const here=all.find(n=>n.id===+f.unit_id)
  const save=async()=>{setBusy(true);try{await api(edit?'/topics/'+edit.id:'/topics',{method:edit?'PUT':'POST',body:{...f,due:undefined,unit_id:+f.unit_id,published:f.published!==false,learning_due_at:f.due?new Date(f.due).toISOString():null}});toast(edit?t("Changes saved"):t("Topic added"));done()}catch(e){toast(e.message)}setBusy(false)}
  const T=(k,l,ph)=><><label>{l}</label><textarea placeholder={ph} value={f[k]} onChange={set(k)}/></>
  return <><Bar title={edit?t("Edit topic"):t("New topic")} sub={here?.label} back={cancel}/><div className="main">
    {!imp&&!fromFiles&&<button className="tool" style={{marginTop:0}} onClick={()=>setImp(true)}><Upload size={14}/>{" "}{t("Fill from files (HTML and config)")}</button>}
    {(imp||fromFiles)&&<div className="qbox" style={{marginTop:0}}><b>{t("Fill from files")}</b><p className="known" style={{margin:'4px 0 8px'}}>{FILES_HELP}</p>
      <input ref={filesRef} type="file" hidden multiple accept=".html,.htm,.md,.markdown,.txt,text/html,text/markdown,image/png,image/jpeg,image/gif,image/webp" onChange={pickFiles}/>
      <div className="two"><button className="btn" style={{margin:0}} disabled={busy} onClick={()=>filesRef.current.click()}><Upload size={16}/> {busy?t("Reading…"):t("Choose files")}</button><button className="btn ghost" style={{margin:0}} onClick={()=>download('topic-config.md',TOPIC_CONFIG_TEMPLATE)}>{t("Config template")}</button></div>
      {fromFiles&&<div role="status" style={{marginTop:10}}><p className="known" style={{margin:0}}>{t("Filled from {names}{v}.",{names:fromFiles.names.join(' and '),v:fromFiles.images?` · ${pl(fromFiles.images,'image')}`:''})}</p>
        {fromFiles.warnings.map((w,i)=><p key={i} className="known" style={{margin:'4px 0 0',color:'var(--warn)'}}>{w}</p>)}</div>}</div>}
    {edit&&units.length>1&&<><label>{t("Unit")}</label><select value={f.unit_id} onChange={set('unit_id')}>{units.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></>}
    <label>{t("Topic title")}</label><input value={f.title} onChange={set('title')} placeholder={t("First law of thermodynamics")}/>
    <label>{t("Topic content")}</label><div className="seg" style={{gridTemplateColumns:'1fr 1fr 1fr',margin:'0 0 8px'}} role="group" aria-label={t("Content format")}>{[['markdown','Markdown'],['html','HTML'],['interactive','HTML + JavaScript']].map(([k,l])=><button key={k} type="button" className={f.content_format===k?'on':''} aria-pressed={f.content_format===k} onClick={()=>setF({...f,content_format:k})}>{l}</button>)}</div>
    <div className="tools"><button type="button" disabled={up} onClick={()=>fileRef.current.click()}>{up?t("Uploading…"):t("Add image")}</button><button type="button" onClick={()=>setPrev(!prev)}>{prev?t("Back to editing"):t("Preview")}</button></div>
    <input ref={fileRef} type="file" hidden accept="image/png,image/jpeg,image/gif,image/webp" onChange={pickImg}/>
    {prev&&inter?(f.content?(frameUrl?<iframe className="pframe" title={t("Preview")} src={frameUrl} sandbox="allow-scripts allow-popups allow-modals allow-forms"/>:<Skeleton/>):<div className="prose"><Md>{t("Nothing to preview yet.")}</Md></div>)
      :prev?<div className="prose">{!f.content?<Md>{t("Nothing to preview yet.")}</Md>:html?<Body text={shown} format="html"/>:<Md>{f.content}</Md>}</div>:<textarea ref={taRef} className={html||inter?'code':''} placeholder={html||inter?t("HTML (or choose an HTML file above)"):t("Paste notes or syllabus text")} value={f.content} onChange={set('content')}/>}
    <p className="known">{inter?t("The page runs as it is, with its own scripts and styles, in a sandbox: it can't reach the app or anyone's account (so it also can't keep data in the browser between visits). Students open it full screen and can highlight its text."):html?t("HTML content shows as it is laid out in the file. Scripts, styles, forms and outside frames are removed when you save, so the page takes the app's look in light and dark mode."):t("Equations: $x^2$ inline. For a centred block, put $$ on its own line above and below the equation. Chemistry: $\\ce{CaCO3 + CO2 + H2O -> Ca(HCO3)2}$")}</p>{T('question_pattern','Question pattern','e.g. 2 marks: define · 13 marks: derive + numerical')}
    <label>{t("Learning deadline")}</label><div className="qopt"><input type="datetime-local" aria-label={t("Learning deadline")} value={f.due} onChange={set('due')}/>{f.due&&<button type="button" className="tool" onClick={()=>setF({...f,due:''})}>{t("No deadline")}</button>}</div>
    <p className="known" style={{marginTop:4}}>{f.due?t("Students should have learnt this topic by then. They can still open it afterwards."):t("No deadline")}</p>
    <label className="chk"><input type="checkbox" checked={f.published!==false} onChange={e=>setF({...f,published:e.target.checked})}/>{" "}{t("Published (students can see this topic)")}</label>
    {T('sample_content','Sample content','A sample question and answer')}{T('guideline','How an answer should be','Intro, labelled diagram, steps, units, conclusion')}
    <button className="btn" disabled={busy||!f.title.trim()} onClick={save}>{edit?t("Save changes"):t("Save topic")}</button></div></>}
function UnitSheet({un,cid,courses,close,done,toast}){  // courses is given to admins only: moving a unit to another course is theirs to do
  const isNew=!un.id,[f,setF]=useState({name:un.name||'',course:cid}),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{await api(isNew?'/units':'/units/'+un.id,{method:isNew?'POST':'PUT',body:{name:f.name,course_id:+f.course}});toast(isNew?t("Unit added"):t("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?t("New unit"):t("Edit unit")}</h3>
    <label>{t("Name")}</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} onKeyDown={e=>e.key==='Enter'&&f.name.trim()&&save()} placeholder={t("Unit 1: Basic concepts")} autoFocus/>
    {!isNew&&courses&&<><label>{t("Course")}</label><select value={f.course} onChange={e=>setF({...f,course:+e.target.value})}>{courses.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></>}
    <button className="btn" disabled={busy||!f.name.trim()} onClick={save}>{isNew?t("Add unit"):t("Save changes")}</button></Sheet>}

const unmarked=(tree,id)=>tree.map(p=>({...p,semesters:p.semesters.map(s=>({...s,courses:s.courses.map(c=>({...c,units:c.units.map(u=>({...u,topics:u.topics.map(x=>x.id===id?{...x,bookmarked:false}:x)}))}))}))}))
const tabTo=e=>e.currentTarget.scrollIntoView?.({inline:'center',block:'nearest'})

const srcLine=x=>x.status==='reading'?(x.done?`Reading scanned pages… ${x.done} of ${x.pages}`:`Waiting to read ${x.pages} scanned pages…`)
  :x.status==='failed'?x.error:`${x.kind==='scan'?'Scanned, read with text recognition · ':''}${x.words.toLocaleString()} words${x.note?' · '+x.note:''}`
const usePoll=(on,fn,ms=3000)=>useEffect(()=>{if(!on)return;const h=setInterval(fn,ms);return()=>clearInterval(h)},[on])  // while scanned pages are being read
function MyMaterial({cid,name,back,toast}){  // a student's own material, filed under the course's syllabus topics (private to them)
  const confirm=useConfirm()
  const [v,setV]=useState(null),[busy,setBusy]=useState(''),[paste,setPaste]=useState(null),[open,setOpen]=useState({}),[pick,setPick]=useState(null),fileRef=useRef()
  const base=`/courses/${cid}/my-material`,load=()=>api(base).then(setV).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[cid]);usePoll(!!v?.reading,()=>api(base).then(setV).catch(()=>{}))
  const run=async(label,fn,msg)=>{setBusy(label);try{const r=await fn();if(r&&r.syllabus)setV(r);else await load();msg&&toast(msg)}catch(e){toast(e.message)}setBusy('')}
  const upload=async e=>{const fs=[...e.target.files];e.target.value='';for(const f of fs)if(tooBig(f))toast(t("{name} is over {MAX_FILE_MB} MB. Split it into smaller files.",{name:f.name,MAX_FILE_MB:MAX_FILE_MB}));else await run('file',async()=>{const r=await fetch('/api'+base+'/files?name='+encodeURIComponent(f.name),{method:'POST',headers:{'Content-Type':'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');if(j.status==='reading')toast(t("{name} is scanned pages. Reading them now; you can stay or come back later.",{name:f.name}))},f.name.toLowerCase().endsWith('.pdf')?'':'Added '+f.name)}
  const match=m=>run(m,()=>api(base+'/match',{method:'POST',body:{method:m}}),'Matched to the syllabus. Check it below, then save.')
  const file=(i,tid)=>{setPick(null);return run('sec',()=>api(base+'/sections',{method:'PUT',body:{sections:v.sections.map((x,k)=>({from:x.from,to:x.to,topic_id:k===i?(tid?+tid:null):x.topic_id}))}}))}
  const read=async x=>{const k=x.from;if(open[k]!==undefined)return setOpen({...open,[k]:undefined});try{const r=await api(`${base}/preview?start=${x.from}&end=${x.to}`);setOpen({...open,[k]:r.content})}catch(e){toast(e.message)}}
  if(!v)return <><Bar title={t("Your material")} back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const names=new Map(v.syllabus.flatMap(u=>u.topics.map(x=>[x.id,x.title]))),filed=new Set(v.sections.map(x=>x.topic_id).filter(Boolean)),missing=v.syllabus.flatMap(u=>u.topics.filter(x=>!filed.has(x.id)).map(x=>x.title)),noAi=!v.ai_available||v.ai_left===0
  return <><Bar title={t("Your material")} sub={name} back={back}/><div className="main">
    <p className="known" style={{marginTop:0}}>{t("Your college sets the course, units and topics. Bring your own notes or book chapters and they are filed under the right topics, so you study the syllabus in your own words. Only you see them.")}</p>
    <h3>{t("1. Your files")}</h3>
    {v.sources.length?v.sources.map((x,i)=><div className="row" key={i}><div>{x.name}<small role={x.status==='reading'?'status':undefined}>{srcLine(x)}</small></div><button className="ic sm" aria-label={t("Remove {name}",{name:x.name})} disabled={!!busy} onClick={()=>run('drop',()=>api(base+'/sources/'+i,{method:'DELETE'}))}><X size={16}/></button></div>):<p className="known">{t("No files yet. PDFs, Word (.docx) and text files work, up to {MAX_FILE_MB} MB each.",{MAX_FILE_MB:MAX_FILE_MB})}{v.ocr_available?t(" Scanned PDFs are read too; that takes a few seconds a page."):t(" Scanned PDFs can't be read on this server yet.")}</p>}
    <div className="two"><button className="btn ghost" disabled={!!busy} onClick={()=>fileRef.current.click()}><Upload size={16}/> {busy==='file'?t("Reading…"):t("Add a file")}</button><button className="btn ghost" disabled={!!busy} onClick={()=>setPaste({text:''})}>{t("Paste text")}</button></div>
    <input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.txt,.md" onChange={upload}/>
    {v.sources.length>0&&<><h3>{t("2. File it under the syllabus")}</h3>
      {v.reading&&<p className="known" role="status">{t("Your scanned pages are still being read. Matching starts once they are done.")}</p>}
      {v.ai_available&&<button className={'btn'+(noAi?' ghost':'')} disabled={!!busy||noAi||v.reading} onClick={()=>match('ai')}><Sparkles size={16}/> {busy==='ai'?t("Matching…"):t("Match with AI")}</button>}
      <button className={'btn'+(noAi?'':' ghost')} disabled={!!busy||v.reading} onClick={()=>match('headings')}>{busy==='headings'?t("Matching…"):v.ai_available?t("Match by headings (no AI)"):t("Match by headings")}</button>
      {noAi&&<p className="known">{v.ai_available?t("No AI requests are left today. "):''}{t("Matching by headings works best when your notes use the topic names as headings.")}</p>}</>}
    {v.sections.length>0&&<><h3>{t("3. Check where each part goes")}</h3>
      <p className="known">{t("Your notes cover {covered} of {topics} topics.",{covered:v.covered,topics:v.topics})}{missing.length>0&&t(" Not covered yet: {missing}{v}.",{missing:missing.slice(0,6).join(', '),v:missing.length>6?' and '+(missing.length-6)+' more':''})}</p>
      {v.sections.map((x,i)=><div className="qbox" key={x.from}>{x.heading?<b>{x.heading}</b>:<span style={{display:'block'}}>“{x.excerpt.slice(0,80)+(x.excerpt.length>80?'…':'')}”</span>}<small className="known" style={{display:'block'}}>{t("Part {v} · {words} words",{v:i+1,words:x.words})}</small>
        <div className="sfile">{x.topic_id?<span className="chip">{names.get(x.topic_id)||t("Topic")}</span>:<span className="chip none">{t("Left out")}</span>}<button className="tool" disabled={!!busy} aria-expanded={pick===i} onClick={()=>setPick(pick===i?null:i)}>{pick===i?t("Cancel"):x.topic_id?t("Change"):t("File it")}</button></div>
        {pick===i&&<select aria-label={t("Topic for part {i}{v}",{i:i,v:1})} autoFocus value={x.topic_id||''} disabled={!!busy} onChange={e=>file(i,e.target.value)}><option value="">{t("Not in the syllabus (left out)")}</option>{v.syllabus.map(u=><optgroup key={u.id} label={u.name}>{u.topics.map(tp=><option key={tp.id} value={tp.id}>{tp.title}</option>)}</optgroup>)}</select>}
        <button className="tool" onClick={()=>read(x)}>{open[x.from]!==undefined?t("Hide"):t("Read it")}</button>{open[x.from]!==undefined&&<div className="prose"><Md>{open[x.from]}</Md></div>}</div>)}
      <button className="btn" disabled={!!busy||!filed.size} onClick={()=>run('save',()=>api(base+'/save',{method:'POST'}),'Saved. Open a topic to study your notes.')}>{v.saved_at?t("Save again to my topics"):t("Save to my topics")}</button>
      {v.saved_at&&<p className="known">{t("Last saved {n}. Saving again rebuilds your notes from this material; your progress and quiz results stay.",{n:when(v.saved_at)})}</p>}</>}
    {v.sources.length>0&&<p style={{marginTop:28}}><button className="link" style={{color:"var(--bad)"}} disabled={!!busy} onClick={async()=>{if(await confirm({title:t("Remove your material?"),body:t("The notes it made in this course are removed too. Your progress and quiz results stay."),ok:t("Remove"),danger:true}))run('del',()=>api(base,{method:'DELETE'}),'Your material was removed')}}>{t("Remove my material from this course")}</button></p>}</div>
    {paste&&<Sheet close={()=>setPaste(null)}><h3>{t("Paste text")}</h3><textarea aria-label={t("Text to add")} value={paste.text} onChange={e=>setPaste({text:e.target.value})} placeholder={t("Paste your notes. Lines starting with # are headings.")}/>
      <button className="btn" disabled={!paste.text.trim()||!!busy} onClick={async()=>{await run('paste',()=>api(base+'/text',{method:'POST',body:{text:paste.text}}),'Added');setPaste(null)}}>{t("Add")}</button></Sheet>}</>}

// every highlight this person has made, newest first: search (passage, note or topic), a colour filter and pages; a highlight opens its topic
function MyHighlights({toast,role}){
  const [q,setQ]=useState(''),[color,setColor]=useState(''),[t,setT]=useState(null)
  const {items,total,page,setPage,reload}=usePaged(o=>`/me/highlights?q=${encodeURIComponent(q)}&color=${color}&limit=${PAGE}&offset=${o}`,[q,color],toast)
  if(t)return <Topic id={t} back={()=>{setT(null);reload()}} toast={toast} role={role}/>
  const drop=async h=>{try{await api('/me/highlights/'+h.id,{method:'DELETE'});toast(t("Highlight removed"));reload()}catch(e){toast(e.message)}}
  return <><Bar title={t("My highlights")} sub={q||color?matches(total):pl(total,'highlight')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={t("Search your highlights")} placeholder={t("Search your highlights, notes or topics")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="chips wrap" role="group" aria-label={t("Colour")} style={{marginTop:12}}>{[['','All colours'],...Object.keys(HL_COL).map(c=>[c,c[0].toUpperCase()+c.slice(1)])].map(([k,l])=><button key={l} className={'sbtn'+(color===k?' on':'')} aria-pressed={color===k} onClick={()=>setColor(k)}>{k&&<i className="hldot" style={{background:HL_COL[k]}}/>}{l}</button>)}</div>
    {items.map(h=><HlItem key={h.id} h={h} toast={toast} where={[h.topic,h.course].filter(Boolean).join(' · ')} onGo={()=>setT(h.topic_id)} onSaved={reload} onDrop={()=>drop(h)}/>)}
    {!items.length&&<p className="known">{q||color?t("No highlight matches."):t("No highlights yet. Open a topic, select some text and pick a colour.")}</p>}
    <Pager page={page} total={total} onPage={setPage}/></div></>}
const FMT=L({markdown:'Markdown',html:'HTML',interactive:'HTML + JavaScript'})
// many topic files into one unit: pick files or a whole folder (with its images), see what each file becomes, then add them all
function BulkTopics({unit,toast,close,done}){
  const [rows,setRows]=useState(null),[files,setFiles]=useState([]),[images,setImages]=useState({}),[scripts,setScripts]=useState(false),[pub,setPub]=useState(false),[busy,setBusy]=useState(''),pick=useRef(null),folder=useRef(null)
  const ext=x=>(x.name.split('.').pop()||'').toLowerCase()
  const send=(dry,o={})=>api(`/units/${unit.id}/topics/bulk`,{method:'POST',body:{files,images,scripts,published:pub,...o,dry_run:dry}})
  const preview=async o=>{if(!(o?.files||files).length)return;setBusy('Checking the files…');try{setRows(await send(true,o))}catch(e){toast(e.message)}setBusy('')}
  const choose=async e=>{const all=[...e.target.files];e.target.value='';if(!all.length)return
    const docs=all.filter(x=>['html','htm','md','markdown','txt'].includes(ext(x))),imgs=all.filter(x=>/^image\//.test(x.type))
    if(!docs.length)return toast(t("Choose .html or .md files, or a folder with them"))
    if(docs.length>200)return toast(t("Choose up to 200 files at a time"))
    const big=imgs.find(x=>x.size>3*1024*1024);if(big)return toast(t("{name} is over 3 MB. Make it smaller first.",{name:big.name}))
    try{setBusy(`Reading ${pl(docs.length,'file')}…`);const fs=await Promise.all(docs.map(async x=>({name:x.webkitRelativePath||x.name,text:await x.text()}))),im={}
      for(const [i,x] of imgs.entries()){setBusy(`Uploading images: ${i+1} of ${imgs.length}…`);im[x.name]=await uploadImg(x)}
      setFiles(fs);setImages(im);await preview({files:fs,images:im})}catch(er){toast(er.message)}setBusy('')}
  const add=async()=>{setBusy('Adding the topics…');try{const r=await send(false);toast(t("{n} added to {name}",{n:pl(r.created,'topic'),name:unit.name}));done()}catch(e){toast(e.message);setBusy('')}}
  const ok=rows?.ready||0
  return <Sheet page close={close}><h3>{t("Upload topic files to")}{" "}{unit.name}</h3>
    <p className="known">{t("One topic per file. Choose .html or .md files, or a whole folder: images in it are matched to the pages by file name. Topics are added in file-name order (2 before 10), after the topics already here. A Markdown file with the config sections (see Config template in the topic editor) also fills in the question pattern, sample answer and guideline.")}</p>
    <label className="chk"><input type="checkbox" checked={scripts} onChange={e=>{setScripts(e.target.checked);preview({scripts:e.target.checked})}}/>{" "}{t("Keep each HTML page's JavaScript (HTML + JavaScript, run in a sandbox)")}</label>
    <label className="chk"><input type="checkbox" checked={pub} onChange={e=>{setPub(e.target.checked);preview({published:e.target.checked})}}/>{" "}{t("Publish them now (otherwise they are drafts)")}</label>
    <div className="two"><button className="btn" disabled={!!busy} onClick={()=>pick.current.click()}><Upload size={16}/>{" "}{t("Choose files")}</button><button className="btn ghost" disabled={!!busy} onClick={()=>folder.current.click()}>{t("Choose a folder")}</button></div>
    <input ref={pick} type="file" hidden multiple accept=".html,.htm,.md,.markdown,.txt,image/png,image/jpeg,image/gif,image/webp" onChange={choose}/>
    <input ref={folder} type="file" hidden multiple webkitdirectory="" onChange={choose}/>
    {busy&&<p className="known" role="status">{busy}</p>}
    {rows&&<><b className="sec" style={{display:'block'}}>{ok}{" "}{t("of {n} ready",{n:pl(rows.topics.length,'file')})}</b>
      {rows.topics.map((r,i)=><div key={i} className="row"><div>{r.ok?<b>{r.title}</b>:<s>{r.title||r.file}</s>}<small>{r.file}{r.ok?` · ${FMT[r.format]} · ${r.published?'published':'draft'}`:''}</small>{r.warnings.map((w,j)=><small key={j} className="warnline">{w}</small>)}</div></div>)}
      <button className="btn" disabled={!ok||!!busy} onClick={add}>{t("Add")}{" "}{pl(ok,'topic')}</button></>}</Sheet>}
function Bookmarks({toast,role}){
  const [tree,setTree]=useState(null),[sem,setSem]=useState(null),[course,setCourse]=useState(null),[t,setT]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t])
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast} role={role}/>
  if(!tree)return <><Bar title={t("Bookmarks")}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const marks=u=>u.topics.filter(x=>x.bookmarked),cnt=c=>c.units.reduce((n,u)=>n+marks(u).length,0)
  const sems=tree.flatMap(p=>p.semesters.map(sm=>({...sm,prog:p.name,courses:sm.courses.filter(c=>cnt(c)>0)}))).filter(sm=>sm.courses.length)
    .sort((a,b)=>a.prog.localeCompare(b.prog)||(a.number??99)-(b.number??99)||a.id-b.id)
  const multi=new Set(sems.map(x=>x.prog)).size>1,total=sems.reduce((n,x)=>n+x.courses.reduce((m,c)=>m+cnt(c),0),0)
  const sm=sems.find(x=>x.id===sem)||sems[0],co=sm?.courses.find(x=>x.id===course)||sm?.courses[0]
  const drop=async id=>{try{await api(`/topics/${id}/bookmark`,{method:'DELETE'});setTree(unmarked(tree,id));toast(t("Bookmark removed"))}catch(e){toast(e.message)}}
  return <><Bar title={t("Bookmarks")} sub={total?total+(total===1?' topic saved':' topics saved'):t("Nothing saved yet")}/><div className="main">
    {!sm&&<p className="known">{t("Open any topic and tap the bookmark icon to save it here. It shows only the topics you saved, grouped by semester or year, course and unit.")}</p>}
    {sm&&<>
      <div className="chips" role="group" aria-label={t("Semester or year")}>{sems.map(x=><button key={x.id} className={'sbtn'+(x.id===sm.id?' on':'')} aria-pressed={x.id===sm.id} onClick={e=>{setSem(x.id);setCourse(null);tabTo(e)}}>
        <span className="lbl">{multi&&x.prog+' · '}{x.name}</span><em>{x.courses.reduce((n,c)=>n+cnt(c),0)}</em></button>)}</div>
      <div className="tabs scroll" role="tablist" aria-label={t("Course")}>{sm.courses.map(c=><button key={c.id} role="tab" aria-selected={c.id===co.id} className={c.id===co.id?'on':''} onClick={e=>{setCourse(c.id);tabTo(e)}}>
        <span className="lbl">{c.name}</span><em>{cnt(c)}</em></button>)}</div>
      {co.units.filter(u=>marks(u).length).map(u=><div key={u.id}><h3 className="sec">{u.name}</h3>
        {marks(u).map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={()=>setT(x.id)}><span className="dot" style={{background:COL[i%5]}}>{x.title[0]}</span><div><b>{x.title}</b></div><Mark s={x.status}/></button>
          <button className="ic sm on" aria-label={t("Remove bookmark: {title}",{title:x.title})} onClick={()=>drop(x.id)}><Bookmark size={16} fill="currentColor"/></button></div>)}</div>)}
    </>}</div></>}

const sheets=[]  // open sheets, topmost last, so Escape closes only the one on top
// a pop-up for short questions; with page set, a form that takes over the content area like a page of its own, with a way back
let pages=0  // forms open as pages right now; while any is open the page under it is hidden
const flat=ch=>Children.toArray(ch).flatMap(c=>isValidElement(c)&&c.type===Fragment?flat(c.props.children):[c])
function Sheet({close,children,page}){
  const box=useRef(null),cb=useRef(close);cb.current=close
  useEffect(()=>{const me={},was=document.activeElement;sheets.push(me)
    const k=e=>{if(e.key==='Escape'&&sheets[sheets.length-1]===me)cb.current()}
    addEventListener('keydown',k);if(box.current&&!box.current.contains(document.activeElement))box.current.focus()
    return()=>{sheets.splice(sheets.indexOf(me),1);removeEventListener('keydown',k);if(was&&was.isConnected)was.focus?.()}},[])
  useEffect(()=>{if(!page)return;pages++;document.body.classList.add('has-page');scrollTo({top:0});return()=>{if(!--pages)document.body.classList.remove('has-page')}},[page])
  const slot=page&&document.getElementById('pageslot')
  if(slot){const all=flat(children),i=all.findIndex(c=>isValidElement(c)&&c.type==='h3'),title=i<0?'':all[i].props.children  // the form's heading becomes the page title
    return createPortal(<><Bar title={title} back={()=>cb.current()}/><div className="main" ref={box} tabIndex={-1} role="region" aria-label={typeof title==='string'?title:undefined}>{all.filter((_,j)=>j!==i)}</div></>,slot)}
  return <div className="scrim" onClick={()=>cb.current()}><div className="sheet" ref={box} tabIndex={-1} role="dialog" aria-modal="true" onClick={e=>e.stopPropagation()}>{children}</div></div>}
const Confirm=({o,answer})=><Sheet close={()=>answer(false)}><h3>{o.title}</h3>{o.body&&<p className="known">{o.body}</p>}
  <button className={'btn'+(o.danger?' danger':'')} onClick={()=>answer(true)}>{o.ok||t("Confirm")}</button><button className="btn ghost" onClick={()=>answer(false)}>{t("Cancel")}</button></Sheet>
const useConfirm=()=>useContext(Ctx).confirm
const Toast=({msg})=>msg?<div className="toast" role="status">{msg}</div>:null
const Skeleton=({rows=3})=><div aria-busy="true" aria-label={t("Loading")}>{Array.from({length:rows},(_,i)=><div className="sk" key={i}/>)}</div>
// numbered pages under a list: Previous, page numbers (with … in long lists), Next, and which rows are shown
const PAGE=25
const pageList=(n,at)=>n<=7?[...Array(n).keys()]:[...new Set([0,1,at-1,at,at+1,n-2,n-1].filter(i=>i>=0&&i<n))].sort((a,b)=>a-b).flatMap((i,j,a)=>j&&i-a[j-1]>1?['…'+i,i]:[i])
function Pager({page,total,onPage,size=PAGE}){
  const n=Math.ceil(total/size);if(n<=1)return null
  const go=i=>{onPage(i);scrollTo({top:0})}
  return <nav className="pgr" aria-label={t("Pages")}><small>{page*size+1}{t("–{Math} of",{Math:Math.min(total,(page+1)*size)})}{" "}{total}</small>
    <span className="pgb"><button className="tool" disabled={page===0} onClick={()=>go(page-1)} aria-label={t("Previous page")}><ChevronLeft size={16}/></button>
      {pageList(n,page).map(i=>typeof i==='string'?<span key={i} className="gap">…</span>:<button key={i} className={'tool'+(i===page?' on':'')} aria-current={i===page?'page':undefined} onClick={()=>go(i)}>{i+1}</button>)}
      <button className="tool" disabled={page>=n-1} onClick={()=>go(page+1)} aria-label={t("Next page")}><ChevronRight size={16}/></button></span></nav>}
// the list's rows for the current page; a filter change goes back to page 1, and a page left empty (say after a delete) steps back one
function usePaged(url,deps,toast){
  const [page,setPage]=useState(0),[items,setItems]=useState([]),[total,setTotal]=useState(0),[n,setN]=useState(0)
  useEffect(()=>{setPage(0)},deps)
  useEffect(()=>{const t=setTimeout(()=>api(url(page*PAGE)).then(r=>{if(!r.items.length&&page>0)setPage(page-1);else{setItems(r.items);setTotal(r.total)}}).catch(e=>toast(e.message)),250);return()=>clearTimeout(t)},[...deps,page,n])
  return {items,total,page,setPage,reload:()=>setN(x=>x+1)}}
const ShowMore=({left,onClick,busy})=><button className="btn ghost" disabled={busy} onClick={onClick}>{t("Show more ({left} left)",{left:left})}</button>
const Tabs=({items,value,onChange,scroll,label})=><div className={'tabs'+(scroll?' scroll':'')} role="tablist" aria-label={label}>{items.map(([k,l])=><button key={k} role="tab" aria-selected={value===k} className={value===k?'on':''} onClick={()=>onChange(k)}>{l}</button>)}</div>
const useRun=(toast,load)=>async(fn,m)=>{try{await fn();toast(m);load&&load()}catch(e){toast(e.message)}}

const download=(name,text)=>{const l=document.createElement('a');l.href=URL.createObjectURL(new Blob([text],{type:'text/csv'}));l.download=name;l.click()}
const USER_TEMPLATE=`name,email,password,role,program,semester
Asha Kumar,asha@example.com,,student,B.E. Mechanical Engineering,3
Ravi S,ravi@example.com,Welcome#2026,student,B.E. Mechanical Engineering,1
`
const TERM_MAX={Grade:12},maxOf=term=>TERM_MAX[term]||8,upTo=n=>Array.from({length:n},(_,i)=>i+1)
const termOf=(progs,id)=>progs.find(p=>String(p.id)===String(id))?.term||'Semester',semsOf=(progs,id)=>upTo(id?maxOf(termOf(progs,id)):Math.max(8,...progs.map(p=>maxOf(p.term))))
const PATTERN_EN={semester:['Semesters','Semester',8,'Semester pattern, for example B.E., B.Tech or M.E. Students move up one semester at a time.'],
  year:['Years','Year',4,'Annual pattern, for example M.B.B.S, B.Sc or law degrees, up to 8 years. For a school, choose School grades. Students move up one year at a time.'],
  grade:['School grades','Grade',12,'School pattern, Grade 1 to Grade 12. Students move up one grade at a time.']},PATTERN=L(PATTERN_EN)  // PATTERN_EN for logic, PATTERN for what is shown

const BULK_TEXT={disable:['Disable these accounts?','They can no longer sign in. Their progress and quiz results are kept, and you can enable them again.','Disable'],
  enable:['Enable these accounts?','They can sign in again.','Enable'],reset_passwords:['Reset these passwords?','Each person gets a new one-time password and must choose their own at next sign-in. Anyone signed in is signed out. You download the list once; it is not shown again.','Reset passwords']}
function BulkSheet({act,ids,progs,toast,close,done}){
  const [p,setP]=useState(''),[s,setS]=useState(''),[busy,setBusy]=useState(false)
  if(act.kind==='result'){const r=act.r,cell=v=>'"'+String(v).replace(/"/g,'""')+'"'
    return <Sheet close={close}><h3>{pl(r.changed,'account')}{" "}{t("updated")}</h3>
      {r.courses_needing_owner>0&&<p className="known">{pl(r.courses_needing_owner,'course')}{" "}{t("now {v} no active owner. Assign new owners under Programs.",{v:r.courses_needing_owner===1?'has':'have'})}</p>}
      {r.skipped_count>0&&<div className="qbox"><b>{r.skipped_count}{" "}{t("skipped")}</b>{r.skipped.slice(0,10).map(x=><p className="known" style={{margin:'4px 0'}} key={x.id}>{x.name}: {x.reason}</p>)}{r.skipped_count>10&&<p className="known">{t("…and {v} more.",{v:r.skipped_count-10})}</p>}</div>}
      {r.credentials&&<button className="btn" onClick={()=>download('new-passwords.csv','name,email,password\n'+r.credentials.map(c=>[c.name,c.email,c.password].map(cell).join(',')).join('\n')+'\n')}>{t("Download the new passwords")}</button>}
      <button className="btn ghost" onClick={close}>{t("Close")}</button></Sheet>}
  const run=async()=>{setBusy(true);try{done(await api('/admin/users/bulk',{method:'POST',body:{ids,action:act.kind,...(act.kind==='set_placement'?{program_id:+p,semester:s?+s:null}:{})}}))}catch(e){toast(e.message);setBusy(false)}}
  if(act.kind==='set_placement')return <Sheet close={close}><h3>{t("Move")}{" "}{pl(ids.length,'user')}</h3><p className="known">{t("Sets the program and semester, year or grade of the selected students. Faculty and admins in the selection are skipped.")}</p>
    <label htmlFor="bp">{t("Program")}</label><select id="bp" value={p} onChange={e=>{const id=e.target.value;setP(id);if(+s>semsOf(progs,id).length)setS('')}}><option value="">{t("Choose a program")}</option>{progs.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    <label htmlFor="bs">{termOf(progs,p)}</label><select id="bs" value={s} onChange={e=>setS(e.target.value)}><option value="">{t("Not set")}</option>{semsOf(progs,p).map(n=><option key={n} value={n}>{termOf(progs,p)} {n}</option>)}</select>
    <button className="btn" disabled={busy||!p} onClick={run}>{busy?t("Working…"):t("Move")}</button><button className="btn ghost" onClick={close}>{t("Cancel")}</button></Sheet>
  const [t,d,l]=BULK_TEXT[act.kind]
  return <Sheet close={close}><h3>{t.replace('these',ids.length===1?'this':'these')}</h3><p className="known">{pl(ids.length,'account')}{" "}{t("selected.")}{" "}{d}</p>
    <button className={'btn'+(act.kind==='disable'?' danger':'')} disabled={busy} onClick={run}>{busy?t("Working…"):l}</button><button className="btn ghost" onClick={close}>{t("Cancel")}</button></Sheet>}
function Users({toast,me}){
  const [q,setQ]=useState(''),[prog,setProg]=useState(''),[sem,setSem]=useState(''),[order,setOrder]=useState('role'),[progs,setProgs]=useState([])
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef(),[selMode,setSelMode]=useState(false),[sel,setSel]=useState([]),[act,setAct]=useState(null)
  const {items,total,page,setPage,reload:load}=usePaged(offset=>`/admin/users?q=${encodeURIComponent(q)}&order=${order}&limit=${PAGE}&offset=${offset}`+(prog?'&program_id='+prog:'')+(sem?'&semester='+sem:''),[q,prog,sem,order],toast)
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name,term:p.term})))).catch(()=>{})},[])
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/users/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/users/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const cell=v=>'"'+String(v).replace(/"/g,'""')+'"',r=bulk?.res,filtered=q||prog||sem,lab=prog?termOf(progs,prog):progs.every(x=>x.term==='Semester')?'Semester':progs.length&&progs.every(x=>x.term==='Grade')?'Grade':'Term'
  if(view)return <UserDetail id={view} me={me} progs={progs} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title={t("Users")} sub={filtered?matches(total):pl(total,'account')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={t("Search users")} placeholder={t("Search name, email, ID, program, semester, year or grade")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters">
      <select aria-label={t("Filter by program")} value={prog} onChange={e=>{const id=e.target.value;setProg(id);if(+sem>semsOf(progs,id).length)setSem('')}}><option value="">{t("All programs")}</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select aria-label={t("Filter by semester, year or grade")} value={sem} onChange={e=>setSem(e.target.value)}><option value="">{lab==='Term'?t("All terms"):t("All {lab}s",{lab:lab.toLowerCase()})}</option>{semsOf(progs,prog).map(n=><option key={n} value={n}>{lab} {n}</option>)}</select>
      <select aria-label={t("Sort by")} value={order} onChange={e=>setOrder(e.target.value)}><option value="role">{t("Sort: role, then name")}</option><option value="name">{t("Sort: name")}</option><option value="program">{t("Sort: program")}</option><option value="semester">{t("Sort:")}{" "}{lab.toLowerCase()}</option><option value="newest">{t("Sort: newest first")}</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>{t("New user")}</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>{t("Bulk upload")}</button></div>
    <button className="btn ghost" style={{marginTop:10}} aria-pressed={selMode} onClick={()=>{setSelMode(!selMode);setSel([])}}>{selMode?t("Done selecting"):t("Select several users")}</button>
    {selMode&&items.length>0&&<div className="selbar"><button className="tool" onClick={()=>setSel(items.map(u=>u.id))}>{t("Select all {length} shown",{length:items.length})}</button>{sel.length>0&&<button className="tool" onClick={()=>setSel([])}>{t("Clear")}</button>}</div>}
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead" aria-hidden="true"><span>{t("Name")}</span><span>{t("Program")}</span><span>{lab==='Semester'?t("Sem"):lab}</span></div>}
    {items.map(u=><button key={u.id} className={'utr'+(selMode?' sel':'')+(sel.includes(u.id)?' on':'')} onClick={()=>selMode?setSel(sel.includes(u.id)?sel.filter(i=>i!==u.id):[...sel,u.id]):setView(u.id)} aria-label={(selMode?(sel.includes(u.id)?'Deselect ':'Select '):'Open ')+u.name} aria-pressed={selMode?sel.includes(u.id):undefined}>
      <span className="nm">{selMode&&<span className="tick" aria-hidden="true">{sel.includes(u.id)&&<Check size={14}/>}</span>}<span className="dot" style={{background:COL[u.id%5]}}>{(u.name||'?')[0]}</span><span className="tx"><b>{u.name}</b>{(u.role!=='student'||!u.active||u.self_registered)&&<span className="tags">{u.role!=='student'&&<span className="pill">{u.role==='admin'?t("Admin"):t("Faculty")}</span>}{u.self_registered&&<span className="pill">{t("Self-registered")}</span>}{!u.active&&<span className="pill off">{t("Disabled")}</span>}</span>}</span></span>
      <span className="pg">{u.program||'—'}</span><span className="sn">{u.semester||'—'}</span></button>)}
    {!items.length&&<p className="known">{filtered?t("No one matches that search."):t("No users yet.")}</p>}
    <Pager page={page} total={total} onPage={setPage}/>
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {selMode&&sel.length>0&&<div className="actbar" role="toolbar" aria-label={t("Actions for selected users")}><b>{sel.length}{" "}{t("selected")}</b>
      <button className="tool" onClick={()=>setAct({kind:'set_placement'})}>{t("Move…")}</button><button className="tool" onClick={()=>setAct({kind:'disable'})}>{t("Disable")}</button><button className="tool" onClick={()=>setAct({kind:'enable'})}>{t("Enable")}</button><button className="tool" onClick={()=>setAct({kind:'reset_passwords'})}>{t("Reset passwords")}</button></div>}
    {act&&<BulkSheet act={act} ids={sel} progs={progs} toast={toast} close={()=>setAct(null)} done={r=>{setAct({kind:'result',r});setSel([]);load()}}/>}
    {ed&&<UserSheet u={ed} me={me} progs={progs} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet page close={()=>setBulk(null)}>
      {bulk.stage==='pick'&&<><h3>{t("Bulk upload users")}</h3><p className="known">{t("One row per person with the columns name, email, password, role, program and semester (the year number for annual programs such as M.B.B.S). Leave the password blank to generate one. Role is student or admin and defaults to student. Program must match a name on the Programs tab, and semester is a number from 1 to 8. Emails that already exist are updated, and blank program or semester cells leave the current value alone.")}</p>
        <button className="btn ghost" onClick={()=>download('users-template.csv',USER_TEMPLATE)}>{t("Download template")}</button><button className="btn" onClick={()=>fileRef.current.click()}>{t("Choose CSV file")}</button></>}
      {bulk.stage==='preview'&&<><h3>{t("Ready to upload")}</h3><p className="known">{r.valid_rows}{" "}{t("of {rows} rows are valid: {created} new, {updated} updated.",{rows:r.rows,created:r.created,updated:r.updated})}{r.generated>0&&t(" {generated} passwords will be generated.",{generated:r.generated})}</p>
        {r.error_count>0&&<div className="prose" style={{maxHeight:'28vh',overflow:'auto',fontSize:14}}><b>{r.error_count}{" "}{t("rows will be skipped")}</b>{r.errors.map(e=><div key={e.row}>{t("Row {row}:",{row:e.row})}{" "}{e.error}</div>)}</div>}
        <button className="btn" disabled={!r.valid_rows} onClick={commit}>{t("Upload {valid_rows} rows",{valid_rows:r.valid_rows})}</button><button className="btn ghost" onClick={()=>setBulk(null)}>{t("Cancel")}</button></>}
      {bulk.stage==='done'&&<><h3>{t("Upload complete")}</h3><p className="known">{r.created}{" "}{t("users created, {updated} updated.",{updated:r.updated})}{r.credentials.length>0&&t(" Download the generated passwords now. They are not shown again.")}</p>
        {r.credentials.length>0&&<button className="btn" onClick={()=>download('new-user-passwords.csv','name,email,password\n'+r.credentials.map(c=>[c.name,c.email,c.password].map(cell).join(',')).join('\n')+'\n')}>{t("Download passwords")}</button>}
        <button className="btn ghost" onClick={()=>setBulk(null)}>{t("Close")}</button></>}
    </Sheet>}</>}

function UserDetail({id,me,progs,back,toast}){
  const confirm=useConfirm()
  const [u,setU]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[pw,setPw]=useState(null),[busy,setBusy]=useState(false),[asg,setAsg]=useState(null),[ctree,setCtree]=useState([])
  const load=()=>api('/admin/users/'+id).then(setU).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id]);useEffect(()=>{if(u?.role==='faculty')api('/tree').then(setCtree)},[u?.role])
  if(!u)return <><Bar title={t("Loading")} back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const reset=async()=>{setBusy(true);try{const r=await api(`/admin/users/${u.id}/reset-password`,{method:'POST'});setAsk(false);setPw(r.password)}catch(e){toast(e.message)}setBusy(false)}
  const remove=async()=>{if(!await confirm({title:t("Delete {name}?",{name:u.name}),body:t("This permanently removes the account and {v}. Content they created stays.{v2} To keep their history, edit the user and set Status to Disabled instead.",{v:u.role==='student'?'their progress, test results and bookmarks':'their own records',v2:u.role==='faculty'?' Courses they own will have no owner.':''}),ok:t("Delete user"),danger:true}))return
    try{await api('/admin/users/'+u.id,{method:'DELETE'});toast(t("{name} deleted",{name:u.name}));back()}catch(e){toast(e.message)}}
  const copy=async()=>{try{await navigator.clipboard.writeText(pw);toast(t("Copied"))}catch{toast(t("Press and hold the password to copy it"))}}
  const row=(v,l)=><div className="row"><div>{v}<small>{l}</small></div></div>
  const allCourses=ctree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared).map(c=>({id:c.id,owner_id:c.owner_id,owner:c.owner,label:`${p.name} › ${s.name} › ${c.name}`}))))
  const saveAsg=async()=>{try{await api(`/admin/users/${u.id}/courses`,{method:'PUT',body:{course_ids:asg}});toast(t("Courses updated"));setAsg(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={u.name} sub={u.email} back={back}/><div className="main">
    <div className="stats"><div className="stat"><b>{u.topics_read}</b>{t("Topics read")}</div><div className="stat"><b>{u.reads}</b>{t("Total reads")}</div></div>
    <h3 className="sec">{t("Profile")}</h3>
    {row({admin:'Admin',faculty:'Faculty'}[u.role]||'Student','Role')}{row(u.active?'Active':'Disabled','Status')}{row(u.program||'Not set','Program')}{row(u.semester||'Not set',termOf(progs,u.program_id))}{u.self_registered&&<>{row(u.institution||'—','Institution')}{row(u.id_number||'—','ID number')}{row(u.phone||'—','Phone')}{row(u.own_ai_key?'Has added their own key':'No key yet · AI is off for them','AI (self-registered, uses their own key)')}</>}{row(day(u.last_active),'Last active')}
    {u.role==='faculty'&&<><h3 className="sec">{t("Courses they own")}</h3>{(u.course_ids||[]).length?allCourses.filter(c=>u.course_ids.includes(c.id)).map(c=><div className="row" key={c.id}><div>{c.label}</div></div>):<p className="known">{t("None yet. They can read published content but edit nothing until they own a course.")}</p>}<button className="btn ghost" onClick={()=>setAsg([...(u.course_ids||[])])}>{t("Assign courses")}</button></>}
    <h3 className="sec">{t("Recently read")}</h3>
    {u.recent.length?u.recent.map((x,i)=><div className="row" key={i}><div>{x.title}<small>{x.reads}{" "}{t("reads, last")}{" "}{day(x.last_read)}</small></div></div>):<p className="known">{t("No reading activity yet.")}</p>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>{t("Edit")}</button><button className="btn" onClick={()=>setAsk(true)}>{t("Reset password")}</button></div>
    {u.id!==me.id&&<button className="btn danger" onClick={remove}>{t("Delete user")}</button>}</div>
    {ed&&<UserSheet u={u} me={me} progs={progs} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>{t("Reset password?")}</h3><p className="known">{t("This gives {name} a new password and replaces the old one straight away. You will see the new password once.",{name:u.name})}</p>
      <button className="btn danger" disabled={busy} onClick={reset}>{t("Reset password")}</button><button className="btn ghost" onClick={()=>setAsk(false)}>{t("Cancel")}</button></Sheet>}
    {pw&&<Sheet close={()=>setPw(null)}><h3>{t("New password")}</h3><p className="known">{t("Share this with {name} now. It is not shown again.",{name:u.name})}</p><div className="pw">{pw}</div>
      <button className="btn" onClick={copy}>{t("Copy password")}</button><button className="btn ghost" onClick={()=>setPw(null)}>{t("Done")}</button></Sheet>}
    {asg&&<Sheet page close={()=>setAsg(null)}><h3>{t("Courses {name} owns",{name:u.name})}</h3><p className="known">{t("The owner adds and edits the units, topics and quizzes of a course. Each course has one owner, so ticking a course another person owns moves it to {name}.",{name:u.name})}</p>{allCourses.map(c=><label key={c.id} className="chk"><input type="checkbox" checked={asg.includes(c.id)} onChange={e=>setAsg(e.target.checked?[...asg,c.id]:asg.filter(i=>i!==c.id))}/> {c.label}{c.owner_id&&c.owner_id!==u.id?t(" (now {owner})",{owner:c.owner}):''}</label>)}<button className="btn" onClick={saveAsg}>{t("Save")}</button><button className="btn ghost" onClick={()=>setAsg(null)}>{t("Cancel")}</button></Sheet>}</>}

function UserSheet({u,me,progs,close,done,toast}){
  const isNew=!u.id,self=u.id===me.id,[busy,setBusy]=useState(false)
  const [f,setF]=useState({name:u.name||'',email:u.email||'',role:u.role||'student',active:u.active??true,password:'',program_id:u.program_id||'',semester:u.semester||''}),set=k=>e=>setF({...f,[k]:e.target.value})
  const save=async()=>{setBusy(true);try{
    const enrol={program_id:f.program_id?+f.program_id:null,semester:f.semester?+f.semester:null}
    if(isNew)await api('/admin/users',{method:'POST',body:{...f,...enrol}})
    const r=isNew?null:await api('/admin/users/'+u.id,{method:'PATCH',body:{name:f.name,email:f.email,...enrol,...(self?{}:{role:f.role,active:f.active})}})
    toast(isNew?t("User added"):r.courses_needing_owner?t("Saved. {courses_needing_owner} course(s) they own need a new owner.",{courses_needing_owner:r.courses_needing_owner}):t("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?t("New user"):t("Edit user")}</h3>
    <label>{t("Name")}</label><input value={f.name} onChange={set('name')}/><label>{t("Email")}</label><input type="email" value={f.email} onChange={set('email')}/>
    <label>{t("Program")}</label><select value={f.program_id} onChange={e=>{const id=e.target.value;setF({...f,program_id:id,semester:+f.semester>semsOf(progs,id).length?'':f.semester})}}><option value="">{t("Not set")}</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <label>{termOf(progs,f.program_id)}</label><select value={f.semester} onChange={set('semester')}><option value="">{t("Not set")}</option>{semsOf(progs,f.program_id).map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>{t("Role")}</label><select disabled={self} value={f.role} onChange={set('role')}><option value="student">{t("Student")}</option><option value="faculty">{t("Faculty")}</option><option value="admin">{t("Admin")}</option></select>
    <label>{t("Status")}</label><select disabled={self} value={f.active?'1':'0'} onChange={e=>setF({...f,active:e.target.value==='1'})}><option value="1">{t("Active")}</option><option value="0">{t("Disabled")}</option></select>
    {isNew?<><label>{t("Password (8+ characters)")}</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/></>
      :<p className="known" style={{marginTop:14}}>{t("To give this person a new password, use Reset password on their page.")}</p>}
    {self&&<p className="known">{t("You can't change your own role or status.")}</p>}
    <button className="btn" disabled={busy} onClick={save}>{isNew?t("Add user"):t("Save changes")}</button></Sheet>}

// every course for admins: search, a program filter, sorting and pages; add, edit or delete here, or open a course for its units and topics
function AdminCourses({toast,onOpen}){
  const confirm=useConfirm(),[q,setQ]=useState(''),[prog,setProg]=useState(''),[order,setOrder]=useState('name'),[status,setStatus]=useState('active'),[tree,setTree]=useState([]),[ed,setEd]=useState(null)
  useEffect(()=>{api('/tree').then(setTree).catch(()=>{})},[])
  const {items,total,page,setPage,reload}=usePaged(offset=>`/admin/courses?q=${encodeURIComponent(q)}&order=${order}&status=${status}&limit=${PAGE}&offset=${offset}`+(prog?'&program_id='+prog:''),[q,prog,order,status],toast)
  const sems=tree.flatMap(p=>p.semesters.map(x=>({id:x.id,label:p.name+' › '+x.name}))),done=()=>{setEd(null);reload()}
  const del=async c=>{if(!await confirm({title:t("Delete “{name}”?",{name:c.name}),body:t("This permanently deletes its {n}, {n2} and quizzes, with students' progress in them. To hide it instead, archive it from the course page.",{n:pl(c.units,'unit'),n2:pl(c.topics,'topic')}),ok:t("Delete course"),danger:true}))return
    try{await api('/courses/'+c.id,{method:'DELETE'});toast(t("Course deleted"));reload()}catch(e){toast(e.message)}}
  return <><Bar title={t("Courses")} sub={q||prog?matches(total):pl(total,'course')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={t("Search courses")} placeholder={t("Search course, program, semester or owner")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label={t("Filter by program")} value={prog} onChange={e=>setProg(e.target.value)}><option value="">{t("All programs")}</option>{tree.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select aria-label={t("Sort by")} value={order} onChange={e=>setOrder(e.target.value)}><option value="name">{t("Sort: name A to Z")}</option><option value="name_desc">{t("Sort: name Z to A")}</option><option value="program">{t("Sort: program, then term")}</option><option value="topics">{t("Sort: most topics")}</option><option value="newest">{t("Sort: newest first")}</option></select>
      <select aria-label={t("Show")} value={status} onChange={e=>setStatus(e.target.value)}><option value="active">{t("Active courses")}</option><option value="archived">{t("Archived courses")}</option><option value="all">{t("All courses")}</option></select></div>
    <button className="btn" onClick={()=>setEd({})}>{t("New course")}</button>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead c" aria-hidden="true"><span>{t("Course")}</span><span>{t("Program › term")}</span><span>{t("Topics")}</span><span/></div>}
    {items.map(c=><div key={c.id} className="utr c"><button className="nm" onClick={()=>onOpen([c.program_id,c.semester_id,c.id].filter(x=>x!=null))} aria-label={t("Open {name}",{name:c.name})}><span className="dot" style={{background:COL[c.id%5]}}>{(c.name||'?')[0]}</span><span className="tx"><b>{c.name}{c.archived&&<span className="pill off sm">{t("Archived")}</span>}</b><small className="sub">{c.owner_problem||t("Owner: {owner}",{owner:c.owner})}</small></span></button>
      <span className="pg">{[c.program,c.semester].filter(Boolean).join(' › ')||'—'}</span><span className="sn">{c.topics}</span>
      <span className="rowacts"><button className="ic sm" aria-label={t("Edit {name}",{name:c.name})} title={t("Edit")} onClick={()=>setEd(c)}><Pencil size={17}/></button><button className="ic sm" aria-label={t("Delete {name}",{name:c.name})} title={t("Delete")} onClick={()=>del(c)}><Trash2 size={17}/></button></span></div>)}
    {!items.length&&<p className="known">{q||prog?t("No course matches that search."):status==='archived'?t("No archived courses."):t("No courses yet. Add one, or bulk upload a CSV under Programs.")}</p>}
    <Pager page={page} total={total} onPage={setPage}/></div>
    {ed&&(ed.id?<CourseSheet c={{id:ed.id,name:ed.name,owner_id:ed.owner_id,owner:ed.owner}} pid={ed.program_id} sid={ed.semester_id} sems={sems} term={ed.term} toast={toast} close={()=>setEd(null)} done={done}/>
      :<NewCourseSheet tree={tree} toast={toast} close={()=>setEd(null)} done={done}/>)}</>}
function NewCourseSheet({tree,toast,close,done}){  // a course is made inside a program's semester or year: pick both, then name it and, optionally, its owner
  const faculty=useFaculty(true),[f,setF]=useState({pid:tree.length===1?String(tree[0].id):'',sid:'',name:'',owner:''}),[busy,setBusy]=useState(false)
  const p=tree.find(x=>String(x.id)===f.pid),sems=p?.semesters||[],term=p?.term||'Semester'
  const save=async()=>{setBusy(true);try{await api(`/programs/${f.pid}/semesters/${f.sid}/courses`,{method:'POST',body:{name:f.name,...(f.owner?{faculty_owner_id:+f.owner}:{})}});toast(t("Course added"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{t("New course")}</h3>
    <label htmlFor="ncp">{t("Program")}</label><select id="ncp" value={f.pid} onChange={e=>setF({...f,pid:e.target.value,sid:''})}><option value="">{tree.length?t("Choose a program"):t("Add a program first")}</option>{tree.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    <label htmlFor="ncs">{term}</label><select id="ncs" value={f.sid} disabled={!p} onChange={e=>setF({...f,sid:e.target.value})}><option value="">{t("Choose a")}{" "}{term.toLowerCase()}</option>{sems.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    {p&&!sems.length&&<p className="known">{p.name}{" "}{t("has no {term} yet. Add one under Programs first.",{term:term.toLowerCase()})}</p>}
    <label htmlFor="ncn">{t("Name")}</label><input id="ncn" value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder={t("Thermodynamics")}/>
    <label htmlFor="nco">{t("Owner (faculty)")}</label><select id="nco" value={f.owner} onChange={e=>setF({...f,owner:e.target.value})}><option value="">{t("Not assigned")}</option>{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    <button className="btn" disabled={busy||!f.sid||!f.name.trim()} onClick={save}>{t("Add course")}</button></Sheet>}
function Programs({toast,onOpen}){
  const [q,setQ]=useState(''),[order,setOrder]=useState('name'),[status,setStatus]=useState('active')
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef()
  const {items,total,page,setPage,reload:load}=usePaged(offset=>`/admin/programs?q=${encodeURIComponent(q)}&order=${order}&status=${status}&limit=${PAGE}&offset=${offset}`,[q,order,status],toast)
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const r=bulk?.res,made=r&&Object.entries(r.created).filter(([,v])=>v).map(([k,v])=>v+' '+k).join(', ')||'nothing new'
  if(view)return <ProgramDetail id={view} onOpen={onOpen} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title={t("Programs")} sub={q?matches(total):pl(total,'program')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={t("Search programs")} placeholder={t("Search program, semester, year or course")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label={t("Sort by")} value={order} onChange={e=>setOrder(e.target.value)}><option value="name">{t("Sort: name")}</option><option value="students">{t("Sort: most students")}</option><option value="newest">{t("Sort: newest first")}</option></select><select aria-label={t("Show")} value={status} onChange={e=>setStatus(e.target.value)}><option value="active">{t("Active programs")}</option><option value="archived">{t("Archived programs")}</option><option value="all">{t("All programs")}</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>{t("New program")}</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>{t("Bulk upload")}</button></div>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead p" aria-hidden="true"><span>{t("Program")}</span><span>{t("Courses")}</span><span>{t("Students")}</span></div>}
    {items.map(x=><button key={x.id} className="utr p" onClick={()=>setView(x.id)} aria-label={t("Open {name}",{name:x.name})}>
      <span className="nm"><span className="dot" style={{background:COL[x.id%5]}}>{(x.name||'?')[0]}</span><span className="tx"><b>{x.name}{x.archived&&<span className="pill off sm">{t("Archived")}</span>}</b><small className="sub">{pl(x.semesters,x.term.toLowerCase())}{t(", {topics} topics",{topics:x.topics})}</small></span></span>
      <span className="sn">{x.courses}</span><span className="sn">{x.students}</span></button>)}
    {!items.length&&<p className="known">{q?t("No program matches that search."):status==='archived'?t("No archived programs."):t("No programs yet. Add one or bulk upload a CSV.")}</p>}
    <Pager page={page} total={total} onPage={setPage}/>
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {ed&&<ProgramSheet p={ed} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet page close={()=>setBulk(null)}>
      {bulk.stage==='pick'&&<><h3>{t("Bulk upload content")}</h3><p className="known">{t("One row per topic, with the columns program, semester, course, unit and topic, plus optional content, question_pattern, sample_content and guideline. Blank program, semester, course or unit cells repeat the row above. Existing names are reused and existing topics are updated. Programs that don't exist yet are created.")}</p>
        <button className="btn ghost" onClick={()=>download('template.csv',TEMPLATE)}>{t("Download template")}</button><button className="btn" onClick={()=>fileRef.current.click()}>{t("Choose CSV file")}</button></>}
      {bulk.stage==='preview'&&<><h3>{t("Ready to upload")}</h3><p className="known">{r.valid_rows}{" "}{t("of {rows} rows are valid. New: {made}. Topics updated: {updated_topics}.",{rows:r.rows,made:made,updated_topics:r.updated_topics})}</p>
        {r.error_count>0&&<div className="prose" style={{maxHeight:'28vh',overflow:'auto',fontSize:14}}><b>{r.error_count}{" "}{t("rows will be skipped")}</b>{r.errors.map(e=><div key={e.row}>{t("Row {row}:",{row:e.row})}{" "}{e.error}</div>)}</div>}
        <button className="btn" disabled={!r.valid_rows} onClick={commit}>{t("Upload {valid_rows} rows",{valid_rows:r.valid_rows})}</button><button className="btn ghost" onClick={()=>setBulk(null)}>{t("Cancel")}</button></>}
      {bulk.stage==='done'&&<><h3>{t("Upload complete")}</h3><p className="known">{t("Created {made}. {updated_topics} topics updated.",{made:made,updated_topics:r.updated_topics})}{r.error_count>0&&t(" {error_count} rows were skipped.",{error_count:r.error_count})}</p>
        <button className="btn ghost" onClick={()=>setBulk(null)}>{t("Close")}</button></>}
    </Sheet>}</>}

function RolloverSheet({p,close,done,toast}){
  const [fin,setFin]=useState('keep'),[r,setR]=useState(null),[busy,setBusy]=useState(false)
  const url=`/admin/programs/${p.id}/rollover`
  useEffect(()=>{setR(null);api(url,{method:'POST',body:{dry_run:true,finishing:fin}}).then(setR).catch(e=>{toast(e.message);close()})},[fin]) 
  const go=async()=>{setBusy(true);try{const x=await api(url,{method:'POST',body:{dry_run:false,finishing:fin}});toast(`${x.moved} students moved up`+(fin==='deactivate'&&x.finishing?`, ${x.finishing} accounts switched off`:''));done()}catch(e){toast(e.message);setBusy(false)}}
  return <Sheet page close={close}><h3>{t("Start a new term")}</h3><p className="known">{t("Moves every active student of {name} up one {v}. Do this once, when the new term begins.",{name:p.name,v:p.term?.toLowerCase()||'semester'})}</p>
    {!r?<div className="sk"/>:<div className="qbox" style={{marginTop:0}}>
      <div className="row"><div>{pl(r.moved,'student')}<small>{r.moved===1?'moves':'move'}{" "}{t("up one")}{" "}{r.term.toLowerCase()}</small></div></div>
      <div className="row"><div>{pl(r.finishing,'student')}<small>{r.finishing===1?'is':'are'}{" "}{t("in the last {term} ({term2} {last_semester})",{term:r.term.toLowerCase(),term2:r.term,last_semester:r.last_semester})}{r.finishing_names.length?': '+r.finishing_names.join(', ')+(r.finishing>r.finishing_names.length?'…':''):''}</small></div></div>
      {r.unplaced>0&&<div className="row"><div>{pl(r.unplaced,'student')}<small>{r.unplaced===1?'has':'have'}{" "}{t("no {term} set and are left alone:",{term:r.term.toLowerCase()})}{" "}{r.unplaced_names.join(', ')}</small></div></div>}</div>}
    <label htmlFor="fin">{t("Students finishing the program")}</label><select id="fin" value={fin} onChange={e=>setFin(e.target.value)}><option value="keep">{t("Leave them as they are")}</option><option value="deactivate">{t("Switch their accounts off")}</option></select>
    <button className="btn" disabled={busy||!r||(!r.moved&&!(fin==='deactivate'&&r.finishing))} onClick={go}>{busy?t("Working…"):t("Apply")}</button><button className="btn ghost" onClick={close}>{t("Cancel")}</button></Sheet>}
function ProgramDetail({id,back,onOpen,toast}){
  const [p,setP]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[busy,setBusy]=useState(false),[addSem,setAddSem]=useState(false),[term,setTerm]=useState(false),[arch,setArch]=useState(null)
  const load=()=>api('/admin/programs/'+id).then(setP).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id])
  if(!p)return <><Bar title={t("Loading")} back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const del=async()=>{setBusy(true);try{await api('/programs/'+p.id,{method:'DELETE'});toast(t("Program deleted"));back()}catch(e){toast(e.message);setBusy(false)}}
  const row=(v,l,k)=><div className="row" key={k}><div>{v}<small>{l}</small></div></div>
  return <><Bar title={p.name} sub={pl(p.semesters,p.term.toLowerCase())+(p.pattern==='year'?' · annual':p.pattern==='grade'?' · school':'')+(p.archived?' · archived':'')} back={back}/><div className="main">
    {p.archived&&<p className="known" style={{marginTop:0}}>{t("This program is archived. Students see its courses as unavailable right now. Restore it to bring everything back.")}</p>}
    <button className="btn ghost lead" onClick={()=>setArch({kind:'programs',id:p.id,name:p.name,on:!p.archived})}>{p.archived?t("Restore program"):t("Archive program")}</button>
    <div className="stats">{[['semesters',p.term+'s'],['courses','Courses'],['topics','Topics'],['students','Students']].map(([k,l])=><div className="stat" key={k}><b>{p[k]}</b>{l}</div>)}</div>
    <h3 className="sec">{p.term}s</h3>
    {p.semester_list.length?p.semester_list.map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={()=>onOpen([p.id,x.id])}><span className="dot" style={{background:COL[i%5]}}>{x.number||'?'}</span><div><b>{x.name}<ArchPill x={x}/></b><span>{t("{v}{courses} courses, {topics} topics",{v:x.number?'':'No '+p.term.toLowerCase()+' number set · ',courses:x.courses,topics:x.topics})}</span></div></button>{!p.archived&&<button className="ic sm" aria-label={(x.archived_self?'Restore ':'Archive ')+x.name} onClick={()=>setArch({kind:'semesters',id:x.id,name:x.name,on:!x.archived_self})}>{x.archived_self?<ArchiveRestore size={16}/>:<Archive size={16}/>}</button>}</div>):<p className="known">{t("No {term}s yet.",{term:p.term.toLowerCase()})}</p>}
    <button className="btn ghost" onClick={()=>setAddSem(true)}>{t("Add")}{" "}{p.term.toLowerCase()}</button>
    <h3 className="sec">{t("Students")}</h3>
    {p.student_list.length?p.student_list.map(u=>row(u.name,(u.semester?p.term+' '+u.semester:p.term+' not set')+(u.active?'':', disabled'),u.id)):<p className="known">{t("No students are enrolled yet. Set a program on a user's page.")}</p>}
    {p.students>p.student_list.length&&<p className="known">{t("Showing {length} of {students}. Use Users to see everyone.",{length:p.student_list.length,students:p.students})}</p>}
    {p.students>0&&<button className="btn ghost" onClick={()=>setTerm(true)}>{t("Start a new term (move students up)")}</button>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>{t("Edit")}</button><button className="btn danger" onClick={()=>setAsk(true)}>{t("Delete")}</button></div>
    <button className="btn ghost" onClick={()=>onOpen([p.id])}>{t("Open {term}s and courses",{term:p.term.toLowerCase()})}</button></div>
    {term&&<RolloverSheet p={p} toast={toast} close={()=>setTerm(false)} done={()=>{setTerm(false);load()}}/>}
    {ed&&<ProgramSheet p={p} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {arch&&<ArchiveSheet a={arch} toast={toast} close={()=>setArch(null)} done={()=>{setArch(null);load()}}/>}
    {addSem&&<SemesterSheet sem={{}} pid={p.id} term={p.term} toast={toast} close={()=>setAddSem(false)} done={()=>{setAddSem(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>{t("Delete “{name}”?",{name:p.name})}</h3><p className="known">{t("This permanently deletes {n}, {courses} courses, {units} units and {topics} topics, including their saved AI answers.",{n:pl(p.semesters,p.term.toLowerCase()),courses:p.courses,units:p.units,topics:p.topics})}{p.students>0&&t(" The {students} enrolled students keep their accounts but lose their program.",{students:p.students})}</p>
      <button className="btn danger" disabled={busy} onClick={del}>{t("Delete program")}</button><button className="btn ghost" onClick={()=>setAsk(false)}>{t("Cancel")}</button></Sheet>}</>}

function OwnerSheet({c,close,done,toast}){
  const faculty=useFaculty(true),[sel,setSel]=useState(c.owner_id||''),[busy,setBusy]=useState(false)
  const save=async()=>{if(String(sel)===String(c.owner_id||''))return close();setBusy(true);try{await api(`/courses/${c.id}/owner`,{method:'PUT',body:{user_id:sel?+sel:null}});toast(t("Owner updated"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{t("Owner of “{name}”",{name:c.name})}</h3><p className="known">{t("The owner adds and edits this course's units, topics and quizzes. Changing the owner keeps all content and student progress.")}{c.owner_problem&&c.owner_id?' '+c.owner_problem+'.':''}</p>
    <label>{t("Owner (faculty)")}</label><select value={sel} onChange={e=>setSel(e.target.value)}><option value="">{t("Not assigned")}</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner}{" "}{t("(can't edit)")}</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    <button className="btn" disabled={busy} onClick={save}>{t("Save")}</button><button className="btn ghost" onClick={close}>{t("Cancel")}</button></Sheet>}

function ProgramSheet({p,close,done,toast}){
  const isNew=!p.id,[name,setName]=useState(p.name||''),[pat,setPat]=useState(p.pattern||'semester'),[terms,setTerms]=useState(PATTERN[pat][2]),[touched,setTouched]=useState(false),[busy,setBusy]=useState(false)
  const lab=PATTERN_EN[pat][1],pick=k=>{setPat(k);setTerms(touched?Math.min(terms,maxOf(PATTERN_EN[k][1])):PATTERN[k][2])}
  const save=async()=>{setBusy(true);try{const r=await api(isNew?'/programs':'/programs/'+p.id,{method:isNew?'POST':'PUT',body:{name,pattern:pat,...(isNew?{terms}:{})}});toast(isNew?(r.terms?t("Program added with {terms} {lab}{v}",{terms:r.terms,lab:lab.toLowerCase(),v:r.terms===1?'':'s'}):t("Program added")):t("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?t("New program"):t("Edit program")}</h3>
    <label>{t("Name")}</label><input value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==='Enter'&&save()} placeholder={t("B.E. Mechanical Engineering")} autoFocus/>
    <p className="known" style={{marginTop:10}}>{t("Names must be unique. The users CSV import matches programs by name.")}</p>
    <label id="pat">{t("How is the program divided?")}</label><div role="group" aria-labelledby="pat" className="seg" style={{marginTop:0}}>{Object.entries(PATTERN).map(([k,[l]])=><button key={k} className={pat===k?'on':''} aria-pressed={pat===k} onClick={()=>pick(k)}>{l}</button>)}</div>
    <p className="known" style={{marginTop:6}}>{PATTERN[pat][3]}</p>
    {isNew?<><label htmlFor="nt">{t("How many {lab}s?",{lab:t(lab).toLowerCase()})}</label><select id="nt" value={terms} onChange={e=>{setTerms(+e.target.value);setTouched(true)}}>{[0,...upTo(maxOf(lab))].map(n=><option key={n} value={n}>{n===0?t("None yet, I will add them myself"):n}</option>)}</select>
      <p className="known" style={{marginTop:6}}>{terms?t("{lab} 1{v} {v2} created for you, so you can go straight to adding courses.",{lab:t(lab),v:terms>1?` to ${lab} ${terms}`:'',v2:terms>1?'are':'is'}):t("You can add them one by one later.")}</p></>
      :p.pattern&&pat!==p.pattern&&<p className="known" style={{marginTop:6}}>{t("Terms still named “{v} n” are renamed to “{lab} n”. Terms you named yourself keep their names.",{v:PATTERN[p.pattern]?.[1]||'Semester',lab:lab})}{pat==='grade'&&t(" Any of Grade 1 to Grade 12 the program does not have yet are added.")}</p>}
    <button className="btn" disabled={busy||!name.trim()} onClick={save}>{isNew?t("Add program"):t("Save changes")}</button></Sheet>}

function Branding({toast,onSaved}){
  const [name,setName]=useState(''),[logo,setLogo]=useState(null),[busy,setBusy]=useState(false),file=useRef(null)
  useEffect(()=>{api('/config').then(c=>{setName(c.name);setLogo(c.logo)}).catch(()=>{})},[])
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;setBusy(true)
    try{const r=await fetch('/api/uploads',{method:'POST',headers:{Authorization:'Bearer '+localStorage.t,'Content-Type':f.type},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');setLogo(j.url)}catch(x){toast(x.message)}setBusy(false)}
  const save=async body=>{setBusy(true);try{await api('/admin/branding',{method:'PUT',body});toast(t("Saved"));onSaved()}catch(e){toast(e.message)}setBusy(false)}
  return <><h3 className="sec first">{t("Institution name and logo")}</h3><p className="known">{t("Shown on the sign-in page and in the menu. Use a square PNG, JPG or WebP under 3 MB.")}</p>
    <div className="lpreview"><Logo src={logo} size={48}/><b>{name||t("Name")}</b></div>
    <label htmlFor="inst">{t("Name")}</label><input id="inst" value={name} maxLength={60} onChange={e=>setName(e.target.value)}/>
    <input ref={file} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={pick}/>
    <div className="two"><button className="btn ghost" disabled={busy} onClick={()=>file.current.click()}><Upload size={16}/> {logo?t("Replace logo"):t("Upload logo")}</button>
      <button className="btn ghost" disabled={busy||!logo} onClick={()=>{setLogo(null);save({remove_logo:true,name})}}>{t("Remove logo")}</button></div>
    <button className="btn" disabled={busy} onClick={()=>save({name,logo_url:logo||undefined})}>{t("Save name and logo")}</button></>}
function AiConfig({toast,onBrand}){
  const confirm=useConfirm()
  const [cfg,setCfg]=useState({}),[key,setKey]=useState(''),[model,setModel]=useState(''),[st,setSt]=useState({}),[tab,setTab]=useState('ai')
  const load=()=>{api('/admin/settings').then(c=>{setCfg(c);setModel(c.model)});api('/admin/stats').then(setSt)};useEffect(load,[])
  const run=useRun(toast,load)
  return <><Bar title={t("Settings")} sub={cfg.key_set?t("AI is on · key {key_hint}",{key_hint:cfg.key_hint}):t("AI is off · no key yet")}/><div className="main"><Tabs label={t("Settings sections")} scroll items={[['ai','AI'],['prompts','AI prompts'],['school','Institution'],['access','Sign-in']]} value={tab} onChange={setTab}/>
    {tab==='school'&&<Branding toast={toast} onSaved={onBrand}/>}{tab==='ai'&&<>
    <label>{t("DeepSeek API key")}</label><input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder={cfg.key_set?t("Leave blank to keep the current key"):t("sk-…")}/>
    <label>{t("Model")}</label><input value={model} onChange={e=>setModel(e.target.value)} placeholder="deepseek-chat"/>
    <button className="btn" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{deepseek_key:key,model}}).then(()=>setKey('')),'AI settings saved')}>{t("Save")}</button>
    {cfg.key_set&&<><button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/ai/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>{t("Test the key")}</button>
      <button className="btn ghost" onClick={async()=>{if(await confirm({title:t("Turn AI off for everyone?"),body:t("Students will see “AI unavailable” until you save a key again."),ok:t("Turn AI off"),danger:true}))run(()=>api('/admin/settings',{method:'PUT',body:{remove_key:true}}),'AI is off')}}>{t("Remove the key (turn AI off)")}</button></>}
    <p className="known" style={{marginTop:20}}>{t("One key serves every student added by staff (people who register themselves use their own key). Until a key is saved, students see “AI unavailable. Try again later.” Each topic is explained once and the answer is shared with every student. {v} answers are saved so far, which has saved about {v2} tokens.",{v:(st.cached??0).toLocaleString(),v2:(st.tokens_saved??0).toLocaleString()})}</p>
    </>}{tab==='prompts'&&<PromptEditor toast={toast}/>}
    {tab==='access'&&<><h3 className="sec first">{t("Self-registration")}</h3><SelfReg cfg={cfg} run={run}/>
    <h3 className="sec">{t("Password reset email")}</h3><p className="known">{cfg.mail_on?t("On. People can reset their own password from the sign-in page."):t("Off. The sign-in page tells people to ask an admin. To turn it on, set SMTP_HOST, SMTP_FROM and APP_URL in .env and restart (see .env.example).")}</p>
    {cfg.mail_on&&<button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/mail/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>{t("Send a test email to me")}</button>}</>}</div></>}

const VERB=L({POST:'Created',PUT:'Changed',PATCH:'Edited',DELETE:'Deleted'})
const describe=(m,p)=>{const s=p.replace(/^\/api\//,'').split('/'),id=s.find(x=>/^\d+$/.test(x)),n=s.filter(x=>!/^\d+$/.test(x)),last=n[n.length-1],noun=n[0]==='admin'?n[1]:n[0],one=(noun||'').replace(/s$/,'')
  if(p==='/api/uploads')return 'Uploaded an image';if(p==='/api/me/password')return 'Changed own password'
  if(p==='/api/admin/import')return 'Imported content from CSV';if(p==='/api/admin/users/import')return 'Imported users from CSV'
  if(last==='reset-password')return `Reset the password of user #${id}`;if(last==='courses')return `Assigned courses to user #${id}`;if(last==='links')return `Changed where course #${id} is shared`
  if(last==='publish')return `Changed publish state of ${one} #${id}`;if(n[0]==='admin'&&n[1]==='settings')return 'Changed settings'
  return `${VERB[m]||m} ${one}${id?' #'+id:''}`}
function Activity(){
  const [q,setQ]=useState(''),[rows,setRows]=useState([]),[total,setTotal]=useState(0),[busy,setBusy]=useState(false)
  const load=(more)=>{setBusy(true);api(`/admin/audit?q=${encodeURIComponent(q)}&offset=${more?rows.length:0}&limit=50`).then(r=>{setRows(more?[...rows,...r.items]:r.items);setTotal(r.total)}).finally(()=>setBusy(false))}
  useEffect(()=>{const t=setTimeout(()=>load(false),250);return()=>clearTimeout(t)},[q])
  return <><Bar title={t("Activity log")} sub={t("Who changed what")}/><div className="main"><div className="search"><Search size={18}/><input type="search" aria-label={t("Search the activity log")} placeholder={t("Search by person or action")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    {rows.length?rows.map(x=><div className="row" key={x.id}><div>{describe(x.method,x.path)}{x.status>=400&&<span className="pill off sm">{x.status===403?t("Not allowed"):t("Failed")}</span>}<small>{x.user} · {when(x.at)}</small></div></div>):busy?<Skeleton/>:<p className="known">{t("No activity yet.")}</p>}
    {rows.length<total&&<ShowMore left={total-rows.length} busy={busy} onClick={()=>load(true)}/>}</div></>}
const day=d=>d?new Date(d).toLocaleDateString(locale(),{day:'numeric',month:'short'}):t('never')
const fetchFile=async(url,name,toast)=>{try{const r=await fetch('/api'+url,{headers:{Authorization:'Bearer '+localStorage.t}});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'Download failed')
  const a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download=name;a.click();URL.revokeObjectURL(a.href)}catch(e){toast(e.message)}}
const Bar2=({v})=><div className="meter"><i style={{width:Math.min(100,v||0)+'%'}}/></div>
function CourseReports({toast,onOpen}){
  const [f,setF]=useState({p:0,s:0}),[rows,setRows]=useState(null),[progs,setProgs]=useState([])
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name,term:p.term,max:Math.max(0,...p.semesters.map(x=>x.number||0))||(p.term==='Year'?4:maxOf(p.term))})))).catch(()=>{})},[])
  const pr=progs.find(x=>x.id===f.p),lab=pr?pr.term:progs.length&&progs.every(x=>x.term==='Semester')?'Semester':progs.length&&progs.every(x=>x.term==='Year')?'Year':progs.length&&progs.every(x=>x.term==='Grade')?'Grade':'Term',top=pr?pr.max:Math.max(1,...progs.map(x=>x.max))
  const qs=`?program_id=${f.p}&semester=${f.s}`
  useEffect(()=>{setRows(null);api('/reports/courses'+qs).then(setRows).catch(e=>toast(e.message))},[f.p,f.s])
  const few=!f.p&&!f.s&&progs.length<=1&&rows&&rows.length<=5  // a handful of courses needs no filters
  return <>{!few&&<div className="qopt"><select value={f.p} onChange={e=>{const p=+e.target.value,x=progs.find(y=>y.id===p);setF({p,s:x&&f.s>x.max?0:f.s})}}><option value={0}>{t("All programs")}</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <select aria-label={t("Filter by {lab}",{lab:lab.toLowerCase()})} value={f.s} onChange={e=>setF({...f,s:+e.target.value})}><option value={0}>{lab==='Term'?t("All terms"):t("All {lab}s",{lab:lab.toLowerCase()})}</option>{Array.from({length:top},(_,i)=>i+1).map(n=><option key={n} value={n}>{lab} {n}</option>)}</select></div>}
    {rows&&!rows.length&&<p className="known">{t("No courses match.")}</p>}
    {rows?.map(x=><button className="row rowbtn" key={x.course_id} onClick={()=>onOpen(x)}><div>{x.course}<small>{x.program}{" "}{t("· {semester} · {students} students · {topics} topics · {avg_completion}% completed · {avg_opened}% opened",{semester:x.semester,students:x.students,topics:x.topics,avg_completion:x.avg_completion,avg_opened:x.avg_opened})}{x.quizzes?t(" · quiz avg {v}%",{v:x.avg_quiz_percent??'–'}):''}</small><Bar2 v={x.avg_completion}/></div><ChevronRight size={18}/></button>)}
    {rows?.length>0&&<button className="btn ghost" onClick={()=>fetchFile('/reports/courses?format=csv&program_id='+f.p+'&semester='+f.s,'courses.csv',toast)}>{t("Download courses CSV")}</button>}</>}
function StudentReport({c,back,toast}){
  const [d,setD]=useState(null),[w,setW]=useState(null);useEffect(()=>{api(`/reports/courses/${c.course_id}/students`).then(setD).catch(e=>toast(e.message));api(`/reports/courses/${c.course_id}/weak-areas`).then(setW).catch(()=>{})},[])
  return <><Bar title={c.course} sub={c.program+' · '+c.semester} back={back}/><div className="main">
    {w&&w.areas.length>0&&<><h3 className="sec first">{t("Topics the class finds hard")}</h3><p className="known" style={{margin:'0 0 8px'}}>{t("From each student's latest quiz results, weakest first.")}</p>{w.areas.slice(0,8).map(a=><div className="row" key={a.topic_id||'u'+a.unit_id}><div>{a.title}<small>{a.percent}{t("% right overall · {needs_study} of {students} students need another round of study",{needs_study:a.needs_study,students:a.students})}</small><Bar2 v={a.percent}/></div></div>)}<h3 className="sec">{t("Students")}</h3></>}
    {d&&!d.students.length&&<p className="known">{t("No students are enrolled for this course yet.")}</p>}
    {d?.students.map(x=><div className="row" key={x.email}><div>{x.name}{!x.active&&<span className="pill off sm">{t("Disabled")}</span>}<small>{x.completion}{t("% completed · {topics_completed}/{topics} done, {topics_read} opened{v} · last active",{topics_completed:x.topics_completed,topics:x.topics,topics_read:x.topics_read,v:c.quizzes?' · quizzes '+x.quizzes_taken+'/'+x.quizzes+(x.avg_quiz_percent!=null?', avg '+x.avg_quiz_percent+'%':''):''})}{" "}{day(x.last_active)}</small>{(x.strong.length>0||x.needs_study.length>0)&&<small>{x.strong.length>0&&t("Strong: {strong}",{strong:x.strong.join(', ')})}{x.strong.length>0&&x.needs_study.length>0&&' · '}{x.needs_study.length>0&&t("Needs another round: {needs_study}",{needs_study:x.needs_study.join(', ')})}</small>}<Bar2 v={x.completion}/></div></div>)}
    {d?.students.length>0&&<button className="btn ghost" onClick={()=>fetchFile(`/reports/courses/${c.course_id}/students?format=csv`,'students-'+c.course.replace(/\s+/g,'_')+'.csv',toast)}>{t("Download students CSV")}</button>}</div></>}
function Reports({role,toast}){
  const [st,setSt]=useState({}),[r,setR]=useState(null),[open,setOpen]=useState(null)
  useEffect(()=>{if(role==='faculty')return;api('/admin/stats').then(setSt);api('/admin/reports').then(setR)},[])
  if(open)return <StudentReport c={open} back={()=>setOpen(null)} toast={toast}/>
  if(role==='faculty')return <><Bar title={t("Reports")} sub={t("Your courses")}/><div className="main"><CourseReports toast={toast} onOpen={setOpen}/></div></>
  const list=(rows,empty,f)=>rows?.length?rows.map((x,i)=><div className="row" key={i}>{f(x)}</div>):<p className="known">{empty}</p>
  return <><Bar title={t("Reports")}/><div className="main"><div className="stats">
    {[['students','Students'],['topics','Topics'],['cached','Saved AI answers'],['tokens_saved','Tokens saved']].map(([k,l])=><div className="stat" key={k}><b>{(st[k]??0).toLocaleString()}</b>{l}</div>)}</div>
    <h3 className="sec">{t("Courses")}</h3><CourseReports toast={toast} onOpen={setOpen}/>
    <h3 className="sec">{t("Most read topics")}</h3>
    {list(r?.top_topics,'No reading activity yet.',x=><div>{x.title}<small>{x.readers}{" "}{t("students, {reads} reads",{reads:x.reads})}</small></div>)}
    <h3 className="sec">{t("Students")}</h3>
    {list(r?.students,'No students yet.',x=><div>{x.name}<small>{x.topics_read}{" "}{t("topics read, last active")}{" "}{day(x.last_active)}{!x.active&&t(", disabled")}</small></div>)}
    <h3 className="sec">{t("Saved AI answers")}</h3>
    {list(r?.ai,'Nothing saved yet.',x=><div>{x.title}<small>{x.kind==='explain'?t("Explanation"):t("Sample answer")}{t(", reused {hits} times, {saved} tokens saved",{hits:x.hits,saved:x.saved.toLocaleString()})}</small></div>)}</div></>}

function About({user}){
  const {appName}=useContext(Ctx),[c,setC]=useState({});useEffect(()=>{api('/config').then(setC)},[])
  return <><Bar title={t("About")}/><div className="main"><div className="hero"><h2>{appName}</h2><p>{t("Version")}{" "}{c.version||''}</p></div>
    <div className="prose"><p>{t("A study companion for engineering students. Your admin adds programs, semesters, courses, units and topics along with the question pattern and answer guideline. Open a topic to get a clear explanation and a sample answer that follows the guideline.")}</p>
    <p>{t("The app remembers which topics you have read. Explanations and sample answers are generated once with DeepSeek and shared, so they open instantly.")}</p>
    <p>{t("Signed in as")}{" "}<strong>{user.name}</strong> ({user.role}).</p></div></div></>}
