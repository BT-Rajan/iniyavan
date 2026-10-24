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
import {Users as UsersIcon,GraduationCap,Sparkles,BarChart3,Info,LogOut,Menu,X,ArrowUp,ArrowDown,Search,ChevronLeft,ChevronRight,Sun,Moon,Monitor,Upload,Copy,Check,Pencil,Trash2,Bookmark,Link2,Eye,EyeOff,History,TrendingUp,Clock,AlertTriangle,Play,Target,RotateCcw,ClipboardList,Archive,ArchiveRestore,Lock,FileText,Bell,BookOpen,Highlighter,Maximize2,Minimize2,Globe,Printer,Flag} from 'lucide-react'
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
import {t as tl,L,LANGS,locale,applyLang,firstLang,loadLang,srv} from './i18n.js'

const api=async(p,o={})=>{const t=localStorage.t
  const r=await fetch('/api'+p,{...o,headers:{'Content-Type':'application/json',...(t&&{Authorization:'Bearer '+t})},body:o.body&&JSON.stringify(o.body)})
  const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(typeof j.detail==='string'?tl(j.detail):tl('Something went wrong'));return j}  // the server's messages are looked up like any other text
const TEMPLATE=`program,semester,course,unit,topic,content,question_pattern,sample_content,guideline
B.E. Mechanical Engineering,Semester 3,Thermodynamics,Unit 1: Basic concepts,First law of thermodynamics,"Energy can change form but is never created or destroyed.","2 marks: define. 13 marks: derive and solve a numerical.","Q: State the first law for a closed system.","Introduction, labelled diagram, steps, units, conclusion"
,,,,Zeroth law of thermodynamics,"If A and B are each in equilibrium with C, they are in equilibrium with each other.","2 marks: state the law.","Q: State the zeroth law.","Definition, one example, significance"
`
const COL=['#722f99','#c2464e','#7a6f70','#9a6420','#4e1d6c']
const when=iso=>new Date(iso).toLocaleString(locale(),{day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'})  // shown in the viewer's own time zone
const localInput=iso=>{if(!iso)return '';const d=new Date(iso),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`}
const Mark=({s})=>s==='completed'?<Check className="done" aria-label={tl("Learned")}/>:null  // only what the student marked as learned; nothing for the rest
const ownerLine=c=>c.mine?tl('Your course'):srv(c.owner_problem)||(c.owner?tl("Owner: {owner}",{owner:c.owner}):tl('Owner not assigned'))
const useFaculty=on=>{const [l,setL]=useState([]);useEffect(()=>{if(on)api('/admin/users?role=faculty&limit=100').then(r=>setL(r.items.filter(u=>u.active))).catch(()=>{})},[on]);return l}

const firstName=n=>{const w=(n||'').trim().split(/\s+/).filter(Boolean);if(!w.length)return '';if(!/^(dr|prof|mr|mrs|ms|miss)\.?$/i.test(w[0]))return w[0];const rest=w.slice(1).filter(x=>x.replace(/\./g,'').length>1);return rest.length?w[0]+' '+rest[0]:w[0]}  // a title stays with the surname it belongs to ("Dr. A. Kumar" → "Dr. Kumar"), skipping initials
const MAX_FILE_MB=20,tooBig=f=>f.size>MAX_FILE_MB*1024*1024  // the server's limit for one file of study material
const PAGE=10  // the rule: any list longer than ten rows gets numbered pages
const pl=(n,w)=>tl(n===1?'{n} '+w:'{n} '+(w==='quiz'?'quizzes':w+'s'),{n})  // "1 topic", "3 topics": each form is its own phrase to translate
const matches=n=>tl(n===1?'{n} match':'{n} matches',{n})
const Ctx=createContext({})
const THEMES=L([['system',Monitor,tl("Auto")],['light',Sun,tl("Light")],['dark',Moon,tl("Dark")]])
const readTheme=()=>{try{return localStorage.theme||'system'}catch{return 'system'}}
const applyTheme=t=>{const r=document.documentElement;if(t==='light'||t==='dark')r.dataset.theme=t;else delete r.dataset.theme;const dark=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);document.querySelector('meta[name=theme-color]')?.setAttribute('content',dark?'#120e17':'#f6f4f7')}
// the Zigora mark: a Z in cream and coral on plum (the same drawing as public/favicon.svg)
const ZMark=({size=40})=><svg className="zmark" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="#722f99"/><rect x="16" y="15" width="32" height="8" rx="2.5" fill="#fee7c8"/><path d="M38.5 23H48L25.5 41H16Z" fill="#ff9292"/><rect x="16" y="41" width="32" height="8" rx="2.5" fill="#fee7c8"/></svg>
const Logo=({src,size=40})=>src?<img className="logo" src={src} alt="" width={size} height={size} style={{width:size,height:size}}/>:<ZMark size={size}/>
const Lockup=({logo,name,size=40})=><div className="lockup"><Logo src={logo} size={size}/><b>{name}</b></div>
// sign-in, reset and first-password pages: the form, with a brand panel beside it on wide screens
// the language switch: English, Arabic (the whole app turns right to left) or Tamil
const cap=w=>w?w[0].toUpperCase()+w.slice(1):''
const LangSwitch=({lang,pick})=><label className="langsw" title={tl("Language")}><Globe size={17} aria-hidden="true"/><select aria-label={tl("Language")} value={lang} onChange={e=>pick(e.target.value)}>{LANGS.map(([k,l])=><option key={k} value={k} lang={k}>{l}</option>)}</select></label>
const AuthFrame=({logo,name,children,lang,pick})=><div className="auth"><div className="authlang"><LangSwitch lang={lang} pick={pick}/></div><aside className="authart" aria-hidden="true"><Lockup logo={logo} name={name} size={44}/>
  <div><h2>{tl("Learn engineering, one topic at a time.")}</h2><p>{tl("Courses, notes, practice tests and progress for every program, semester and student, in one place.")}</p></div>
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
  if(resetTok)return <AuthFrame logo={logo} name={name} lang={lang} pick={pickLang}><ResetPassword token={resetTok} toast={toast} msg={msg} canReset={canReset} appName={name} logo={logo} done={u=>{history.replaceState(null,'',location.pathname);setResetTok(null);setUser(u);toast(tl("Password changed. You are signed in."))}} leave={()=>{history.replaceState(null,'',location.pathname);setResetTok(null)}}/></AuthFrame>
  if(!user)return <AuthFrame logo={logo} name={name} lang={lang} pick={pickLang}><Login onIn={setUser} toast={toast} msg={msg} appName={name} logo={logo} canReset={canReset} canReg={canReg}/></AuthFrame>
  if(user.must_change)return <AuthFrame logo={logo} name={name} lang={lang} pick={pickLang}><ChangePassword forced appName={name} logo={logo} toast={toast} msg={msg} done={()=>setUser({...user,must_change:false})} out={()=>{localStorage.removeItem('t');setUser(null)}}/></AuthFrame>
  const student=user.role==='student',page=pageSel||'home',admin=user.role==='admin',go=k=>{if(k==='build')setStudyStart(null);setPage(k);setOpen(false)},openIn=nav=>{setStart(nav);go('learn')},openStudy=t=>{setPage('build');setOpen(false);setStudyStart(t)},find=q=>{setFindQ(f=>({q,n:f.n+1}));go('search')},signOut=()=>{localStorage.removeItem('t');setOpen(false);setPage(null);setUser(null)}
  // the side menu (the logo goes Home; search, change password, theme and sign out are in the header)
  const links=student?[['learn',GraduationCap,tl("My courses")],['saved',Bookmark,tl("Saved")],['progress',TrendingUp,tl("My progress")],['build',Upload,tl("Build a course")],...(user.self_registered?[['aikey',Sparkles,tl("My AI key")]]:[])]  // a short menu: routine lives in My progress, About in the footer
    :admin?[['programs',GraduationCap,tl("Programs")],['courses',BookOpen,tl("Courses")],['users',UsersIcon,tl("Users")],['reports',BarChart3,tl("Reports")],['activity',History,tl("Activity log")],['ai',Sparkles,tl("Settings")],['about',Info,tl("About")]]
    :[['learn',BookOpen,tl("Courses")],['bookmarks',Bookmark,tl("Bookmarks")],['highlights',Highlighter,tl("My highlights")],['reports',BarChart3,tl("Reports")],...(user.self_registered?[['aikey',Sparkles,tl("My AI key")]]:[]),['about',Info,tl("About")]]
  return <Ctx.Provider value={{menu:()=>setOpen(true),appName:name,confirm,role:user.role}}>
    <TopBar user={user} lang={lang} pickLang={pickLang} theme={theme} pickTheme={pickTheme} onMenu={()=>setOpen(true)} onHome={()=>go('home')} onAccount={()=>go('password')} onOut={signOut} onNote={()=>go('home')} page={page}/>
    {page!=='search'&&<GlobalSearch key={findQ.n} onFind={find}/>}
    <div id="pageslot"/>
    {page==='home'&&student&&<Dashboard user={user} toast={toast} onOpen={openIn} onStudy={openStudy} onRoutine={()=>go('routine')}/>}
    {page==='routine'&&student&&<RoutinePage toast={toast} done={()=>go('home')}/>}
    {page==='home'&&!student&&<StaffHome user={user} toast={toast} open={openIn}/>}
    {page==='search'&&<SearchPage key={findQ.n} initial={findQ.q} user={user} toast={toast}/>}{page==='learn'&&<Learn key={String(start)} start={start} user={user} toast={toast} appName={name}/>}
    {page==='progress'&&user.role==='student'&&<Insights toast={toast} role={user.role} onRoutine={()=>go('routine')}/>}{page==='saved'&&student&&<Saved toast={toast} role={user.role}/>}
    {page==='build'&&user.role==='student'&&<StudyHome key={JSON.stringify(studyStart)} start={studyStart} toast={toast}/>}
    {page==='bookmarks'&&!admin&&<Bookmarks toast={toast} role={user.role}/>}{page==='highlights'&&!admin&&<MyHighlights toast={toast} role={user.role}/>}
    {page==='users'&&admin&&<Users toast={toast} me={user}/>}{page==='courses'&&admin&&<AdminCourses toast={toast} onOpen={openIn}/>}{page==='programs'&&admin&&<Programs toast={toast} onOpen={openIn}/>}
    {page==='ai'&&admin&&<AiConfig toast={toast} onBrand={()=>api('/config').then(c=>{setName(c.name);setLogo(c.logo||null);document.title=c.name})}/>}{page==='reports'&&(admin||user.role==='faculty')&&<Reports role={user.role} toast={toast}/>}{page==='activity'&&admin&&<Activity toast={toast}/>}{page==='aikey'&&user.self_registered&&<MyAiKey toast={toast}/>}{page==='password'&&<ChangePassword toast={toast} done={()=>go('learn')}/>}{page==='about'&&<About user={user}/>}
    <div className={'drawer'+(open?' open':'')}><div className="dscrim" onClick={()=>setOpen(false)}/>
      <nav className="panel" aria-label={tl("Main menu")}>
        <div className="dhead"><button className={'homebtn'+(page==='home'?' on':'')} aria-label={tl("{name}, home",{name:name})} aria-current={page==='home'?'page':undefined} onClick={()=>go('home')}><Logo src={logo} size={36}/><span><b>{name}</b><small>{user.name}, {tl(cap(user.role)).toLowerCase()}</small></span></button><button className="ic" aria-label={tl("Close menu")} onClick={()=>setOpen(false)}><X/></button></div>
        <div className="panlang"><LangSwitch lang={lang} pick={pickLang}/></div>
        {links.map(([k,I,l])=><button key={k} className={'dlink'+(page===k?' on':'')} onClick={()=>{if(k==='learn')setStart(null);go(k)}}><I size={20}/>{tl(l)}</button>)}
      </nav></div>
    <footer className="foot"><span>{tl("© {v} {name}. All rights reserved.",{v:new Date().getFullYear(),name:name})}</span>{student&&<>{" · "}<button className="link footl" onClick={()=>go('about')}>{tl("About")}</button></>}</footer>
    <Toast msg={msg}/>
    {ask&&<Confirm o={ask.o} answer={ok=>{ask.res(ok);setAsk(null)}}/>}
  </Ctx.Provider>}

function Login({onIn,toast,msg,appName,logo,canReset,canReg}){
  const [f,setF]=useState({email:'',password:''}),[b,setB]=useState(false),[mode,setMode]=useState('in'),[sent,setSent]=useState('')
  const go=async()=>{setB(true);try{const r=await api('/login',{method:'POST',body:f});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  const forgot=async()=>{setB(true);try{setSent((await api('/forgot',{method:'POST',body:{email:f.email}})).message)}catch(e){toast(e.message)}setB(false)}
  if(mode==='register')return <Register onIn={onIn} toast={toast} msg={msg} appName={appName} logo={logo} back={()=>setMode('in')}/>
  if(mode==='forgot')return <div className="login"><Lockup logo={logo} name={appName}/><h1>{tl("Forgot your password?")}</h1>{sent?<p>{sent}</p>:<><p>{tl("Enter your account email and we will send a link to choose a new one.")}</p>
    <label>{tl("Email")}</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})} onKeyDown={e=>e.key==='Enter'&&forgot()}/>
    <button className="btn" disabled={b||!f.email} onClick={forgot}>{tl("Send reset link")}</button></>}
    <button className="btn ghost" onClick={()=>{setMode('in');setSent('')}}>{tl("Back to sign in")}</button><Toast msg={msg}/></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>{tl("Sign in")}</h1><p>{tl("Use the account your institution created for you.")}</p>
    <label>{tl("Email")}</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})}/>
    <label>{tl("Password")}</label><input type="password" autoComplete="current-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>{tl("Sign in")}</button>
    {canReset?<button className="btn ghost" onClick={()=>setMode('forgot')}>{tl("Forgot password?")}</button>:<p className="known">{tl("Forgot your password? Ask your admin to reset it.")}</p>}{canReg&&<button className="btn ghost" onClick={()=>setMode('register')}>{tl("Create an account")}</button>}<Toast msg={msg}/></div>}

function Register({onIn,toast,msg,appName,logo,back}){
  const [f,setF]=useState({name:'',institution:'',id_number:'',email:'',phone:'',password:''}),[stage,setStage]=useState('form'),[code,setCode]=useState(''),[b,setB]=useState(false),[wait,setWait]=useState(0),[info,setInfo]=useState(''),[st,setSt]=useState({domains:[]})
  useEffect(()=>{api('/register/status').then(setSt).catch(()=>{})},[])
  useEffect(()=>{if(wait<=0)return;const t=setTimeout(()=>setWait(wait-1),1000);return()=>clearTimeout(t)},[wait])
  const set=k=>e=>setF({...f,[k]:e.target.value}),ok=Object.values(f).every(v=>v.trim())
  const start=async()=>{setB(true);try{const r=await api('/register/start',{method:'POST',body:f});setInfo(r.message);setStage('code');setWait(30)}catch(e){toast(e.message)}setB(false)}
  const verify=async()=>{setB(true);try{const r=await api('/register/verify',{method:'POST',body:{email:f.email,code}});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  const resend=async()=>{try{await api('/register/resend',{method:'POST',body:{email:f.email}});toast(tl("A new code is on its way"));setWait(30);setCode('')}catch(e){toast(e.message)}}
  if(stage==='code')return <div className="login"><Lockup logo={logo} name={appName}/><h1>{tl("Enter the code")}</h1><p>{info}</p>
    <label htmlFor="otp">{tl("6-digit code")}</label><input id="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} onKeyDown={e=>e.key==='Enter'&&code.length===6&&verify()} style={{letterSpacing:'.4em',fontSize:22,textAlign:'center'}}/>
    <button className="btn" disabled={b||code.length!==6} onClick={verify}>{tl("Verify and create my account")}</button>
    <button className="btn ghost" disabled={wait>0} onClick={resend}>{wait>0?tl("Send a new code in {wait}s",{wait:wait}):tl("Send a new code")}</button>
    <button className="btn ghost" onClick={()=>{setStage('form');setCode('')}}>{tl("Change my details")}</button><Toast msg={msg}/></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>{tl("Create an account")}</h1><p>{tl("We will email you a code to confirm your address.")}{st.domains.length>0&&tl(" Use your institution email ({domains}).",{domains:st.domains.map(d=>'@'+d).join(', ')})}</p>
    <label htmlFor="rn">{tl("Full name")}</label><input id="rn" autoComplete="name" value={f.name} onChange={set('name')}/>
    <label htmlFor="ri">{tl("Institution")}</label><input id="ri" autoComplete="organization" value={f.institution} onChange={set('institution')}/>
    <label htmlFor="rid">{tl("ID number")}</label><input id="rid" value={f.id_number} onChange={set('id_number')} placeholder={tl("Roll or employee number")}/>
    <label htmlFor="re">{tl("Email")}</label><input id="re" type="email" autoComplete="email" value={f.email} onChange={set('email')}/>
    <label htmlFor="rp">{tl("Phone")}</label><input id="rp" type="tel" autoComplete="tel" value={f.phone} onChange={set('phone')} placeholder="+91 98765 43210"/>
    <label htmlFor="rw">{tl("Password")}</label><input id="rw" type="password" autoComplete="new-password" value={f.password} onChange={set('password')} onKeyDown={e=>e.key==='Enter'&&ok&&start()}/>
    <p className="known">{tl("At least 8 characters. AI help on this account uses your own DeepSeek API key, which you add after signing in.")}</p>
    <button className="btn" disabled={b||!ok} onClick={start}>{tl("Send me a code")}</button><button className="btn ghost" onClick={back}>{tl("Back to sign in")}</button><Toast msg={msg}/></div>}

function MyAiKey({toast}){
  const confirm=useConfirm()
  const [d,setD]=useState(null),[key,setKey]=useState(''),[b,setB]=useState(false)
  const load=()=>api('/me/ai-key').then(setD).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  const save=async()=>{setB(true);try{await api('/me/ai-key',{method:'PUT',body:{key}});setKey('');toast(tl("Key saved. AI help is on."));load()}catch(e){toast(e.message)}setB(false)}
  const del=async()=>{if(!await confirm({title:tl("Remove your key?"),body:tl("AI help turns off for you until you add one again."),ok:tl("Remove key"),danger:true}))return;try{await api('/me/ai-key',{method:'DELETE'});toast(tl("Key removed"));load()}catch(e){toast(e.message)}}
  return <><Bar title={tl("My AI key")} sub={d?.key_set?tl("AI is on · key {key_hint}",{key_hint:d.key_hint}):tl("AI is off · no key yet")}/><div className="main">
    <p className="known">{tl("AI explanations on your account use your own DeepSeek API key, so any usage is billed to your DeepSeek account. Create a key at platform.deepseek.com, paste it here and save. We check it with DeepSeek first, then store it encrypted. It is never shown again in full.")}</p>
    <label htmlFor="k">{tl("DeepSeek API key")}</label><input id="k" type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder={d?.key_set?tl("Paste a new key to replace the current one"):tl("sk-…")}/>
    <button className="btn" disabled={b||!key.trim()} onClick={save}>{b?tl("Checking the key…"):tl("Save key")}</button>
    {d?.key_set&&<button className="btn ghost" onClick={del}>{tl("Remove my key")}</button>}</div></>}

function PromptEditor({toast}){
  const confirm=useConfirm()
  const [items,setItems]=useState(null),[draft,setDraft]=useState({}),[busy,setBusy]=useState('')
  const load=()=>api('/admin/prompts').then(r=>{setItems(r.items);setDraft({})}).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  if(!items)return <div className="sk"/>
  const save=async x=>{const text=draft[x.kind];if(x.saved_answers>0&&!await confirm({title:tl("Save this prompt?"),body:tl("Saving discards the {n} written with the old prompt, so students get fresh ones.",{n:pl(x.saved_answers,'saved answer')}),ok:tl("Save prompt")}))return
    setBusy(x.kind);try{const r=await api('/admin/prompts/'+x.kind,{method:'PUT',body:{text}});toast(tl("Prompt saved{v}",{v:r.cleared?` · ${pl(r.cleared,'saved answer')} cleared`:''}));load()}catch(e){toast(e.message)}setBusy('')}
  const reset=async x=>{if(!await confirm({title:tl("Go back to the built-in prompt?"),body:x.saved_answers?tl("This also discards {n}.",{n:pl(x.saved_answers,'saved answer')}):null,ok:tl("Reset to built-in")}))return
    setBusy(x.kind);try{await api('/admin/prompts/'+x.kind,{method:'DELETE'});toast(tl("Back to the built-in prompt"));load()}catch(e){toast(e.message)}setBusy('')}
  return <><p className="known">{tl("These are the instructions the AI gets before it answers. Change the tone, depth, language or format to suit your students. Saving a prompt discards the saved answers it wrote, so the new wording applies from the next question (that costs tokens again).")}</p>
    <div className="qbox"><b>{tl("Built-in safety rules")}</b><p className="known" style={{margin:'4px 0 0'}}>{tl("Every AI request starts with the app's safety rules, ahead of the prompts below. They keep answers to studies and safe for young people, treat notes and uploads as material rather than instructions, and answer a student in crisis with care. They are part of the app's code: they cannot be changed or turned off here, and a prompt below cannot override them.")}</p>
      <GuardText/></div>
    {items.map(x=>{const v=draft[x.kind]??x.text,dirty=v.trim()!==x.text.trim()
      return <div key={x.kind} className="qbox"><b>{x.label}{x.custom&&<span className="chip" style={{marginLeft:8}}>{tl("Edited")}</span>}</b><p className="known" style={{margin:'4px 0 8px'}}>{x.help}</p>
        <textarea aria-label={tl("{label} prompt",{label:x.label})} rows={9} value={v} maxLength={4000} onChange={e=>setDraft({...draft,[x.kind]:e.target.value})}/>
        <small className="known">{v.length}{" "}{tl("/ 4000 characters")}</small>
        <div className="two"><button className="btn" disabled={!dirty||busy===x.kind||v.trim().length<20} onClick={()=>save(x)}>{tl("Save prompt")}</button><button className="btn ghost" disabled={busy===x.kind||(!x.custom&&!dirty)} onClick={()=>x.custom?reset(x):setDraft({...draft,[x.kind]:x.default})}>{x.custom?tl("Reset to built-in"):tl("Undo changes")}</button></div></div>})}</>}

function SelfReg({cfg,run}){
  const [dom,setDom]=useState(null);const on=!!cfg.self_registration,shown=dom??cfg.allowed_domains??''
  return <><p className="known">{on?tl("On. The sign-in page shows “Create an account”. People confirm their email with a code, then you place them in a program and semester or year from Users (they show as Self-registered)."):tl("Off. Only admins can create accounts.")} {!cfg.mail_on&&tl("Emailing codes needs SMTP set up first (see the email section below), so registration stays closed until it is.")} {cfg.self_registered_users>0&&tl("{self_registered_users} people have registered themselves so far.",{self_registered_users:cfg.self_registered_users})}</p>
    <label className="chk"><input type="checkbox" checked={on} onChange={e=>run(()=>api('/admin/settings',{method:'PUT',body:{self_registration:e.target.checked}}),e.target.checked?'Self-registration is on':'Self-registration is off')}/>{" "}{tl("Allow people to register themselves")}</label>
    <label htmlFor="dom">{tl("Only these email domains (optional)")}</label><input id="dom" value={shown} onChange={e=>setDom(e.target.value)} placeholder={tl("college.edu, mail.college.edu")}/>
    <button className="btn ghost" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{allowed_domains:shown}}).then(()=>setDom(null)),'Domains saved')}>{tl("Save domains")}</button>
    <p className="known">{tl("Self-registered people always use their own DeepSeek key, never yours.")}</p></>}

function ResetPassword({token,toast,msg,done,leave,canReset,appName,logo}){
  const [ok,setOk]=useState(null),[f,setF]=useState({password:'',again:''}),[b,setB]=useState(false)
  useEffect(()=>{api('/reset/check',{method:'POST',body:{token}}).then(r=>setOk(r.valid)).catch(()=>setOk(false))},[token])
  const go=async()=>{if(f.password.length<8)return toast(tl("Use at least 8 characters"));if(f.password!==f.again)return toast(tl("The passwords don't match"))
    setB(true);try{const r=await api('/reset',{method:'POST',body:{token,new_password:f.password}});localStorage.t=r.token;done(r.user)}catch(e){toast(e.message)}setB(false)}
  if(ok===null)return null
  if(!ok)return <div className="login"><Lockup logo={logo} name={appName}/><h1>{tl("This link has expired")}</h1><p>{tl("Reset links work once and only for a short time.")}{canReset?tl(" Ask for a new one from the sign-in page."):tl(" Ask your admin to reset your password.")}</p><button className="btn" onClick={leave}>{tl("Go to sign in")}</button></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>{tl("Choose a new password")}</h1><p>{tl("Use at least 8 characters.")}</p>
    <label>{tl("New password")}</label><input type="password" autoComplete="new-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})}/>
    <label>{tl("Repeat new password")}</label><input type="password" autoComplete="new-password" value={f.again} onChange={e=>setF({...f,again:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>{tl("Save and sign in")}</button><Toast msg={msg}/></div>}

function ChangePassword({forced,appName,logo,toast,msg,done,out}){
  const [f,setF]=useState({current:'',password:'',again:''}),[b,setB]=useState(false),set=k=>e=>setF({...f,[k]:e.target.value})
  const go=async()=>{if(f.password.length<8)return toast(tl("Use at least 8 characters"));if(f.password!==f.again)return toast(tl("The new passwords don't match"))
    setB(true);try{const d=await api('/me/password',{method:'POST',body:{current:f.current,new_password:f.password}});if(d.token)localStorage.t=d.token;toast(tl("Password changed"));done()}catch(e){toast(e.message)}setB(false)}
  const form=<><label>{forced?tl("Password your admin gave you"):tl("Current password")}</label><input type="password" autoComplete="current-password" value={f.current} onChange={set('current')}/>
    <label>{tl("New password (8+ characters)")}</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/>
    <label>{tl("Repeat new password")}</label><input type="password" autoComplete="new-password" value={f.again} onChange={set('again')} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>{tl("Change password")}</button></>
  if(forced)return <div className="login"><Lockup logo={logo} name={appName}/><h1>{tl("Choose your own password")}</h1><p>{tl("Your admin set a temporary password. Pick a new one to continue.")}</p>{form}<button className="btn ghost" onClick={out}>{tl("Sign out")}</button><Toast msg={msg}/></div>
  return <><Bar title={tl("Change password")}/><div className="main">{form}</div></>}

const Bar=({title,sub,back,right})=><div className="bar">{back&&<button className="ic" aria-label={tl("Back")} onClick={back}><ChevronLeft/></button>}
  <h1>{title}{sub&&<small>{sub}</small>}</h1>{right}</div>
// the header on every signed-in page: menu (phone), notifications, theme, the signed-in user (opens Change password) and sign out at the far right
const initials=n=>(n||'?').trim().split(/\s+/).filter(w=>!/^(dr|prof|mr|mrs|ms|miss)\.?$/i.test(w)).slice(0,2).map(w=>w[0]).join('').toUpperCase()||'?'
function TopBar({user,lang,pickLang,theme,pickTheme,onMenu,onHome,onAccount,onOut,onNote,page}){
  const {appName}=useContext(Ctx),i=THEMES.findIndex(t=>t[0]===theme),[,ThemeIcon,themeLabel]=THEMES[i<0?0:i],nextTheme=THEMES[(i+1)%THEMES.length]
  return <header className="top"><button className="ic menu" aria-label={tl("Open menu")} onClick={onMenu}><Menu/></button><button className="topname" onClick={onHome}>{appName}</button>
    <span className="topgap"/>
    <Notifications onOpen={onNote} page={page}/>
    <LangSwitch lang={lang} pick={pickLang}/>
    <button className="ic" aria-label={tl("Theme: {themeLabel}. Switch to {v}",{themeLabel:themeLabel,v:nextTheme[2]})} title={tl("Theme: {themeLabel}",{themeLabel:themeLabel})} onClick={()=>pickTheme(nextTheme[0])}><ThemeIcon size={19}/></button>
    <button className={'who'+(page==='password'?' on':'')} onClick={onAccount} title={tl("Change password")}><span className="av" aria-hidden="true">{initials(user.name)}</span><span className="whotx"><b>{user.name}</b><small>{tl(cap(user.role))}</small></span></button>
    <button className="ic" aria-label={tl("Sign out")} title={tl("Sign out")} onClick={onOut}><LogOut size={19}/></button></header>}
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
  return <div className="notes" ref={box}><button className="ic" aria-label={n?tl("Notifications, {n} new",{n:n}):tl("Notifications")} aria-expanded={open} onClick={toggle}><Bell size={19}/>{n>0&&<em className="badge">{n>9?'9+':n}</em>}</button>
    {open&&<div className="pop" role="dialog" aria-label={tl("Notifications")}><b className="poph">{tl("Notifications")}{n>0&&<small>{" "}{tl("· {n} new",{n:n})}</small>}</b>
      {d===null?<Skeleton/>:items.length?<Paged rows={items} render={x=><button key={x.key} className={'note'+(x.unread?' new':'')} onClick={()=>{setOpen(false);load();onOpen()}}><span>{srv(x.text)}</span>{x.sub&&<small>{srv(x.sub)}</small>}</button>}/>:<p className="known">{tl("You're all caught up.")}</p>}
      {d?.mail&&<label className="chk notemail"><input type="checkbox" checked={!!d.digest} onChange={e=>digest(e.target.checked)}/>{" "}{tl("Email me a daily summary of new ones")}</label>}</div>}</div>}
// the search box under the header on every page: Enter opens Search with the query
function GlobalSearch({onFind}){
  const [q,setQ]=useState('')
  return <form className="gsearch" role="search" onSubmit={e=>{e.preventDefault();if(q.trim().length>=2)onFind(q.trim())}}><div className="search"><Search size={18}/><input type="search" aria-label={tl("Search topics")} placeholder={tl("Search topics, or ask a question")} value={q} maxLength={200} onChange={e=>setQ(e.target.value)}/></div></form>}

const ARCHIVE_WHAT=L({programs:'every semester or year, course, unit, topic and quiz in it',semesters:'every course, unit, topic and quiz in it',courses:'its units, topics and quizzes',units:'its topics and quizzes',topics:'this topic'})
const ONE=L({programs:'program',semesters:'semester or year',courses:'course',units:'unit',topics:'topic'})
function ArchiveSheet({a,close,done,toast}){  // archive or restore one item; archiving takes everything under it along, nothing is deleted
  const [busy,setBusy]=useState(false)
  const go=async()=>{setBusy(true);try{await api(`/${a.kind}/${a.id}/archive`,{method:'PUT',body:{archived:a.on}});toast(a.on?tl("Archived"):tl("Restored"));done()}catch(e){toast(e.message);setBusy(false)}}
  return <Sheet close={close}><h3>{a.on?tl("Archive"):tl("Restore")} “{a.name}”?</h3>
    <p className="known">{a.on?tl("This hides the {v} and {v2} from students, who see “unavailable right now” instead. Nothing is deleted and reading progress and quiz results are kept. You can restore it any time.",{v:ONE[a.kind],v2:ARCHIVE_WHAT[a.kind]})
      :tl("This brings back the {v} and everything that was archived along with it. Anything you archived on its own inside it stays archived until you restore that too.",{v:ONE[a.kind]})}</p>
    <button className={'btn'+(a.on?' danger':'')} disabled={busy} onClick={go}>{busy?tl("Working…"):a.on?tl("Archive"):tl("Restore")}</button><button className="btn ghost" onClick={close}>{tl("Cancel")}</button></Sheet>}
const ArchPill=({x})=>x.archived?<span className="pill off sm">{x.archived_self?tl("Archived"):tl("Archived with its parent")}</span>:null
function Learn({user,toast,appName,start}){
  const isAdmin=user.role==='admin',staff=user.role!=='student'
  const [mat,setMat]=useState(false),[rev,setRev]=useState(null)
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
  if(rev)return <RevisionSheet uid={rev} toast={toast} back={()=>setRev(null)}/>
  if(gb)return <Gradebook cid={gb} back={()=>setGb(null)} toast={toast} role={user.role}/>
  if(ed)return <TopicEditor role={user.role} toast={toast} edit={ed.id?ed:null} unitId={ed.unit_id} done={()=>setEd(null)} cancel={()=>setEd(null)}/>
  const tsub=x=>[x.published===false&&'Draft · students cannot see it',x.learning_due_at&&(staff?'Due '+when(x.learning_due_at):tl("Your teacher's date")+': '+day(x.learning_due_at)),
    cp?.topics[x.id]&&`${cp.topics[x.id].completed}/${cp.students} completed`+(cp.topics[x.id].overdue?` · ${cp.topics[x.id].overdue} overdue`:'')].filter(Boolean).join(' · ')
  const row=(x,kind,one,sub,extra={})=>({id:x.id,n:x.name,sub,kind,archived:x.archived,archived_self:x.archived_self,locked:!staff&&kind==='courses'&&x.archived,can:kind==='programs'||kind==='semesters'?isAdmin:kind==='courses'?(isAdmin||x.mine)&&!x.shared:mayEdit&&!co?.shared,go:()=>setNav([...nav,x.id]),edit:()=>setEd({kind:one,id:x.id,name:x.name,...extra})})
  const drafts=t=>t.filter(x=>x.published===false).length
  const setPub=async(url,published,msg)=>{try{await api(url,{method:'PUT',body:{published}});toast(msg);load()}catch(e){toast(e.message)}}
  const move=async(items,i,d,url)=>{const ids=items.map(x=>x.id),j=i+d;if(j<0||j>=ids.length)return;[ids[i],ids[j]]=[ids[j],ids[i]];try{await api(url,{method:'PUT',body:{ids}});load()}catch(e){toast(e.message)}}
  const list0=unit?unit.topics.map(x=>({id:x.id,n:x.title,s:x.status,b:x.bookmarked,kind:'topics',archived:x.archived,archived_self:x.archived_self,can:mayEdit&&!co.shared,sub:tsub(x),late:x.overdue,draft:x.published===false,go:()=>setT(x.id),edit:()=>setEd({id:x.id}),pub:()=>setPub(`/topics/${x.id}/publish`,x.published===false,x.published===false?'Published':'Moved to drafts')}))
    :co?co.units.map(x=>({...row(x,'units','unit',pl(x.topics.length,'topic')+(mayEdit&&drafts(x.topics)?' · '+tl('{n} draft',{n:drafts(x.topics)}):'')),edit:()=>setSheet({type:'unit',un:x,cid:co.id})}))
    :sem?sem.courses.map(x=>({...row(x,'courses','course',(staff?pl(x.units.length,'unit'):pl(x.units.flatMap(n=>n.topics).length,'topic'))+(x.shared?tl(" · shared from {home}",{home:x.home}):x.shared_with?tl(" · shared with {shared_with} more",{shared_with:x.shared_with}):'')+(staff?' · '+ownerLine(x):'')),edit:()=>setSheet({type:'course',c:x,pid:prog.id,sid:x.semester_id}),share:()=>setSh({id:x.id,name:x.name,home:x.semester_id,sel:x.link_ids||[]}),unlink:x.shared?{id:x.id,keep:(x.link_ids||[]).filter(i=>i!==sem.id)}:null}))
    :prog?prog.semesters.map(x=>({...row(x,'semesters','semester',(isAdmin?(x.number?tl('{term} no. {n}',{term:prog.term,n:x.number}):tl('No {term} number set',{term:prog.term.toLowerCase()}))+' · ':'')+pl(x.courses.length,'course')),edit:()=>setSheet({type:'semester',sem:x,pid:prog.id})}))
    :tree.map(x=>({...row(x,'programs','program',x.semesters.length+' '+x.term.toLowerCase()+(x.semesters.length===1?'':'s')),edit:()=>setSheet({type:'program',p:x})}))
  const hidden=staff?list0.filter(x=>x.archived).length:0,list=staff&&!showArch?list0.filter(x=>!x.archived):list0,anyArch=staff&&tree.some(p=>p.archived||p.semesters.some(s=>s.archived||s.courses.some(c=>c.archived||c.units.some(n=>n.archived_self||n.topics.some(t=>t.archived_self)))))
  const cur=unit||co||sem||prog,crumbs=[prog,sem,co,unit].filter(Boolean).slice(0,-1).map(x=>x.name).join(' › ')
  const allSems=tree.flatMap(p=>p.semesters.map(s=>({id:s.id,label:p.name+' › '+s.name})))
  const myCourses=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>c.mine&&!c.shared&&(!c.archived||showArch)).map(c=>({p,s,c}))))
  const saveShare=async()=>{try{await api(`/courses/${sh.id}/links`,{method:'PUT',body:{semester_ids:sh.sel}});toast(tl("Sharing updated"));setSh(null);load()}catch(e){toast(e.message)}}
  const remove=async()=>{try{if(del.unlink)await api(`/courses/${del.unlink.id}/links`,{method:'PUT',body:{semester_ids:del.unlink.keep}});else await api(`/${del.kind}/${del.id}`,{method:'DELETE'});toast(tl("Deleted"));setDel(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={cur?.name||appName} sub={nav.length?crumbs:tl("Hi {name}",{name:user.name})} back={nav.length>0&&(()=>setNav(nav.slice(0,-1)))}/>
   <div className="main">{unit&&mayEdit&&drafts(unit.topics)>0&&<button className="btn" style={{marginTop:0,marginBottom:12}} onClick={()=>setPub(`/units/${unit.id}/publish`,true,'All drafts published')}>{tl("Publish all {drafts} drafts",{drafts:drafts(unit.topics)})}</button>}{!nav.length&&!(user.role==='faculty'&&myCourses.length>0)&&<div className="hero"><h2>{tl("Choose a program")}</h2></div>}
     {staff&&(anyArch||showArch)&&<label className="chk" style={{marginBottom:12}}><input type="checkbox" checked={showArch} onChange={e=>setShowArch(e.target.checked)}/>{" "}{tl("Show archived")}{!showArch&&hidden>0?tl(" ({hidden} here)",{hidden:hidden}):''}</label>}
     {isAdmin&&!sem&&<button className="btn ghost lead" onClick={()=>setSheet(prog?{type:'semester',sem:{},pid:prog.id}:{type:'program',p:{}})}>{prog?tl("Add {term} to {name}",{term:prog.term.toLowerCase(),name:prog.name}):tl("New program")}</button>}
     {isAdmin&&sem&&!co&&<button className="btn ghost lead" onClick={()=>setSheet({type:'course',c:{},pid:prog.id,sid:sem.id})}>{tl("Add course to")}{" "}{sem.name}</button>}
     {co&&!unit&&!staff&&(()=>{const ts=co.units.flatMap(n=>n.topics),k=ts.filter(x=>x.has_notes).length;return <div className="card"><button className="hit" onClick={()=>setMat(true)}><span className="dot" style={{background:COL[3]}}><FileText size={20}/></span>
       <div><b>{k?tl("Your notes in {k} of {length} topics",{k:k,length:ts.length}):tl("Bring your own notes")}</b><span>{k?tl("Add or update your material"):tl("Upload your PDF or Word notes. They are filed under this course's topics, for you only.")}</span></div></button></div>})()}
     {co&&!unit&&staff&&<div className="qbox" style={{marginTop:0}}><p className="known" style={{margin:0}}>{tl("Owner:")}{" "}<b>{co.mine?tl("You"):srv(co.owner_problem)||co.owner||tl("Not assigned")}</b>{sem.number?tl(" · {term} no. {number}",{term:prog.term,number:sem.number}):''}</p>
       {isAdmin&&!co.shared&&<div className="two"><button className="btn ghost" onClick={()=>setSheet({type:'course',c:co,pid:prog.id,sid:co.semester_id})}>{tl("Edit course")}</button><button className="btn ghost" onClick={()=>setSheet({type:'owner',c:co})}>{tl("Change owner")}</button></div>}</div>}
     {!nav.length&&user.role==='faculty'&&<><h3 className="sec first">{tl("My courses")}</h3>{myCourses.length?<Paged rows={myCourses} render={({p,s,c},i)=><div key={c.id} className="card"><button className="hit" onClick={()=>setNav([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div><b>{c.name}<ArchPill x={c}/></b><span>{p.name}{" "}{tl("› {name} · {length} units",{name:s.name,length:c.units.length})}</span></div></button></div>}/>
       :<p className="known">{tl("No course is assigned to you yet. An admin makes you the owner of a course.")}</p>}<h3 className="sec">{tl("All programs")}</h3></>}
    {mayEdit&&co&&!unit&&!co.shared&&<button className="btn ghost lead" onClick={()=>setSheet({type:'unit',un:{},cid:co.id})}>{tl("Add unit")}</button>}
    {mayEdit&&unit&&!co.shared&&<div className="two lead2"><button className="btn ghost" onClick={()=>setEd({unit_id:unit.id})}>{tl("Add topic to")}{" "}{unit.name}</button><button className="btn ghost" onClick={()=>setBulk(unit)}><Upload size={16}/>{" "}{tl("Upload topic files")}</button></div>}
    {!staff&&unit&&<button className="btn ghost lead" onClick={()=>setRev(unit.id)}><FileText size={16}/>{" "}{tl("Revision sheet")}</button>}
    {staff&&unit&&<button className="btn ghost lead" onClick={()=>setCopy({kind:'unit',id:unit.id,title:unit.name})}>{tl("Copy this unit to another course")}</button>}
    {<Paged rows={list} render={(x,i)=>x.locked?<div key={x.id} className="card" style={{opacity:.7}}><button className="hit" onClick={()=>toast(tl("This course is unavailable right now"))} aria-label={tl("{n}, unavailable right now",{n:x.n})}><span className="dot" style={{background:'var(--mut)'}}><Lock size={18}/></span><div><b>{x.n}</b><span>{tl("Unavailable right now")}</span></div></button></div>:<div key={x.id} className="card" style={x.archived?{opacity:.75}:undefined}><button className="hit" onClick={x.go}><span className="dot" style={{background:COL[i%5]}}>{x.n[0]}</span><div><b>{x.n}<ArchPill x={x}/></b>{x.sub&&<span>{x.sub}</span>}</div>{(x.s||x.b)&&<span className="marks">{x.b&&<Bookmark className="bm" size={16} fill="currentColor"/>}{x.s&&<Mark s={x.s}/>}</span>}</button>
      <div className="acts">{staff&&x.can&&(x.archived_self||!x.archived)&&<button className="ic sm" aria-label={(x.archived_self?'Restore ':'Archive ')+x.n} onClick={()=>setArch({kind:x.kind,id:x.id,name:x.n,on:!x.archived_self})}>{x.archived_self?<ArchiveRestore size={16}/>:<Archive size={16}/>}</button>}
      {mayEdit&&<>{(x.kind==='units'||x.kind==='topics')&&list.length>1&&[[-1,ArrowUp,'up'],[1,ArrowDown,'down']].map(([d,I,w])=><button key={w} className="ic sm" aria-label={tl("Move {n} {w}",{n:x.n,w:w})} disabled={i+d<0||i+d>=list.length} onClick={()=>move(list,i,d,x.kind==='units'?`/courses/${co.id}/units/order`:`/units/${unit.id}/topics/order`)}><I size={16}/></button>)}{x.pub&&<button className="ic sm" aria-label={(x.draft?'Publish ':'Unpublish ')+x.n} onClick={x.pub}>{x.draft?<Eye size={16}/>:<EyeOff size={16}/>}</button>}{x.share&&<button className="ic sm" aria-label={tl("Share {n}",{n:x.n})} onClick={x.share}><Link2 size={16}/></button>}<button className="ic sm" aria-label={tl("Edit {n}",{n:x.n})} onClick={x.edit}><Pencil size={16}/></button><button className="ic sm" aria-label={tl("Delete {n}",{n:x.n})} onClick={()=>setDel(x.unlink?{...x,unlink:x.unlink}:x)}><Trash2 size={16}/></button></>}</div></div>}/>}
    {co&&!unit&&(co.tests?.length>0||(mayEdit&&!co.shared))&&<><h3 className="sec">{tl("MCQ tests")}</h3>
      {<Paged rows={co.tests} render={(q,i)=><div key={q.id} className="card"><button className="hit" onClick={()=>setQz(q.id)}><span className="dot" style={{background:COL[(i+1)%5]}}><ClipboardList size={18}/></span><div><b>{q.title}</b><span>{q.questions}{" "}{tl("questions · pass {pass_percent}%",{pass_percent:q.pass_percent})}{q.best!=null?tl(" · best {best}%",{best:q.best}):''}{q.published?'':tl(" · Draft")}</span></div>{q.best!=null&&q.best>=q.pass_percent&&<span className="marks"><Check size={16}/></span>}</button>
        {mayEdit&&<><button className="ic sm" aria-label={tl("Results of {title}",{title:q.title})} onClick={()=>setQr(q.id)}><BarChart3 size={16}/></button><button className="ic sm" aria-label={tl("Edit {title}",{title:q.title})} onClick={()=>setQe({id:q.id,course_id:co.id})}><Pencil size={16}/></button></>}</div>}/>}
      {mayEdit&&!co.shared&&<button className="btn ghost" onClick={()=>setQe({course_id:co.id,csvFirst:true})}><Upload size={16}/>{" "}{tl("New MCQ test from a CSV")}</button>}
      {mayEdit&&<button className="btn ghost" onClick={()=>setGb(co.id)}><BarChart3 size={16}/>{" "}{tl("Gradebook: final scores for every test")}</button>}</>}
    {unit&&(unit.quizzes.length>0||mayEdit)&&<><h3 className="sec">{tl("Quizzes")}</h3>
      {<Paged rows={unit.quizzes} render={(q,i)=><div key={q.id} className="card"><button className="hit" onClick={()=>setQz(q.id)}><span className="dot" style={{background:COL[(i+3)%5]}}>?</span><div><b>{q.title}</b><span>{q.questions}{" "}{tl("questions · pass {pass_percent}%",{pass_percent:q.pass_percent})}{q.best!=null?tl(" · best {best}%",{best:q.best}):''}{q.published?'':tl(" · Draft")}</span></div>{q.best!=null&&q.best>=q.pass_percent&&<span className="marks"><Check size={16}/></span>}</button>
        {mayEdit&&<><button className="ic sm" aria-label={tl("Results of {title}",{title:q.title})} onClick={()=>setQr(q.id)}><BarChart3 size={16}/></button><button className="ic sm" aria-label={tl("Edit {title}",{title:q.title})} onClick={()=>setQe({id:q.id,unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}><Pencil size={16}/></button></>}</div>}/>}
      {mayEdit&&<button className="btn ghost" onClick={()=>setQe({unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}>{tl("Add quiz")}</button>}</>}
    {!list.length&&<p className="known">{(mayEdit&&co)||isAdmin?tl("Nothing here yet. Use the button above to add it."):!nav.length&&user.role==='student'?tl("You are not enrolled in a program yet. Ask your admin to add you to one."):tl("Nothing here yet. Your admin will add it soon.")}</p>}</div>
   {arch&&<ArchiveSheet a={arch} toast={toast} close={()=>setArch(null)} done={()=>setArch(null)}/>}
   {copy&&<CopySheet {...copy} toast={toast} close={()=>{setCopy(null);load()}}/>}{bulk&&<BulkTopics unit={bulk} toast={toast} close={()=>setBulk(null)} done={()=>{setBulk(null);load()}}/>}
   {del&&<Sheet close={()=>setDel(null)}><h3>{del.unlink?tl("Remove"):tl("Delete")} “{del.n}”{del.unlink?tl(" from this {v}",{v:(prog?.term||'semester').toLowerCase()}):''}?</h3>
     <p className="known">{del.unlink?tl("It only disappears from this {v}. The course stays where it was created.",{v:(prog?.term||'semester').toLowerCase()}):DELETES[del.kind]}{" "}{tl("This can't be undone.")}</p>
     <button className="btn danger" onClick={remove}>{del.unlink?tl("Remove"):tl("Delete")}</button><button className="btn ghost" onClick={()=>setDel(null)}>{tl("Cancel")}</button></Sheet>}
   {sh&&<Sheet page close={()=>setSh(null)}><h3>{tl("Share “{name}”",{name:sh.name})}</h3><p className="known">{tl("Tick every semester or year that should also show this course. You still edit it in one place.")}</p>
     {allSems.filter(x=>x.id!==sh.home).map(x=><label key={x.id} className="chk"><input type="checkbox" checked={sh.sel.includes(x.id)} onChange={e=>setSh({...sh,sel:e.target.checked?[...sh.sel,x.id]:sh.sel.filter(i=>i!==x.id)})}/> {x.label}</label>)}
     <button className="btn" onClick={saveShare}>{tl("Save")}</button><button className="btn ghost" onClick={()=>setSh(null)}>{tl("Cancel")}</button></Sheet>}
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
  const save=async()=>{setBusy(true);try{const body={name:f.name,semester_no:f.no?+f.no:null};await api(isNew?`/programs/${pid}/semesters`:'/semesters/'+sem.id,{method:isNew?'POST':'PUT',body:isNew?body:{...body,program_id:pid}});toast(isNew?tl("{term} added",{term:term}):tl("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?tl("New {term}",{term:term.toLowerCase()}):tl("Edit {term}",{term:term.toLowerCase()})}</h3>
    <label>{term}{" "}{tl("number")}</label><select value={f.no} onChange={pickNo}><option value="">{tl("Choose…")}</option>{upTo(maxOf(term)).map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>{tl("Name")}</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder={term+" 3"}/>
    <p className="known" style={{marginTop:10}}>{tl("The number sets the order and which students see it: a student in {term} 3 sees {term2}s 1 to 3. Each number is used once per program.",{term:term.toLowerCase(),term2:term.toLowerCase()})}</p>
    <button className="btn" disabled={busy||!f.no||!f.name.trim()} onClick={save}>{isNew?tl("Add {term}",{term:term.toLowerCase()}):tl("Save changes")}</button></Sheet>}
function CourseSheet({c,pid,sid,sems,term='Semester',close,done,toast}){
  const isNew=!c.id,faculty=useFaculty(true),[f,setF]=useState({name:c.name||'',sem:sid,owner:c.owner_id||''}),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{const owner=String(f.owner)!==String(c.owner_id||'')?{faculty_owner_id:f.owner?+f.owner:null}:{}  // unchanged owners are left alone
    await api(isNew?`/programs/${pid}/semesters/${sid}/courses`:'/courses/'+c.id,{method:isNew?'POST':'PUT',body:isNew?{name:f.name,...owner}:{name:f.name,semester_id:+f.sem,...owner}});toast(isNew?tl("Course added"):tl("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?tl("New course in {v}",{v:sems.find(x=>x.id===sid)?.label||''}):tl("Edit course")}</h3>
    <label>{tl("Name")}</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder={tl("Thermodynamics")}/>
    {!isNew&&<><label>{term}</label><select value={f.sem} onChange={e=>setF({...f,sem:+e.target.value})}>{sems.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></>}
    <label>{tl("Owner (faculty)")}</label><select value={f.owner} onChange={e=>setF({...f,owner:e.target.value})}><option value="">{tl("Not assigned")}</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner}{" "}{tl("(can't edit)")}</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    {!isNew&&+f.sem!==sid&&<p className="known">{tl("Moving the course takes its units, topics, quizzes and owner with it. Students placed there will see it.")}</p>}
    <button className="btn" disabled={busy||!f.name.trim()} onClick={save}>{isNew?tl("Add course"):tl("Save changes")}</button></Sheet>}

const STUDY=L({not_started:'Not opened yet',in_progress:'Opened, not marked completed',completed:'Marked completed'})
const AREA_GROUPS=L([['needs_study',tl("Needs another round of study"),tl("Read these topics again, then retake the quiz.")],['getting_there',tl("Getting there"),''],['strong',tl("Strong areas"),tl("You answered these well.")]])
function AreaList({areas,onStudy,staff}){
  return <>{AREA_GROUPS.map(([k,title,hint])=>{const L=areas.filter(a=>a.status===k);if(!L.length)return null
    return <div className={'qbox area '+k} key={k}><b>{title} ({L.length})</b>{hint&&!staff&&<p className="known" style={{margin:'4px 0 8px'}}>{hint}</p>}
      {<Paged rows={L} render={a=><div className="arow" key={a.topic_id||'u'+a.unit_id}><div><span>{a.title}</span><small>{a.correct}{" "}{tl("of {total} right · {percent}%",{total:a.total,percent:a.percent})}{a.study&&!staff?' · '+STUDY[a.study]:''}{a.course?' · '+a.course:''}</small><Bar2 v={a.percent}/></div>
        {a.topic_id&&onStudy&&<button className="tool" onClick={()=>onStudy(a.topic_id)}>{k==='strong'?tl("Review"):tl("Study again")}</button>}</div>}/>}</div>})}</>}
const ATTN_GO={drafts:'drafts',empty_courses:'empty_courses',unowned:'unowned',unenrolled:'unenrolled',semester_numbers:'semester_numbers',never_opened:'never_opened'}
const RS_PAGE=PAGE
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
  const total=d?.total??0,pages=Math.max(1,Math.ceil(total/RS_PAGE)),title=srv(d?.title)||tl('Loading')
  return <><Bar title={title} sub={d?tl(q?(total===1?'{n} match':'{n} matches'):'{n} in total',{n:total}):''} back={back}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={tl("Search {title}",{title:title.toLowerCase()})} placeholder={tl("Search")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="qopt"><select aria-label={tl("Sort by")} value={order} onChange={e=>setOrder(e.target.value)}><option value="name">{tl("Sort: A to Z")}</option><option value="name_desc">{tl("Sort: Z to A")}</option><option value="detail">{tl("Sort: by details")}</option><option value="newest">{tl("Sort: newest first")}</option>{d?.can_recent&&<option value="recent">{tl("Sort: last active")}</option>}</select></div>
    {!d&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {d&&d.items.length>0&&<div className="uhead" aria-hidden="true"><span>{tl("Name")}</span><span>{tl("Details")}</span><span/></div>}
    {d?.items.map(x=><button key={x.id} className="utr" onClick={()=>setView(x)} aria-label={tl("Open {title}",{title:x.title})}>
      <span className="nm"><span className="dot" style={{background:COL[x.id%5]}}>{(x.title||'?')[0]}</span><span className="tx"><b>{x.title}</b><small className="sub">{x.sub}</small></span></span>
      <span className="pg">{x.detail||'—'}</span><span className="sn"><ChevronRight size={16}/></span></button>)}
    {d&&!d.items.length&&<p className="known">{q?tl("Nothing matches that search."):tl("Nothing here. All clear.")}</p>}
    {d&&total>RS_PAGE&&<nav className="pager" aria-label={tl("Pages")}><button className="btn ghost" disabled={page===0} onClick={()=>setPage(page-1)}><ChevronLeft size={18}/><span>{tl("Previous")}</span></button><small>{tl("Page {v} of",{v:page+1})}{" "}{pages}</small><button className="btn ghost" disabled={page+1>=pages} onClick={()=>setPage(page+1)}><span>{tl("Next")}</span><ChevronRight size={18}/></button></nav>}
  </div></>}
function StaffHome({user,toast,open}){
  const [o,setO]=useState(null),[list,setList]=useState(null),[rep,setRep]=useState(null),[flags,setFlags]=useState(0),[fp,setFp]=useState(false)
  useEffect(()=>{if(!list&&!rep&&!fp){api('/overview').then(setO).catch(e=>toast(e.message));api('/flags?limit=1').then(r=>setFlags(r.total)).catch(()=>{})}},[toast,list,rep,fp])
  if(fp)return <FlagsPage toast={toast} back={()=>setFp(false)}/>
  if(rep)return <StudentReport c={rep} back={()=>setRep(null)} toast={toast}/>
  if(list)return <ResultSet kind={list} user={user} back={()=>setList(null)} toast={toast} open={open}/>
  const admin=user.role==='admin',hour=new Date().getHours(),hi=hour<12?'Good morning, {name}':hour<17?'Good afternoon, {name}':'Good evening, {name}'
  const stats=o?(admin?[[o.people.students,'Active students','students'],[o.people.active_week,'Studied this week','active_week'],[o.people.faculty,'Faculty','faculty'],[o.courses,'Courses','courses']]:[[o.courses,'Your courses','courses'],[o.topics,'Topics','topics'],[o.drafts,'Drafts','drafts']]):[]
  return <><Bar title={tl(hi,{name:firstName(user.name)})} sub={admin?tl("Across the whole college"):tl("Your courses")}/><div className="main">
    {!o&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {o&&<div className="stats">{stats.map(([n,l0,k])=>{const l=tl(l0);return <button className="stat" key={l0} style={{textAlign:'start',width:'100%'}} onClick={()=>setList(k)} aria-label={tl("{v} {l}. Show the list",{v:(n??0).toLocaleString(),l:l})}><b>{(n??0).toLocaleString()}</b>{l}</button>})}</div>}
    {flags>0&&<button className="card flagcard" style={{textAlign:'start',width:'100%'}} onClick={()=>setFp(true)}><span className="dot" style={{background:'var(--coral)'}}><Flag size={18}/></span><div style={{flex:1}}><b>{tl(flags===1?'1 AI answer flagged by students':'{n} AI answers flagged by students',{n:flags})}</b><span>{tl("Check it, then have it written again or let it stand")}</span></div><ChevronRight size={18}/></button>}
    {o&&<><h3 className="sec">{tl("Needs attention")}</h3>
      {o.attention.length?<Paged rows={o.attention} render={x=><button key={x.kind} className="card" style={{textAlign:'start'}} onClick={()=>setList(ATTN_GO[x.kind]||'drafts')}><div style={{flex:1}}><b>{srv(x.text)}</b></div><ChevronRight size={18}/></button>}/>
        :<p className="known">{tl("Nothing needs your attention right now.")}</p>}</>}
    {o&&!o.courses&&!admin&&<p className="known">{tl("No course is assigned to you yet. An admin makes you the owner of a course.")}</p>}
    {o?.courses>0&&<><h3 className="sec">{admin?tl("Courses"):tl("Your courses")}</h3><CourseReports toast={toast} onOpen={setRep}/></>}
  </div></>}
// AI replies students flagged as looking wrong, on this person's topics (all of them for admins), never with who flagged them
const FLAG_KIND={gist:'The gist',why:'Why?',example:'Example',exam:'Exam angle',check:'Quick check',simpler:'More simply',outline:'Answer outline',explain:'Explain',answer:'Sample answer',line:'Highlight explanation',search:'Search answer'}
function FlagsPage({toast,back}){
  const confirm=useConfirm(),[t,setT]=useState(null)
  const {items,total,page,setPage,ready,reload}=usePaged(o=>`/flags?limit=${PAGE}&offset=${o}`,[],toast)
  const act=async(f,action)=>{if(action==='rewrite'&&!await confirm({title:tl("Have it written again?"),body:tl("The saved answer is dropped, and the next student who asks gets a new one (that uses AI tokens)."),ok:tl("Write it again")}))return
    try{await api(`/flags/${f.id}/resolve`,{method:'POST',body:{action}});toast(action==='rewrite'?tl("It will be written again"):tl("Left as it is"));reload()}catch(e){toast(e.message)}}
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast} role="faculty"/>
  return <><Bar title={tl("Flagged AI answers")} sub={ready?pl(total,'answer'):''} back={back}/><div className="main">
    <p className="known" style={{marginTop:0}}>{tl("Students flagged these AI answers as looking wrong. Who flagged them is never shown.")}</p>
    {!ready?<Skeleton/>:!items.length?<p className="known">{tl("Nothing is flagged right now.")}</p>:items.map(f=><div key={f.id} className="qbox flagrow">
      <small className="steplab">{tl(FLAG_KIND[f.kind]||f.kind)}{f.topic?' · '+f.topic+(f.course?' · '+f.course:''):''}</small>
      <div className="flagex"><Md>{f.excerpt||''}</Md></div>
      <p className="known" style={{margin:'6px 0'}}>{tl(f.count===1?'Flagged by 1 student':'Flagged by {n} students',{n:f.count})}{f.reasons.length>0&&':'}</p>
      {f.reasons.length>0&&<ul className="flagwhy">{f.reasons.map((r,i)=><li key={i}>“{r}”</li>)}</ul>}
      <div className="tools">{f.source==='topic'&&f.topic_id&&<button onClick={()=>setT(f.topic_id)}>{tl("Open the topic")}</button>}<button onClick={()=>act(f,'rewrite')}>{tl("Write it again")}</button><button onClick={()=>act(f,'keep')}>{tl("It's fine")}</button></div></div>)}
    <Pager page={page} total={total} onPage={setPage}/></div></>}
function Dashboard({user,toast,onOpen,onStudy,onRoutine}){
  const [sme,setSme]=useState(null);useEffect(()=>{api('/study/me').then(setSme).catch(()=>{})},[])
  const [tree,setTree]=useState(null),[today,setToday]=useState(null),[topic,setTopic]=useState(null),[sess,setSess]=useState(null)
  useEffect(()=>{if(topic)return;api('/tree').then(setTree).catch(e=>toast(e.message));api('/me/today').then(setToday).catch(()=>{})},[topic,toast])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={user.role}/>
  const hour=new Date().getHours(),hi=hour<12?'Good morning, {name}':hour<17?'Good afternoon, {name}':'Good evening, {name}'
  const seen=new Map(),courses=[]
  for(const p of tree||[])for(const s of p.semesters)for(const c of s.courses){const at=seen.get(c.id),item={p,s,c,topics:c.units.flatMap(un=>un.topics.map(t=>({...t,unit:un})))}
    if(at===undefined){seen.set(c.id,courses.length);courses.push(item)}else if(courses[at].c.archived&&!c.archived)courses[at]=item}  // a course shown twice counts once, and a live place wins over an archived one
  const resume=(today?.focus||[]).filter(f=>f.kind==='resume').sort((a,b)=>(b.last_read||'').localeCompare(a.last_read||''))[0]||(today?.focus||[]).find(f=>f.kind==='next')
  return <><Bar title={tl(hi,{name:firstName(user.name)})}/><div className="main">
    <SessionCard toast={toast} onRoutine={onRoutine} openTopic={setTopic} onStudy={onStudy} refresh={topic} onLoad={setSess}/>
    {!sess?.routine&&resume&&<div className="card"><button className="hit" onClick={()=>setTopic(resume.topic_id)}><span className="dot" style={{background:'var(--acc)'}}><Play size={18}/></span><div><b>{resume.title}</b><span>{resume.kind==='resume'?tl("Where you left off"):tl("Up next, if you like")} · {resume.course}</span></div><ChevronRight size={18}/></button></div>}
    <RecallCard open={setTopic}/>
    {sme&&sme.courses>0&&<><h3 className="sec">{tl("Your own courses")}</h3><LearnCard me={sme} compact onContinue={n=>onStudy({id:n.course_id,topic:n.topic_id})} onReview={cid=>onStudy({review:cid})}/></>}
    {sme&&!sme.courses&&tree&&!courses.length&&<button className="row rowbtn" onClick={()=>onStudy(null)}><span className="dot" style={{background:'var(--acc)'}}><Upload size={18}/></span><div>{tl("Build a course from your own notes")}<small>{tl("Upload a PDF or Word file and study it with quick checks, quizzes and reviews")}</small></div><ChevronRight size={18}/></button>}
    {!tree&&<><div className="sk"/><div className="sk"/></>}
    {tree&&!courses.length&&<p className="known">{user.self_registered&&!user.placed?tl("Your account is ready. An admin will place you in your program and semester or year, and your courses will appear here."):tl("You are not enrolled in a course yet. Ask your admin to add you to one.")}</p>}
    {courses.length>0&&<><h3 className="sec">{tl("My courses")}</h3><Paged rows={courses} render={({p,s,c,topics},i)=>{const done=topics.filter(t=>t.status==='completed').length,opened=topics.filter(t=>t.status!=='not_started').length
      if(c.archived)return <div key={c.id} className="card" style={{opacity:.7}}><button className="hit" onClick={()=>toast(tl("This course is unavailable right now"))} aria-label={tl("{name}, unavailable right now",{name:c.name})}><span className="dot" style={{background:'var(--mut)'}}><Lock size={18}/></span><div><b>{c.name}</b><span>{tl("Unavailable right now")}</span></div></button></div>
      return <div key={c.id} className="card"><button className="hit" onClick={()=>onOpen([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div><b>{c.name}</b><span>{pl(topics.length,'topic')}{opened?' · '+tl("{n} opened",{n:opened}):''}{done?' · '+tl("{n} learned",{n:done}):''}</span></div><ChevronRight size={18}/></button></div>}}/></>}
  </div></>}
// "Remember this?": one curious question from something read a few days ago, answered with a tap, easy to ignore (hidden for the day once dismissed)
function RecallCard({open}){
  const today=new Date().toDateString(),[d,setD]=useState(null),[off,setOff]=useState(()=>{try{return localStorage.recallOff===today}catch{return false}})
  useEffect(()=>{if(!off)api('/me/recall').then(r=>setD(r.item)).catch(()=>{})},[off])
  if(off||!d)return null
  const hide=()=>{try{localStorage.recallOff=today}catch{/* a private window: it just shows again next time */}setOff(true)}
  return <div className="recall"><div className="recallh"><small>{tl("Remember this?")}</small><button className="ic sm" aria-label={tl("Not now")} title={tl("Not now")} onClick={hide}><X size={15}/></button></div>
    <p className="recallq">{d.question}</p>
    <Reveal label={tl("Think, then tap for the answer")}><Md>{d.answer}</Md><button className="link" onClick={()=>open(d.topic_id)}>{tl("Open {title}",{title:d.title})}</button></Reveal></div>}
const WD=[0,1,2,3,4,5,6],wd=i=>new Date(2024,0,1+i).toLocaleDateString(locale(),{weekday:'short'})  // Monday first; 1 Jan 2024 was a Monday. Names in the reader's language
const nextStudyDay=days=>{for(let k=1;k<=7;k++){const d=new Date(Date.now()+k*864e5);if(days[(d.getDay()+6)%7]==='1')return k===1?tl('tomorrow'):wd((d.getDay()+6)%7)}return ''}
function SessionCard({toast,onRoutine,openTopic,onStudy,refresh,onLoad}){  // today's one session, from the student's own routine
  const [v,setV]=useState(null),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/me/session').then(x=>{setV(x);onLoad?.(x)}).catch(()=>{})},[refresh])
  if(!v)return null
  if(!v.routine)return null  // a routine is the student's own idea: it lives under My routine, never pushed on Home
  const open=x=>x.kind==='review'?onStudy({review:x.course_id}):x.src==='study'?onStudy({id:x.course_id,topic:x.id}):openTopic(x.id)
  const extra=async()=>{setBusy(true);try{const x=await api('/me/session',{method:'POST'});setV(x);onLoad?.(x)}catch(e){toast(e.message)}setBusy(false)}
  const r=v.routine,ss=v.session,left=ss?.items.filter(x=>!x.done)||[]
  return <div className="hero session"><div className="shead"><small>{tl("Today's session · {minutes} min",{minutes:r.minutes})}{r.at?' · '+r.at:''}</small><button className="schip" onClick={onRoutine} aria-label={tl("Change my routine")}><Clock size={14}/>{" "}{tl("Routine")}</button></div>
    {v.missed>=2&&!v.studied_today&&<p style={{margin:'6px 0 0'}}>{tl("Welcome back. Today is just one session, the same as always. No catching up needed.")}</p>}
    {!ss&&<><h2 style={{fontSize:22}}>{tl("Rest day")}</h2><p>{tl("Your next session is {nextStudyDay}.",{nextStudyDay:nextStudyDay(r.days)})}</p><button className="btn inv" disabled={busy} onClick={extra}>{tl("Study anyway")}</button></>}
    {ss&&ss.caught_up&&<><h2 style={{fontSize:22}}>{tl("All caught up")}</h2><p>{tl("Nothing is left to study right now. Well done.")}</p></>}
    {ss&&!ss.caught_up&&<>{ss.done?<h2 style={{fontSize:22}}><Check size={22}/>{" "}{tl("Done for today")}</h2>:<h2 style={{fontSize:22}}>{left.length}{" "}{tl("of {length} to go",{length:ss.items.length})}</h2>}
      <ul className="sitems">{ss.items.map((x,i)=><li key={i}><button className={'sitem'+(x.done?' done':'')} onClick={()=>open(x)}><span className="sx">{x.done?<Check size={16}/>:x.kind==='review'?<RotateCcw size={16}/>:<Play size={16}/>}</span><span><b>{x.title}</b><small>{x.course}</small></span></button></li>)}</ul>
      {!ss.done&&<button className="btn inv" onClick={()=>open(left[0])}>{left.length===ss.items.length?tl("Start"):tl("Continue")}: {left[0].title}</button>}
      {ss.done&&<p>{tl("See you {nextStudyDay}.",{nextStudyDay:nextStudyDay(r.days)})}</p>}</>}
    <p className="splan">{v.plan.left?tl("{left} topics left · at this pace, done by {v}",{left:v.plan.left,v:new Date(v.plan.finish+'T00:00').toLocaleDateString(undefined,{day:'numeric',month:'short'})}):tl("Nothing left in your courses")}{v.plan.late>0?tl(" · {late} would miss their deadline. {v}",{late:v.plan.late,v:v.plan.advice||''}):''}</p></div>}
function RoutinePage({toast,done}){
  const confirm=useConfirm()
  const [v,setV]=useState(null),[f,setF]=useState({days:'1111110',minutes:30,at:''}),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/me/session').then(x=>{setV(x);if(x.routine)setF({days:x.routine.days,minutes:x.routine.minutes,at:x.routine.at||''})}).catch(e=>toast(e.message))},[])
  const flip=k=>setF({...f,days:f.days.slice(0,k)+(f.days[k]==='1'?'0':'1')+f.days.slice(k+1)})
  const save=async()=>{setBusy(true);try{setV(await api('/me/routine',{method:'PUT',body:{...f,at:f.at||null}}));toast(tl("Routine saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  const stop=async()=>{if(!await confirm({title:tl("Stop your routine?"),body:tl("Your progress stays. Home goes back to showing what to do next."),ok:tl("Stop the routine")}))return;try{await api('/me/routine/stop',{method:'POST'});toast(tl("Routine stopped"));done()}catch(e){toast(e.message)}}
  const per={15:1,30:1,45:2,60:3}[f.minutes]
  return <><Bar title={tl("My routine")} sub={tl("Study at your own pace, a little every day")}/><div className="main">
    <p className="known" style={{marginTop:0}}>{tl("Pick the days you study and how long. Each study day you get one session: {v} and any reviews that are due. Miss a day and nothing piles up: the next session is the same size.",{v:per===1?tl('one new topic'):tl('{n} new topics',{n:per})})}</p>
    <label>{tl("Study days")}</label><div className="chips wrap" role="group" aria-label={tl("Study days")}>{WD.map((d,k)=><button key={d} className={'sbtn'+(f.days[k]==='1'?' on':'')} aria-pressed={f.days[k]==='1'} onClick={()=>flip(k)}><span className="lbl">{wd(d)}</span></button>)}</div>
    <label htmlFor="mins">{tl("Minutes a session")}</label><select id="mins" value={f.minutes} onChange={e=>setF({...f,minutes:+e.target.value})}>{[15,30,45,60].map(m=><option key={m} value={m}>{m}{" "}{tl("minutes")}</option>)}</select>
    <label htmlFor="at">{tl("Usual time (optional)")}</label><input id="at" type="time" value={f.at} onChange={e=>setF({...f,at:e.target.value})}/>
    {v?.plan&&<p className="known">{v.plan.left?tl("With your current routine you would finish the {left} topics left by {v}.",{left:v.plan.left,v:new Date(v.plan.finish+'T00:00').toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'})}):tl("Nothing is left to study right now.")}{v.plan.late>0?tl(" {late} topics would miss their deadline. {v}",{late:v.plan.late,v:v.plan.advice||''}):''}</p>}
    <button className="btn" disabled={busy||!f.days.includes('1')} onClick={save}>{tl("Save routine")}</button>
    {v?.routine&&<button className="btn ghost" onClick={stop}>{tl("Stop the routine")}</button>}</div></>}
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
  return <><Bar title={tl("Search")} sub={tl("Find a topic, or ask the AI")}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={tl("Search topics")} autoFocus placeholder={tl("e.g. temporary hardness of water")} value={q} maxLength={200} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&submit()}/></div>
    <button className="btn" disabled={pend||aiBusy||typed.length<2} onClick={submit}>{pend?tl("Searching…"):tl("Search")}</button>
    {!asked&&live&&live.results.length>0&&<><h3 className="sec">{tl("Topics in your courses")}</h3><p className="known">{tl("Press Enter to search properly. If nothing here fits, the AI answers.")}</p>{live.results.slice(0,5).map(x=><Hit key={x.id} x={x} open={setTopic}/>)}</>}
    {!asked&&typed.length>=2&&live&&!live.results.length&&<p className="known">{tl("Nothing in your courses matches yet. Press Enter and the AI will answer instead.")}</p>}
    {res&&<>{res.results.length>0?<><h3 className="sec">{aiNote?tl("Possible matches in your courses"):tl("In your courses")}</h3>{<Paged rows={res.results} render={x=><Hit key={x.id} x={x} open={setTopic}/>}/>}</>
      :<p className="known" style={{marginTop:18}}>{tl("Nothing in your courses matches “{asked}”.",{asked:asked})}</p>}
      {!ai&&!aiBusy&&<button className="btn ghost" onClick={()=>askAi(asked,false)}><Sparkles size={16}/>{" "}{tl("Not what you wanted? Recheck with AI")}</button>}</>}
    {aiBusy&&<div className="qbox" aria-live="polite"><b>{tl("Asking the AI…")}</b><div className="sk"/></div>}
    {aiErr&&<div className="qbox" role="alert"><b>{tl("The AI could not answer")}</b><p className="known" style={{margin:'6px 0 0'}}>{aiErr}</p></div>}
    {ai&&!aiBusy&&<><h3 className="sec">{tl("AI answer")}</h3><div className="prose">{ai.cached&&<span className="chip">{tl("Saved answer · no tokens used")}</span>}<Md>{ai.text}</Md>{!ai.support&&<FlagLink source="search" id={ai.id} excerpt={ai.text}/>}</div>
      <p className="known">{tl("AI answers can contain mistakes. Check them against your notes and textbook.")}</p>
      <button className="btn ghost" disabled={aiBusy} onClick={()=>askAi(ai.for,true)}><Sparkles size={16}/>{" "}{tl("Not happy? Recheck with AI")}</button></>}</div></>}
function Hit({x,open}){return <button className="hitrow" onClick={()=>open(x.id)}><b>{x.title}{x.in_title&&<span className="chip" style={{marginLeft:8}}>{tl("Best match")}</span>}</b><small>{[x.program,x.semester,x.course,x.unit].filter(Boolean).join(' › ')}</small>{x.snippet&&<span className="snip">{x.snippet}</span>}</button>}

// My progress: a calm mirror, not a report card. What clicked and what is worth another look (from quizzes and tests, without percentages),
// the optional routine, test results folded away, and what the app has picked up about how they learn
function Insights({toast,role,onRoutine}){
  const [d,setD]=useState(null),[topic,setTopic]=useState(null),[sc,setSc]=useState(null)
  useEffect(()=>{if(!topic)api('/me/insights').then(setD).catch(e=>toast(e.message))},[topic])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(sc)return <ScoreCourse c={sc} back={()=>setSc(null)} toast={toast} role={role}/>
  const clicked=d?.strong||[],looks=d?[...d.needs_study,...d.getting_there]:[]
  const item=a=><button key={a.topic_id||'u'+a.unit_id} className="row rowbtn" disabled={!a.topic_id} onClick={()=>setTopic(a.topic_id)}><div>{a.title}<small>{a.course}</small></div>{a.topic_id&&<ChevronRight size={18}/>}</button>
  return <><Bar title={tl("My progress")}/><div className="main">
    {!d&&<Skeleton/>}
    {d&&!clicked.length&&!looks.length&&<p className="known">{tl("After you try a quiz or a test, the topics that clicked and the ones worth another look show up here.")}</p>}
    {clicked.length>0&&<><h3 className="sec first">{tl("What clicked")}</h3><Paged rows={clicked} render={item}/></>}
    {looks.length>0&&<><h3 className={'sec'+(clicked.length?'':' first')}>{tl("Worth another look")}</h3><Paged rows={looks} render={item}/></>}
    <h3 className="sec">{tl("Study routine")}</h3>
    <button className="row rowbtn" onClick={onRoutine}><div>{tl("Set or change your study days")}<small>{tl("Optional. Some people like a rhythm; nothing changes unless you set one.")}</small></div><ChevronRight size={18}/></button>
    <details className="fold"><summary>{tl("Test results")}</summary><MyScores onCourse={setSc}/></details>
    <AdaptCard toast={toast}/></div></>}
// what the app has picked up from how this student uses a topic's steps, in plain words, with a way to start fresh. Only they see it
function AdaptCard({toast}){
  const {appName}=useContext(Ctx),[d,setD]=useState(null),load=()=>api('/me/learning').then(setD).catch(()=>{});useEffect(()=>{load()},[])
  if(!d)return null
  const taps=Object.values(d.taps||{}).reduce((a,b)=>a+b,0),fav=taps>=3?STEP_LABEL(d.order[0]):null
  const lines=[fav&&tl("{step} comes first on a topic, since you reach for it most",{step:fav}),
    d.level==='hard'&&tl("Quick checks ask you to apply ideas, since you have been getting them"),d.level==='easy'&&tl("Quick checks are plainer for now, with a hint when it helps"),
    tl("After a few topics in a unit, a topic starts with its question and keeps the gist one tap away"),
    tl("Remember this? brings back topics you marked “Not quite”")].filter(Boolean)
  const reset=async()=>{try{await api('/me/learning/steps',{method:'DELETE'});toast(tl("Started fresh"));load()}catch(e){toast(e.message)}}
  return <><h3 className="sec">{tl("How {name} adapts to you",{name:appName})}</h3><div className="qbox"><ul className="adapt">{lines.map((x,i)=><li key={i}>{x}</li>)}</ul>
    <p className="known" style={{margin:'8px 0 0'}}>{tl("It learns only from the steps you open and your own “I had it” / “Not quite”. Your teachers never see this.")}</p>
    {(taps>0||d.checks>0)&&<button className="btn ghost" onClick={reset}>{tl("Start fresh")}</button>}</div></>}

const uploadImg=async f=>{const r=await fetch('/api/uploads',{method:'POST',headers:{'Content-Type':f.type||'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(tl(j.detail||'Upload failed'));return j.url}
// one image place on a question or an answer: shows the image, the file the CSV asked for, or a small "Add image" button
function ImgSlot({url,need,label,onSet,toast,small}){
  const ref=useRef(),[busy,setBusy]=useState(false)
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;setBusy(true);try{onSet(await uploadImg(f))}catch(x){toast(x.message)}setBusy(false)}
  const input=<input ref={ref} type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden onChange={pick}/>
  if(url)return <div className={'islot'+(small?' sm':'')}>{input}<img src={url} alt={label}/><span><button className="tool" onClick={()=>ref.current.click()}>{tl("Replace")}</button><button className="tool" onClick={()=>onSet('')}>{tl("Remove image")}</button></span></div>
  if(need)return <div className="islot need" role="status">{input}<AlertTriangle size={16}/><span>{tl("Needs")}{" "}<b>{need}</b></span><button className="tool" disabled={busy} onClick={()=>ref.current.click()}>{busy?tl("Uploading…"):tl("Upload")}</button><button className="tool" onClick={()=>onSet('',true)}>{tl("Skip")}</button></div>
  return <>{input}<button className="tool" disabled={busy} onClick={()=>ref.current.click()} aria-label={tl("Add image to {label}",{label:label})}>{busy?tl("Uploading…"):small?tl("Image"):tl("Add image")}</button></>}
const QImg=({src,alt})=>src?<img className="qimg" src={src} alt={alt} loading="lazy"/>:null
const OptBody=({text,img,k})=><span className="obody">{img&&<img src={img} alt={tl("Answer {k}",{k:LET[k]})}/>}{text?<Md>{text}</Md>:!img&&<span>—</span>}</span>
const LET='ABCDEF'
function QuizPlay({id,back,toast,role}){
  const [q,setQ]=useState(null),[ans,setAns]=useState([]),[res,setRes]=useState(null),[busy,setBusy]=useState(false),[topic,setTopic]=useState(null),[view,setView]=useState(null)
  const start=d=>{setQ(d);setAns(d.questions.map(()=>null));setRes(null)}
  useEffect(()=>{api('/quizzes/'+id).then(start).catch(e=>{toast(e.message);back()})},[id])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(view)return view.kind==='attempt'?<AttemptView id={view.id} back={()=>setView(null)} toast={toast} role={role}/>:view.kind==='mine'?<MyAttempts quiz={id} back={()=>setView(null)} toast={toast} role={role}/>:<QuizResults id={id} back={()=>setView(null)} toast={toast} role={role}/>
  if(!q)return <><Bar title={tl("Quiz")} back={back}/><div className="main"><Skeleton/></div></>
  const left=ans.filter(a=>a===null).length
  const submit=async()=>{setBusy(true);try{setRes(await api(`/quizzes/${id}/attempt`,{method:'POST',body:{answers:ans}}));window.scrollTo(0,0)}catch(e){toast(e.message)}setBusy(false)}
  return <><Bar title={q.title} sub={tl("{length} questions · pass mark {pass_percent}%{v}",{length:q.questions.length,pass_percent:q.pass_percent,v:q.kind==='course'?' · course test':''})} back={back}/><div className="main">
    {!res&&q.can_edit&&<button className="btn ghost" style={{marginTop:0}} onClick={()=>setView({kind:'results'})}><BarChart3 size={16}/>{" "}{tl("Results and scores")}</button>}
    {!res&&q.attempts>0&&<p className="known" style={{marginTop:0}}>{tl("You have tried this {n}. Best {best}% · latest {latest}%.",{n:pl(q.attempts,'time'),best:q.best,latest:q.latest})}{" "}<button className="tool" onClick={()=>setView({kind:'mine'})}>{tl("See your attempts")}</button></p>}
    {res&&<div className="qbox"><h2 style={{margin:0}}>{res.score} / {res.total} · {res.percent}%</h2><p className="known">{tl("Pass mark {pass}%.",{pass:res.pass_percent??q.pass_percent})}{res.summary&&' '+res.summary}</p>
      <div className="two"><button className="btn" onClick={()=>setView({kind:'attempt',id:res.attempt_id})}>{tl("Review answers")}</button><button className="btn ghost" onClick={()=>start(q)}>{tl("Try again")}</button></div><button className="btn ghost" onClick={back}>{tl("Back")}</button></div>}
    {res&&res.areas?.length>0&&<><h3 className="sec">{tl("What you are good at and what to revisit")}</h3><AreaList areas={res.areas} onStudy={setTopic}/></>}
    {q.questions.map((x,i)=><div className="qbox" key={x.id}><b>{tl("Question")}{" "}{i+1}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={tl("Picture for question {i}{v}",{i:i,v:1})}/>
      {x.options.map((o,k)=>{const r=res&&res.results[i],cls=r?(k===r.correct||(r.ok&&k===r.chosen)?' ok':k===r.chosen?' bad':''):ans[i]===k?' sel':''
        return <button key={k} className={'opt'+cls} disabled={!!res} aria-pressed={!res&&ans[i]===k} onClick={()=>setAns(ans.map((a,n)=>n===i?k:a))}><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/></button>})}
      {res&&res.results[i].explanation&&<div className="known"><Md>{res.results[i].explanation}</Md></div>}</div>)}
    {!res&&<button className="btn" disabled={busy} onClick={submit}>{busy?tl("Checking…"):tl("Submit answers")}</button>}
    {!res&&left>0&&<p className="known">{left}{" "}{tl("unanswered. Blank answers count as wrong.")}</p>}</div></>}
// one attempt, question by question
function AttemptView({id,back,toast,role}){
  const [d,setD]=useState(null),[topic,setTopic]=useState(null)
  useEffect(()=>{api('/attempts/'+id).then(setD).catch(e=>{toast(e.message);back()})},[id])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(!d)return <><Bar title={tl("Attempt")} back={back}/><div className="main"><Skeleton/></div></>
  const staff=role!=='student',right=d.questions.filter(x=>x.ok).length
  return <><Bar title={d.quiz} sub={(staff?d.user+' · ':'')+when(d.at)} back={back}/><div className="main">
    <div className="qbox" style={{marginTop:0}}><h2 style={{margin:0}}>{d.score} / {d.total} · {d.percent}%</h2><p className="known" style={{marginBottom:0}}>{tl("Pass mark {pass}%.",{pass:d.pass_percent})}{d.summary&&' '+d.summary}</p></div>
    {d.areas.length>0&&<><h3 className="sec">{staff?tl("Strengths and weak areas"):tl("What you are good at and what to revisit")}</h3><AreaList areas={d.areas} onStudy={staff?null:setTopic} staff={staff}/></>}
    {d.no_detail&&<p className="known">{tl("This attempt was made before answers were kept question by question, so only the score is known.")}</p>}
    {d.changed>0&&<p className="known">{pl(d.changed,'question')}{" "}{tl("of this attempt {v} changed or removed since, so {v2} not shown.",{v:d.changed===1?'was':'were',v2:d.changed===1?'it is':'they are'})}</p>}
    {!d.reveal&&d.questions.length>0&&<p className="known">{tl("You see which answers were right ({right} of {length}). This quiz does not show the correct answers.",{right:right,length:d.questions.length})}</p>}
    {d.questions.map((x,i)=><div className="qbox" key={x.id}><b>{tl("Question {v} ·",{v:i+1})}{" "}{x.ok?tl("Right"):tl("Wrong")}{x.area?' · '+x.area:''}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={tl("Picture for question {i}{v}",{i:i,v:1})}/>
      {x.options.map((o,k)=>{const mine=x.chosen_known&&x.chosen===k,key=d.reveal&&x.correct===k,cls=key||(mine&&x.ok)?' ok':mine?' bad':''
        return <div key={k} className={'opt'+cls}><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/>{(mine||key)&&<span className="otag">{[mine&&(staff?'Their answer':'Your answer'),key&&'Correct answer'].filter(Boolean).join(' · ')}</span>}</div>})}
      {x.chosen_known&&x.chosen==null&&<p className="known">{tl("Left blank.")}</p>}
      {x.explanation&&<div className="known"><Md>{x.explanation}</Md></div>}</div>)}</div></>}
function MyAttempts({quiz,user,back,toast,role}){  // a person's attempts at one quiz; staff pass user to see a student's
  const [d,setD]=useState(null),[open,setOpen]=useState(null)
  useEffect(()=>{api(`/quizzes/${quiz}/attempts`+(user?'?user_id='+user:'')).then(setD).catch(e=>{toast(e.message);back()})},[quiz,user])
  if(open)return <AttemptView id={open} back={()=>setOpen(null)} toast={toast} role={role}/>
  return <><Bar title={d?.quiz||tl("Attempts")} sub={d?(user?d.user+' · ':'')+pl(d.items.length,'attempt'):''} back={back}/><div className="main">
    {d&&!d.items.length&&<p className="known">{tl("No attempts yet.")}</p>}
    {<Paged rows={d?.items} render={(a,i)=><button key={a.id} className="row rowbtn" onClick={()=>setOpen(a.id)}><div>{a.score} / {a.total} · {a.percent}%<small>{when(a.at)}{a.passed?' · '+tl("reached the pass mark"):''}{i===0?tl(" · latest"):''}</small><Bar2 v={a.percent}/></div><ChevronRight size={18}/></button>}/>}</div></>}

const MCQ_TEMPLATE=`question,a,b,c,d,correct,explanation,topic,area,question_image,a_image,b_image,c_image,d_image
"Which ion makes water hard?",Na+,Ca2+,Cl-,K+,B,"Calcium and magnesium salts cause hardness.",Water Treatment,,,,,,
"Which boiler is shown in the picture?",Fire tube,Water tube,Electric,Packaged,A,,Boilers,,boiler.png,,,,
"Pick the symbol for a resistor",,,,,C,,,Circuit symbols,,sym-a.png,sym-b.png,sym-c.png,sym-d.png
"What is 15% of 200?",20,30,15,35,30,,,Arithmetic,,,,,
`
const CSV_COLS=[['question',tl("The question. Markdown and $math$ work.")],['a, b, c, d (up to f)','The answer choices. Leave the later ones blank if a question has fewer. A choice can be only an image.'],
  ['correct',tl("The right answer: its letter (B), its number (2) or its exact text.")],['explanation',tl("Optional. Shown after submitting when the test reveals answers.")],
  ['topic',tl("Optional. A topic title from this course; strengths are worked out per topic.")],['area',tl("Optional. A skill or area name for questions not tied to a topic.")],
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
    await api(`/quizzes/${qid}/questions`,{method:'PUT',body:{questions:payload()}});toast(course?tl("Test saved"):tl("Quiz saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  const readCsv=async(f,replace)=>{try{const r=await api('/quizzes/parse-csv',{method:'POST',body:{csv:await f.text(),...(course?{course_id:cid}:{unit_id})}});setCsv(r)
    if(!r.questions.length){toast(tl("No questions could be read from the file"));return}
    const got=r.questions.map(fromCsv);setQs(cur=>replace?got:[...cur.filter(x=>x.text.trim()||x.image),...got])
    if(replace&&!m.title)setM(v=>({...v,title:f.name.replace(/\.[^.]+$/,'').replace(/[_-]+/g,' ').slice(0,200)}))
    setStage('edit');toast(tl("{n} read. Check them below{v}, then save.",{n:pl(r.questions.length,'question'),v:r.images_needed.length?' and upload the images':''}))}catch(e){toast(e.message)}}
  const importCsv=async e=>{const f=e.target.files[0];e.target.value='';if(f)readCsv(f,stage==='csv')}
  const bulkImages=async e=>{const files=[...e.target.files];e.target.value='';if(!files.length)return;setBusy(true);let used=0;const extra=[];let next=qs
    for(const f of files){const hits=missing(next).filter(s=>s.name.toLowerCase()===f.name.toLowerCase());if(!hits.length){extra.push(f.name);continue}
      try{const url=await uploadImg(f);used++;next=next.map((x,i)=>{const h=hits.filter(s=>s.i===i);if(!h.length)return x
        return {...x,image:h.some(s=>s.k<0)?url:x.image,option_images:x.option_images.map((v,k)=>h.some(s=>s.k===k)?url:v),need:{image:h.some(s=>s.k<0)?'':x.need.image,options:x.need.options.map((n,k)=>h.some(s=>s.k===k)?'':n)}}})}catch(x){toast(f.name+': '+x.message)}}
    setQs(next);setBusy(false);toast(tl("{n} matched{v}",{n:pl(used,'image'),v:extra.length?`. Not in the CSV: ${extra.slice(0,3).join(', ')}${extra.length>3?'…':''}`:''}))}
  const addFromBank=picked=>{setQs(cur=>[...cur.filter(x=>x.text.trim()),...picked.map(x=>({...blankQ(),text:x.text,options:x.options,option_images:x.options.map(()=>''),correct:x.correct,explanation:x.explanation||''}))]);setBank(false);toast(tl("{n} added. Tie them to topics if you like, then save.",{n:pl(picked.length,'question')}))}
  const toBank=async()=>{const list=qs.filter(x=>x.text.trim());let added=0,skipped=0,bad=0;setBusy(true)
    for(const x of list){if(x.image||x.option_images.some(Boolean)){bad++;continue}try{await api('/bank',{method:'POST',body:{text:x.text,options:x.options,correct:x.correct,explanation:x.explanation,tags:btags,source:m.title}});added++}catch(e){/already in the bank/.test(e.message)?skipped++:bad++}}
    setBusy(false);toast(tl("{added} saved to the bank{v}{v2}",{added:added,v:skipped?`, ${skipped} already there`:'',v2:bad?`, ${bad} skipped (incomplete or with images)`:''}))}
  const del=async()=>{if(!await confirm({title:tl("Delete this {v}?",{v:course?'test':'quiz'}),body:tl("This also deletes every student attempt. This can't be undone."),ok:tl("Delete"),danger:true}))return;try{await api('/quizzes/'+id,{method:'DELETE'});toast(tl("Deleted"));done()}catch(e){toast(e.message)}}
  const fileInputs=<><input ref={csvRef} type="file" accept=".csv,text/csv,text/plain" hidden onChange={importCsv}/><input ref={imgRef} type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple hidden onChange={bulkImages}/></>
  const csvNotes=csv&&(csv.error_count>0||csv.warnings.length>0)&&<div className="qbox" role="alert">{csv.error_count>0&&<><b>{pl(csv.error_count,'row')}{" "}{tl("could not be read and {v} left out",{v:csv.error_count===1?'was':'were'})}</b>{csv.errors.slice(0,10).map((x,i)=><p className="known" style={{margin:'4px 0'}} key={i}>{tl("Row {row}:",{row:x.row})}{" "}{x.error}</p>)}{csv.error_count>10&&<p className="known">{tl("…and {v} more.",{v:csv.error_count-10})}</p>}</>}
    {csv.warnings.length>0&&<><b style={{display:'block',marginTop:csv.error_count?10:0}}>{tl("Worth a look")}</b>{csv.warnings.slice(0,8).map((w,i)=><p className="known" style={{margin:'4px 0'}} key={i}>{w}</p>)}{csv.warnings.length>8&&<p className="known">{tl("…and {v} more.",{v:csv.warnings.length-8})}</p>}</>}</div>
  if(stage==='csv')return <><Bar title={tl("New MCQ test")} sub={tl("Step 1 of 2 · attach the questions CSV")} back={done}/><div className="main">{fileInputs}
    <p className="known" style={{marginTop:0}}>{tl("A course test is built from a CSV file with one question per row. In the next step you check every question, upload any pictures for questions and answer choices, then save.")}</p>
    <button className="btn" onClick={()=>csvRef.current.click()}><Upload size={16}/>{" "}{tl("Choose the CSV file")}</button><button className="btn ghost" onClick={()=>download('mcq-template.csv',MCQ_TEMPLATE)}>{tl("Download the template")}</button>
    {csvNotes}
    <h3 className="sec">{tl("Columns")}</h3>{CSV_COLS.map(([c,h])=><div className="row" key={c}><div><code>{c}</code><small>{h}</small></div></div>)}
    <p className="known">{tl("The first row names the columns. Comma, semicolon and tab separated files all work. A course test holds up to 200 questions.")}</p></div></>
  return <><Bar title={id?(course?tl("Edit test"):tl("Edit quiz")):csvFirst?tl("New MCQ test"):tl("New quiz")} sub={csvFirst&&!id?tl("Step 2 of 2 · check, add images, save"):''} back={done}/><div className="main">{fileInputs}
    {csvNotes}
    {todo.length>0&&<div className="qbox need" role="status"><b>{pl(todo.length,'image')}{" "}{tl("still to upload")}</b><p className="known" style={{margin:'4px 0 8px'}}>{tl("Choose them all at once and they are matched to their questions by file name, or upload each one below.")}{" "}{[...new Set(todo.map(x=>x.name))].slice(0,6).join(', ')}{todo.length>6?'…':''}</p>
      <button className="btn" style={{margin:0}} disabled={busy} onClick={()=>imgRef.current.click()}><Upload size={16}/> {busy?tl("Uploading…"):tl("Upload images")}</button></div>}
    <label>{tl("Title")}</label><input value={m.title} onChange={e=>setM({...m,title:e.target.value})} placeholder={course?tl("e.g. Chemistry final MCQ"):tl("e.g. Water treatment check")}/>
    <label>{tl("Pass mark (%)")}</label><input type="number" min="1" max="100" value={m.pass_percent} onChange={e=>setM({...m,pass_percent:e.target.value})}/>
    <label className="chk"><input type="checkbox" checked={m.published} onChange={e=>setM({...m,published:e.target.checked})}/>{" "}{tl("Published (students can take it)")}</label>
    <label className="chk"><input type="checkbox" checked={m.reveal} onChange={e=>setM({...m,reveal:e.target.checked})}/>{" "}{tl("Show students the correct answers and explanations after they submit")}</label>
    {qs.map((x,i)=><div className="qbox" key={i}><b>{tl("Question")}{" "}{i+1}</b>
      <textarea placeholder={tl("Question (Markdown and $math$ work)")} value={x.text} onChange={e=>upd(i,{text:e.target.value})}/>
      <ImgSlot url={x.image} need={x.need.image} label={tl("question {i}{v}",{i:i,v:1})} toast={toast} onSet={(v,skip)=>setQImg(i,v,skip)}/>
      {x.options.map((o,k)=><div key={k}><div className="qopt"><input type="radio" name={'c'+i} aria-label={tl("Answer {k} is correct",{k:LET[k]})} checked={x.correct===k} onChange={()=>upd(i,{correct:k})}/><b className="olet">{LET[k]}</b><input value={o} placeholder={tl("Answer {k}{v}",{k:LET[k],v:x.option_images[k]?' (optional with an image)':''})} onChange={e=>setOpt(i,k,e.target.value)}/>
        {!x.option_images[k]&&!x.need.options[k]&&<ImgSlot small label={tl("answer {k}",{k:LET[k]})} toast={toast} onSet={v=>setOptImg(i,k,v)}/>}{x.options.length>2&&<button className="ic sm" aria-label={tl("Remove answer {k}",{k:LET[k]})} onClick={()=>delOpt(i,k)}><X size={16}/></button>}</div>
        {(x.option_images[k]||x.need.options[k])&&<div style={{paddingLeft:48}}><ImgSlot small url={x.option_images[k]} need={x.need.options[k]} label={tl("answer {k}",{k:LET[k]})} toast={toast} onSet={(v,skip)=>setOptImg(i,k,v,skip)}/></div>}</div>)}
      {x.options.length<6&&<button className="tool" onClick={()=>upd(i,{options:[...x.options,''],option_images:[...x.option_images,'']})}>{tl("Add answer")}</button>}
      <label>{tl("Topic this tests")}</label><select value={x.topic_id??''} onChange={e=>upd(i,{topic_id:e.target.value?+e.target.value:null})}><option value="">{tl("Not tied to one topic")}</option>{topics.map(t=><option key={t.id} value={t.id}>{t.unit?t.unit+' › ':''}{t.title}</option>)}</select>
      {x.topic_id==null&&<><label>{tl("Area or skill")}</label><input value={x.area} onChange={e=>upd(i,{area:e.target.value})} placeholder={tl("e.g. Arithmetic (used for strengths when there is no topic)")}/></>}
      <textarea placeholder={tl("Explanation shown after submitting (optional)")} value={x.explanation} onChange={e=>upd(i,{explanation:e.target.value})}/>
      {qs.length>1&&<button className="tool" onClick={()=>setQs(qs.filter((_,n)=>n!==i))}>{tl("Remove question")}</button>}</div>)}
    <p className="known">{tl("Tick the radio button beside the correct answer. Tie each question to the topic it tests, or name an area: students then see what they are good at and what needs another round of study.")}</p>
    <button className="btn ghost" onClick={()=>setQs([...qs,blankQ()])}>{tl("Add question")}</button>
    <div className="two"><button className="btn ghost" onClick={()=>csvRef.current.click()}><Upload size={16}/>{" "}{tl("Add from a CSV")}</button><button className="btn ghost" onClick={()=>download('mcq-template.csv',MCQ_TEMPLATE)}>{tl("CSV template")}</button></div>
    <button className="btn ghost" onClick={()=>setBank(true)}>{tl("Add from the question bank")}</button>
    <label htmlFor="bt">{tl("Share these questions in the bank")}</label><div className="two"><input id="bt" value={btags} onChange={e=>setBtags(e.target.value)} placeholder={tl("Tags, e.g. water, hardness (optional)")}/><button className="btn ghost" disabled={busy||!qs.some(x=>x.text.trim())} onClick={toBank}>{tl("Save to bank")}</button></div>
    <button className="btn" disabled={busy||todo.length>0} onClick={save}>{busy?tl("Saving…"):todo.length?tl("Upload {n} first",{n:pl(todo.length,'image')}):id?tl("Save changes"):course?tl("Create test"):tl("Save quiz")}</button>{bank&&<BankSheet close={()=>setBank(false)} onAdd={addFromBank} toast={toast}/>}
    {id&&<button className="btn danger" onClick={del}>{tl("Delete")}{" "}{course?'test':'quiz'}</button>}</div></>}

// score spread: one series, so one hue and no legend; every bar has its count as text and a tooltip
const Spread=({rows,pass})=>{const top=Math.max(1,...rows.map(r=>r.count))
  return <figure className="spread" aria-label={tl("How many students scored in each band")}><div className="sbars">{rows.map((r,i)=><div key={r.label} className="sbar" title={`${r.label}%: ${pl(r.count,'student')}`}><em>{r.count||''}</em><i style={{height:r.count?Math.max(4,100*r.count/top)+'%':0}} className={i*10+9<pass?'below':''}/></div>)}</div>
    <div className="saxis">{rows.map(r=><span key={r.label}>{r.label.split('–')[0]}</span>)}</div><figcaption>{tl("Final score in bands of 10%. Lighter bars are below the {pass}% pass mark.",{pass:pass})}</figcaption></figure>}
const PassPill=({ok})=><span className={'pill sm '+(ok?'okp':'off')}>{ok?tl("Passed"):tl("Not yet")}</span>
function QuizResults({id,back,toast,role}){
  const [d,setD]=useState(null),[tab,setTab]=useState('overview'),[who,setWho]=useState(null),[sort,setSort]=useState('order')
  useEffect(()=>{api(`/quizzes/${id}/results`).then(setD).catch(e=>{toast(e.message);back()})},[id])
  if(who)return <MyAttempts quiz={id} user={who} back={()=>setWho(null)} toast={toast} role={role}/>
  if(!d)return <><Bar title={tl("Results")} back={back}/><div className="main"><Skeleton/></div></>
  const sm=d.summary,qs=sort==='hard'?[...d.questions].sort((a,b)=>(a.percent??101)-(b.percent??101)):d.questions
  return <><Bar title={d.title} sub={tl("Results · {took} of {students} students took it",{took:sm.took,students:sm.students})} back={back}/><div className="main">
    <Tabs scroll label={tl("Result sections")} items={[['overview',tl("Overview")],['students',tl("Students")],['questions',tl("Questions")],['areas',tl("Strengths")]]} value={tab} onChange={setTab}/>
    {tab==='overview'&&<>{!sm.took?<p className="known">{tl("Nobody has taken it yet.")}{d.published?'':tl(" It is still a draft, so students cannot see it.")}</p>:<>
      <div className="stats">{[['Average final score',sm.average+'%'],['Pass rate',sm.pass_rate+'%',`${sm.passed} of ${sm.took} passed`],['Median',sm.median+'%'],['Highest · lowest',sm.highest+'% · '+sm.lowest+'%'],
        ['Took it',sm.took+' / '+sm.students,sm.not_taken?tl("{not_taken} not yet",{not_taken:sm.not_taken}):tl('everyone')],['Attempts',sm.attempts,tl("latest average {average_latest}%",{average_latest:sm.average_latest})]].map(([l,v,x])=><div className="stat" key={l}><b>{v}</b>{l}{x&&<small style={{display:'block',color:'var(--mut)'}}>{x}</small>}</div>)}</div>
      <h3 className="sec">{tl("Spread of final scores")}</h3><Spread rows={sm.distribution} pass={d.pass_percent}/>
      <p className="known">{tl("The final score is each student's best attempt. Strengths and the question analysis use each student's latest attempt, so a retake replaces the earlier result.")}</p></>}
      {d.not_taken.length>0&&<><h3 className="sec">{tl("Not taken yet ({not_taken})",{not_taken:sm.not_taken})}</h3><p className="known" style={{margin:0}}>{d.not_taken.map(x=>x.name).join(', ')}{sm.not_taken>d.not_taken.length?'…':''}</p></>}
      <button className="btn ghost" onClick={()=>fetchFile(`/quizzes/${id}/results?format=csv`,'results-'+d.title.replace(/\s+/g,'_')+'.csv',toast)}>{tl("Download results CSV")}</button></>}
    {tab==='students'&&<>{!d.students.length&&<p className="known">{tl("No results yet.")}</p>}
      {<Paged rows={d.students} render={x=><button key={x.user_id} className="row rowbtn" onClick={()=>setWho(x.user_id)}><div>{x.name}<PassPill ok={x.passed}/><small>{tl("Final {best}% · latest {latest}% · {n} ·",{best:x.best,latest:x.latest,n:pl(x.attempts,'attempt')})}{" "}{day(x.last_at)}</small>
        {(x.strong.length>0||x.needs_study.length>0)&&<small>{x.strong.length>0&&tl("Good at: {strong}",{strong:x.strong.join(', ')})}{x.strong.length>0&&x.needs_study.length>0&&' · '}{x.needs_study.length>0&&tl("Revisit: {needs_study}",{needs_study:x.needs_study.join(', ')})}</small>}<Bar2 v={x.best}/></div><ChevronRight size={18}/></button>}/>}</>}
    {tab==='questions'&&<><div className="seg" style={{gridTemplateColumns:'1fr 1fr',margin:'0 0 12px'}}>{[['order',tl("In test order")],['hard',tl("Hardest first")]].map(([k,l])=><button key={k} className={sort===k?'on':''} aria-pressed={sort===k} onClick={()=>setSort(k)}>{l}</button>)}</div>
      {qs.map(x=>{const n=x.picks.reduce((a,b)=>a+b,0)+x.blank
        return <div className="qbox" key={x.id}><b>{tl("Question {pos} ·",{pos:x.pos})}{" "}{x.percent==null?tl("no answers yet"):tl("{percent}% right",{percent:x.percent})}{x.area?' · '+x.area:''}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={tl("Picture for question {pos}",{pos:x.pos})}/>
          {x.options.map((o,k)=>{const c=x.picks[k],pc=n?Math.round(100*c/n):0
            return <div key={k} className="pick" title={`${LET[k]}: ${pl(c,'student')}`}><div className="pickh"><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/>{k===x.correct&&<span className="otag ok"><Check size={14}/>{" "}{tl("Correct")}</span>}<span className="pickn">{c} · {pc}%</span></div><div className="meter"><i style={{width:pc+'%'}} className={k===x.correct?'ok':''}/></div></div>})}
          {x.picks_known>0&&x.blank>0&&<p className="known" style={{margin:'6px 0 0'}}>{tl("Left blank:")}{" "}{x.blank}</p>}
          {x.total>x.picks_known&&<p className="known" style={{margin:'6px 0 0'}}>{x.total-x.picks_known}{" "}{tl("older {v} not record which answer was picked.",{v:x.total-x.picks_known===1?'attempt does':'attempts do'})}</p>}</div>})}</>}
    {tab==='areas'&&<>{!d.areas.length?<p className="known">{tl("No results yet.")}</p>:<><p className="known" style={{marginTop:0}}>{tl("Weakest first, from each student's latest attempt.")}</p>
      {<Paged rows={d.areas} render={a=><div className="row" key={a.title+(a.topic_id||'')}><div>{a.title}<small>{a.percent}{tl("% right · {strong} strong · {getting_there} getting there · {needs_study} need another round",{strong:a.strong,getting_there:a.getting_there,needs_study:a.needs_study})}{a.unit?' · '+a.unit:''}</small><Bar2 v={a.percent}/></div></div>}/>}</>}</>}</div></>}
function Gradebook({cid,back,toast,role}){
  const [d,setD]=useState(null),[open,setOpen]=useState(null),[stu,setStu]=useState(null),gb=useLocalPage(d?.students,[d]),top=useRef()
  useEffect(()=>{api(`/courses/${cid}/gradebook`).then(setD).catch(e=>{toast(e.message);back()})},[cid])
  if(open)return <QuizResults id={open} back={()=>setOpen(null)} toast={toast} role={role}/>
  if(stu)return stu.quiz?<MyAttempts quiz={stu.quiz} user={stu.id} back={()=>setStu({...stu,quiz:null})} toast={toast} role={role}/>
    :<><Bar title={stu.name} sub={tl("{course} · final {v}",{course:d.course,v:stu.final==null?'–':stu.final+'%'})} back={()=>setStu(null)}/><div className="main">{<Paged rows={d.tests} render={(t,i)=><button key={t.id} className="row rowbtn" disabled={stu.scores[i]==null} onClick={()=>setStu({...stu,quiz:t.id})}><div>{t.title}{stu.scores[i]!=null&&<PassPill ok={stu.scores[i]>=t.pass_percent}/>}<small>{t.unit||tl("Course test")}{" "}{tl("· {v} · pass {pass_percent}%",{v:stu.scores[i]==null?'not taken':'final '+stu.scores[i]+'%',pass_percent:t.pass_percent})}</small>{stu.scores[i]!=null&&<Bar2 v={stu.scores[i]}/>}</div>{stu.scores[i]!=null&&<ChevronRight size={18}/>}</button>}/>}</div></>
  if(!d)return <><Bar title={tl("Gradebook")} back={back}/><div className="main"><Skeleton/></div></>
  return <><Bar title={tl("Gradebook")} sub={d.course+' · '+pl(d.tests.length,'test')} back={back}/><div className="main">
    {!d.tests.length?<p className="known">{tl("No published tests or quizzes in this course yet.")}</p>:<>
    <p className="known" style={{marginTop:0}}>{tl("Each cell is a student's final (best) score. The final course score is the average of the tests they took. Tap a student or a test to drill down.")}</p>
    <div className="gbwrap pgtop" ref={top}><table className="gb"><thead><tr><th>{tl("Student")}</th>{d.tests.map(t=><th key={t.id}><button className="tool" onClick={()=>setOpen(t.id)} title={t.unit||tl("Course test")}>{t.title}</button><small>{tl("avg {v}%",{v:t.average??'–'})}</small></th>)}<th>{tl("Final")}</th></tr></thead>
      <tbody>{gb.items.map(r=><tr key={r.user_id}><td><button className="tool" onClick={()=>setStu(r)}>{r.name}</button></td>{r.scores.map((v,i)=><td key={i} className={v==null?'na':v>=d.tests[i].pass_percent?'':'low'}>{v==null?'–':v+'%'}</td>)}<td><b>{r.final==null?'–':r.final+'%'}</b><small>{r.taken}/{d.tests.length}</small></td></tr>)}</tbody></table></div>
    <Pager page={gb.page} total={gb.total} onPage={gb.setPage} anchor={top}/>
    <p className="known">{tl("A dash means not taken. Scores below a test's pass mark are marked with a lighter background.")}</p>
    <button className="btn ghost" onClick={()=>fetchFile(`/courses/${cid}/gradebook?format=csv`,'gradebook-'+d.course.replace(/\s+/g,'_')+'.csv',toast)}>{tl("Download gradebook CSV")}</button></>}</div></>}
function ScoreCourse({c,back,toast,role}){  // one course of a student's scores: each test, then its attempts
  const [q,setQ]=useState(null)
  if(q)return <MyAttempts quiz={q} back={()=>setQ(null)} toast={toast} role={role}/>
  return <><Bar title={c.course} sub={tl("Final score {v} · {taken} of {length} taken",{v:c.final==null?'–':c.final+'%',taken:c.taken,length:c.tests.length})} back={back}/><div className="main">
    {<Paged rows={c.tests} render={t=><button key={t.id} className="row rowbtn" disabled={!t.attempts} onClick={()=>setQ(t.id)}><div>{t.title}{t.attempts>0&&t.passed&&<PassPill ok/>}<small>{t.unit||tl("Course test")}{" "}{tl("· {v} · pass {pass_percent}%",{v:t.attempts?`best ${t.best}% · latest ${t.latest}% · ${pl(t.attempts,'attempt')}`:'not taken yet',pass_percent:t.pass_percent})}</small>{t.attempts>0&&<Bar2 v={t.best}/>}</div>{t.attempts>0&&<ChevronRight size={18}/>}</button>}/>}
    <p className="known">{tl("Your final score in a test is your best attempt. The course score is the average of the tests you have taken.")}</p></div></>}
function MyScores({onCourse}){  // a student's final score per course
  const [d,setD]=useState(null)
  useEffect(()=>{api('/me/scores').then(setD).catch(()=>setD({courses:[]}))},[])
  if(!d)return null
  if(!d.courses.length)return <p className="known">{tl("No test results yet.")}</p>
  return <><h3 className="sec first">{tl("Scores")}</h3>{<Paged rows={d.courses} render={x=><button key={x.course_id} className="row rowbtn" onClick={()=>onCourse(x)}><div>{x.course}<small>{x.final==null?tl("No tests taken yet"):tl("Final score {final}%",{final:x.final})}{" "}{tl("· {taken} of {length} taken · {passed} passed",{taken:x.taken,length:x.tests.length,passed:x.passed})}</small>{x.final!=null&&<Bar2 v={x.final}/>}</div><ChevronRight size={18}/></button>}/>}</>}
// ---- courses students build from their own material ----
const STAR_HELP='★ topic completed · ★★ quiz passed · ★★★ mastered (90%+ in a quiz)'
// the next step in a course the student built, and topics ready to look at again: no streaks, points or levels
function LearnCard({me,onContinue,onReview}){
  if(!me)return null
  return <div className="learn">
    {me.next&&<button className="btn" onClick={()=>onContinue(me.next)}><Play size={16}/> {me.next.done?tl("Continue"):tl("Start")}: {me.next.topic}<small className="sub">{me.next.course}</small></button>}
    {me.reviews_due>0&&<button className="btn ghost" onClick={()=>onReview(me.review_courses[0].course_id)}><RotateCcw size={16}/>{" "}{tl("Look again at {n}",{n:pl(me.reviews_due,'topic')})}</button>}</div>}
const STEPS=['Name','Material','Slice','Preview'],AREA_LABEL={strong:'Strong',getting_there:'Getting there',needs_study:'Revisit'}
const Steps=({at})=><ol className="steps" aria-label={tl("Setup steps")}>{STEPS.map((s,i)=><li key={s} className={i<at?'done':i===at?'on':''} aria-current={i===at?'step':undefined}><span>{i<at?<Check size={14}/>:i+1}</span>{s}</li>)}</ol>
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
    <div>{c.title}{c.status!=='ready'&&<span className="pill sm" style={{marginLeft:6}}>{tl("Setup not finished")}</span>}{c.mine&&c.share==='program'&&<span className="pill sm okp" style={{marginLeft:6}}>{tl("Shared")}</span>}
      <small>{c.status==='ready'?tl("{completed} of {topics} topics completed",{completed:c.completed,topics:c.topics}):tl("Continue the setup")}{!c.mine?tl(" · by {owner}",{owner:c.owner}):''}</small>{c.status==='ready'&&c.topics>0&&<Bar2 v={100*c.completed/c.topics}/>}</div><ChevronRight size={18}/></button>
  return <><Bar title={tl("Build a course")} sub={tl("Turn your own notes into a course")}/><div className="main">
    {me&&me.courses>0&&<LearnCard me={me} onContinue={n=>setOpen({id:n.course_id,topic:n.topic_id})} onReview={review}/>}
    <p className="known" style={{marginTop:me&&me.courses>0?16:0}}>{tl("Upload your notes, textbook chapters or handouts. The AI slices them into units and small topics, you check and adjust the outline, and then you study it with explanations, practice MCQs and quizzes.")}</p>
    <button className="btn lead" onClick={()=>setMake(true)}><Upload size={16}/>{" "}{tl("New course from my material")}</button>
    {!d?<Skeleton/>:<>{d.mine.length>0&&<><h3 className="sec">{tl("My courses")}</h3>{<Paged rows={d.mine} render={card}/>}</>}
      {d.shared.length>0&&<><h3 className="sec">{tl("Shared by classmates")}</h3>{<Paged rows={d.shared} render={card}/>}</>}
      {!d.mine.length&&!d.shared.length&&<p className="known">{tl("You have not built a course yet.")}</p>}</>}
    {make&&<Sheet close={()=>setMake(false)}><h3>{tl("New course")}</h3><label htmlFor="sct">{tl("Course name")}</label><input id="sct" autoFocus value={title} onChange={e=>setTitle(e.target.value)} onKeyDown={e=>e.key==='Enter'&&title.trim()&&create()} placeholder={tl("e.g. Islamic Education · Unit 4")}/>
      <button className="btn" disabled={busy||!title.trim()} onClick={create}>{tl("Next: add material")}</button><button className="btn ghost" onClick={()=>setMake(false)}>{tl("Cancel")}</button></Sheet>}</div></>}
function StudyWizard({id,toast,back,done}){
  const confirm=useConfirm()
  const [c,setC]=useState(null),[step,setStep]=useState(null),[text,setText]=useState(''),[busy,setBusy]=useState(''),[notes,setNotes]=useState(''),[plan,setPlan]=useState(null),[dirty,setDirty]=useState(false),[peek,setPeek]=useState(null),fileRef=useRef()
  const load=async(go)=>{try{const d=await api('/study/courses/'+id);setC(d);setNotes(d.notes);setPlan(d.plan);setDirty(false);setStep(go??(d.plan?3:d.sources.length?2:1));return d}catch(e){toast(e.message);back()}}
  useEffect(()=>{load()},[id]);usePoll(!!c?.reading,()=>api('/study/courses/'+id).then(d=>setC(d)).catch(()=>{}))  // only the file list refreshes; the step and outline stay
  if(!c||step==null)return <><Bar title={tl("Set up your course")} back={back}/><div className="main"><Skeleton/></div></>
  const files=async e=>{const fs=[...e.target.files];e.target.value='';for(const f of fs){if(tooBig(f)){toast(tl("{name} is over {MAX_FILE_MB} MB. Split it into smaller files.",{name:f.name,MAX_FILE_MB:MAX_FILE_MB}));continue}setBusy(tl("Reading {name}…",{name:f.name}))
      try{const r=await fetch(`/api/study/courses/${id}/files?name=${encodeURIComponent(f.name)}`,{method:'POST',headers:{'Content-Type':'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(tl(j.detail||'Upload failed'));toast(j.status==='reading'?tl("{name} is scanned pages. Reading them now…",{name:f.name}):tl("{name}: {n} read",{name:f.name,n:pl(j.words,'word')}))}catch(x){toast(f.name+': '+x.message)}}
    setBusy('');load(1)}
  const paste=async()=>{setBusy('Adding…');try{const r=await api(`/study/courses/${id}/text`,{method:'POST',body:{text}});setText('');toast(tl("{n} added",{n:pl(r.words,'word')}))}catch(e){toast(e.message)}setBusy('');load(1)}
  const dropSrc=async i=>{if(!await confirm({title:tl("Remove this material?"),body:tl("Its text is taken out of the course. Any outline already made is cleared."),ok:tl("Remove"),danger:true}))return;try{await api(`/study/courses/${id}/sources/${i}`,{method:'DELETE'});load(1)}catch(e){toast(e.message)}}
  const slice=async method=>{if(dirty&&!await confirm({title:tl("Slice again?"),body:tl("Your renames, merges and removals in the current outline are replaced."),ok:tl("Slice again")}))return
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
        setBusy('');if(!await confirm({title:tl("Replace the course's topics?"),body:tl("Finishing again builds the topics from this outline. Progress and quiz results on the old topics are removed."),ok:tl("Replace topics"),danger:true}))return
        setBusy('Building your course…');await api(`/study/courses/${id}/finish`,{method:'POST',body:{replace:true}})}
      toast(tl("Your course is ready"));done()}catch(e){toast(e.message)}setBusy('')}
  const words=c.sources.reduce((a,x)=>a+x.words,0)
  return <><Bar title={c.title} sub={tl("Set up · step {step}{v} of 4",{step:step,v:1})} back={back}/><div className="main">
    <Steps at={step}/>
    {busy&&<div className="qbox" role="status" style={{marginTop:0}}><b>{busy}</b></div>}
    {step===1&&<>
      <h3 className="sec first">{tl("Add your material")}</h3><p className="known" style={{marginTop:0}}>{tl("PDF, Word (.docx), or .txt and .md files, up to {MAX_FILE_MB} MB each. Add several and they are joined in the order you add them. You can also paste text.",{MAX_FILE_MB:MAX_FILE_MB})}{c.ocr_available?tl(" Scanned PDFs are read with text recognition, a few seconds a page."):tl(" Scanned PDFs can't be read on this server yet.")}</p>
      <input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown" onChange={files}/>
      <button className="btn" disabled={!!busy} onClick={()=>fileRef.current.click()}><Upload size={16}/>{" "}{tl("Choose files")}</button>
      <label htmlFor="pst">{tl("Or paste text")}</label><textarea id="pst" value={text} onChange={e=>setText(e.target.value)} placeholder={tl("Paste notes here. Leave an empty line between paragraphs; lines starting with # become headings.")}/>
      <button className="btn ghost" disabled={!!busy||!text.trim()} onClick={paste}>{tl("Add this text")}</button>
      {c.sources.length>0&&<><h3 className="sec">{tl("Your material ·")}{" "}{pl(words,'word')}</h3>{c.sources.map((x,i)=><div className="row" key={i}><div>{x.name}<small role={x.status==='reading'?'status':undefined}>{x.status?srcLine(x):<>{x.kind.toUpperCase()} · {pl(x.words,'word')} · {pl(x.paras,'paragraph')}</>}</small></div><div className="acts"><button className="ic sm" aria-label={tl("Remove {name}",{name:x.name})} onClick={()=>dropSrc(i)}><Trash2 size={16}/></button></div></div>)}
        <button className="btn" disabled={!!c.reading} onClick={()=>setStep(2)}>{c.reading?tl("Reading scanned pages…"):tl("Next: slice it into topics")}</button></>}</>}
    {step===2&&<>
      <h3 className="sec first">{tl("How should it be sliced?")}</h3><p className="known" style={{marginTop:0}}>{tl("The AI groups your {n} into units and the smallest topics that make sense on their own. It keeps your own words; it only decides where each topic starts and ends and what to call it.",{n:pl(c.paragraphs,'paragraph')})}</p>
      <label htmlFor="nts">{tl("Notes for the AI")}</label><textarea id="nts" value={notes} onChange={e=>setNotes(e.target.value)} placeholder={NOTES_HINT}/>
      <AiNote o={c}/>
      <button className={'btn'+(c.ai_available&&c.ai_left!==0?'':' ghost')} disabled={!!busy||!c.ai_available||c.ai_left===0} onClick={()=>slice('ai')}><Sparkles size={16}/>{" "}{tl("Slice with AI")}</button>
      <button className={'btn'+(c.ai_available&&c.ai_left!==0?' ghost':'')} disabled={!!busy} onClick={()=>slice('headings')}>{tl("Slice by headings instead (no AI)")}</button>
      <button className="btn ghost" onClick={()=>setStep(1)}>{tl("Back to material")}</button></>}
    {step===3&&plan&&<>
      <h3 className="sec first">{tl("Check the outline")}</h3><p className="known" style={{marginTop:0}}>{pl(plan.units.length,'unit')}{tl(", {n}{v}. Rename anything, merge a topic into the next one, or remove one you don't need. Not right? Change the notes and slice again.",{n:pl(flat.length,'topic'),v:c.sliced_by==='headings'?' · sliced by headings':''})}</p>
      {plan.units.map((u,ui)=><section key={ui} className="qbox"><label className="sr" htmlFor={'u'+ui}>{tl("Unit {v} title",{v:ui+1})}</label><input id={'u'+ui} className="utitle" value={u.title} onChange={e=>rename(ui,null,e.target.value)}/>
        {u.topics.map((t,ti)=>{const last=ui===plan.units.length-1&&ti===u.topics.length-1
          return <div key={t.from} className="ptopic"><label className="sr" htmlFor={`t${ui}-${ti}`}>{tl("Topic title")}</label><input id={`t${ui}-${ti}`} value={t.title} onChange={e=>rename(ui,ti,e.target.value)}/>
            <small className="known">{t.summary?t.summary+' · ':''}{pl(t.words||0,'word')}</small><p className="excerpt">{t.excerpt}{t.excerpt&&t.excerpt.length>=280?'…':''}</p>
            <div className="acts"><button className="tool" onClick={async()=>{try{setPeek({title:t.title,...(await api(`/study/courses/${id}/preview?start=${t.from}&end=${t.to}`))})}catch(e){toast(e.message)}}}>{tl("Read it all")}</button>
              {!last&&<button className="tool" onClick={()=>merge(ui,ti)}>{tl("Merge with next")}</button>}{flat.length>1&&<button className="tool" onClick={()=>remove(ui,ti)}>{tl("Remove")}</button>}</div></div>})}</section>)}
      <h3 className="sec">{tl("Slice it differently")}</h3><label htmlFor="nts2">{tl("Notes for the AI")}</label><textarea id="nts2" value={notes} onChange={e=>setNotes(e.target.value)} placeholder={NOTES_HINT}/>
      <div className="two"><button className="btn ghost" disabled={!!busy} onClick={()=>slice('ai')}><Sparkles size={16}/>{" "}{tl("Slice again with AI")}</button><button className="btn ghost" disabled={!!busy} onClick={()=>setStep(1)}>{tl("Change material")}</button></div>
      <button className="btn" disabled={!!busy} onClick={finish}><Check size={16}/>{" "}{tl("Finish: build my course")}</button>
      {dirty&&<button className="btn ghost" disabled={!!busy} onClick={async()=>{try{await savePlan();toast(tl("Outline saved"))}catch(e){toast(e.message)}}}>{tl("Save outline and finish later")}</button>}</>}
    {peek&&<Sheet close={()=>setPeek(null)}><h3>{peek.title}</h3><div className="prose"><Md>{peek.content}</Md></div><button className="btn ghost" onClick={()=>setPeek(null)}>{tl("Close")}</button></Sheet>}</div></>}
function StudyCourse({id,topic:first,toast,back,setup}){
  const confirm=useConfirm()
  const [c,setC]=useState(null),[p,setP]=useState(null),[topic,setTopic]=useState(first||null),[ren,setRen]=useState(null),[rev,setRev]=useState(null),[find,setFind]=useState('')
  const load=()=>{api('/study/courses/'+id).then(setC).catch(e=>{toast(e.message);back()});api(`/study/courses/${id}/progress`).then(setP).catch(()=>{})}
  useEffect(()=>{if(!topic&&!rev)load()},[id,topic,rev])
  if(rev)return <StudyQuizPlay quiz={rev} toast={toast} back={()=>setRev(null)}/>
  if(topic)return <StudyTopicPage id={topic} toast={toast} back={()=>setTopic(null)} go={setTopic}/>
  if(!c)return <><Bar title={tl("Course")} back={back}/><div className="main"><Skeleton/></div></>
  if(c.status!=='ready')return <><Bar title={c.title} back={back}/><div className="main"><p className="known">{tl("This course is being set up.")}</p>{c.can_edit&&<button className="btn" onClick={setup}>{tl("Continue the setup")}</button>}</div></>
  const all=c.units.flatMap(u=>u.topics),done=all.filter(t=>t.status==='completed').length
  const share=async v=>{try{await api('/study/courses/'+id,{method:'PUT',body:{share:v}});toast(v==='program'?tl("Classmates in your program can now study it"):tl("Only you can see it now"));load()}catch(e){toast(e.message)}}
  const del=async()=>{if(!await confirm({title:tl("Delete “{title}”?",{title:c.title}),body:tl("Its topics, your progress and your quiz results are removed. This can't be undone."),ok:tl("Delete course"),danger:true}))return;try{await api('/study/courses/'+id,{method:'DELETE'});toast(tl("Course deleted"));back()}catch(e){toast(e.message)}}
  const reopen=async()=>{if(!await confirm({title:tl("Change the setup?"),body:tl("You go back to the outline. Your topics stay as they are until you finish the setup again."),ok:tl("Change the setup")}))return;try{await api(`/study/courses/${id}/reopen`,{method:'POST'});setup()}catch(e){toast(e.message)}}
  const next=all.find(t=>t.status!=='completed')
  return <><Bar title={c.title} sub={c.mine?tl("Your course"):tl("Shared by {owner}",{owner:c.owner})} back={back}/><div className="main">
    <div className="qbox" style={{marginTop:0}}><p className="known" style={{margin:0}}>{pl(all.length,'topic')}</p>
      {c.reviews_due>0&&<button className="btn ghost" onClick={async()=>{try{setRev(await api(`/study/courses/${id}/review`,{method:'POST'}))}catch(e){toast(e.message)}}}><RotateCcw size={16}/>{" "}{tl("Look again at {n}",{n:pl(c.reviews_due,'topic')})}</button>}
      {p&&p.quizzed>0&&<p className="known" style={{margin:'8px 0 0'}}>{tl("Quiz average {average}% over {n}.",{average:p.average,n:pl(p.quizzed,'topic')})}{p.summary&&' '+p.summary}</p>}
      {next&&<button className={'btn'+(c.reviews_due?' ghost':'')} onClick={()=>setTopic(next.id)}><Play size={16}/> {done?tl("Continue"):tl("Start")}: {next.title}</button>}<p className="known" style={{margin:'8px 0 0'}}>{STAR_HELP}</p></div>
    {all.length>12&&<div className="search" style={{marginTop:14}}><Search size={18}/><input type="search" aria-label={tl("Find a topic")} placeholder={tl("Find a topic")} value={find} onChange={e=>setFind(e.target.value)}/></div>}
    <Paged rows={c.units.flatMap(u=>u.topics.filter(t=>has(find,t.title,t.summary)).map(t=>({u,t})))} render={({u,t},i,j,pg)=><Fragment key={t.id}>{(!j||pg[j-1].u!==u)&&<h3 className={'sec'+(i?'':' first')}>{u.title}</h3>}
      <button className="row rowbtn" onClick={()=>setTopic(t.id)}><div>{t.title}{t.due&&<span className="pill sm" style={{marginLeft:6}}>{tl("Review due")}</span>}<small>{t.summary||''}{t.best!=null?tl("{v}best quiz {best}%",{v:t.summary?' · ':'',best:t.best}):''}</small></div><ChevronRight size={18}/></button></Fragment>}/>
    {p&&p.areas.length>0&&<><h3 className="sec">{tl("From your quizzes")}</h3><p className="known" style={{marginTop:0}}>{tl("Your best quiz score in each topic, weakest first.")}</p>
      {<Paged rows={p.areas} render={a=><button key={a.topic_id} className="row rowbtn" onClick={()=>setTopic(a.topic_id)}><div>{a.title}<span className={'pill sm '+(a.status==='strong'?'okp':a.status==='needs_study'?'off':'')} style={{marginLeft:6}}>{AREA_LABEL[a.status]}</span><small>{tl("Best quiz {percent}%",{percent:a.percent})}</small><Bar2 v={a.percent}/></div><ChevronRight size={18}/></button>}/>}</>}
    {c.can_edit&&<><h3 className="sec">{tl("Course settings")}</h3>
      <label id="shr">{tl("Who can study it")}</label><div className="seg" role="group" aria-labelledby="shr" style={{gridTemplateColumns:'1fr 1fr',margin:'0 0 8px'}}>{[['private',tl("Only me")],['program',tl("My classmates")]].map(([k,l])=><button key={k} className={c.share===k?'on':''} aria-pressed={c.share===k} onClick={()=>c.share!==k&&share(k)}>{l}</button>)}</div>
      <p className="known" style={{marginTop:0}}>{c.share==='program'?tl("Students in your program can open it and take their own quizzes. Only you can change it."):tl("Private: only you can see it.")}</p>
      <div className="two"><button className="btn ghost" onClick={()=>setRen(c.title)}><Pencil size={16}/>{" "}{tl("Rename")}</button><button className="btn ghost" onClick={reopen}>{tl("Change the setup")}</button></div>
      <button className="btn danger" onClick={del}>{tl("Delete course")}</button></>}
    {ren!=null&&<Sheet close={()=>setRen(null)}><h3>{tl("Rename course")}</h3><label htmlFor="rnm">{tl("Course name")}</label><input id="rnm" autoFocus value={ren} onChange={e=>setRen(e.target.value)}/>
      <button className="btn" disabled={!ren.trim()} onClick={async()=>{try{await api('/study/courses/'+id,{method:'PUT',body:{title:ren}});setRen(null);load()}catch(e){toast(e.message)}}}>{tl("Save")}</button><button className="btn ghost" onClick={()=>setRen(null)}>{tl("Cancel")}</button></Sheet>}</div></>}
const AiNote=({o})=>!o?null:!o.ai_available?<p className="known" role="note">{o.ai_own_key?tl("Add your own DeepSeek API key under “My AI key” in the menu to use explanations, quick checks and quizzes."):tl("AI help is switched off right now. Ask your admin to add an AI key.")}</p>
  :o.ai_left!=null&&o.ai_left<=10?<p className="known" role="note">{o.ai_left?tl("{n} left today for your own courses.",{n:pl(o.ai_left,'AI request')}):tl("You have used today's AI requests for your own courses. Reviews still work; new questions come back tomorrow.")}</p>:null
function StudyTopicPage({id,toast,back,go}){
  const confirm=useConfirm()
  const [t,setT]=useState(null),[tab,setTab]=useState('notes'),[ex,setEx]=useState(null),[busy,setBusy]=useState(''),[quiz,setQuiz]=useState(null),[ed,setEd]=useState(null)
  const load=()=>api('/study/topics/'+id).then(setT).catch(e=>{toast(e.message);back()})
  useEffect(()=>{setT(null);setEx(null);setTab('notes');load();window.scrollTo(0,0)},[id])
  useEffect(()=>{if(!quiz&&t)load()},[quiz])
  if(quiz)return <StudyQuizPlay quiz={quiz} toast={toast} back={()=>setQuiz(null)} again={k=>make(k)} next={t?.next&&{title:t.next.title,go:()=>{setQuiz(null);go(t.next.id)}}}/>
  if(!t)return <><Bar title={tl("Topic")} back={back}/><div className="main"><Skeleton/></div></>
  const explain=async()=>{setBusy('explain');try{setEx(await api(`/study/topics/${id}/explain`))}catch(e){toast(e.message)}setBusy('')}
  async function make(kind){setBusy(kind);try{setQuiz(await api(`/study/topics/${id}/quizzes`,{method:'POST',body:{kind}}))}catch(e){toast(e.message)}setBusy('')}
  const done=async on=>{try{await api(`/study/topics/${id}/progress`,{method:'PUT',body:{completed:on}});setT({...t,completed:on});toast(on?tl("Marked as completed"):tl("Marked as not completed"))}catch(e){toast(e.message)}}
  const saveEd=async()=>{try{await api('/study/topics/'+id,{method:'PUT',body:ed});setEd(null);setEx(null);toast(tl("Topic saved"));load()}catch(e){toast(e.message)}}
  const delTopic=async()=>{if(!await confirm({title:tl("Delete “{title}”?",{title:t.title}),body:tl("The topic, your progress and your checks on it are removed. This can't be undone."),ok:tl("Delete topic"),danger:true}))return
    try{await api('/study/topics/'+id,{method:'DELETE'});toast(tl("Topic deleted"));back()}catch(e){toast(e.message)}}
  const noAi=!t.ai_available||t.ai_left===0
  return <><Bar title={t.title} sub={tl("{course} › {unit} · {position} of {total}",{course:t.course,unit:t.unit,position:t.position,total:t.total})} back={back}/><div className="main">
    <Tabs label={tl("Topic sections")} items={[['notes',tl("Notes")],['explain',tl("Explain")]]} value={tab} onChange={setTab}/>
    {tab==='notes'&&<div className="prose"><Md>{t.content}</Md></div>}
    {tab==='explain'&&(ex?<div className="prose">{ex.cached&&<span className="chip">{tl("Saved explanation · no AI request used")}</span>}<Md>{ex.text}</Md></div>
      :t.has_explain||!noAi?<button className="btn" disabled={!!busy} onClick={explain}><Sparkles size={16}/> {busy==='explain'?tl("Thinking…"):tl("Explain it to me")}</button>:<AiNote o={t}/>)}
    <h3 className="sec">{tl("Check yourself")}</h3>
    <AiNote o={t}/>
    <div className="two"><button className="btn" disabled={!!busy||noAi} onClick={()=>make('mcq')}><ClipboardList size={16}/> {busy==='mcq'?tl("Writing questions…"):tl("5 quick questions")}</button><button className="btn ghost" disabled={!!busy||noAi} onClick={()=>make('quiz')}><Target size={16}/> {busy==='quiz'?tl("Writing the quiz…"):tl("Full quiz · 10")}</button></div>
    <p className="known">{tl("Quick check: 5 practice MCQs with the answer right after each one; 4 right marks the topic completed. Full quiz: 10 questions scored at the end; pass it for ★★, score 90% for ★★★. New questions every time, and the topic comes back for review before you forget it.")}</p>
    {t.attempts.length>0&&<><h3 className="sec">{tl("Your results here")}</h3>{<Paged rows={t.attempts} render={a=><div className="row" key={a.id}><div>{a.kind==='quiz'?tl("Quiz"):tl("Practice MCQs")} · {a.score} / {a.total} · {a.percent}%<small>{when(a.at)}</small><Bar2 v={a.percent}/></div></div>}/>}</>}
    <div style={{marginTop:16}}>{t.completed?<button className="btn ghost" onClick={()=>done(false)}>{tl("Mark as not completed")}</button>:<button className="btn" onClick={()=>done(true)}><Check size={16}/>{" "}{tl("Mark as completed")}</button>}</div>
    <div className="two">{t.prev?<button className="btn ghost" onClick={()=>go(t.prev.id)}><ChevronLeft size={16}/>{" "}{tl("Previous")}</button>:<span/>}{t.next&&<button className="btn ghost" onClick={()=>go(t.next.id)}>{tl("Next")}{" "}<ChevronRight size={16}/></button>}</div>
    {t.can_edit&&<div className="two"><button className="btn ghost" onClick={()=>setEd({title:t.title,content:t.content})}><Pencil size={16}/>{" "}{tl("Edit topic")}</button><button className="btn ghost" onClick={delTopic}><Trash2 size={16}/>{" "}{tl("Delete topic")}</button></div>}
    {ed&&<Sheet close={()=>setEd(null)}><h3>{tl("Edit topic")}</h3><label htmlFor="ett">{tl("Title")}</label><input id="ett" value={ed.title} onChange={e=>setEd({...ed,title:e.target.value})}/>
      <label htmlFor="etc">{tl("Text")}</label><textarea id="etc" style={{minHeight:260}} value={ed.content} onChange={e=>setEd({...ed,content:e.target.value})}/>
      <p className="known">{tl("Markdown works: # for headings, - for lists, **bold**. Your progress and stars stay.")}</p>
      <button className="btn" disabled={!ed.title.trim()||!ed.content.trim()} onClick={saveEd}>{tl("Save")}</button><button className="btn ghost" onClick={()=>setEd(null)}>{tl("Cancel")}</button></Sheet>}</div></>}
function StudyQuizPlay({quiz,toast,back,again,next}){
  const mcq=quiz.kind!=='quiz',[ans,setAns]=useState(quiz.questions.map(()=>null)),[fb,setFb]=useState({}),[res,setRes]=useState(null),[busy,setBusy]=useState(false)
  const [flagged,setFlagged]=useState({})
  const flag=async i=>{try{await api(`/study/quizzes/${quiz.id}/flag`,{method:'POST',body:{index:i}});setFlagged(f=>({...f,[i]:true}));toast(tl("Thanks. That question won't come back in your reviews."))}catch(e){toast(e.message)}}
  const pick=async(i,k)=>{if(res||(mcq&&fb[i]))return;setAns(a=>a.map((v,n)=>n===i?k:v));if(!mcq)return
    try{const r=await api(`/study/quizzes/${quiz.id}/check`,{method:'POST',body:{index:i,answer:k}});setFb(f=>({...f,[i]:r}))}catch(e){toast(e.message)}}
  const submit=async()=>{setBusy(true);try{setRes(await api(`/study/quizzes/${quiz.id}/attempt`,{method:'POST',body:{answers:ans}}));window.scrollTo(0,0)}catch(e){toast(e.message)}setBusy(false)}
  const left=ans.filter(a=>a==null).length,review=quiz.kind==='review',label=review?'Review':mcq?'Quick check':'Full quiz'
  return <><Bar title={label} sub={quiz.topic+' · '+pl(quiz.questions.length,'question')} back={back}/><div className="main">
    {res&&<div className="qbox score" style={{marginTop:0}} role="status">
      <h2 style={{margin:0}}>{res.score} / {res.total} · {res.percent}%</h2>
      <p className="known">{review?tl("Review done."):mcq?tl("Done. The answers are below."):tl("Done. A new set is there whenever you want one.")}{res.summary&&' '+res.summary}{res.next_review&&' '+res.next_review+'.'}</p>
      {next&&<button className="btn" onClick={next.go}>{tl("Next topic: {title}",{title:next.title})}{" "}<ChevronRight size={16}/></button>}
      <div className="two">{again&&<button className={'btn'+(next?' ghost':'')} onClick={()=>again(quiz.kind)}>{tl("New")}{" "}{mcq?'questions':'quiz'}</button>}<button className={'btn'+(again||next?' ghost':'')} onClick={back}>{review?tl("Done"):tl("Back to the topic")}</button></div></div>}
    {res&&!mcq&&res.areas.length>0&&<><h3 className="sec">{tl("What you know well and what to revisit")}</h3><AreaList areas={res.areas} onStudy={null} staff/></>}
    {quiz.questions.map((x,i)=>{const f=mcq?fb[i]:res&&res.results[i]
      return <div className="qbox" key={i}><b>{tl("Question")}{" "}{i+1}{f?(f.ok?tl(" · Right"):tl(" · Wrong")):''}</b>{x.topic&&<small className="known" style={{display:'block'}}>{x.topic}</small>}<div className="prose"><Md>{x.text}</Md></div>
        {x.options.map((o,k)=>{const cls=f?(k===f.correct?' ok':k===ans[i]?' bad':''):ans[i]===k?' sel':''
          return <button key={k} className={'opt'+cls} disabled={!!f||!!res} aria-pressed={ans[i]===k} onClick={()=>pick(i,k)}><b className="olet">{LET[k]}</b><span className="obody"><Md>{o}</Md></span>{f&&k===f.correct&&<span className="otag ok"><Check size={14}/>{" "}{tl("Correct")}</span>}</button>})}
        {f&&f.explanation&&<div className="known"><Md>{f.explanation}</Md></div>}
        {f&&(flagged[i]?<p className="known" style={{margin:'4px 0 0'}}>{tl("Reported.")}</p>:<button className="tool" onClick={()=>flag(i)}>{tl("This question is wrong")}</button>)}</div>})}
    {!res&&<><button className="btn" disabled={busy||(mcq&&Object.keys(fb).length<quiz.questions.length)} onClick={submit}>{busy?tl("Checking…"):mcq?tl("See my score"):tl("Submit answers")}</button>
      {mcq?<p className="known">{tl("Pick an answer to see right away if it is right.")}{Object.keys(fb).length<quiz.questions.length?tl(" {v} to go.",{v:quiz.questions.length-Object.keys(fb).length}):''}</p>:left>0&&<p className="known">{left}{" "}{tl("unanswered. Blank answers count as wrong.")}</p>}</>}</div></>}
function BankSheet({close,onAdd,toast}){
  const confirm=useConfirm()
  const [q,setQ]=useState(''),[tag,setTag]=useState(''),[mine,setMine]=useState(false),[sel,setSel]=useState({}),top=useRef()
  const {items,total,page,setPage,ready,data,reload}=usePaged(o=>`/bank?limit=${PAGE}&offset=${o}&q=${encodeURIComponent(q)}&tag=${encodeURIComponent(tag)}`+(mine?'&mine=true':''),[q,tag,mine],toast)
  const picked=Object.values(sel)
  const flip=x=>{const c={...sel};c[x.id]?delete c[x.id]:c[x.id]=x;setSel(c)}
  const del=async x=>{if(!await confirm({title:tl("Delete this question from the bank?"),body:tl("It disappears for everyone. Quizzes that already use it keep their copy."),ok:tl("Delete"),danger:true}))return;try{await api('/bank/'+x.id,{method:'DELETE'});const c={...sel};delete c[x.id];setSel(c);reload()}catch(e){toast(e.message)}}
  return <Sheet close={close}><h3>{tl("Question bank")}</h3><p className="known">{tl("Questions shared by every teacher. Adding one puts a copy in this quiz, so later changes to the bank never alter a quiz students are taking.")}</p>
    <div className="search"><Search size={18}/><input type="search" aria-label={tl("Search the bank")} placeholder={tl("Search questions, tags or source")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label={tl("Filter by tag")} value={tag} onChange={e=>setTag(e.target.value)}><option value="">{tl("All tags")}</option>{(data?.tags||[]).map(t=><option key={t} value={t}>{t}</option>)}</select>
      <label className="chk" style={{padding:0}}><input type="checkbox" checked={mine} onChange={e=>setMine(e.target.checked)}/>{" "}{tl("Only mine")}</label></div>
    <span ref={top} className="pgtop"/>{!ready?<div className="sk"/>:!items.length?<p className="known">{q||tag||mine?tl("Nothing matches that."):tl("The bank is empty. Use “Save to bank” in any quiz to start it.")}</p>:items.map(x=><div key={x.id} className="row"><label className="chk" style={{alignItems:'flex-start',flex:1}}><input type="checkbox" checked={!!sel[x.id]} onChange={()=>flip(x)}/><span><span style={{display:'block'}}>{x.text.length>180?x.text.slice(0,180)+'…':x.text}</span><small>{x.options.length}{" "}{tl("answers{v} · by",{v:x.tags.length>0&&' · '+x.tags.join(', ')})}{" "}{x.owner||'someone'}{x.uses>0&&tl(" · used {n}",{n:pl(x.uses,'time')})}</small></span></label>{x.can_edit&&<button className="ic sm" aria-label={tl("Delete from the bank")} onClick={()=>del(x)}><Trash2 size={16}/></button>}</div>)}
    <Pager page={page} total={total} onPage={setPage} anchor={top}/>
    <button className="btn" disabled={!picked.length} onClick={()=>onAdd(picked)}>{picked.length?tl("Add {n}",{n:pl(picked.length,'question')}):tl("Choose questions to add")}</button><button className="btn ghost" onClick={close}>{tl("Cancel")}</button></Sheet>}

function CopySheet({kind,id,title,close,toast}){
  const [tree,setTree]=useState(null),[cid,setCid]=useState(''),[uid,setUid]=useState(''),[wq,setWq]=useState(true),[busy,setBusy]=useState(false),[res,setRes]=useState(null)
  useEffect(()=>{api('/tree').then(setTree).catch(e=>{toast(e.message);close()})},[toast,close])
  const courses=(tree||[]).flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>c.editable&&!c.shared).map(c=>({...c,label:`${p.name} › ${s.name} › ${c.name}`}))))
  const dest=courses.find(c=>String(c.id)===cid)
  const run=async()=>{setBusy(true);try{setRes(await api(`/${kind==='topic'?'topics':'units'}/${id}/copy`,{method:'POST',body:kind==='topic'?{unit_id:+uid}:{course_id:+cid,with_quizzes:wq}}))}catch(e){toast(e.message)}setBusy(false)}
  if(res)return <Sheet close={close}><h3>{tl("Copied")}</h3><p className="known">{kind==='topic'?tl("“{title}” is a draft in {label} › {name}.",{title:res.title,label:dest.label,name:dest.units.find(u=>u.id===res.unit_id)?.name}):tl("“{name}” is in {label} with {n}{v}.",{name:res.name,label:dest.label,n:pl(res.topics,'topic'),v:res.quizzes?` and ${pl(res.quizzes,'quiz')}`:''})}{" "}{tl("Everything arrives as a draft, so students see nothing until you publish it.")}</p><button className="btn" onClick={close}>{tl("Done")}</button></Sheet>
  return <Sheet close={close}><h3>{tl("Copy")}{" "}{kind==='topic'?'topic':'unit'}</h3><p className="known">{tl("Makes a copy of “{title}”{v} in a course you can edit. The original is not changed. Reading progress and bookmarks are not copied.",{title:title,v:kind==='unit'?' with its topics'+(' and, if you may edit the original, its quizzes'):''})}</p>
    {!tree?<div className="sk"/>:!courses.length?<p className="known">{tl("You do not own a course to copy into. An admin makes you the owner of a course.")}</p>:<>
      <label htmlFor="cc">{tl("Copy into course")}</label><select id="cc" value={cid} onChange={e=>{setCid(e.target.value);setUid('')}}><option value="">{tl("Choose a course")}</option>{courses.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select>
      {kind==='topic'&&dest&&<><label htmlFor="cu">{tl("Unit")}</label><select id="cu" value={uid} onChange={e=>setUid(e.target.value)}><option value="">{tl("Choose a unit")}</option>{dest.units.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select>{!dest.units.length&&<p className="known">{tl("That course has no units yet. Add a unit first.")}</p>}</>}
      {kind==='unit'&&<label className="chk"><input type="checkbox" checked={wq} onChange={e=>setWq(e.target.checked)}/>{" "}{tl("Include its quizzes (as drafts)")}</label>}</>}
    <button className="btn" disabled={busy||!dest||(kind==='topic'&&!uid)} onClick={run}>{busy?tl("Copying…"):tl("Copy")}</button><button className="btn ghost" onClick={close}>{tl("Cancel")}</button></Sheet>}
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
  const restore=async()=>{if(!await confirm({title:tl("Put this version back?"),body:tl("What is there now stays in the history, so you can undo it."),ok:tl("Restore version")}))return;setBusy(true)
    try{await api(`/topic-versions/${v.id}/restore`,{method:'POST'});toast(tl("Version restored"));done()}catch(e){toast(e.message);setBusy(false)}}
  if(v){const changed=Object.keys(FIELD_LABEL).filter(k=>v[k]!==v.now[k])
    return <Sheet close={close}><button className="link" onClick={()=>setV(null)}><ChevronLeft size={16}/>{" "}{tl("All versions")}</button>
      <h3>{v.saved_at?when(v.saved_at):tl("Earlier version")}</h3><p className="known">{v.note}{v.current?tl(" · this is the current text"):''}</p>
      {!changed.length&&<p className="known">{tl("Same as the current text.")}</p>}
      {changed.map(k=><div key={k} className="qbox"><b>{FIELD_LABEL[k]}</b><p className="known" style={{margin:'2px 0 8px'}}>{tl("Red lines are in this version only. Green lines are in the current text.")}</p>
        <div className="diff">{lineDiff(v[k],v.now[k]).map((l,i)=><div key={i} className={'dl '+l.k}>{l.t||'\u00a0'}</div>)}</div></div>)}
      {!v.current&&<button className="btn" disabled={busy} onClick={restore}>{tl("Restore this version")}</button>}<button className="btn ghost" onClick={close}>{tl("Close")}</button></Sheet>}
  return <Sheet close={close}><h3>{tl("Version history")}</h3><p className="known">{tl("Every save is kept (the latest {v}). Pick one to compare it with the current text.",{v:100})}</p>
    {!list?<div className="sk"/>:!list.length?<p className="known">{tl("No versions recorded yet. They appear the next time this topic is saved.")}</p>
      :<Paged rows={list} render={x=><button key={x.id} className="row" style={{width:'100%',textAlign:'start',background:'none'}} onClick={()=>open(x)}><div>{x.saved_at&&!(x.by===null&&x.note.startsWith('Before'))?when(x.saved_at):tl("Before history began")}<small>{x.note}{x.by?' · '+x.by:''}</small></div>{x.current&&<span className="pill">{tl("Current")}</span>}<ChevronRight size={16}/></button>}/>}
    <button className="btn ghost" onClick={close}>{tl("Close")}</button></Sheet>}
function Topic({id:first,back,toast,role}){
  const [practice,setPractice]=useState(null),[checking,setChecking]=useState(''),[reading,setReading]=useState(false),[hls,setHls]=useState([])
  const [id,setId]=useState(first),[editing,setEditing]=useState(false),[v,setV]=useState(0),[t,setT]=useState(null),[tab,setTab]=useState('notes'),[known,setKnown]=useState([]),[ai,setAi]=useState({}),[aiOk,setAiOk]=useState(null),[ownKey,setOwnKey]=useState(false),[aiMsg,setAiMsg]=useState(''),[busy,setBusy]=useState(false),[bm,setBm]=useState(false),[pv,setPv]=useState(false),[hist,setHist]=useState(false),[cp,setCp]=useState(false),[gone,setGone]=useState('')
  const [mat,setMat]=useState(false),[upNext,setUpNext]=useState(null),opened=useRef(false),jump=nid=>{opened.current=false;setUpNext(null);setGone('');setT(null);setTab('notes');setAi({});setAiMsg('');setKnown([]);setEditing(false);setId(nid);window.scrollTo(0,0)},learn=r=>setT(p=>({...p,status:r.status,overdue:r.overdue,late:r.late,completed_at:r.completed_at}))
  useEffect(()=>{api('/topics/'+id).then(x=>{setT(x);setBm(!!x.bookmarked)
    if(!opened.current){opened.current=true;api(`/topics/${id}/read`,{method:'POST'}).then(r=>{setKnown(r.known);learn(r)}).catch(()=>{})}}).catch(e=>{toast(e.message);if(/unavailable right now/.test(e.message))setGone(e.message)})},[id,v])  // opening starts it, after the page has loaded
  const setDone=async on=>{try{learn(await api(`/topics/${id}/complete`,{method:on?'PUT':'DELETE'}));toast(on?tl("Marked as completed"):tl("Marked as not completed"))}catch(e){toast(e.message);return}
    setUpNext(null);if(!on||role!=='student')return
    try{const items=(await api('/me/session')).session?.items||[];if(items.some(x=>x.id===id&&x.kind!=='review'&&x.src!=='study'))setUpNext({items,next:items.find(x=>!x.done)})}catch{/* no session today: nothing to lead on to */}}
  useEffect(()=>{api('/ai/status').then(r=>{setAiOk(r.available);setOwnKey(!!r.own_key)}).catch(()=>{})},[id])
  useEffect(()=>{setHls([]);api(`/topics/${id}/highlights`).then(r=>setHls(r.items)).catch(()=>{})},[id,v])
  const dropHl=async h=>{try{await api('/me/highlights/'+h.id,{method:'DELETE'});setHls(l=>l.filter(x=>x.id!==h.id));toast(tl("Highlight removed"))}catch(e){toast(e.message)}}
  const ask=async k=>{setBusy(true);setAiMsg('');try{const r=await api(`/topics/${id}/ai/${k}`);setAi(a=>({...a,[k]:r}))}catch(e){setAiMsg(e.message)}setBusy(false)}
  async function practise(kind){setChecking(kind);try{setPractice(await api(`/topics/${id}/practice`,{method:'POST',body:{kind}}))}catch(e){toast(e.message)}setChecking('')}
  if(mat&&t)return <MyMaterial cid={t.course_id} name={t.course} back={()=>{setMat(false);setAi({});setAiMsg('');setV(v+1)}} toast={toast}/>  // clear saved answers: the notes may have changed, so Explain must be asked again
  if(practice)return <StudyQuizPlay quiz={practice} toast={toast} back={()=>setPractice(null)} again={k=>practise(k)}/>
  if(editing)return <TopicEditor role={role} toast={toast} edit={{id}} done={()=>{setEditing(false);setV(v+1)}} cancel={()=>setEditing(false)}/>
  if(gone)return <><Bar title={tl("Unavailable")} back={back}/><div className="main"><div className="hero"><h2>{gone}</h2><p>{tl("It has been archived. Check back later or ask your teacher.")}</p></div></div></>
  if(!t)return <><Bar title={tl("Loading")} back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const flip=async()=>{const on=!bm;setBm(on);try{await api(`/topics/${id}/bookmark`,{method:on?'PUT':'DELETE'});toast(on?tl("Bookmarked"):tl("Bookmark removed"))}catch(e){setBm(!on);toast(e.message)}}
  const view=k=>ai[k]?<div className="prose">{ai[k].cached&&<span className="chip">{tl("Saved answer · no tokens used")}</span>}{ai[k].own_notes&&<span className="chip">{tl("Written with your own notes")}</span>}<Md>{ai[k].text}</Md><FlagLink source="topic" id={ai[k].id} topicId={id} excerpt={ai[k].text}/></div>
    :aiOk===false?<p className="known">{ownKey?tl("Add your own DeepSeek API key under “My AI key” in the menu to use AI help."):tl("AI unavailable. Try again later.")}</p>
    :<><button className="btn" disabled={busy} onClick={()=>ask(k)}><Sparkles size={16}/> {busy?tl("Thinking…"):k==='explain'?tl("Explain it to me"):tl("Show a sample answer")}</button>{t.my_notes&&<p className="known">{tl("Uses your own notes too. It counts toward your daily AI requests.")}</p>}{aiMsg&&<p className="known">{aiMsg}</p>}</>
  return <><Bar title={t.title} sub={[t.program,t.semester,t.course,t.unit].filter(Boolean).join(' › ')} back={back} right={role!=='admin'&&<button className={'ic'+(bm?' on':'')} aria-label={bm?tl("Remove bookmark"):tl("Bookmark this topic")} aria-pressed={bm} onClick={flip}><Bookmark fill={bm?'currentColor':'none'}/></button>}/><div className="main">
    {t.can_edit&&pv&&<div className="qbox" style={{marginTop:0}}><b>{tl("Previewing as a student")}</b><p className="known" style={{margin:'4px 0 8px'}}>{tl("This is what students see: no editing buttons, and drafts show as unavailable to them.")}</p><button className="btn ghost" style={{marginTop:0}} onClick={()=>setPv(false)}>{tl("Back to editing")}</button></div>}
    {t.can_edit&&!pv&&<div className="two" style={{marginBottom:12}}><button className="btn ghost" style={{marginTop:0}} onClick={()=>setEditing(true)}><Pencil size={16}/>{" "}{tl("Edit topic")}</button>
      <button className="btn ghost" style={{marginTop:0}} onClick={async()=>{try{await api(`/topics/${id}/publish`,{method:'PUT',body:{published:!t.published}});toast(t.published?tl("Moved to drafts"):tl("Published"));setV(v+1)}catch(e){toast(e.message)}}}>{t.published?<><EyeOff size={16}/>{" "}{tl("Unpublish")}</>:<><Eye size={16}/>{" "}{tl("Publish")}</>}</button></div>}
    {role!=='student'&&<div className="qbox" style={{marginTop:0}}><div className="row"><div>{t.learning_due_at?when(t.learning_due_at):tl("No deadline")}<small>{tl("Learn by")}</small></div></div></div>}
    {upNext&&<div className="qbox" role="status"><b>{tl("Today's session · {length} of {length2} done",{length:upNext.items.filter(x=>x.done).length,length2:upNext.items.length})}</b>
      {!upNext.next?<p className="known" style={{margin:'4px 0 0'}}>{tl("That's today's session done. See you next study day.")}</p>
        :upNext.next.kind!=='review'&&upNext.next.src!=='study'?<button className="btn" onClick={()=>jump(upNext.next.id)}>{tl("Next:")}{" "}{upNext.next.title}<ChevronRight size={16}/></button>
        :<button className="btn ghost" onClick={back}>{tl("Back for the next part:")}{" "}{upNext.next.title}</button>}</div>}
    {t.can_edit&&!pv&&<><button className="tool" onClick={()=>setPv(true)}><Eye size={14}/>{" "}{tl("Preview as student")}</button><button className="tool" onClick={()=>setHist(true)}><History size={14}/>{" "}{tl("Version history")}</button></>}
    {role!=='student'&&!pv&&<button className="tool" onClick={()=>setCp(true)}><Copy size={14}/>{" "}{tl("Copy to another course")}</button>}
    {cp&&<CopySheet kind="topic" id={id} title={t.title} toast={toast} close={()=>setCp(false)}/>}
    {hist&&<HistorySheet tid={id} toast={toast} close={()=>setHist(false)} done={()=>{setHist(false);setV(v+1)}}/>}
    {t.can_edit&&!t.published&&<p className="known" style={{marginTop:0}}>{tl("Draft · students cannot see it")}</p>}
    {aiOk&&<TopicSteps id={id} student={role==='student'}/>}
    <Tabs label={tl("Topic sections")} items={[['notes',tl("Notes")],['explain',tl("Explain")],['answer',tl("Sample answer")]]} value={tab} onChange={setTab}/>
    {known.length>0&&tab==='explain'&&<p className="known">{tl("You’ve already covered:")}{" "}{known.join(', ')}</p>}
    {tab==='notes'&&t.content&&<button className="btn lead" onClick={()=>setReading(true)}><Maximize2 size={16}/> {t.content_format==='interactive'?tl("Open the interactive page"):tl("Read in full screen")}</button>}
    {tab==='notes'&&<div className="prose">{t.content?(t.content_format==='interactive'?<p className="known" style={{margin:0}}>{tl("This topic is an interactive page. Open it above to use it and highlight its text.")}</p>:<Body text={t.content} format={t.content_format}/>):!t.my_notes&&<Md>{tl("No notes yet.")}</Md>}{t.my_notes&&<>{t.content&&<h3>{tl("Your notes")}</h3>}{!t.content&&<span className="chip">{tl("Your notes")}</span>}<Md>{t.my_notes}</Md></>}{t.question_pattern&&<><h3>{tl("Question pattern")}</h3><Md>{t.question_pattern}</Md></>}{t.guideline&&<><h3>{tl("Answer guideline")}</h3><Md>{t.guideline}</Md></>}{role==='student'&&<button className="tool" onClick={()=>setMat(true)}><FileText size={14}/> {t.my_notes?tl("Update your notes for this course"):tl("Add your own notes for this topic")}</button>}</div>}
    {tab==='notes'&&hls.length>0&&<><h3 className="sec">{tl("Your highlights ({length})",{length:hls.length})}</h3>{<Paged rows={hls} render={h=><HlItem key={h.id} h={{...h,tid:id}} toast={toast} onSaved={r=>setHls(l=>l.map(x=>x.id===r.id?r:x))} onDrop={()=>dropHl(h)}/>}/>}</>}
    {tab==='explain'&&view('explain')}{tab==='answer'&&(aiOk===false?view('answer'):<><Outline id={id}/>{ai.answer?view('answer'):<button className="btn ghost" disabled={busy} onClick={()=>ask('answer')}>{busy?tl("Thinking…"):tl("Show the full sample answer")}</button>}{!ai.answer&&aiMsg&&<p className="known">{aiMsg}</p>}</>)}
    {reading&&<Reader t={t} auto={role==='student'} toast={toast} onList={setHls} close={()=>setReading(false)}/>}
    {role==='student'&&aiOk!==false&&<><h3 className="sec">{tl("Want to test yourself?")}</h3><div className="two"><button className="btn ghost" disabled={!!checking} onClick={()=>practise('mcq')}><ClipboardList size={16}/> {checking==='mcq'?tl("Writing questions…"):tl("5 quick questions")}</button><button className="btn ghost" disabled={!!checking} onClick={()=>practise('quiz')}><Target size={16}/> {checking==='quiz'?tl("Writing the quiz…"):tl("Full quiz · 10")}</button></div>
      <p className="known" style={{marginTop:4}}>{tl("New questions from this topic's notes each time. 5 quick questions: the answer right after each one. Full quiz: scored at the end.")}</p></>}
    {role==='student'&&<div className="mine"><span>{t.learning_due_at&&<>{tl("Your teacher's date")}: {day(t.learning_due_at)} · </>}{t.status==='completed'?tl("You marked this as learned"):tl("Not marked as learned yet")}</span>
      {t.status==='completed'?<button className="link" onClick={()=>setDone(false)}>{tl("Undo")}</button>:<button className="link" onClick={()=>setDone(true)}>{tl("I've learned this")}</button>}</div>}
    {t.nav&&t.nav.total>1&&<nav className="pager" aria-label={tl("Topics in this unit")}><button className="btn ghost" disabled={!t.nav.prev} onClick={()=>jump(t.nav.prev.id)} aria-label={t.nav.prev?tl("Previous topic: {title}",{title:t.nav.prev.title}):tl("No previous topic")}><ChevronLeft size={18}/><span>{t.nav.prev?t.nav.prev.title:tl("Previous")}</span></button>
      <small>{t.nav.position}{" "}{tl("of")}{" "}{t.nav.total}</small>
      <button className={'btn'+(t.nav.next?'':' ghost')} disabled={!t.nav.next} onClick={()=>jump(t.nav.next.id)} aria-label={t.nav.next?tl("Next topic: {title}",{title:t.nav.next.title}):tl("No next topic")}><span>{t.nav.next?t.nav.next.title:tl("Next")}</span><ChevronRight size={18}/></button></nav>}</div></>}

// the top of a topic page: the gist and one curious question, then short steps the reader picks (Why?, Example, Exam angle, Quick check).
// Every reply is a few lines and saved for everyone; the notes below stay the reference
const STEP_KINDS=L([['why',tl("Why?")],['example',tl("Example")],['exam',tl("Exam angle")],['check',tl("Quick check")]])
const STEP_LABEL=k=>k==='simpler'?tl("More simply"):STEP_KINDS.find(x=>x[0]===k)?.[1]
const Reveal=({label,children})=>{const [on,setOn]=useState(false);return on?<div className="reveal">{children}</div>:<button className="link" onClick={()=>setOn(true)}>{label}</button>}
const Hook=({q,a})=><div className="hook"><p>{q}</p>{a&&<Reveal label={tl("Think, then tap for the answer")}><Md>{a}</Md></Reveal>}</div>
// after a quick check's answer: the student's own private "I had it" / "Not quite"; not quite offers the idea again, more simply
function SelfMark({id,onSimpler}){
  const [got,setGot]=useState('')
  const mark=async o=>{setGot(o);try{await api(`/topics/${id}/check-result`,{method:'POST',body:{outcome:o}})}catch{/* only a hint for next time */}}
  if(got==='knew')return <p className="known selfm">{tl("Nice. The next ones will stretch you a little more.")}</p>
  if(got==='not_yet')return <p className="known selfm">{tl("That's fine, it takes a few goes.")}{onSimpler&&<>{" "}<button className="link inl" onClick={onSimpler}>{tl("Explain it more simply")}</button></>}</p>
  return <div className="selfm" role="group" aria-label={tl("How did it go? Only you see this")}><button className="stepchip" onClick={()=>mark('knew')}>{tl("I had it")}</button><button className="stepchip" onClick={()=>mark('not_yet')}>{tl("Not quite")}</button><small className="known">{tl("Only you see this")}</small></div>}
function StepCard({id,rid,k,d,student,onSimpler}){
  return <div className={'stepcard '+k}><small className="steplab">{STEP_LABEL(k)}</small>
    {k==='why'||k==='example'||k==='simpler'?<><Md>{d.text||''}</Md>{d.hook&&<p className="hookq">{d.hook}</p>}</>
      :<><div className="stepq"><Md>{d.question||''}</Md></div><Reveal label={k==='exam'?tl("Show a model answer"):tl("Show the answer")}><Md>{d.answer||''}</Md>{d.tip&&<p className="known">{tl("Examiners look for")}: {d.tip}</p>}{k==='check'&&student&&<SelfMark id={id} onSimpler={onSimpler}/>}</Reveal></>}<FlagLink source="topic" id={rid} topicId={id}/></div>}
// the top of a topic page: the gist and one curious question, then short steps the reader picks. It adapts to each student, privately:
// the steps they use most come first, quick checks get easier or harder from their own "I had it" / "Not quite", and after a few topics
// in a unit the question comes first with the gist one tap away. Every reply is a few lines and saved for everyone; the notes stay the reference
function TopicSteps({id,student}){
  const [g,setG]=useState(null),[you,setYou]=useState(null),[err,setErr]=useState(''),[trail,setTrail]=useState([]),[busy,setBusy]=useState(''),[open,setOpen]=useState(false)
  const [gid,setGid]=useState(null)
  useEffect(()=>{setG(null);setYou(null);setOpen(false);setErr('');setTrail([]);api(`/topics/${id}/ai/gist`).then(r=>{setG(r.data);setGid(r.id);setYou(r.you||null)}).catch(e=>setErr(e.message))},[id])
  const step=async k=>{setBusy(k);setErr('');try{const r=await api(`/topics/${id}/ai/${k}`);setTrail(x=>[...x.filter(y=>y.k!==k),{k,d:r.data,rid:r.id,raw:r.text}])}catch(e){setErr(e.message)}setBusy('')}
  if(err&&!g)return null  // without AI the page is the notes, as before
  const order=you?.order||STEP_KINDS.map(x=>x[0]),left=order.filter(k=>!trail.some(x=>x.k===k)).map(k=>[k,STEP_LABEL(k)])
  const qFirst=you?.question_first&&!open&&g?.hook
  return <section className="gist" aria-label={tl("The gist")} aria-busy={!g}>
    {!g?<Skeleton rows={2}/>:qFirst?<><h3>{tl("A question first")}<small>{tl("then the gist")}</small></h3><Hook q={g.hook} a={g.hook_answer}/>
        <button className="link" style={{marginTop:10}} onClick={()=>setOpen(true)}>{tl("Show the gist")}</button></>
      :<><h3>{tl("The gist")}<small>{tl("about 30 seconds")}</small></h3>
        <ul>{(g.points||[]).map((x,i)=><li key={i}><Md>{x}</Md></li>)}</ul>
        {g.hook&&!open&&<Hook q={g.hook} a={g.hook_answer}/>}<FlagLink source="topic" id={gid} topicId={id}/></>}
    {g&&<>{trail.map(x=><StepCard key={x.k} id={id} rid={x.rid} k={x.k} d={x.d} student={student} onSimpler={trail.some(y=>y.k==='simpler')?null:()=>step('simpler')}/>)}
      {err&&<p className="known" role="alert">{err}</p>}
      {left.length>0&&<div className="stepchips">{left.map(([k,l])=><button key={k} className="stepchip" disabled={!!busy} onClick={()=>step(k)}>{busy===k?tl("Thinking…"):l}</button>)}</div>}
      {busy==='simpler'&&<p className="known">{tl("Thinking…")}</p>}</>}
  </section>}
// "This looks wrong?" under an AI reply: a student's private report, which the topic's teacher sees (never who sent it) and can have written again
function FlagLink({source,id,topicId,excerpt}){
  const {role}=useContext(Ctx),[st,setSt]=useState(''),[why,setWhy]=useState(''),[err,setErr]=useState('')
  if(role!=='student')return null
  if(st==='sent')return <p className="known flagl">{tl("Thanks. Your teacher will take a look.")}</p>
  if(st!=='open')return <button className="link flagl" onClick={()=>setSt('open')}><Flag size={13}/> {tl("This looks wrong?")}</button>
  const send=async()=>{setErr('');try{await api('/ai/flag',{method:'POST',body:{source,id:id||null,topic_id:topicId||null,excerpt:String(excerpt||'').slice(0,600),reason:why}});setSt('sent')}catch(e){setErr(e.message)}}
  return <div className="flagf"><input value={why} maxLength={300} onChange={e=>setWhy(e.target.value)} placeholder={tl("What looks wrong? (optional)")} aria-label={tl("What looks wrong? (optional)")}/>
    <div className="tools"><button onClick={send}>{tl("Send to my teacher")}</button><button onClick={()=>setSt('')}>{tl("Cancel")}</button></div>{err&&<p className="known">{err}</p>}</div>}
// the safety rules every AI request starts with, read-only, for admins who want to see exactly what they say
function GuardText(){
  const [t,setT]=useState(null)
  return t?<pre className="guardtx">{t}</pre>:<button className="link" style={{marginTop:6}} onClick={()=>api('/admin/guardrails').then(r=>setT(r.text)).catch(()=>{})}>{tl("Read the safety rules")}</button>}
// a unit on one printable sheet, made only when the student asks: each topic's gist and question, and their own highlights.
// Saved gists show at once; the missing ones are written two at a time and fill in as they arrive. A print page, so no numbered pages
function RevisionSheet({uid,back,toast}){
  const [d,setD]=useState(null),[left,setLeft]=useState(0)
  useEffect(()=>{let live=true
    api(`/units/${uid}/revision`).then(async r=>{if(!live)return;setD(r);const q=r.topics.filter(x=>!x.gist);if(!q.length)return
      const on=await api('/ai/status').then(x=>x.available).catch(()=>false);if(!on||!live)return;setLeft(q.length)
      const work=async()=>{while(live&&q.length){const x=q.shift();try{const g=(await api(`/topics/${x.id}/ai/gist`)).data;if(live)setD(p=>({...p,topics:p.topics.map(y=>y.id===x.id?{...y,gist:g}:y)}))}catch{/* that topic stays without its gist */}if(live)setLeft(n=>n-1)}}
      await Promise.all([work(),work()])}).catch(e=>toast(e.message))
    return()=>{live=false}},[uid,toast])
  return <><Bar title={tl("Revision sheet")} sub={d?d.course+' · '+d.unit:''} back={back}/><div className="main">
    <div className="revtools"><button className="btn ghost" style={{marginTop:0}} onClick={()=>window.print()}><Printer size={16}/>{" "}{tl("Print or save as PDF")}</button>{left>0&&<small className="known">{tl("Writing {n} more…",{n:left})}</small>}</div>
    {!d?<Skeleton/>:<article className="revsheet"><h2 className="revhead">{d.unit}<small>{d.course}</small></h2>
      {d.topics.map(x=><section key={x.id} className="revtopic"><h3>{x.title}</h3>
        {x.gist?<ul>{(x.gist.points||[]).map((p,i)=><li key={i}><Md>{p}</Md></li>)}</ul>:<p className="known">{left>0?tl("Writing…"):tl("No gist yet. Open the topic once to make it.")}</p>}
        {x.gist?.hook&&<p className="revq">{tl("Ask yourself")}: {x.gist.hook}</p>}
        {x.highlights.length>0&&<div className="revhl"><small>{tl("Your highlights")}</small><ul>{x.highlights.map((h,i)=><li key={i}>{h}</li>)}</ul></div>}</section>)}</article>}
  </div></>}
// the skeleton of a full-marks answer, shown before the full sample answer
function Outline({id}){
  const [d,setD]=useState(null),[err,setErr]=useState(''),[rid,setRid]=useState(null)
  useEffect(()=>{setD(null);setErr('');api(`/topics/${id}/ai/outline`).then(r=>{setD(r.data);setRid(r.id)}).catch(e=>setErr(e.message))},[id])
  if(err)return <p className="known">{err}</p>
  if(!d)return <Skeleton rows={2}/>
  return <div className="gist"><h3>{tl("How a full-marks answer goes")}</h3><ol>{(d.points||[]).map((x,i)=><li key={i}><Md>{x}</Md></li>)}</ol>{d.marks&&<p className="known">{d.marks}</p>}<FlagLink source="topic" id={rid} topicId={id}/></div>}

// a topic's content full screen, with the reader's own highlights: select text to highlight it, tap a highlight to remove it.
// Markdown and HTML are highlighted right here; an interactive page runs in a sandboxed frame (no access to the app or the sign-in) and
// sends its highlight requests here by postMessage, which this page checks and saves for it.
const Content=memo(({text,format})=><Body text={text} format={format}/>)
const HL_COL={coral:'#ff9292',yellow:'#ffd60a',green:'#50c878',blue:'#5aa0ff'}
// one saved highlight: the passage in its colour, where it is (on the list of all of them), the reader's note, and remove
function HlItem({h,where,onGo,onSaved,onDrop,onExplain,focus,toast}){
  const [ed,setEd]=useState(!!focus),[note,setNote]=useState(h.note||''),ta=useRef(null)
  useEffect(()=>{if(focus)setEd(true)},[focus])
  useEffect(()=>{if(ed)ta.current?.focus()},[ed])
  const save=async()=>{try{onSaved(await api('/me/highlights/'+h.id,{method:'PATCH',body:{note}}));setEd(false)}catch(e){toast(e.message)}}
  return <div className="hlrow" style={{'--hc':HL_COL[h.color]||HL_COL.coral}}><div className="hlbody">
    {onGo?<button className="hltext" onClick={onGo}>{h.text}</button>:<p className="hltext">{h.text}</p>}
    {where&&<small className="hlwhere">{where}</small>}
    {h.explain?<div className="hlexp"><Md>{h.explain.text}</Md><FlagLink source="topic" id={h.explain.id} topicId={h.topic_id||h.tid}/></div>:onExplain&&<button className="link hladd" onClick={onExplain}>{tl("Explain this")}</button>}
    {ed?<><textarea ref={ta} className="hlnote" value={note} maxLength={2000} placeholder={tl("Your note")} aria-label={tl("Your note")} onChange={e=>setNote(e.target.value)}/><div className="tools"><button onClick={save}>{tl("Save note")}</button><button onClick={()=>{setNote(h.note||'');setEd(false)}}>{tl("Cancel")}</button></div></>
      :h.note?<button className="hlnoted" onClick={()=>setEd(true)} title={tl("Edit note")}>{h.note}</button>:<button className="link hladd" onClick={()=>setEd(true)}>{tl("Add a note")}</button>}</div>
    <button className="ic sm" aria-label={tl("Remove highlight")} title={tl("Remove")} onClick={onDrop}><Trash2 size={15}/></button></div>}
// "Not clear?" on a marked phrase. Step one stays on the server: where the phrase sits in the topic and in the student's own notes, and a kept AI answer if there is one.
// Step two, only if the student asks for it, sends the AI the names of the program, semester, course and topic and the phrase. Never the notes.
function DoubtBox({tid,phrase,close,toast}){
  const [d,setD]=useState(null),[ans,setAns]=useState(null),[busy,setBusy]=useState(false),[err,setErr]=useState('')
  useEffect(()=>{setD(null);setAns(null);setErr('');api(`/topics/${tid}/doubt`,{method:'POST',body:{phrase}}).then(setD).catch(e=>{toast(e.message);close()})},[tid,phrase])
  const ask=async()=>{setBusy(true);setErr('');try{setAns(await api(`/topics/${tid}/doubt/ask`,{method:'POST',body:{phrase}}))}catch(e){setErr(e.message)}setBusy(false)}
  const shown=ans||(d?.saved?{text:d.saved,cached:true}:null)
  return <><div className="tools" style={{justifyContent:'space-between'}}><b>{tl("Not clear?")}</b><button className="ic sm" aria-label={tl("Close")} onClick={close}><X size={16}/></button></div>
    <p className="hltext" style={{marginTop:8}}>“{phrase}”</p>
    {!d?<Skeleton/>:<>
      {d.where&&<small className="known">{[d.where.program,d.where.semester,d.where.course,d.where.topic].filter(Boolean).join(' › ')}</small>}
      <h4 style={{margin:'14px 0 4px'}}>{tl("In your topic")}</h4>
      {d.passage?<p className="prose">{d.passage}</p>:<p className="known">{tl("This exact phrase is not in the topic text. It may be in a picture or formula.")}</p>}
      {d.my_passage&&<><h4 style={{margin:'14px 0 4px'}}>{tl("In your own notes")}</h4><p className="prose">{d.my_passage}</p></>}
      {shown?<><h4 style={{margin:'14px 0 4px'}}>{tl("Explained")}</h4>{shown.cached&&<span className="chip">{tl("Saved answer · nothing was sent")}</span>}{shown.support?<p>{shown.text}</p>:<div className="prose"><Md>{shown.text}</Md></div>}</>
        :<><button className="btn" disabled={busy} onClick={ask}><Sparkles size={16}/> {busy?tl("Thinking…"):tl("Still not clear? Ask AI")}</button>
          <p className="known">{tl("Only the names of your program, semester, course and topic and this phrase are sent. Your notes never are.")}{d.ai_left!=null&&d.ai_left<=10?' '+tl("{n} left today.",{n:d.ai_left}):''}</p>
          {err&&<p className="known">{err}</p>}</>}</>}</>}
function Reader({t,auto,toast,onList,close}){
  const [list,setList]=useState(null),[panel,setPanel]=useState(false),[doubt,setDoubt]=useState(null),[noteFor,setNoteFor]=useState(null),[fs,setFs]=useState(!!document.fullscreenElement),box=useRef(null),frame=useRef(null),hl=useRef(null),now=useRef([])
  const inter=t.content_format==='interactive',ready=list!==null
  now.current=list||[]
  useEffect(()=>{api(`/topics/${t.id}/highlights`).then(r=>setList(r.items)).catch(e=>{toast(e.message);setList([])})},[t.id,toast])
  useEffect(()=>{if(list)onList?.(list)},[list,onList])
  useEffect(()=>{document.body.style.overflow='hidden';if(auto)document.documentElement.requestFullscreen?.().catch(()=>{/* the browser wants a tap first: the button is there */})
    const f=()=>setFs(!!document.fullscreenElement),k=e=>{if(e.key==='Escape'&&!document.fullscreenElement)close()}
    document.addEventListener('fullscreenchange',f);addEventListener('keydown',k)
    return()=>{document.body.style.overflow='';document.removeEventListener('fullscreenchange',f);removeEventListener('keydown',k);if(document.fullscreenElement)document.exitFullscreen().catch(()=>{})}},[auto,close])
  // the explanation of a passage: written when it is highlighted (and AI is on), shown in a small card, kept on the highlight
  const [exp,setExp]=useState(null),[aiOn,setAiOn]=useState(false)
  useEffect(()=>{api('/ai/status').then(r=>setAiOn(!!r.available)).catch(()=>{})},[])
  const explain=useCallback(async hid=>{const have=now.current.find(x=>x.id===+hid)?.explain;if(have){setExp({hid:+hid,...have});return}
    setExp({hid:+hid,busy:true});try{const x=(await api(`/me/highlights/${hid}/explain`,{method:'POST'})).explain;setExp({hid:+hid,...x});setList(l=>l.map(y=>y.id===+hid?{...y,explain:x}:y))}catch(e){setExp({hid:+hid,err:e.message})}},[])
  const save=useCallback(async h=>{const r=await api(`/topics/${t.id}/highlights`,{method:'POST',body:{text:String(h.text||'').slice(0,5000),prefix:String(h.prefix||'').slice(-200),color:h.color||'coral'}});setList(l=>[...l,r]);if(aiOn)setTimeout(()=>explain(r.id),0);return r},[t.id,aiOn,explain])
  const remove=useCallback(async id=>{await api('/me/highlights/'+id,{method:'DELETE'});setList(l=>l.filter(x=>x.id!==+id))},[])
  const recolor=useCallback(async(id,color)=>{const r=await api('/me/highlights/'+id,{method:'PATCH',body:{color}});setList(l=>l.map(x=>x.id===r.id?r:x));return r},[])
  const noteOn=useCallback(id=>{setPanel(true);setNoteFor(+id)},[])
  useEffect(()=>{if(!ready||inter||!box.current||!window.zgHighlighter)return
    const loud=f=>(...a)=>f(...a).catch(e=>{toast(e.message);throw e})
    hl.current=window.zgHighlighter.attach(box.current,{list:now.current,save:loud(save),remove:loud(remove),update:loud((id,c)=>recolor(id,c.color)),note:noteOn,doubt:p=>{setPanel(false);setDoubt(p)},...(aiOn?{explain}:{}),doubtLabel:tl("Not clear?")})
    return()=>{hl.current?.detach();hl.current=null}},[ready,inter,save,remove,recolor,noteOn,toast,aiOn,explain])
  useEffect(()=>{if(!ready||!inter)return
    const win=()=>frame.current?.contentWindow,reply=(k,d)=>win()?.postMessage({zg:1,k,...d},'*')
    const on=async e=>{const d=e.data;if(!win()||e.source!==win()||!d||d.zg!==1)return  // only our own frame, and only these requests
      if(d.type==='ready')win().postMessage({zg:1,type:'init',list:now.current.map(({id,text,prefix,color})=>({id,text,prefix,color}))},'*')
      else if(d.type==='save'){try{const h=await save(d);reply(d.k,{id:h.id})}catch(er){toast(er.message);reply(d.k,{error:1})}}
      else if(d.type==='remove'){try{await remove(+d.id);reply(d.k,{})}catch(er){toast(er.message);reply(d.k,{error:1})}}
      else if(d.type==='update'){try{await recolor(+d.id,String(d.color));reply(d.k,{})}catch(er){toast(er.message);reply(d.k,{error:1})}}
      else if(d.type==='note')noteOn(d.id)
      else if(d.type==='explain'&&aiOn)explain(+d.id)
      else if(d.type==='store'&&d.data&&typeof d.data==='object'){const data=Object.fromEntries(Object.entries(d.data).filter(([,v])=>typeof v==='string'))  // the page's localStorage, kept for this person
        api(`/topics/${t.id}/store`,{method:'PUT',body:{data}}).catch(er=>toast(er.message))}}
    addEventListener('message',on);return()=>removeEventListener('message',on)},[ready,inter,save,remove,recolor,noteOn,toast,t.id,aiOn,explain])
  const goTo=id=>{if(inter)frame.current?.contentWindow?.postMessage({zg:1,type:'scroll',id},'*');else hl.current?.scrollTo(id);if(innerWidth<900)setPanel(false)}
  const drop=async id=>{try{await remove(id);if(inter)frame.current?.contentWindow?.postMessage({zg:1,type:'unpaint',id},'*');else hl.current?.remove(id)}catch(e){toast(e.message)}}
  const toggleFs=()=>document.fullscreenElement?document.exitFullscreen().catch(()=>{}):document.documentElement.requestFullscreen?.().catch(()=>toast(tl("Full screen is not available here")))
  return <div className="reader" role="dialog" aria-modal="true" aria-label={t.title}>
    <div className="rbar"><button className="ic" aria-label={tl("Close")} title={tl("Close")} onClick={close}><X size={20}/></button>
      <span className="rtitle"><b>{t.title}</b><small>{[t.course,t.unit].filter(Boolean).join(' › ')}</small></span>
      <span className="rhint">{tl("Select text to highlight it")}</span>
      <button className={'tool rhl'+(panel?' on':'')} aria-expanded={panel} onClick={()=>setPanel(!panel)}><Highlighter size={15}/> {list?.length||0}<span className="rlab">{" "}{tl("highlight")}{list?.length===1?'':'s'}</span></button>
      <button className="ic" aria-label={fs?tl("Exit full screen"):tl("Full screen")} title={fs?tl("Exit full screen"):tl("Full screen")} onClick={toggleFs}>{fs?<Minimize2 size={19}/>:<Maximize2 size={19}/>}</button></div>
    <div className="rmain">
      {inter?(ready&&<iframe ref={frame} className="rframe" title={t.title} src={t.frame_url} sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox allow-modals allow-forms allow-downloads"/>)
        :<div className="rscroll"><div className="prose rtext" ref={box}>{ready?<Content text={t.content} format={t.content_format}/>:<Skeleton/>}</div></div>}
      {doubt&&<aside className="rpanel" aria-label={tl("Not clear?")}><DoubtBox tid={t.id} phrase={doubt} close={()=>setDoubt(null)} toast={toast}/></aside>}
      {!doubt&&panel&&<aside className="rpanel" aria-label={tl("Your highlights")}><b>{tl("Your highlights")}</b><p className="known">{tl("Select text and pick a colour. Tap a highlight to change its colour, add a note or remove it.")}</p>
        {list?.length?<Paged rows={list} render={h=><HlItem key={h.id} h={{...h,tid:t.id}} toast={toast} focus={noteFor===h.id} onExplain={aiOn?()=>explain(h.id):null} onGo={()=>goTo(h.id)} onSaved={r=>{setList(l=>l.map(x=>x.id===r.id?r:x));setNoteFor(null)}} onDrop={()=>drop(h.id)}/>}/>:<p className="known">{tl("None yet.")}</p>}</aside>}</div>
    {exp&&<div className="rexp" role="status"><div className="rexph"><small>{tl("What this means")}</small><button className="ic sm" aria-label={tl("Close")} onClick={()=>setExp(null)}><X size={15}/></button></div>
      <p className="rexpq">“{(list?.find(x=>x.id===exp.hid)?.text||'').slice(0,140)}{(list?.find(x=>x.id===exp.hid)?.text||'').length>140?'…':''}”</p>
      {exp.busy?<p className="known">{tl("Thinking…")}</p>:exp.err?<p className="known">{exp.err}</p>:<><Md>{exp.text||''}</Md><FlagLink source="topic" id={exp.id} topicId={t.id}/></>}</div>}</div>}

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
    if(htmlF.length>1||cfgF.length>1)return toast(tl("Choose one HTML file and one config file at a time"))
    if(!htmlF.length&&!cfgF.length)return toast(tl("Choose an HTML file, a config .md file, or both"))
    if((f.content.trim()||f.question_pattern.trim()||f.sample_content.trim()||f.guideline.trim())&&!await confirm({title:tl("Replace what is in the form?"),body:tl("The boxes the files fill in are replaced. Nothing is saved until you save."),ok:tl("Fill from files")}))return
    setBusy(true);try{const images={};for(const x of imgs)images[x.name]=await uploadImg(x)
      const r=await api('/topics/from-files',{method:'POST',body:{unit_id:+(f.unit_id||unitId),html:htmlF.length?await htmlF[0].text():'',config:cfgF.length?await cfgF[0].text():'',images,scripts:f.content_format==='interactive'}})
      setF(cur=>({...cur,...['title','content','content_format','question_pattern','sample_content','guideline'].reduce((o,k)=>r[k]!==undefined?{...o,[k]:r[k]}:o,{}),...(r.published!==undefined?{published:r.published}:{}),...(r.learning_due_at?{due:r.learning_due_at}:{})}))
      setFromFiles({names:[...htmlF,...cfgF].map(x=>x.name),warnings:r.warnings,images:r.images_saved+imgs.length});setPrev(!!r.content&&['html','interactive'].includes(r.content_format));toast(tl("Filled from {v}. Check it, then save.",{v:[...htmlF,...cfgF].map(x=>x.name).join(' and ')}))}catch(er){toast(er.message)}setBusy(false)}
  const pickImg=async e=>{const file=e.target.files[0];e.target.value='';if(!file)return;if(file.size>3*1024*1024)return toast(tl("Image is too large. Keep it under 3 MB."))
    setUp(true);try{const r=await fetch('/api/uploads',{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:file});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Upload failed')
      const pos=taRef.current?.selectionStart??f.content.length,tag=html||inter?`\n<p><img src="${d.url}" alt="Describe the image"></p>\n`:`\n\n![Describe the image](${d.url})\n\n`;setF({...f,content:f.content.slice(0,pos)+tag+f.content.slice(pos)});toast(tl("Image added"))}catch(er){toast(er.message)}setUp(false)}
  const all=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared&&c.editable).flatMap(c=>c.units.map(n=>({...n,course_id:c.id,label:`${c.name} › ${n.name}`})))))
  const units=role==='admin'?all:all.filter(n=>n.course_id===cid)  // faculty move a topic only between units of its own course
  const here=all.find(n=>n.id===+f.unit_id)
  const save=async()=>{setBusy(true);try{await api(edit?'/topics/'+edit.id:'/topics',{method:edit?'PUT':'POST',body:{...f,due:undefined,unit_id:+f.unit_id,published:f.published!==false,learning_due_at:f.due?new Date(f.due).toISOString():null}});toast(edit?tl("Changes saved"):tl("Topic added"));done()}catch(e){toast(e.message)}setBusy(false)}
  const T=(k,l,ph)=><><label>{l}</label><textarea placeholder={ph} value={f[k]} onChange={set(k)}/></>
  return <><Bar title={edit?tl("Edit topic"):tl("New topic")} sub={here?.label} back={cancel}/><div className="main">
    {!imp&&!fromFiles&&<button className="tool" style={{marginTop:0}} onClick={()=>setImp(true)}><Upload size={14}/>{" "}{tl("Fill from files (HTML and config)")}</button>}
    {(imp||fromFiles)&&<div className="qbox" style={{marginTop:0}}><b>{tl("Fill from files")}</b><p className="known" style={{margin:'4px 0 8px'}}>{FILES_HELP}</p>
      <input ref={filesRef} type="file" hidden multiple accept=".html,.htm,.md,.markdown,.txt,text/html,text/markdown,image/png,image/jpeg,image/gif,image/webp" onChange={pickFiles}/>
      <div className="two"><button className="btn" style={{margin:0}} disabled={busy} onClick={()=>filesRef.current.click()}><Upload size={16}/> {busy?tl("Reading…"):tl("Choose files")}</button><button className="btn ghost" style={{margin:0}} onClick={()=>download('topic-config.md',TOPIC_CONFIG_TEMPLATE)}>{tl("Config template")}</button></div>
      {fromFiles&&<div role="status" style={{marginTop:10}}><p className="known" style={{margin:0}}>{tl("Filled from {names}{v}.",{names:fromFiles.names.join(' and '),v:fromFiles.images?` · ${pl(fromFiles.images,'image')}`:''})}</p>
        {fromFiles.warnings.map((w,i)=><p key={i} className="known" style={{margin:'4px 0 0',color:'var(--warn)'}}>{w}</p>)}</div>}</div>}
    {edit&&units.length>1&&<><label>{tl("Unit")}</label><select value={f.unit_id} onChange={set('unit_id')}>{units.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></>}
    <label>{tl("Topic title")}</label><input value={f.title} onChange={set('title')} placeholder={tl("First law of thermodynamics")}/>
    <label>{tl("Topic content")}</label><div className="seg" style={{gridTemplateColumns:'1fr 1fr 1fr',margin:'0 0 8px'}} role="group" aria-label={tl("Content format")}>{[['markdown',tl("Markdown")],['html',tl("HTML")],['interactive',tl("HTML + JavaScript")]].map(([k,l])=><button key={k} type="button" className={f.content_format===k?'on':''} aria-pressed={f.content_format===k} onClick={()=>setF({...f,content_format:k})}>{l}</button>)}</div>
    <div className="tools"><button type="button" disabled={up} onClick={()=>fileRef.current.click()}>{up?tl("Uploading…"):tl("Add image")}</button><button type="button" onClick={()=>setPrev(!prev)}>{prev?tl("Back to editing"):tl("Preview")}</button></div>
    <input ref={fileRef} type="file" hidden accept="image/png,image/jpeg,image/gif,image/webp" onChange={pickImg}/>
    {prev&&inter?(f.content?(frameUrl?<iframe className="pframe" title={tl("Preview")} src={frameUrl} sandbox="allow-scripts allow-popups allow-modals allow-forms"/>:<Skeleton/>):<div className="prose"><Md>{tl("Nothing to preview yet.")}</Md></div>)
      :prev?<div className="prose">{!f.content?<Md>{tl("Nothing to preview yet.")}</Md>:html?<Body text={shown} format="html"/>:<Md>{f.content}</Md>}</div>:<textarea ref={taRef} className={html||inter?'code':''} placeholder={html||inter?tl("HTML (or choose an HTML file above)"):tl("Paste notes or syllabus text")} value={f.content} onChange={set('content')}/>}
    <p className="known">{inter?tl("The page runs as it is, with its own scripts and styles, in a sandbox: it can't reach the app or anyone's account (so it also can't keep data in the browser between visits). Students open it full screen and can highlight its text."):html?tl("HTML content shows as it is laid out in the file. Scripts, styles, forms and outside frames are removed when you save, so the page takes the app's look in light and dark mode."):tl("Equations: $x^2$ inline. For a centred block, put $$ on its own line above and below the equation. Chemistry: $\\ce{CaCO3 + CO2 + H2O -> Ca(HCO3)2}$")}</p>{T('question_pattern','Question pattern','e.g. 2 marks: define · 13 marks: derive + numerical')}
    <label>{tl("Learning deadline")}</label><div className="qopt"><input type="datetime-local" aria-label={tl("Learning deadline")} value={f.due} onChange={set('due')}/>{f.due&&<button type="button" className="tool" onClick={()=>setF({...f,due:''})}>{tl("No deadline")}</button>}</div>
    <p className="known" style={{marginTop:4}}>{f.due?tl("Students should have learnt this topic by then. They can still open it afterwards."):tl("No deadline")}</p>
    <label className="chk"><input type="checkbox" checked={f.published!==false} onChange={e=>setF({...f,published:e.target.checked})}/>{" "}{tl("Published (students can see this topic)")}</label>
    {T('sample_content','Sample content','A sample question and answer')}{T('guideline','How an answer should be','Intro, labelled diagram, steps, units, conclusion')}
    <button className="btn" disabled={busy||!f.title.trim()} onClick={save}>{edit?tl("Save changes"):tl("Save topic")}</button></div></>}
function UnitSheet({un,cid,courses,close,done,toast}){  // courses is given to admins only: moving a unit to another course is theirs to do
  const isNew=!un.id,[f,setF]=useState({name:un.name||'',course:cid}),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{await api(isNew?'/units':'/units/'+un.id,{method:isNew?'POST':'PUT',body:{name:f.name,course_id:+f.course}});toast(isNew?tl("Unit added"):tl("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?tl("New unit"):tl("Edit unit")}</h3>
    <label>{tl("Name")}</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} onKeyDown={e=>e.key==='Enter'&&f.name.trim()&&save()} placeholder={tl("Unit 1: Basic concepts")} autoFocus/>
    {!isNew&&courses&&<><label>{tl("Course")}</label><select value={f.course} onChange={e=>setF({...f,course:+e.target.value})}>{courses.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></>}
    <button className="btn" disabled={busy||!f.name.trim()} onClick={save}>{isNew?tl("Add unit"):tl("Save changes")}</button></Sheet>}

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
  const upload=async e=>{const fs=[...e.target.files];e.target.value='';for(const f of fs)if(tooBig(f))toast(tl("{name} is over {MAX_FILE_MB} MB. Split it into smaller files.",{name:f.name,MAX_FILE_MB:MAX_FILE_MB}));else await run('file',async()=>{const r=await fetch('/api'+base+'/files?name='+encodeURIComponent(f.name),{method:'POST',headers:{'Content-Type':'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(tl(j.detail||'Upload failed'));if(j.status==='reading')toast(tl("{name} is scanned pages. Reading them now; you can stay or come back later.",{name:f.name}))},f.name.toLowerCase().endsWith('.pdf')?'':tl("Added {name}",{name:f.name}))}
  const match=m=>run(m,()=>api(base+'/match',{method:'POST',body:{method:m}}),'Matched to the syllabus. Check it below, then save.')
  const file=(i,tid)=>{setPick(null);return run('sec',()=>api(base+'/sections',{method:'PUT',body:{sections:v.sections.map((x,k)=>({from:x.from,to:x.to,topic_id:k===i?(tid?+tid:null):x.topic_id}))}}))}
  const read=async x=>{const k=x.from;if(open[k]!==undefined)return setOpen({...open,[k]:undefined});try{const r=await api(`${base}/preview?start=${x.from}&end=${x.to}`);setOpen({...open,[k]:r.content})}catch(e){toast(e.message)}}
  if(!v)return <><Bar title={tl("Your material")} back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const names=new Map(v.syllabus.flatMap(u=>u.topics.map(x=>[x.id,x.title]))),filed=new Set(v.sections.map(x=>x.topic_id).filter(Boolean)),missing=v.syllabus.flatMap(u=>u.topics.filter(x=>!filed.has(x.id)).map(x=>x.title)),noAi=!v.ai_available||v.ai_left===0
  return <><Bar title={tl("Your material")} sub={name} back={back}/><div className="main">
    <p className="known" style={{marginTop:0}}>{tl("Your college sets the course, units and topics. Bring your own notes or book chapters and they are filed under the right topics, so you study the syllabus in your own words. Only you see them.")}</p>
    <h3>{tl("1. Your files")}</h3>
    {v.sources.length?<Paged rows={v.sources} render={(x,i)=><div className="row" key={i}><div>{x.name}<small role={x.status==='reading'?'status':undefined}>{srcLine(x)}</small></div><button className="ic sm" aria-label={tl("Remove {name}",{name:x.name})} disabled={!!busy} onClick={()=>run('drop',()=>api(base+'/sources/'+i,{method:'DELETE'}))}><X size={16}/></button></div>}/>:<p className="known">{tl("No files yet. PDFs, Word (.docx) and text files work, up to {MAX_FILE_MB} MB each.",{MAX_FILE_MB:MAX_FILE_MB})}{v.ocr_available?tl(" Scanned PDFs are read too; that takes a few seconds a page."):tl(" Scanned PDFs can't be read on this server yet.")}</p>}
    <div className="two"><button className="btn ghost" disabled={!!busy} onClick={()=>fileRef.current.click()}><Upload size={16}/> {busy==='file'?tl("Reading…"):tl("Add a file")}</button><button className="btn ghost" disabled={!!busy} onClick={()=>setPaste({text:''})}>{tl("Paste text")}</button></div>
    <input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.txt,.md" onChange={upload}/>
    {v.sources.length>0&&<><h3>{tl("2. File it under the syllabus")}</h3>
      {v.reading&&<p className="known" role="status">{tl("Your scanned pages are still being read. Matching starts once they are done.")}</p>}
      {v.ai_available&&<button className={'btn'+(noAi?' ghost':'')} disabled={!!busy||noAi||v.reading} onClick={()=>match('ai')}><Sparkles size={16}/> {busy==='ai'?tl("Matching…"):tl("Match with AI")}</button>}
      <button className={'btn'+(noAi?'':' ghost')} disabled={!!busy||v.reading} onClick={()=>match('headings')}>{busy==='headings'?tl("Matching…"):v.ai_available?tl("Match by headings (no AI)"):tl("Match by headings")}</button>
      {noAi&&<p className="known">{v.ai_available?tl("No AI requests are left today. "):''}{tl("Matching by headings works best when your notes use the topic names as headings.")}</p>}</>}
    {v.sections.length>0&&<><h3>{tl("3. Check where each part goes")}</h3>
      <p className="known">{tl("Your notes cover {covered} of {topics} topics.",{covered:v.covered,topics:v.topics})}{missing.length>0&&tl(" Not covered yet: {missing}{v}.",{missing:missing.slice(0,6).join(', '),v:missing.length>6?' and '+(missing.length-6)+' more':''})}</p>
      {<Paged rows={v.sections} render={(x,i)=><div className="qbox" key={x.from}>{x.heading?<b>{x.heading}</b>:<span style={{display:'block'}}>“{x.excerpt.slice(0,80)+(x.excerpt.length>80?'…':'')}”</span>}<small className="known" style={{display:'block'}}>{tl("Part {v} · {words} words",{v:i+1,words:x.words})}</small>
        <div className="sfile">{x.topic_id?<span className="chip">{names.get(x.topic_id)||tl("Topic")}</span>:<span className="chip none">{tl("Left out")}</span>}<button className="tool" disabled={!!busy} aria-expanded={pick===i} onClick={()=>setPick(pick===i?null:i)}>{pick===i?tl("Cancel"):x.topic_id?tl("Change"):tl("File it")}</button></div>
        {pick===i&&<select aria-label={tl("Topic for part {i}{v}",{i:i,v:1})} autoFocus value={x.topic_id||''} disabled={!!busy} onChange={e=>file(i,e.target.value)}><option value="">{tl("Not in the syllabus (left out)")}</option>{v.syllabus.map(u=><optgroup key={u.id} label={u.name}>{u.topics.map(tp=><option key={tp.id} value={tp.id}>{tp.title}</option>)}</optgroup>)}</select>}
        <button className="tool" onClick={()=>read(x)}>{open[x.from]!==undefined?tl("Hide"):tl("Read it")}</button>{open[x.from]!==undefined&&<div className="prose"><Md>{open[x.from]}</Md></div>}</div>}/>}
      <button className="btn" disabled={!!busy||!filed.size} onClick={()=>run('save',()=>api(base+'/save',{method:'POST'}),'Saved. Open a topic to study your notes.')}>{v.saved_at?tl("Save again to my topics"):tl("Save to my topics")}</button>
      {v.saved_at&&<p className="known">{tl("Last saved {n}. Saving again rebuilds your notes from this material; your progress and quiz results stay.",{n:when(v.saved_at)})}</p>}</>}
    {v.sources.length>0&&<p style={{marginTop:28}}><button className="link" style={{color:"var(--bad)"}} disabled={!!busy} onClick={async()=>{if(await confirm({title:tl("Remove your material?"),body:tl("The notes it made in this course are removed too. Your progress and quiz results stay."),ok:tl("Remove"),danger:true}))run('del',()=>api(base,{method:'DELETE'}),'Your material was removed')}}>{tl("Remove my material from this course")}</button></p>}</div>
    {paste&&<Sheet close={()=>setPaste(null)}><h3>{tl("Paste text")}</h3><textarea aria-label={tl("Text to add")} value={paste.text} onChange={e=>setPaste({text:e.target.value})} placeholder={tl("Paste your notes. Lines starting with # are headings.")}/>
      <button className="btn" disabled={!paste.text.trim()||!!busy} onClick={async()=>{await run('paste',()=>api(base+'/text',{method:'POST',body:{text:paste.text}}),'Added');setPaste(null)}}>{tl("Add")}</button></Sheet>}</>}

// every highlight this person has made, newest first: search (passage, note or topic), a colour filter and pages; a highlight opens its topic
function MyHighlights({toast,role,head}){
  const [q,setQ]=useState(''),[color,setColor]=useState(''),[t,setT]=useState(null)
  const {items,total,page,setPage,reload}=usePaged(o=>`/me/highlights?q=${encodeURIComponent(q)}&color=${color}&limit=${PAGE}&offset=${o}`,[q,color],toast)
  if(t)return <Topic id={t} back={()=>{setT(null);reload()}} toast={toast} role={role}/>
  const drop=async h=>{try{await api('/me/highlights/'+h.id,{method:'DELETE'});toast(tl("Highlight removed"));reload()}catch(e){toast(e.message)}}
  return <><Bar title={head?tl("Saved"):tl("My highlights")} sub={q||color?matches(total):pl(total,'highlight')}/><div className="main">{head}
    <div className="search"><Search size={18}/><input type="search" aria-label={tl("Search your highlights")} placeholder={tl("Search your highlights, notes or topics")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="chips wrap" role="group" aria-label={tl("Colour")} style={{marginTop:12}}>{[['',tl('All colours')],...Object.keys(HL_COL).map(c=>[c,tl(c[0].toUpperCase()+c.slice(1))])].map(([k,l])=><button key={l} className={'sbtn'+(color===k?' on':'')} aria-pressed={color===k} onClick={()=>setColor(k)}>{k&&<i className="hldot" style={{background:HL_COL[k]}}/>}{l}</button>)}</div>
    {items.map(h=><HlItem key={h.id} h={h} toast={toast} where={[h.topic,h.course].filter(Boolean).join(' · ')} onGo={()=>setT(h.topic_id)} onSaved={reload} onDrop={()=>drop(h)}/>)}
    {!items.length&&<p className="known">{q||color?tl("No highlight matches."):tl("No highlights yet. Open a topic, select some text and pick a colour.")}</p>}
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
    if(!docs.length)return toast(tl("Choose .html or .md files, or a folder with them"))
    if(docs.length>200)return toast(tl("Choose up to 200 files at a time"))
    const big=imgs.find(x=>x.size>3*1024*1024);if(big)return toast(tl("{name} is over 3 MB. Make it smaller first.",{name:big.name}))
    try{setBusy(`Reading ${pl(docs.length,'file')}…`);const fs=await Promise.all(docs.map(async x=>({name:x.webkitRelativePath||x.name,text:await x.text()}))),im={}
      for(const [i,x] of imgs.entries()){setBusy(`Uploading images: ${i+1} of ${imgs.length}…`);im[x.name]=await uploadImg(x)}
      setFiles(fs);setImages(im);await preview({files:fs,images:im})}catch(er){toast(er.message)}setBusy('')}
  const add=async()=>{setBusy('Adding the topics…');try{const r=await send(false);toast(tl("{n} added to {name}",{n:pl(r.created,'topic'),name:unit.name}));done()}catch(e){toast(e.message);setBusy('')}}
  const ok=rows?.ready||0
  return <Sheet page close={close}><h3>{tl("Upload topic files to")}{" "}{unit.name}</h3>
    <p className="known">{tl("One topic per file. Choose .html or .md files, or a whole folder: images in it are matched to the pages by file name. Topics are added in file-name order (2 before 10), after the topics already here. A Markdown file with the config sections (see Config template in the topic editor) also fills in the question pattern, sample answer and guideline.")}</p>
    <label className="chk"><input type="checkbox" checked={scripts} onChange={e=>{setScripts(e.target.checked);preview({scripts:e.target.checked})}}/>{" "}{tl("Keep each HTML page's JavaScript (HTML + JavaScript, run in a sandbox)")}</label>
    <label className="chk"><input type="checkbox" checked={pub} onChange={e=>{setPub(e.target.checked);preview({published:e.target.checked})}}/>{" "}{tl("Publish them now (otherwise they are drafts)")}</label>
    <div className="two"><button className="btn" disabled={!!busy} onClick={()=>pick.current.click()}><Upload size={16}/>{" "}{tl("Choose files")}</button><button className="btn ghost" disabled={!!busy} onClick={()=>folder.current.click()}>{tl("Choose a folder")}</button></div>
    <input ref={pick} type="file" hidden multiple accept=".html,.htm,.md,.markdown,.txt,image/png,image/jpeg,image/gif,image/webp" onChange={choose}/>
    <input ref={folder} type="file" hidden multiple webkitdirectory="" onChange={choose}/>
    {busy&&<p className="known" role="status">{busy}</p>}
    {rows&&<><b className="sec" style={{display:'block'}}>{ok}{" "}{tl("of {n} ready",{n:pl(rows.topics.length,'file')})}</b>
      {rows.topics.map((r,i)=><div key={i} className="row"><div>{r.ok?<b>{r.title}</b>:<s>{r.title||r.file}</s>}<small>{r.file}{r.ok?` · ${FMT[r.format]} · ${r.published?'published':'draft'}`:''}</small>{r.warnings.map((w,j)=><small key={j} className="warnline">{w}</small>)}</div></div>)}
      <button className="btn" disabled={!ok||!!busy} onClick={add}>{tl("Add")}{" "}{pl(ok,'topic')}</button></>}</Sheet>}
// Saved: a student's bookmarks and highlights in one place
function Saved({toast,role}){
  const [tab,setTab]=useState('bookmarks'),head=<Tabs label={tl("Saved")} items={[['bookmarks',tl("Bookmarks")],['highlights',tl("Highlights")]]} value={tab} onChange={setTab}/>
  return tab==='bookmarks'?<Bookmarks toast={toast} role={role} head={head}/>:<MyHighlights toast={toast} role={role} head={head}/>}
function Bookmarks({toast,role,head}){
  const [tree,setTree]=useState(null),[sem,setSem]=useState(null),[course,setCourse]=useState(null),[t,setT]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t])
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast} role={role}/>
  if(!tree)return <><Bar title={head?tl("Saved"):tl("Bookmarks")}/><div className="main">{head}<div className="sk"/><div className="sk"/></div></>
  const marks=u=>u.topics.filter(x=>x.bookmarked),cnt=c=>c.units.reduce((n,u)=>n+marks(u).length,0)
  const sems=tree.flatMap(p=>p.semesters.map(sm=>({...sm,prog:p.name,courses:sm.courses.filter(c=>cnt(c)>0)}))).filter(sm=>sm.courses.length)
    .sort((a,b)=>a.prog.localeCompare(b.prog)||(a.number??99)-(b.number??99)||a.id-b.id)
  const multi=new Set(sems.map(x=>x.prog)).size>1,total=sems.reduce((n,x)=>n+x.courses.reduce((m,c)=>m+cnt(c),0),0)
  const sm=sems.find(x=>x.id===sem)||sems[0],co=sm?.courses.find(x=>x.id===course)||sm?.courses[0]
  const drop=async id=>{try{await api(`/topics/${id}/bookmark`,{method:'DELETE'});setTree(unmarked(tree,id));toast(tl("Bookmark removed"))}catch(e){toast(e.message)}}
  return <><Bar title={head?tl("Saved"):tl("Bookmarks")} sub={total?tl(total===1?'{n} topic saved':'{n} topics saved',{n:total}):tl("Nothing saved yet")}/><div className="main">{head}
    {!sm&&<p className="known">{tl("Open any topic and tap the bookmark icon to save it here. It shows only the topics you saved, grouped by semester or year, course and unit.")}</p>}
    {sm&&<>
      <div className="chips" role="group" aria-label={tl("Semester or year")}>{sems.map(x=><button key={x.id} className={'sbtn'+(x.id===sm.id?' on':'')} aria-pressed={x.id===sm.id} onClick={e=>{setSem(x.id);setCourse(null);tabTo(e)}}>
        <span className="lbl">{multi&&x.prog+' · '}{x.name}</span><em>{x.courses.reduce((n,c)=>n+cnt(c),0)}</em></button>)}</div>
      <div className="tabs scroll" role="tablist" aria-label={tl("Course")}>{sm.courses.map(c=><button key={c.id} role="tab" aria-selected={c.id===co.id} className={c.id===co.id?'on':''} onClick={e=>{setCourse(c.id);tabTo(e)}}>
        <span className="lbl">{c.name}</span><em>{cnt(c)}</em></button>)}</div>
      <Paged rows={co.units.flatMap(u=>marks(u).map(x=>({u,x})))} render={({u,x},i,j,pg)=><Fragment key={x.id}>{(!j||pg[j-1].u!==u)&&<h3 className="sec">{u.name}</h3>}
        <div className="card"><button className="hit" onClick={()=>setT(x.id)}><span className="dot" style={{background:COL[i%5]}}>{x.title[0]}</span><div><b>{x.title}</b></div><Mark s={x.status}/></button>
          <button className="ic sm on" aria-label={tl("Remove bookmark: {title}",{title:x.title})} onClick={()=>drop(x.id)}><Bookmark size={16} fill="currentColor"/></button></div></Fragment>}/>
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
  <button className={'btn'+(o.danger?' danger':'')} onClick={()=>answer(true)}>{o.ok||tl("Confirm")}</button><button className="btn ghost" onClick={()=>answer(false)}>{tl("Cancel")}</button></Sheet>
const useConfirm=()=>useContext(Ctx).confirm
const Toast=({msg})=>msg?<div className="toast" role="status">{msg}</div>:null
const Skeleton=({rows=3})=><div aria-busy="true" aria-label={tl("Loading")}>{Array.from({length:rows},(_,i)=><div className="sk" key={i}/>)}</div>
// numbered pages under a list: Previous, page numbers (with … in long lists), Next, and which rows are shown
const pageList=(n,at)=>n<=7?[...Array(n).keys()]:[...new Set([0,1,at-1,at,at+1,n-2,n-1].filter(i=>i>=0&&i<n))].sort((a,b)=>a-b).flatMap((i,j,a)=>j&&i-a[j-1]>1?['…'+i,i]:[i])
function Pager({page,total,onPage,size=PAGE,anchor}){
  const n=Math.ceil(total/size);if(n<=1)return null
  const go=i=>{onPage(i);if(anchor?.current)anchor.current.scrollIntoView({block:'start'});else scrollTo({top:0})}
  return <nav className="pgr" aria-label={tl("Pages")}><small>{page*size+1}{tl("–{Math} of",{Math:Math.min(total,(page+1)*size)})}{" "}{total}</small>
    <span className="pgb"><button className="tool" disabled={page===0} onClick={()=>go(page-1)} aria-label={tl("Previous page")}><ChevronLeft size={16}/></button>
      {pageList(n,page).map(i=>typeof i==='string'?<span key={i} className="gap">…</span>:<button key={i} className={'tool'+(i===page?' on':'')} aria-current={i===page?'page':undefined} onClick={()=>go(i)}>{i+1}</button>)}
      <button className="tool" disabled={page>=n-1} onClick={()=>go(page+1)} aria-label={tl("Next page")}><ChevronRight size={16}/></button></span></nav>}
// the list's rows for the current page; a filter change goes back to page 1, and a page left empty (say after a delete) steps back one
function usePaged(url,deps,toast,size=PAGE){
  const [page,setPage]=useState(0),[items,setItems]=useState([]),[total,setTotal]=useState(0),[n,setN]=useState(0),[ready,setReady]=useState(false),[data,setData]=useState(null)
  useEffect(()=>{setPage(0)},deps)
  useEffect(()=>{const t=setTimeout(()=>api(url(page*size)).then(r=>{if(!r.items.length&&page>0)setPage(page-1);else{setItems(r.items);setTotal(r.total);setData(r);setReady(true)}}).catch(e=>toast(e.message)),250);return()=>clearTimeout(t)},[...deps,page,n])
  return {items,total,page,setPage,ready,data,reload:()=>setN(x=>x+1)}}
// the same for a list the browser already holds: the rows of the current page, back to page 1 when the search, filter or sort changes
function useLocalPage(rows,deps,size=PAGE){
  const [page,setPage]=useState(0)
  useEffect(()=>{setPage(0)},deps)
  const n=Math.max(1,Math.ceil((rows?.length||0)/size)),at=Math.min(page,n-1)
  return {items:(rows||[]).slice(at*size,(at+1)*size),total:rows?.length||0,page:at,setPage}}
// a list the page already holds, ten rows at a time; render gets each row, its place in the whole list, and its place on this page
function Paged({rows,render,size=PAGE}){
  const [page,setPage]=useState(0),top=useRef(),all=rows||[],n=Math.max(1,Math.ceil(all.length/size)),at=Math.min(page,n-1),shown=all.slice(at*size,(at+1)*size)
  if(all.length<=size)return all.map((x,i)=>render(x,i,i,all))
  return <><span ref={top} className="pgtop"/>{shown.map((x,j)=>render(x,at*size+j,j,shown))}<Pager page={at} total={all.length} onPage={setPage} size={size} anchor={top}/></>}
const has=(q,...v)=>{q=q.trim().toLowerCase();return !q||v.some(x=>String(x??'').toLowerCase().includes(q))}
const Opts=({label,value,set,items})=><select aria-label={label} value={value} onChange={e=>set(e.target.value)}>{items.map(([k,l])=><option key={k} value={k}>{l}</option>)}</select>
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
    return <Sheet close={close}><h3>{pl(r.changed,'account')}{" "}{tl("updated")}</h3>
      {r.courses_needing_owner>0&&<p className="known">{pl(r.courses_needing_owner,'course')}{" "}{tl("now {v} no active owner. Assign new owners under Programs.",{v:r.courses_needing_owner===1?'has':'have'})}</p>}
      {r.skipped_count>0&&<div className="qbox"><b>{r.skipped_count}{" "}{tl("skipped")}</b>{r.skipped.slice(0,10).map(x=><p className="known" style={{margin:'4px 0'}} key={x.id}>{x.name}: {srv(x.reason)}</p>)}{r.skipped_count>10&&<p className="known">{tl("…and {v} more.",{v:r.skipped_count-10})}</p>}</div>}
      {r.credentials&&<button className="btn" onClick={()=>download('new-passwords.csv','name,email,password\n'+r.credentials.map(c=>[c.name,c.email,c.password].map(cell).join(',')).join('\n')+'\n')}>{tl("Download the new passwords")}</button>}
      <button className="btn ghost" onClick={close}>{tl("Close")}</button></Sheet>}
  const run=async()=>{setBusy(true);try{done(await api('/admin/users/bulk',{method:'POST',body:{ids,action:act.kind,...(act.kind==='set_placement'?{program_id:+p,semester:s?+s:null}:{})}}))}catch(e){toast(e.message);setBusy(false)}}
  if(act.kind==='set_placement')return <Sheet close={close}><h3>{tl("Move")}{" "}{pl(ids.length,'user')}</h3><p className="known">{tl("Sets the program and semester, year or grade of the selected students. Faculty and admins in the selection are skipped.")}</p>
    <label htmlFor="bp">{tl("Program")}</label><select id="bp" value={p} onChange={e=>{const id=e.target.value;setP(id);if(+s>semsOf(progs,id).length)setS('')}}><option value="">{tl("Choose a program")}</option>{progs.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    <label htmlFor="bs">{termOf(progs,p)}</label><select id="bs" value={s} onChange={e=>setS(e.target.value)}><option value="">{tl("Not set")}</option>{semsOf(progs,p).map(n=><option key={n} value={n}>{termOf(progs,p)} {n}</option>)}</select>
    <button className="btn" disabled={busy||!p} onClick={run}>{busy?tl("Working…"):tl("Move")}</button><button className="btn ghost" onClick={close}>{tl("Cancel")}</button></Sheet>
  const [t,d,l]=BULK_TEXT[act.kind]
  return <Sheet close={close}><h3>{t.replace('these',ids.length===1?'this':'these')}</h3><p className="known">{pl(ids.length,'account')}{" "}{tl("selected.")}{" "}{d}</p>
    <button className={'btn'+(act.kind==='disable'?' danger':'')} disabled={busy} onClick={run}>{busy?tl("Working…"):l}</button><button className="btn ghost" onClick={close}>{tl("Cancel")}</button></Sheet>}
function Users({toast,me}){
  const [q,setQ]=useState(''),[prog,setProg]=useState(''),[sem,setSem]=useState(''),[order,setOrder]=useState('role'),[progs,setProgs]=useState([])
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef(),[selMode,setSelMode]=useState(false),[sel,setSel]=useState([]),[act,setAct]=useState(null)
  const {items,total,page,setPage,reload:load}=usePaged(offset=>`/admin/users?q=${encodeURIComponent(q)}&order=${order}&limit=${PAGE}&offset=${offset}`+(prog?'&program_id='+prog:'')+(sem?'&semester='+sem:''),[q,prog,sem,order],toast)
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name,term:p.term})))).catch(()=>{})},[])
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/users/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/users/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const cell=v=>'"'+String(v).replace(/"/g,'""')+'"',r=bulk?.res,filtered=q||prog||sem,lab=prog?termOf(progs,prog):progs.every(x=>x.term==='Semester')?'Semester':progs.length&&progs.every(x=>x.term==='Grade')?'Grade':'Term'
  if(view)return <UserDetail id={view} me={me} progs={progs} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title={tl("Users")} sub={filtered?matches(total):pl(total,'account')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={tl("Search users")} placeholder={tl("Search name, email, ID, program, semester, year or grade")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters">
      <select aria-label={tl("Filter by program")} value={prog} onChange={e=>{const id=e.target.value;setProg(id);if(+sem>semsOf(progs,id).length)setSem('')}}><option value="">{tl("All programs")}</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select aria-label={tl("Filter by semester, year or grade")} value={sem} onChange={e=>setSem(e.target.value)}><option value="">{lab==='Term'?tl("All terms"):tl("All {lab}s",{lab:lab.toLowerCase()})}</option>{semsOf(progs,prog).map(n=><option key={n} value={n}>{lab} {n}</option>)}</select>
      <select aria-label={tl("Sort by")} value={order} onChange={e=>setOrder(e.target.value)}><option value="role">{tl("Sort: role, then name")}</option><option value="name">{tl("Sort: name")}</option><option value="program">{tl("Sort: program")}</option><option value="semester">{tl("Sort:")}{" "}{lab.toLowerCase()}</option><option value="newest">{tl("Sort: newest first")}</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>{tl("New user")}</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>{tl("Bulk upload")}</button></div>
    <button className="btn ghost" style={{marginTop:10}} aria-pressed={selMode} onClick={()=>{setSelMode(!selMode);setSel([])}}>{selMode?tl("Done selecting"):tl("Select several users")}</button>
    {selMode&&items.length>0&&<div className="selbar"><button className="tool" onClick={()=>setSel(items.map(u=>u.id))}>{tl("Select all {length} shown",{length:items.length})}</button>{sel.length>0&&<button className="tool" onClick={()=>setSel([])}>{tl("Clear")}</button>}</div>}
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead" aria-hidden="true"><span>{tl("Name")}</span><span>{tl("Program")}</span><span>{lab==='Semester'?tl("Sem"):lab}</span></div>}
    {items.map(u=><button key={u.id} className={'utr'+(selMode?' sel':'')+(sel.includes(u.id)?' on':'')} onClick={()=>selMode?setSel(sel.includes(u.id)?sel.filter(i=>i!==u.id):[...sel,u.id]):setView(u.id)} aria-label={tl(selMode?(sel.includes(u.id)?'Deselect {name}':'Select {name}'):'Open {name}',{name:u.name})} aria-pressed={selMode?sel.includes(u.id):undefined}>
      <span className="nm">{selMode&&<span className="tick" aria-hidden="true">{sel.includes(u.id)&&<Check size={14}/>}</span>}<span className="dot" style={{background:COL[u.id%5]}}>{(u.name||'?')[0]}</span><span className="tx"><b>{u.name}</b>{(u.role!=='student'||!u.active||u.self_registered)&&<span className="tags">{u.role!=='student'&&<span className="pill">{u.role==='admin'?tl("Admin"):tl("Faculty")}</span>}{u.self_registered&&<span className="pill">{tl("Self-registered")}</span>}{!u.active&&<span className="pill off">{tl("Disabled")}</span>}</span>}</span></span>
      <span className="pg">{u.program||'—'}</span><span className="sn">{u.semester||'—'}</span></button>)}
    {!items.length&&<p className="known">{filtered?tl("No one matches that search."):tl("No users yet.")}</p>}
    <Pager page={page} total={total} onPage={setPage}/>
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {selMode&&sel.length>0&&<div className="actbar" role="toolbar" aria-label={tl("Actions for selected users")}><b>{sel.length}{" "}{tl("selected")}</b>
      <button className="tool" onClick={()=>setAct({kind:'set_placement'})}>{tl("Move…")}</button><button className="tool" onClick={()=>setAct({kind:'disable'})}>{tl("Disable")}</button><button className="tool" onClick={()=>setAct({kind:'enable'})}>{tl("Enable")}</button><button className="tool" onClick={()=>setAct({kind:'reset_passwords'})}>{tl("Reset passwords")}</button></div>}
    {act&&<BulkSheet act={act} ids={sel} progs={progs} toast={toast} close={()=>setAct(null)} done={r=>{setAct({kind:'result',r});setSel([]);load()}}/>}
    {ed&&<UserSheet u={ed} me={me} progs={progs} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet page close={()=>setBulk(null)}>
      {bulk.stage==='pick'&&<><h3>{tl("Bulk upload users")}</h3><p className="known">{tl("One row per person with the columns name, email, password, role, program and semester (the year number for annual programs such as M.B.B.S). Leave the password blank to generate one. Role is student or admin and defaults to student. Program must match a name on the Programs tab, and semester is a number from 1 to 8. Emails that already exist are updated, and blank program or semester cells leave the current value alone.")}</p>
        <button className="btn ghost" onClick={()=>download('users-template.csv',USER_TEMPLATE)}>{tl("Download template")}</button><button className="btn" onClick={()=>fileRef.current.click()}>{tl("Choose CSV file")}</button></>}
      {bulk.stage==='preview'&&<><h3>{tl("Ready to upload")}</h3><p className="known">{r.valid_rows}{" "}{tl("of {rows} rows are valid: {created} new, {updated} updated.",{rows:r.rows,created:r.created,updated:r.updated})}{r.generated>0&&tl(" {generated} passwords will be generated.",{generated:r.generated})}</p>
        {r.error_count>0&&<div className="prose" style={{maxHeight:'28vh',overflow:'auto',fontSize:14}}><b>{r.error_count}{" "}{tl("rows will be skipped")}</b>{r.errors.map(e=><div key={e.row}>{tl("Row {row}:",{row:e.row})}{" "}{e.error}</div>)}</div>}
        <button className="btn" disabled={!r.valid_rows} onClick={commit}>{tl("Upload {valid_rows} rows",{valid_rows:r.valid_rows})}</button><button className="btn ghost" onClick={()=>setBulk(null)}>{tl("Cancel")}</button></>}
      {bulk.stage==='done'&&<><h3>{tl("Upload complete")}</h3><p className="known">{r.created}{" "}{tl("users created, {updated} updated.",{updated:r.updated})}{r.credentials.length>0&&tl(" Download the generated passwords now. They are not shown again.")}</p>
        {r.credentials.length>0&&<button className="btn" onClick={()=>download('new-user-passwords.csv','name,email,password\n'+r.credentials.map(c=>[c.name,c.email,c.password].map(cell).join(',')).join('\n')+'\n')}>{tl("Download passwords")}</button>}
        <button className="btn ghost" onClick={()=>setBulk(null)}>{tl("Close")}</button></>}
    </Sheet>}</>}

function UserDetail({id,me,progs,back,toast}){
  const confirm=useConfirm()
  const [u,setU]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[pw,setPw]=useState(null),[busy,setBusy]=useState(false),[asg,setAsg]=useState(null),[ctree,setCtree]=useState([])
  const load=()=>api('/admin/users/'+id).then(setU).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id]);useEffect(()=>{if(u?.role==='faculty')api('/tree').then(setCtree)},[u?.role])
  if(!u)return <><Bar title={tl("Loading")} back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const reset=async()=>{setBusy(true);try{const r=await api(`/admin/users/${u.id}/reset-password`,{method:'POST'});setAsk(false);setPw(r.password)}catch(e){toast(e.message)}setBusy(false)}
  const remove=async()=>{if(!await confirm({title:tl("Delete {name}?",{name:u.name}),body:tl("This permanently removes the account and {v}. Content they created stays.{v2} To keep their history, edit the user and set Status to Disabled instead.",{v:u.role==='student'?'their progress, test results and bookmarks':'their own records',v2:u.role==='faculty'?' Courses they own will have no owner.':''}),ok:tl("Delete user"),danger:true}))return
    try{await api('/admin/users/'+u.id,{method:'DELETE'});toast(tl("{name} deleted",{name:u.name}));back()}catch(e){toast(e.message)}}
  const copy=async()=>{try{await navigator.clipboard.writeText(pw);toast(tl("Copied"))}catch{toast(tl("Press and hold the password to copy it"))}}
  const row=(v,l)=><div className="row"><div>{v}<small>{l}</small></div></div>
  const allCourses=ctree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared).map(c=>({id:c.id,owner_id:c.owner_id,owner:c.owner,label:`${p.name} › ${s.name} › ${c.name}`}))))
  const saveAsg=async()=>{try{await api(`/admin/users/${u.id}/courses`,{method:'PUT',body:{course_ids:asg}});toast(tl("Courses updated"));setAsg(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={u.name} sub={u.email} back={back}/><div className="main">
    <div className="stats"><div className="stat"><b>{u.topics_read}</b>{tl("Topics read")}</div><div className="stat"><b>{u.reads}</b>{tl("Total reads")}</div></div>
    <h3 className="sec">{tl("Profile")}</h3>
    {row({admin:'Admin',faculty:'Faculty'}[u.role]||'Student','Role')}{row(u.active?'Active':'Disabled','Status')}{row(u.program||'Not set','Program')}{row(u.semester||'Not set',termOf(progs,u.program_id))}{u.self_registered&&<>{row(u.institution||'—','Institution')}{row(u.id_number||'—','ID number')}{row(u.phone||'—','Phone')}{row(u.own_ai_key?'Has added their own key':'No key yet · AI is off for them','AI (self-registered, uses their own key)')}</>}{row(day(u.last_active),'Last active')}
    {u.role==='faculty'&&<><h3 className="sec">{tl("Courses they own")}</h3>{(u.course_ids||[]).length?allCourses.filter(c=>u.course_ids.includes(c.id)).map(c=><div className="row" key={c.id}><div>{c.label}</div></div>):<p className="known">{tl("None yet. They can read published content but edit nothing until they own a course.")}</p>}<button className="btn ghost" onClick={()=>setAsg([...(u.course_ids||[])])}>{tl("Assign courses")}</button></>}
    <h3 className="sec">{tl("Recently read")}</h3>
    {u.recent.length?<Paged rows={u.recent} render={(x,i)=><div className="row" key={i}><div>{x.title}<small>{x.reads}{" "}{tl("reads, last")}{" "}{day(x.last_read)}</small></div></div>}/>:<p className="known">{tl("No reading activity yet.")}</p>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>{tl("Edit")}</button><button className="btn" onClick={()=>setAsk(true)}>{tl("Reset password")}</button></div>
    {u.id!==me.id&&<button className="btn danger" onClick={remove}>{tl("Delete user")}</button>}</div>
    {ed&&<UserSheet u={u} me={me} progs={progs} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>{tl("Reset password?")}</h3><p className="known">{tl("This gives {name} a new password and replaces the old one straight away. You will see the new password once.",{name:u.name})}</p>
      <button className="btn danger" disabled={busy} onClick={reset}>{tl("Reset password")}</button><button className="btn ghost" onClick={()=>setAsk(false)}>{tl("Cancel")}</button></Sheet>}
    {pw&&<Sheet close={()=>setPw(null)}><h3>{tl("New password")}</h3><p className="known">{tl("Share this with {name} now. It is not shown again.",{name:u.name})}</p><div className="pw">{pw}</div>
      <button className="btn" onClick={copy}>{tl("Copy password")}</button><button className="btn ghost" onClick={()=>setPw(null)}>{tl("Done")}</button></Sheet>}
    {asg&&<Sheet page close={()=>setAsg(null)}><h3>{tl("Courses {name} owns",{name:u.name})}</h3><p className="known">{tl("The owner adds and edits the units, topics and quizzes of a course. Each course has one owner, so ticking a course another person owns moves it to {name}.",{name:u.name})}</p>{allCourses.map(c=><label key={c.id} className="chk"><input type="checkbox" checked={asg.includes(c.id)} onChange={e=>setAsg(e.target.checked?[...asg,c.id]:asg.filter(i=>i!==c.id))}/> {c.label}{c.owner_id&&c.owner_id!==u.id?tl(" (now {owner})",{owner:c.owner}):''}</label>)}<button className="btn" onClick={saveAsg}>{tl("Save")}</button><button className="btn ghost" onClick={()=>setAsg(null)}>{tl("Cancel")}</button></Sheet>}</>}

function UserSheet({u,me,progs,close,done,toast}){
  const isNew=!u.id,self=u.id===me.id,[busy,setBusy]=useState(false)
  const [f,setF]=useState({name:u.name||'',email:u.email||'',role:u.role||'student',active:u.active??true,password:'',program_id:u.program_id||'',semester:u.semester||''}),set=k=>e=>setF({...f,[k]:e.target.value})
  const save=async()=>{setBusy(true);try{
    const enrol={program_id:f.program_id?+f.program_id:null,semester:f.semester?+f.semester:null}
    if(isNew)await api('/admin/users',{method:'POST',body:{...f,...enrol}})
    const r=isNew?null:await api('/admin/users/'+u.id,{method:'PATCH',body:{name:f.name,email:f.email,...enrol,...(self?{}:{role:f.role,active:f.active})}})
    toast(isNew?tl("User added"):r.courses_needing_owner?tl("Saved. {courses_needing_owner} course(s) they own need a new owner.",{courses_needing_owner:r.courses_needing_owner}):tl("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?tl("New user"):tl("Edit user")}</h3>
    <label>{tl("Name")}</label><input value={f.name} onChange={set('name')}/><label>{tl("Email")}</label><input type="email" value={f.email} onChange={set('email')}/>
    <label>{tl("Program")}</label><select value={f.program_id} onChange={e=>{const id=e.target.value;setF({...f,program_id:id,semester:+f.semester>semsOf(progs,id).length?'':f.semester})}}><option value="">{tl("Not set")}</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <label>{termOf(progs,f.program_id)}</label><select value={f.semester} onChange={set('semester')}><option value="">{tl("Not set")}</option>{semsOf(progs,f.program_id).map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>{tl("Role")}</label><select disabled={self} value={f.role} onChange={set('role')}><option value="student">{tl("Student")}</option><option value="faculty">{tl("Faculty")}</option><option value="admin">{tl("Admin")}</option></select>
    <label>{tl("Status")}</label><select disabled={self} value={f.active?'1':'0'} onChange={e=>setF({...f,active:e.target.value==='1'})}><option value="1">{tl("Active")}</option><option value="0">{tl("Disabled")}</option></select>
    {isNew?<><label>{tl("Password (8+ characters)")}</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/></>
      :<p className="known" style={{marginTop:14}}>{tl("To give this person a new password, use Reset password on their page.")}</p>}
    {self&&<p className="known">{tl("You can't change your own role or status.")}</p>}
    <button className="btn" disabled={busy} onClick={save}>{isNew?tl("Add user"):tl("Save changes")}</button></Sheet>}

// every course for admins: search, a program filter, sorting and pages; add, edit or delete here, or open a course for its units and topics
function AdminCourses({toast,onOpen}){
  const confirm=useConfirm(),[q,setQ]=useState(''),[prog,setProg]=useState(''),[order,setOrder]=useState('name'),[status,setStatus]=useState('active'),[tree,setTree]=useState([]),[ed,setEd]=useState(null)
  useEffect(()=>{api('/tree').then(setTree).catch(()=>{})},[])
  const {items,total,page,setPage,reload}=usePaged(offset=>`/admin/courses?q=${encodeURIComponent(q)}&order=${order}&status=${status}&limit=${PAGE}&offset=${offset}`+(prog?'&program_id='+prog:''),[q,prog,order,status],toast)
  const sems=tree.flatMap(p=>p.semesters.map(x=>({id:x.id,label:p.name+' › '+x.name}))),done=()=>{setEd(null);reload()}
  const del=async c=>{if(!await confirm({title:tl("Delete “{name}”?",{name:c.name}),body:tl("This permanently deletes its {n}, {n2} and quizzes, with students' progress in them. To hide it instead, archive it from the course page.",{n:pl(c.units,'unit'),n2:pl(c.topics,'topic')}),ok:tl("Delete course"),danger:true}))return
    try{await api('/courses/'+c.id,{method:'DELETE'});toast(tl("Course deleted"));reload()}catch(e){toast(e.message)}}
  return <><Bar title={tl("Courses")} sub={q||prog?matches(total):pl(total,'course')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={tl("Search courses")} placeholder={tl("Search course, program, semester or owner")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label={tl("Filter by program")} value={prog} onChange={e=>setProg(e.target.value)}><option value="">{tl("All programs")}</option>{tree.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select aria-label={tl("Sort by")} value={order} onChange={e=>setOrder(e.target.value)}><option value="name">{tl("Sort: name A to Z")}</option><option value="name_desc">{tl("Sort: name Z to A")}</option><option value="program">{tl("Sort: program, then term")}</option><option value="topics">{tl("Sort: most topics")}</option><option value="newest">{tl("Sort: newest first")}</option></select>
      <select aria-label={tl("Show")} value={status} onChange={e=>setStatus(e.target.value)}><option value="active">{tl("Active courses")}</option><option value="archived">{tl("Archived courses")}</option><option value="all">{tl("All courses")}</option></select></div>
    <button className="btn" onClick={()=>setEd({})}>{tl("New course")}</button>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead c" aria-hidden="true"><span>{tl("Course")}</span><span>{tl("Program › term")}</span><span>{tl("Topics")}</span><span/></div>}
    {items.map(c=><div key={c.id} className="utr c"><button className="nm" onClick={()=>onOpen([c.program_id,c.semester_id,c.id].filter(x=>x!=null))} aria-label={tl("Open {name}",{name:c.name})}><span className="dot" style={{background:COL[c.id%5]}}>{(c.name||'?')[0]}</span><span className="tx"><b>{c.name}{c.archived&&<span className="pill off sm">{tl("Archived")}</span>}</b><small className="sub">{srv(c.owner_problem)||tl("Owner: {owner}",{owner:c.owner})}</small></span></button>
      <span className="pg">{[c.program,c.semester].filter(Boolean).join(' › ')||'—'}</span><span className="sn">{c.topics}</span>
      <span className="rowacts"><button className="ic sm" aria-label={tl("Edit {name}",{name:c.name})} title={tl("Edit")} onClick={()=>setEd(c)}><Pencil size={17}/></button><button className="ic sm" aria-label={tl("Delete {name}",{name:c.name})} title={tl("Delete")} onClick={()=>del(c)}><Trash2 size={17}/></button></span></div>)}
    {!items.length&&<p className="known">{q||prog?tl("No course matches that search."):status==='archived'?tl("No archived courses."):tl("No courses yet. Add one, or bulk upload a CSV under Programs.")}</p>}
    <Pager page={page} total={total} onPage={setPage}/></div>
    {ed&&(ed.id?<CourseSheet c={{id:ed.id,name:ed.name,owner_id:ed.owner_id,owner:ed.owner}} pid={ed.program_id} sid={ed.semester_id} sems={sems} term={ed.term} toast={toast} close={()=>setEd(null)} done={done}/>
      :<NewCourseSheet tree={tree} toast={toast} close={()=>setEd(null)} done={done}/>)}</>}
function NewCourseSheet({tree,toast,close,done}){  // a course is made inside a program's semester or year: pick both, then name it and, optionally, its owner
  const faculty=useFaculty(true),[f,setF]=useState({pid:tree.length===1?String(tree[0].id):'',sid:'',name:'',owner:''}),[busy,setBusy]=useState(false)
  const p=tree.find(x=>String(x.id)===f.pid),sems=p?.semesters||[],term=p?.term||'Semester'
  const save=async()=>{setBusy(true);try{await api(`/programs/${f.pid}/semesters/${f.sid}/courses`,{method:'POST',body:{name:f.name,...(f.owner?{faculty_owner_id:+f.owner}:{})}});toast(tl("Course added"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{tl("New course")}</h3>
    <label htmlFor="ncp">{tl("Program")}</label><select id="ncp" value={f.pid} onChange={e=>setF({...f,pid:e.target.value,sid:''})}><option value="">{tree.length?tl("Choose a program"):tl("Add a program first")}</option>{tree.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    <label htmlFor="ncs">{term}</label><select id="ncs" value={f.sid} disabled={!p} onChange={e=>setF({...f,sid:e.target.value})}><option value="">{tl("Choose a")}{" "}{term.toLowerCase()}</option>{sems.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    {p&&!sems.length&&<p className="known">{p.name}{" "}{tl("has no {term} yet. Add one under Programs first.",{term:term.toLowerCase()})}</p>}
    <label htmlFor="ncn">{tl("Name")}</label><input id="ncn" value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder={tl("Thermodynamics")}/>
    <label htmlFor="nco">{tl("Owner (faculty)")}</label><select id="nco" value={f.owner} onChange={e=>setF({...f,owner:e.target.value})}><option value="">{tl("Not assigned")}</option>{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    <button className="btn" disabled={busy||!f.sid||!f.name.trim()} onClick={save}>{tl("Add course")}</button></Sheet>}
function Programs({toast,onOpen}){
  const [q,setQ]=useState(''),[order,setOrder]=useState('name'),[status,setStatus]=useState('active')
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef()
  const {items,total,page,setPage,reload:load}=usePaged(offset=>`/admin/programs?q=${encodeURIComponent(q)}&order=${order}&status=${status}&limit=${PAGE}&offset=${offset}`,[q,order,status],toast)
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const r=bulk?.res,made=r&&Object.entries(r.created).filter(([,v])=>v).map(([k,v])=>v+' '+k).join(', ')||'nothing new'
  if(view)return <ProgramDetail id={view} onOpen={onOpen} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title={tl("Programs")} sub={q?matches(total):pl(total,'program')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label={tl("Search programs")} placeholder={tl("Search program, semester, year or course")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label={tl("Sort by")} value={order} onChange={e=>setOrder(e.target.value)}><option value="name">{tl("Sort: name")}</option><option value="students">{tl("Sort: most students")}</option><option value="newest">{tl("Sort: newest first")}</option></select><select aria-label={tl("Show")} value={status} onChange={e=>setStatus(e.target.value)}><option value="active">{tl("Active programs")}</option><option value="archived">{tl("Archived programs")}</option><option value="all">{tl("All programs")}</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>{tl("New program")}</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>{tl("Bulk upload")}</button></div>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead p" aria-hidden="true"><span>{tl("Program")}</span><span>{tl("Courses")}</span><span>{tl("Students")}</span></div>}
    {items.map(x=><button key={x.id} className="utr p" onClick={()=>setView(x.id)} aria-label={tl("Open {name}",{name:x.name})}>
      <span className="nm"><span className="dot" style={{background:COL[x.id%5]}}>{(x.name||'?')[0]}</span><span className="tx"><b>{x.name}{x.archived&&<span className="pill off sm">{tl("Archived")}</span>}</b><small className="sub">{pl(x.semesters,x.term.toLowerCase())}{tl(", {topics} topics",{topics:x.topics})}</small></span></span>
      <span className="sn">{x.courses}</span><span className="sn">{x.students}</span></button>)}
    {!items.length&&<p className="known">{q?tl("No program matches that search."):status==='archived'?tl("No archived programs."):tl("No programs yet. Add one or bulk upload a CSV.")}</p>}
    <Pager page={page} total={total} onPage={setPage}/>
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {ed&&<ProgramSheet p={ed} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet page close={()=>setBulk(null)}>
      {bulk.stage==='pick'&&<><h3>{tl("Bulk upload content")}</h3><p className="known">{tl("One row per topic, with the columns program, semester, course, unit and topic, plus optional content, question_pattern, sample_content and guideline. Blank program, semester, course or unit cells repeat the row above. Existing names are reused and existing topics are updated. Programs that don't exist yet are created.")}</p>
        <button className="btn ghost" onClick={()=>download('template.csv',TEMPLATE)}>{tl("Download template")}</button><button className="btn" onClick={()=>fileRef.current.click()}>{tl("Choose CSV file")}</button></>}
      {bulk.stage==='preview'&&<><h3>{tl("Ready to upload")}</h3><p className="known">{r.valid_rows}{" "}{tl("of {rows} rows are valid. New: {made}. Topics updated: {updated_topics}.",{rows:r.rows,made:made,updated_topics:r.updated_topics})}</p>
        {r.error_count>0&&<div className="prose" style={{maxHeight:'28vh',overflow:'auto',fontSize:14}}><b>{r.error_count}{" "}{tl("rows will be skipped")}</b>{r.errors.map(e=><div key={e.row}>{tl("Row {row}:",{row:e.row})}{" "}{e.error}</div>)}</div>}
        <button className="btn" disabled={!r.valid_rows} onClick={commit}>{tl("Upload {valid_rows} rows",{valid_rows:r.valid_rows})}</button><button className="btn ghost" onClick={()=>setBulk(null)}>{tl("Cancel")}</button></>}
      {bulk.stage==='done'&&<><h3>{tl("Upload complete")}</h3><p className="known">{tl("Created {made}. {updated_topics} topics updated.",{made:made,updated_topics:r.updated_topics})}{r.error_count>0&&tl(" {error_count} rows were skipped.",{error_count:r.error_count})}</p>
        <button className="btn ghost" onClick={()=>setBulk(null)}>{tl("Close")}</button></>}
    </Sheet>}</>}

function RolloverSheet({p,close,done,toast}){
  const [fin,setFin]=useState('keep'),[r,setR]=useState(null),[busy,setBusy]=useState(false)
  const url=`/admin/programs/${p.id}/rollover`
  useEffect(()=>{setR(null);api(url,{method:'POST',body:{dry_run:true,finishing:fin}}).then(setR).catch(e=>{toast(e.message);close()})},[fin]) 
  const go=async()=>{setBusy(true);try{const x=await api(url,{method:'POST',body:{dry_run:false,finishing:fin}});toast(`${x.moved} students moved up`+(fin==='deactivate'&&x.finishing?`, ${x.finishing} accounts switched off`:''));done()}catch(e){toast(e.message);setBusy(false)}}
  return <Sheet page close={close}><h3>{tl("Start a new term")}</h3><p className="known">{tl("Moves every active student of {name} up one {v}. Do this once, when the new term begins.",{name:p.name,v:p.term?.toLowerCase()||'semester'})}</p>
    {!r?<div className="sk"/>:<div className="qbox" style={{marginTop:0}}>
      <div className="row"><div>{pl(r.moved,'student')}<small>{r.moved===1?'moves':'move'}{" "}{tl("up one")}{" "}{r.term.toLowerCase()}</small></div></div>
      <div className="row"><div>{pl(r.finishing,'student')}<small>{r.finishing===1?'is':'are'}{" "}{tl("in the last {term} ({term2} {last_semester})",{term:r.term.toLowerCase(),term2:r.term,last_semester:r.last_semester})}{r.finishing_names.length?': '+r.finishing_names.join(', ')+(r.finishing>r.finishing_names.length?'…':''):''}</small></div></div>
      {r.unplaced>0&&<div className="row"><div>{pl(r.unplaced,'student')}<small>{r.unplaced===1?'has':'have'}{" "}{tl("no {term} set and are left alone:",{term:r.term.toLowerCase()})}{" "}{r.unplaced_names.join(', ')}</small></div></div>}</div>}
    <label htmlFor="fin">{tl("Students finishing the program")}</label><select id="fin" value={fin} onChange={e=>setFin(e.target.value)}><option value="keep">{tl("Leave them as they are")}</option><option value="deactivate">{tl("Switch their accounts off")}</option></select>
    <button className="btn" disabled={busy||!r||(!r.moved&&!(fin==='deactivate'&&r.finishing))} onClick={go}>{busy?tl("Working…"):tl("Apply")}</button><button className="btn ghost" onClick={close}>{tl("Cancel")}</button></Sheet>}
function ProgramDetail({id,back,onOpen,toast}){
  const [p,setP]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[busy,setBusy]=useState(false),[addSem,setAddSem]=useState(false),[term,setTerm]=useState(false),[arch,setArch]=useState(null)
  const load=()=>api('/admin/programs/'+id).then(setP).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id])
  if(!p)return <><Bar title={tl("Loading")} back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const del=async()=>{setBusy(true);try{await api('/programs/'+p.id,{method:'DELETE'});toast(tl("Program deleted"));back()}catch(e){toast(e.message);setBusy(false)}}
  const row=(v,l,k)=><div className="row" key={k}><div>{v}<small>{l}</small></div></div>
  return <><Bar title={p.name} sub={pl(p.semesters,p.term.toLowerCase())+(p.pattern==='year'?' · annual':p.pattern==='grade'?' · school':'')+(p.archived?' · archived':'')} back={back}/><div className="main">
    {p.archived&&<p className="known" style={{marginTop:0}}>{tl("This program is archived. Students see its courses as unavailable right now. Restore it to bring everything back.")}</p>}
    <button className="btn ghost lead" onClick={()=>setArch({kind:'programs',id:p.id,name:p.name,on:!p.archived})}>{p.archived?tl("Restore program"):tl("Archive program")}</button>
    <div className="stats">{[['semesters',p.term+'s'],['courses',tl("Courses")],['topics',tl("Topics")],['students',tl("Students")]].map(([k,l])=><div className="stat" key={k}><b>{p[k]}</b>{l}</div>)}</div>
    <h3 className="sec">{p.term}s</h3>
    {p.semester_list.length?<Paged rows={p.semester_list} render={(x,i)=><div key={x.id} className="card"><button className="hit" onClick={()=>onOpen([p.id,x.id])}><span className="dot" style={{background:COL[i%5]}}>{x.number||'?'}</span><div><b>{x.name}<ArchPill x={x}/></b><span>{tl("{v}{courses} courses, {topics} topics",{v:x.number?'':'No '+p.term.toLowerCase()+' number set · ',courses:x.courses,topics:x.topics})}</span></div></button>{!p.archived&&<button className="ic sm" aria-label={(x.archived_self?'Restore ':'Archive ')+x.name} onClick={()=>setArch({kind:'semesters',id:x.id,name:x.name,on:!x.archived_self})}>{x.archived_self?<ArchiveRestore size={16}/>:<Archive size={16}/>}</button>}</div>}/>:<p className="known">{tl("No {term}s yet.",{term:p.term.toLowerCase()})}</p>}
    <button className="btn ghost" onClick={()=>setAddSem(true)}>{tl("Add")}{" "}{p.term.toLowerCase()}</button>
    <h3 className="sec">{tl("Students")}</h3>
    {p.student_list.length?<Paged rows={p.student_list} render={u=>row(u.name,(u.semester?tl('{term} {n}',{term:p.term,n:u.semester}):tl("{term} not set",{term:p.term}))+(u.active?'':tl(', disabled')),u.id)}/>:<p className="known">{tl("No students are enrolled yet. Set a program on a user's page.")}</p>}
    {p.students>p.student_list.length&&<p className="known">{tl("Showing {length} of {students}. Use Users to see everyone.",{length:p.student_list.length,students:p.students})}</p>}
    {p.students>0&&<button className="btn ghost" onClick={()=>setTerm(true)}>{tl("Start a new term (move students up)")}</button>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>{tl("Edit")}</button><button className="btn danger" onClick={()=>setAsk(true)}>{tl("Delete")}</button></div>
    <button className="btn ghost" onClick={()=>onOpen([p.id])}>{tl("Open {term}s and courses",{term:p.term.toLowerCase()})}</button></div>
    {term&&<RolloverSheet p={p} toast={toast} close={()=>setTerm(false)} done={()=>{setTerm(false);load()}}/>}
    {ed&&<ProgramSheet p={p} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {arch&&<ArchiveSheet a={arch} toast={toast} close={()=>setArch(null)} done={()=>{setArch(null);load()}}/>}
    {addSem&&<SemesterSheet sem={{}} pid={p.id} term={p.term} toast={toast} close={()=>setAddSem(false)} done={()=>{setAddSem(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>{tl("Delete “{name}”?",{name:p.name})}</h3><p className="known">{tl("This permanently deletes {n}, {courses} courses, {units} units and {topics} topics, including their saved AI answers.",{n:pl(p.semesters,p.term.toLowerCase()),courses:p.courses,units:p.units,topics:p.topics})}{p.students>0&&tl(" The {students} enrolled students keep their accounts but lose their program.",{students:p.students})}</p>
      <button className="btn danger" disabled={busy} onClick={del}>{tl("Delete program")}</button><button className="btn ghost" onClick={()=>setAsk(false)}>{tl("Cancel")}</button></Sheet>}</>}

function OwnerSheet({c,close,done,toast}){
  const faculty=useFaculty(true),[sel,setSel]=useState(c.owner_id||''),[busy,setBusy]=useState(false)
  const save=async()=>{if(String(sel)===String(c.owner_id||''))return close();setBusy(true);try{await api(`/courses/${c.id}/owner`,{method:'PUT',body:{user_id:sel?+sel:null}});toast(tl("Owner updated"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{tl("Owner of “{name}”",{name:c.name})}</h3><p className="known">{tl("The owner adds and edits this course's units, topics and quizzes. Changing the owner keeps all content and student progress.")}{c.owner_problem&&c.owner_id?' '+srv(c.owner_problem)+'.':''}</p>
    <label>{tl("Owner (faculty)")}</label><select value={sel} onChange={e=>setSel(e.target.value)}><option value="">{tl("Not assigned")}</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner}{" "}{tl("(can't edit)")}</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    <button className="btn" disabled={busy} onClick={save}>{tl("Save")}</button><button className="btn ghost" onClick={close}>{tl("Cancel")}</button></Sheet>}

function ProgramSheet({p,close,done,toast}){
  const isNew=!p.id,[name,setName]=useState(p.name||''),[pat,setPat]=useState(p.pattern||'semester'),[terms,setTerms]=useState(PATTERN[pat][2]),[touched,setTouched]=useState(false),[busy,setBusy]=useState(false)
  const lab=PATTERN_EN[pat][1],pick=k=>{setPat(k);setTerms(touched?Math.min(terms,maxOf(PATTERN_EN[k][1])):PATTERN[k][2])}
  const save=async()=>{setBusy(true);try{const r=await api(isNew?'/programs':'/programs/'+p.id,{method:isNew?'POST':'PUT',body:{name,pattern:pat,...(isNew?{terms}:{})}});toast(isNew?(r.terms?tl("Program added with {terms} {lab}{v}",{terms:r.terms,lab:lab.toLowerCase(),v:r.terms===1?'':'s'}):tl("Program added")):tl("Changes saved"));done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?tl("New program"):tl("Edit program")}</h3>
    <label>{tl("Name")}</label><input value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==='Enter'&&save()} placeholder={tl("B.E. Mechanical Engineering")} autoFocus/>
    <p className="known" style={{marginTop:10}}>{tl("Names must be unique. The users CSV import matches programs by name.")}</p>
    <label id="pat">{tl("How is the program divided?")}</label><div role="group" aria-labelledby="pat" className="seg" style={{marginTop:0}}>{Object.entries(PATTERN).map(([k,[l]])=><button key={k} className={pat===k?'on':''} aria-pressed={pat===k} onClick={()=>pick(k)}>{l}</button>)}</div>
    <p className="known" style={{marginTop:6}}>{PATTERN[pat][3]}</p>
    {isNew?<><label htmlFor="nt">{tl("How many {lab}s?",{lab:tl(lab).toLowerCase()})}</label><select id="nt" value={terms} onChange={e=>{setTerms(+e.target.value);setTouched(true)}}>{[0,...upTo(maxOf(lab))].map(n=><option key={n} value={n}>{n===0?tl("None yet, I will add them myself"):n}</option>)}</select>
      <p className="known" style={{marginTop:6}}>{terms?tl("{lab} 1{v} {v2} created for you, so you can go straight to adding courses.",{lab:tl(lab),v:terms>1?` to ${lab} ${terms}`:'',v2:terms>1?'are':'is'}):tl("You can add them one by one later.")}</p></>
      :p.pattern&&pat!==p.pattern&&<p className="known" style={{marginTop:6}}>{tl("Terms still named “{v} n” are renamed to “{lab} n”. Terms you named yourself keep their names.",{v:PATTERN[p.pattern]?.[1]||'Semester',lab:lab})}{pat==='grade'&&tl(" Any of Grade 1 to Grade 12 the program does not have yet are added.")}</p>}
    <button className="btn" disabled={busy||!name.trim()} onClick={save}>{isNew?tl("Add program"):tl("Save changes")}</button></Sheet>}

function Branding({toast,onSaved}){
  const [name,setName]=useState(''),[logo,setLogo]=useState(null),[busy,setBusy]=useState(false),file=useRef(null)
  useEffect(()=>{api('/config').then(c=>{setName(c.name);setLogo(c.logo)}).catch(()=>{})},[])
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;setBusy(true)
    try{const r=await fetch('/api/uploads',{method:'POST',headers:{Authorization:'Bearer '+localStorage.t,'Content-Type':f.type},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(tl(j.detail||'Upload failed'));setLogo(j.url)}catch(x){toast(x.message)}setBusy(false)}
  const save=async body=>{setBusy(true);try{await api('/admin/branding',{method:'PUT',body});toast(tl("Saved"));onSaved()}catch(e){toast(e.message)}setBusy(false)}
  return <><h3 className="sec first">{tl("Institution name and logo")}</h3><p className="known">{tl("Shown on the sign-in page and in the menu. Use a square PNG, JPG or WebP under 3 MB.")}</p>
    <div className="lpreview"><Logo src={logo} size={48}/><b>{name||tl("Name")}</b></div>
    <label htmlFor="inst">{tl("Name")}</label><input id="inst" value={name} maxLength={60} onChange={e=>setName(e.target.value)}/>
    <input ref={file} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={pick}/>
    <div className="two"><button className="btn ghost" disabled={busy} onClick={()=>file.current.click()}><Upload size={16}/> {logo?tl("Replace logo"):tl("Upload logo")}</button>
      <button className="btn ghost" disabled={busy||!logo} onClick={()=>{setLogo(null);save({remove_logo:true,name})}}>{tl("Remove logo")}</button></div>
    <button className="btn" disabled={busy} onClick={()=>save({name,logo_url:logo||undefined})}>{tl("Save name and logo")}</button></>}
function AiConfig({toast,onBrand}){
  const confirm=useConfirm()
  const [cfg,setCfg]=useState({}),[key,setKey]=useState(''),[model,setModel]=useState(''),[st,setSt]=useState({}),[tab,setTab]=useState('ai')
  const load=()=>{api('/admin/settings').then(c=>{setCfg(c);setModel(c.model)});api('/admin/stats').then(setSt)};useEffect(load,[])
  const run=useRun(toast,load)
  return <><Bar title={tl("Settings")} sub={cfg.key_set?tl("AI is on · key {key_hint}",{key_hint:cfg.key_hint}):tl("AI is off · no key yet")}/><div className="main"><Tabs label={tl("Settings sections")} scroll items={[['ai','AI'],['prompts',tl("AI prompts")],['school',tl("Institution")],['access',tl("Sign-in")]]} value={tab} onChange={setTab}/>
    {tab==='school'&&<Branding toast={toast} onSaved={onBrand}/>}{tab==='ai'&&<>
    <label>{tl("DeepSeek API key")}</label><input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder={cfg.key_set?tl("Leave blank to keep the current key"):tl("sk-…")}/>
    <label>{tl("Model")}</label><input value={model} onChange={e=>setModel(e.target.value)} placeholder="deepseek-chat"/>
    <button className="btn" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{deepseek_key:key,model}}).then(()=>setKey('')),'AI settings saved')}>{tl("Save")}</button>
    {cfg.key_set&&<><button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/ai/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>{tl("Test the key")}</button>
      <button className="btn ghost" onClick={async()=>{if(await confirm({title:tl("Turn AI off for everyone?"),body:tl("Students will see “AI unavailable” until you save a key again."),ok:tl("Turn AI off"),danger:true}))run(()=>api('/admin/settings',{method:'PUT',body:{remove_key:true}}),'AI is off')}}>{tl("Remove the key (turn AI off)")}</button></>}
    <p className="known" style={{marginTop:20}}>{tl("One key serves every student added by staff (people who register themselves use their own key). Until a key is saved, students see “AI unavailable. Try again later.” Each topic is explained once and the answer is shared with every student. {v} answers are saved so far, which has saved about {v2} tokens.",{v:(st.cached??0).toLocaleString(),v2:(st.tokens_saved??0).toLocaleString()})}</p>
    </>}{tab==='prompts'&&<PromptEditor toast={toast}/>}
    {tab==='access'&&<><h3 className="sec first">{tl("Self-registration")}</h3><SelfReg cfg={cfg} run={run}/>
    <h3 className="sec">{tl("Password reset email")}</h3><p className="known">{cfg.mail_on?tl("On. People can reset their own password from the sign-in page."):tl("Off. The sign-in page tells people to ask an admin. To turn it on, set SMTP_HOST, SMTP_FROM and APP_URL in .env and restart (see .env.example).")}</p>
    {cfg.mail_on&&<button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/mail/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>{tl("Send a test email to me")}</button>}</>}</div></>}

// an activity-log row in words: whole phrases (with the item and its number filled in), so each language can order them its own way
const describe=(m,p)=>{const s=p.replace(/^\/api\//,'').split('/'),id=s.find(x=>/^\d+$/.test(x)),n=s.filter(x=>!/^\d+$/.test(x)),last=n[n.length-1],noun=n[0]==='admin'?n[1]:n[0],what=tl((noun||'').replace(/s$/,''))
  if(p==='/api/uploads')return tl('Uploaded an image');if(p==='/api/me/password')return tl('Changed own password');if(p==='/api/me/lang')return tl('Changed own language')
  if(p==='/api/admin/import')return tl('Imported content from CSV');if(p==='/api/admin/users/import')return tl('Imported users from CSV')
  if(last==='reset-password')return tl('Reset the password of user #{id}',{id});if(last==='courses')return tl('Assigned courses to user #{id}',{id});if(last==='links')return tl('Changed where course #{id} is shared',{id})
  if(last==='publish')return tl('Changed publish state of {what} #{id}',{what,id});if(n[0]==='admin'&&n[1]==='settings')return tl('Changed settings')
  const verb={POST:'Created',PUT:'Changed',PATCH:'Edited',DELETE:'Deleted'}[m]
  return verb?tl(verb+(id?' {what} #{id}':' {what}'),{what,id}):m+' '+what+(id?' #'+id:'')}
function Activity({toast}){
  const [q,setQ]=useState(''),[action,setAction]=useState(''),[result,setResult]=useState(''),[days,setDays]=useState(''),[sort,setSort]=useState('newest')
  const qs=`q=${encodeURIComponent(q)}&action=${action}&result=${result}&days=${days||0}&sort=${sort}`,filtered=q||action||result||days
  const {items,total,page,setPage,ready}=usePaged(o=>`/admin/audit?${qs}&limit=${PAGE}&offset=${o}`,[q,action,result,days,sort],toast)
  return <><Bar title={tl("Activity log")} sub={filtered&&ready?matches(total):tl("Who changed what")}/><div className="main"><div className="search"><Search size={18}/><input type="search" aria-label={tl("Search the activity log")} placeholder={tl("Search by person or action")} value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters fit">
      <Opts label={tl("Action")} value={action} set={setAction} items={[['',tl("All actions")],['created',tl("Created")],['changed',tl("Changed or edited")],['deleted',tl("Deleted")]]}/>
      <Opts label={tl("Result")} value={result} set={setResult} items={[['',tl("Any result")],['ok',tl("Succeeded")],['failed',tl("Failed or not allowed")]]}/>
      <Opts label={tl("When")} value={days} set={setDays} items={[['',tl("Any time")],['1',tl("Last 24 hours")],['7',tl("Last 7 days")],['30',tl("Last 30 days")]]}/>
      <Opts label={tl("Sort by")} value={sort} set={setSort} items={[['newest',tl("Sort: newest first")],['oldest',tl("Sort: oldest first")]]}/></div>
    {!ready?<Skeleton/>:items.length?items.map(x=><div className="row" key={x.id}><div>{describe(x.method,x.path)}{x.status>=400&&<span className="pill off sm">{x.status===403?tl("Not allowed"):tl("Failed")}</span>}<small>{x.user} · {when(x.at)}</small></div></div>):<p className="known">{filtered?tl("Nothing matches."):tl("No activity yet.")}</p>}
    <Pager page={page} total={total} onPage={setPage}/>
    {total>0&&<button className="btn ghost" onClick={()=>fetchFile('/admin/audit?format=csv&'+qs,'activity-log.csv',toast)}>{tl("Download as CSV")}</button>}</div></>}
const day=d=>d?new Date(d).toLocaleDateString(locale(),{day:'numeric',month:'short'}):tl('never')
const fetchFile=async(url,name,toast)=>{try{const r=await fetch('/api'+url,{headers:{Authorization:'Bearer '+localStorage.t}});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'Download failed')
  const a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download=name;a.click();URL.revokeObjectURL(a.href)}catch(e){toast(e.message)}}
const Bar2=({v})=><div className="meter"><i style={{width:Math.min(100,v||0)+'%'}}/></div>
function CourseReports({toast,onOpen}){
  const [f,setF]=useState({p:0,s:0}),[rows,setRows]=useState(null),[progs,setProgs]=useState([])
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name,term:p.term,max:Math.max(0,...p.semesters.map(x=>x.number||0))||(p.term==='Year'?4:maxOf(p.term))})))).catch(()=>{})},[])
  const pr=progs.find(x=>x.id===f.p),lab=pr?pr.term:progs.length&&progs.every(x=>x.term==='Semester')?'Semester':progs.length&&progs.every(x=>x.term==='Year')?'Year':progs.length&&progs.every(x=>x.term==='Grade')?'Grade':'Term',top=pr?pr.max:Math.max(1,...progs.map(x=>x.max))
  const qs=`?program_id=${f.p}&semester=${f.s}`
  useEffect(()=>{setRows(null);api('/reports/courses'+qs).then(setRows).catch(e=>toast(e.message))},[f.p,f.s])
  const [q,setQ]=useState(''),[sort,setSort]=useState('name'),head=useRef()
  const few=!f.p&&!f.s&&progs.length<=1&&rows&&rows.length<=5  // a handful of courses needs no filters
  const by={name:(a,b)=>a.course.localeCompare(b.course),low:(a,b)=>a.avg_completion-b.avg_completion,high:(a,b)=>b.avg_completion-a.avg_completion,students:(a,b)=>b.students-a.students,quiz:(a,b)=>(a.avg_quiz_percent??101)-(b.avg_quiz_percent??101)}[sort]
  const shown=rows&&rows.filter(x=>has(q,x.course,x.program,x.semester)).sort(by),{items,total,page,setPage}=useLocalPage(shown,[q,sort,f.p,f.s],PAGE)
  return <><div ref={head} className="pgtop"/>{!few&&<div className="qopt"><select value={f.p} onChange={e=>{const p=+e.target.value,x=progs.find(y=>y.id===p);setF({p,s:x&&f.s>x.max?0:f.s})}}><option value={0}>{tl("All programs")}</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <select aria-label={tl("Filter by {lab}",{lab:lab.toLowerCase()})} value={f.s} onChange={e=>setF({...f,s:+e.target.value})}><option value={0}>{lab==='Term'?tl("All terms"):tl("All {lab}s",{lab:lab.toLowerCase()})}</option>{Array.from({length:top},(_,i)=>i+1).map(n=><option key={n} value={n}>{lab} {n}</option>)}</select></div>}
    {!few&&<div className="filters fit"><div className="search"><Search size={18}/><input type="search" aria-label={tl("Search courses")} placeholder={tl("Search courses")} value={q} onChange={e=>setQ(e.target.value)}/></div>
      <Opts label={tl("Sort by")} value={sort} set={setSort} items={[['name',tl("Sort: name")],['low',tl("Sort: lowest completion first")],['high',tl("Sort: highest completion first")],['students',tl("Sort: most students")],['quiz',tl("Sort: lowest quiz average first")]]}/></div>}
    {!rows&&<Skeleton/>}{rows&&!total&&<p className="known">{tl("No courses match.")}</p>}
    {items.map(x=><button className="row rowbtn" key={x.course_id} onClick={()=>onOpen(x)}><div>{x.course}<small>{x.program}{" "}{['',x.semester,pl(x.students,'student'),pl(x.topics,'topic'),tl('{n}% completed',{n:x.avg_completion}),tl('{n}% opened',{n:x.avg_opened})].join(' · ')}{x.quizzes?tl(" · quiz avg {v}%",{v:x.avg_quiz_percent??'–'}):''}</small><Bar2 v={x.avg_completion}/></div><ChevronRight size={18}/></button>)}
    <Pager page={page} total={total} onPage={setPage} size={PAGE} anchor={head}/>
    {rows?.length>0&&<button className="btn ghost" onClick={()=>fetchFile('/reports/courses?format=csv&program_id='+f.p+'&semester='+f.s,'courses.csv',toast)}>{tl("Download courses CSV")}</button>}</>}
function StudentReport({c,back,toast}){
  const [q,setQ]=useState(''),[show,setShow]=useState(''),[sort,setSort]=useState('name')
  const [d,setD]=useState(null),[w,setW]=useState(null);useEffect(()=>{api(`/reports/courses/${c.course_id}/students`).then(setD).catch(e=>toast(e.message));api(`/reports/courses/${c.course_id}/weak-areas`).then(setW).catch(()=>{})},[])
  const keep={'':()=>true,active:x=>x.active,disabled:x=>!x.active,never:x=>!x.topics_read,behind:x=>x.completion<50,needs:x=>x.needs_study.length>0}[show],seen=x=>x.last_active||''
  const by={name:(a,b)=>(a.name||'').localeCompare(b.name||''),low:(a,b)=>a.completion-b.completion,high:(a,b)=>b.completion-a.completion,recent:(a,b)=>seen(b).localeCompare(seen(a)),quiet:(a,b)=>seen(a).localeCompare(seen(b))}[sort]
  const shown=d&&d.students.filter(x=>keep(x)&&has(q,x.name,x.email)).sort(by),{items,total,page,setPage}=useLocalPage(shown,[q,show,sort])
  return <><Bar title={c.course} sub={c.program+' · '+c.semester} back={back}/><div className="main">
    {w&&w.areas.length>0&&<><h3 className="sec first">{tl("Topics the class finds hard")}</h3><p className="known" style={{margin:'0 0 8px'}}>{tl("From each student's latest quiz results, weakest first.")}</p>{<Paged rows={w.areas} render={a=><div className="row" key={a.topic_id||'u'+a.unit_id}><div>{a.title}<small>{a.percent}{tl("% right overall · {needs_study} of {students} students need another round of study",{needs_study:a.needs_study,students:a.students})}</small><Bar2 v={a.percent}/></div></div>}/>}<h3 className="sec">{tl("Students")}</h3></>}
    {d&&!d.students.length&&<p className="known">{tl("No students are enrolled for this course yet.")}</p>}
    {d?.students.length>5&&<><div className="search"><Search size={18}/><input type="search" aria-label={tl("Search students")} placeholder={tl("Search by name or email")} value={q} onChange={e=>setQ(e.target.value)}/></div>
      <div className="filters fit"><Opts label={tl("Show")} value={show} set={setShow} items={[['',tl("All students")],['active',tl("Active")],['disabled',tl("Disabled")],['never',tl("Never opened a topic")],['behind',tl("Under 50% completed")],['needs',tl("Need another round of study")]]}/>
        <Opts label={tl("Sort by")} value={sort} set={setSort} items={[['name',tl("Sort: name")],['low',tl("Sort: lowest completion first")],['high',tl("Sort: highest completion first")],['recent',tl("Sort: recently active first")],['quiet',tl("Sort: longest inactive first")]]}/></div>
      {!total&&<p className="known">{tl("Nothing matches.")}</p>}</>}
    {!d&&<Skeleton/>}{items.map(x=><div className="row" key={x.email}><div>{x.name}{!x.active&&<span className="pill off sm">{tl("Disabled")}</span>}<small>{x.completion}{tl("% completed · {topics_completed}/{topics} done, {topics_read} opened{v} · last active",{topics_completed:x.topics_completed,topics:x.topics,topics_read:x.topics_read,v:c.quizzes?' · quizzes '+x.quizzes_taken+'/'+x.quizzes+(x.avg_quiz_percent!=null?', avg '+x.avg_quiz_percent+'%':''):''})}{" "}{day(x.last_active)}</small>{(x.strong.length>0||x.needs_study.length>0)&&<small>{x.strong.length>0&&tl("Strong: {strong}",{strong:x.strong.join(', ')})}{x.strong.length>0&&x.needs_study.length>0&&' · '}{x.needs_study.length>0&&tl("Needs another round: {needs_study}",{needs_study:x.needs_study.join(', ')})}</small>}<Bar2 v={x.completion}/></div></div>)}
    <Pager page={page} total={total} onPage={setPage}/>
    {d?.students.length>0&&<button className="btn ghost" onClick={()=>fetchFile(`/reports/courses/${c.course_id}/students?format=csv`,'students-'+c.course.replace(/\s+/g,'_')+'.csv',toast)}>{tl("Download students CSV")}</button>}</div></>}
function Reports({role,toast}){
  const [st,setSt]=useState({}),[open,setOpen]=useState(null)
  useEffect(()=>{if(role==='faculty')return;api('/admin/stats').then(setSt).catch(()=>{})},[])
  if(open)return <StudentReport c={open} back={()=>setOpen(null)} toast={toast}/>
  if(role==='faculty')return <><Bar title={tl("Reports")} sub={tl("Your courses")}/><div className="main"><CourseReports toast={toast} onOpen={setOpen}/></div></>
  return <><Bar title={tl("Reports")}/><div className="main"><div className="stats">
    {[['students',tl("Students")],['topics',tl("Topics")],['cached',tl("Saved AI answers")],['tokens_saved',tl("Tokens saved")]].map(([k,l])=><div className="stat" key={k}><b>{(st[k]??0).toLocaleString()}</b>{l}</div>)}</div>
    <h3 className="sec">{tl("Courses")}</h3><CourseReports toast={toast} onOpen={setOpen}/>
    <h3 className="sec">{tl("Most read topics")}</h3>
    <ReportList kind="topics" toast={toast} search={tl("Search topics or courses")} empty="No reading activity yet."
      sorts={[['reads',tl("Sort: most reads")],['readers',tl("Sort: most students")],['least',tl("Sort: fewest reads")],['title',tl("Sort: title")]]}
      render={x=><div>{x.title}<small>{[x.course,pl(x.readers,'student'),pl(x.reads,'read')].join(' · ')}</small></div>}/>
    <h3 className="sec">{tl("Students")}</h3>
    <ReportList kind="students" toast={toast} search={tl("Search by name or email")} empty="No students yet."
      shows={[['',tl("All students")],['active',tl("Active")],['disabled',tl("Disabled")],['never',tl("Never opened a topic")],['quiet',tl("Not active in the last 7 days")]]}
      sorts={[['recent',tl("Sort: recently active first")],['quiet',tl("Sort: longest inactive first")],['most',tl("Sort: most topics read")],['least',tl("Sort: fewest topics read")],['name',tl("Sort: name")]]}
      render={x=><div>{x.name}<small>{x.topics_read}{" "}{tl("topics read, last active")}{" "}{day(x.last_active)}{!x.active&&tl(", disabled")}</small></div>}/>
    <h3 className="sec">{tl("Saved AI answers")}</h3>
    <ReportList kind="ai" toast={toast} search={tl("Search topics")} empty="Nothing saved yet."
      shows={[['',tl("Explanations and sample answers")],['explain',tl("Explanations")],['answer',tl("Sample answers")]]}
      sorts={[['saved',tl("Sort: most tokens saved")],['hits',tl("Sort: most reused")],['newest',tl("Sort: newest first")],['title',tl("Sort: title")]]}
      render={x=><div>{x.title}<small>{x.kind==='explain'?tl("Explanation"):tl("Sample answer")}{tl(", reused {hits} times, {saved} tokens saved",{hits:x.hits,saved:x.saved.toLocaleString()})}</small></div>}/></div></>}
// one of the admin Reports lists, a page at a time from the server: search, a filter and a sort above it, numbered pages below
function ReportList({kind,toast,search,shows,sorts,render,empty}){
  const [q,setQ]=useState(''),[show,setShow]=useState(''),[sort,setSort]=useState(sorts[0][0]),top=useRef()
  const {items,total,page,setPage,ready}=usePaged(o=>`/admin/reports/${kind}?q=${encodeURIComponent(q)}&show=${show}&sort=${sort}&limit=${PAGE}&offset=${o}`,[q,show,sort],toast,PAGE)
  return <div ref={top} className="pgtop"><div className="filters fit"><div className="search"><Search size={18}/><input type="search" aria-label={search} placeholder={search} value={q} onChange={e=>setQ(e.target.value)}/></div>
      {shows&&<Opts label={tl("Show")} value={show} set={setShow} items={shows}/>}<Opts label={tl("Sort by")} value={sort} set={setSort} items={sorts}/></div>
    {!ready?<Skeleton/>:items.length?items.map(x=><div className="row" key={x.id}>{render(x)}</div>):<p className="known">{q||show?tl("Nothing matches."):tl(empty)}</p>}
    <Pager page={page} total={total} onPage={setPage} size={PAGE} anchor={top}/></div>}

function About({user}){
  const {appName}=useContext(Ctx),[c,setC]=useState({});useEffect(()=>{api('/config').then(setC)},[])
  return <><Bar title={tl("About")}/><div className="main"><div className="hero"><h2>{appName}</h2><p>{tl("Version")}{" "}{c.version||''}</p></div>
    <div className="prose"><p>{tl("A study companion for engineering students. Your admin adds programs, semesters, courses, units and topics along with the question pattern and answer guideline. Open a topic to get a clear explanation and a sample answer that follows the guideline.")}</p>
    <p>{tl("The app remembers which topics you have read. Explanations and sample answers are generated once with DeepSeek and shared, so they open instantly.")}</p>
    <p>{tl("Signed in as")}{" "}<strong>{user.name}</strong> ({user.role}).</p></div></div></>}
