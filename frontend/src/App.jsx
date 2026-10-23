import {useState,useEffect,useCallback,useRef,createContext,useContext} from 'react'
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
import {Users as UsersIcon,GraduationCap,Sparkles,BarChart3,Info,LogOut,Menu,X,ArrowUp,ArrowDown,Search,ChevronLeft,ChevronRight,Sun,Moon,Monitor,Upload,Copy,Check,Pencil,Trash2,Bookmark,Link2,Eye,EyeOff,History,TrendingUp,Flame,Clock,AlertTriangle,Play,Target,RotateCcw,ClipboardList,ArrowRight,Archive,ArchiveRestore,Lock,FileText,Bell,BookOpen} from 'lucide-react'
import '@fontsource/bricolage-grotesque/600.css'
import '@fontsource/bricolage-grotesque/800.css'
import '@fontsource/instrument-sans/400.css'
import '@fontsource/instrument-sans/500.css'
import '@fontsource/instrument-sans/600.css'
import '@fontsource/instrument-sans/700.css'
import './styles.css'

const api=async(p,o={})=>{const t=localStorage.t
  const r=await fetch('/api'+p,{...o,headers:{'Content-Type':'application/json',...(t&&{Authorization:'Bearer '+t})},body:o.body&&JSON.stringify(o.body)})
  const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Something went wrong');return j}
const TEMPLATE=`program,semester,course,unit,topic,content,question_pattern,sample_content,guideline
B.E. Mechanical Engineering,Semester 3,Thermodynamics,Unit 1: Basic concepts,First law of thermodynamics,"Energy can change form but is never created or destroyed.","2 marks: define. 13 marks: derive and solve a numerical.","Q: State the first law for a closed system.","Introduction, labelled diagram, steps, units, conclusion"
,,,,Zeroth law of thermodynamics,"If A and B are each in equilibrium with C, they are in equilibrium with each other.","2 marks: state the law.","Q: State the zeroth law.","Definition, one example, significance"
`
const COL=['#722f99','#c2464e','#7a6f70','#9a6420','#4e1d6c']
const when=iso=>new Date(iso).toLocaleString(undefined,{day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'})  // shown in the viewer's own time zone
const localInput=iso=>{if(!iso)return '';const d=new Date(iso),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`}
const STATUS={not_started:'Not started',in_progress:'In progress',completed:'Completed'}
const doneOf=ts=>`${ts.filter(x=>x.status==='completed').length} of ${ts.length}`  // worked out from each topic's state, never stored
const Mark=({s})=>s==='completed'?<Check className="done" aria-label="Completed"/>:<span className="st" aria-label={STATUS[s]}>{s==='in_progress'?'●':'—'}</span>
const ownerLine=c=>c.mine?'Your course':c.owner_problem||(c.owner?'Owner: '+c.owner:'Owner not assigned')
const useFaculty=on=>{const [l,setL]=useState([]);useEffect(()=>{if(on)api('/admin/users?role=faculty&limit=100').then(r=>setL(r.items.filter(u=>u.active))).catch(()=>{})},[on]);return l}

const firstName=n=>{const w=(n||'').trim().split(/\s+/).filter(Boolean);if(!w.length)return '';if(!/^(dr|prof|mr|mrs|ms|miss)\.?$/i.test(w[0]))return w[0];const rest=w.slice(1).filter(x=>x.replace(/\./g,'').length>1);return rest.length?w[0]+' '+rest[0]:w[0]}  // a title stays with the surname it belongs to ("Dr. A. Kumar" → "Dr. Kumar"), skipping initials
const MAX_FILE_MB=20,tooBig=f=>f.size>MAX_FILE_MB*1024*1024  // the server's limit for one file of study material
const pl=(n,w)=>`${n} ${w}${n===1?'':'s'}`
const matches=n=>`${n} ${n===1?'match':'matches'}`
const Ctx=createContext({})
const THEMES=[['system',Monitor,'Auto'],['light',Sun,'Light'],['dark',Moon,'Dark']]
const readTheme=()=>{try{return localStorage.theme||'system'}catch{return 'system'}}
const applyTheme=t=>{const r=document.documentElement;if(t==='light'||t==='dark')r.dataset.theme=t;else delete r.dataset.theme;const dark=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);document.querySelector('meta[name=theme-color]')?.setAttribute('content',dark?'#120e17':'#f6f4f7')}
// the Zigora mark: a Z in cream and coral on plum (the same drawing as public/favicon.svg)
const ZMark=({size=40})=><svg className="zmark" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="15" fill="#722f99"/><rect x="16" y="15" width="32" height="8" rx="2.5" fill="#fee7c8"/><path d="M38.5 23H48L25.5 41H16Z" fill="#ff9292"/><rect x="16" y="41" width="32" height="8" rx="2.5" fill="#fee7c8"/></svg>
const Logo=({src,size=40})=>src?<img className="logo" src={src} alt="" width={size} height={size} style={{width:size,height:size}}/>:<ZMark size={size}/>
const Lockup=({logo,name,size=40})=><div className="lockup"><Logo src={logo} size={size}/><b>{name}</b></div>
// sign-in, reset and first-password pages: the form, with a brand panel beside it on wide screens
const AuthFrame=({logo,name,children})=><div className="auth"><aside className="authart" aria-hidden="true"><Lockup logo={logo} name={name} size={44}/>
  <div><h2>Learn engineering, one topic at a time.</h2><p>Courses, notes, practice tests and progress for every program, semester and student, in one place.</p></div>
  <div className="bands"><i style={{background:'#722f99'}}/><i style={{background:'#c5c1c1'}}/><i style={{background:'#fee7c8'}}/><i style={{background:'#ff9292'}}/></div></aside>{children}</div>

export default function App(){
  const [user,setUser]=useState(null),[ready,setReady]=useState(false),[pageSel,setPage]=useState(null),[msg,setMsg]=useState(''),[open,setOpen]=useState(false),[name,setName]=useState('Zigora'),[canReset,setCanReset]=useState(false),[canReg,setCanReg]=useState(false),[resetTok,setResetTok]=useState(()=>(/^#reset=([\w-]+)$/.exec(location.hash)||[])[1]||null),[start,setStart]=useState(null),[logo,setLogo]=useState(null),[theme,setTheme]=useState(readTheme),[ask,setAsk]=useState(null),[studyStart,setStudyStart]=useState(null),[findQ,setFindQ]=useState({q:'',n:0})
  const confirm=useCallback(o=>new Promise(res=>setAsk({o,res})),[])  // in-app replacement for window.confirm: await confirm({title,body,ok,danger})
  const toast=useCallback(m=>{setMsg(m);setTimeout(()=>setMsg(''),2800)},[])
  useEffect(()=>{Promise.allSettled([api('/config').then(c=>{setName(c.name);setLogo(c.logo||null);setCanReset(!!c.email_reset);setCanReg(!!c.self_registration);document.title=c.name}),localStorage.t?api('/me').then(setUser).catch(()=>localStorage.removeItem('t')):null]).then(()=>setReady(true))},[])
  useEffect(()=>{applyTheme(theme);if(theme!=='system')return;const m=matchMedia('(prefers-color-scheme: dark)'),f=()=>applyTheme('system');m.addEventListener('change',f);return()=>m.removeEventListener('change',f)},[theme])
  const pickTheme=t=>{setTheme(t);try{t==='system'?localStorage.removeItem('theme'):localStorage.theme=t}catch{/* private mode: the choice lasts until the page closes */}}
  useEffect(()=>{const k=e=>e.key==='Escape'&&setOpen(false);addEventListener('keydown',k);return()=>removeEventListener('keydown',k)},[])
  useEffect(()=>{document.body.style.overflow=open?'hidden':''},[open])
  if(!ready)return null
  if(resetTok)return <AuthFrame logo={logo} name={name}><ResetPassword token={resetTok} toast={toast} msg={msg} canReset={canReset} appName={name} logo={logo} done={u=>{history.replaceState(null,'',location.pathname);setResetTok(null);setUser(u);toast('Password changed. You are signed in.')}} leave={()=>{history.replaceState(null,'',location.pathname);setResetTok(null)}}/></AuthFrame>
  if(!user)return <AuthFrame logo={logo} name={name}><Login onIn={setUser} toast={toast} msg={msg} appName={name} logo={logo} canReset={canReset} canReg={canReg}/></AuthFrame>
  if(user.must_change)return <AuthFrame logo={logo} name={name}><ChangePassword forced appName={name} logo={logo} toast={toast} msg={msg} done={()=>setUser({...user,must_change:false})} out={()=>{localStorage.removeItem('t');setUser(null)}}/></AuthFrame>
  const student=user.role==='student',page=pageSel||'home',admin=user.role==='admin',go=k=>{if(k==='build')setStudyStart(null);setPage(k);setOpen(false)},openIn=nav=>{setStart(nav);go('learn')},openStudy=t=>{setPage('build');setOpen(false);setStudyStart(t)},find=q=>{setFindQ(f=>({q,n:f.n+1}));go('search')},signOut=()=>{localStorage.removeItem('t');setOpen(false);setPage(null);setUser(null)}
  // the side menu (the logo goes Home; search, change password, theme and sign out are in the header)
  const links=student?[['learn',GraduationCap,'My courses'],['routine',Clock,'My routine'],['progress',TrendingUp,'My progress'],['build',Upload,'Build a course'],['bookmarks',Bookmark,'Bookmarks'],...(user.self_registered?[['aikey',Sparkles,'My AI key']]:[]),['about',Info,'About']]
    :admin?[['programs',GraduationCap,'Programs'],['courses',BookOpen,'Courses'],['users',UsersIcon,'Users'],['reports',BarChart3,'Reports'],['activity',History,'Activity log'],['ai',Sparkles,'Settings'],['about',Info,'About']]
    :[['learn',BookOpen,'Courses'],['bookmarks',Bookmark,'Bookmarks'],['reports',BarChart3,'Reports'],...(user.self_registered?[['aikey',Sparkles,'My AI key']]:[]),['about',Info,'About']]
  return <Ctx.Provider value={{menu:()=>setOpen(true),appName:name,confirm}}>
    <TopBar user={user} theme={theme} pickTheme={pickTheme} onMenu={()=>setOpen(true)} onHome={()=>go('home')} onAccount={()=>go('password')} onOut={signOut} onNote={()=>go('home')} page={page}/>
    {page!=='search'&&<GlobalSearch key={findQ.n} onFind={find}/>}
    {page==='home'&&student&&<Dashboard user={user} toast={toast} onOpen={openIn} onSearch={()=>go('search')} onStudy={openStudy} onRoutine={()=>go('routine')}/>}
    {page==='routine'&&student&&<RoutinePage toast={toast} done={()=>go('home')}/>}
    {page==='home'&&!student&&<StaffHome user={user} toast={toast} open={openIn}/>}
    {page==='search'&&<SearchPage key={findQ.n} initial={findQ.q} user={user} toast={toast}/>}{page==='learn'&&<Learn key={String(start)} start={start} user={user} toast={toast} appName={name}/>}
    {page==='progress'&&user.role==='student'&&<Insights toast={toast} role={user.role}/>}
    {page==='build'&&user.role==='student'&&<StudyHome key={JSON.stringify(studyStart)} start={studyStart} toast={toast}/>}
    {page==='bookmarks'&&!admin&&<Bookmarks toast={toast} role={user.role}/>}
    {page==='users'&&admin&&<Users toast={toast} me={user}/>}{page==='courses'&&admin&&<AdminCourses toast={toast} onOpen={openIn}/>}{page==='programs'&&admin&&<Programs toast={toast} onOpen={openIn}/>}
    {page==='ai'&&admin&&<AiConfig toast={toast} onBrand={()=>api('/config').then(c=>{setName(c.name);setLogo(c.logo||null);document.title=c.name})}/>}{page==='reports'&&(admin||user.role==='faculty')&&<Reports role={user.role} toast={toast}/>}{page==='activity'&&admin&&<Activity/>}{page==='aikey'&&user.self_registered&&<MyAiKey toast={toast}/>}{page==='password'&&<ChangePassword toast={toast} done={()=>go('learn')}/>}{page==='about'&&<About user={user}/>}
    <div className={'drawer'+(open?' open':'')}><div className="dscrim" onClick={()=>setOpen(false)}/>
      <nav className="panel" aria-label="Main menu">
        <div className="dhead"><button className={'homebtn'+(page==='home'?' on':'')} aria-label={name+', home'} aria-current={page==='home'?'page':undefined} onClick={()=>go('home')}><Logo src={logo} size={36}/><span><b>{name}</b><small>{user.name}, {user.role}</small></span></button><button className="ic" aria-label="Close menu" onClick={()=>setOpen(false)}><X/></button></div>
        {links.map(([k,I,l])=><button key={k} className={'dlink'+(page===k?' on':'')} onClick={()=>{if(k==='learn')setStart(null);go(k)}}><I size={20}/>{l}</button>)}
      </nav></div>
    <footer className="foot"><span>© {new Date().getFullYear()} {name}. All rights reserved.</span></footer>
    <Toast msg={msg}/>
    {ask&&<Confirm o={ask.o} answer={ok=>{ask.res(ok);setAsk(null)}}/>}
  </Ctx.Provider>}

function Login({onIn,toast,msg,appName,logo,canReset,canReg}){
  const [f,setF]=useState({email:'',password:''}),[b,setB]=useState(false),[mode,setMode]=useState('in'),[sent,setSent]=useState('')
  const go=async()=>{setB(true);try{const r=await api('/login',{method:'POST',body:f});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  const forgot=async()=>{setB(true);try{setSent((await api('/forgot',{method:'POST',body:{email:f.email}})).message)}catch(e){toast(e.message)}setB(false)}
  if(mode==='register')return <Register onIn={onIn} toast={toast} msg={msg} appName={appName} logo={logo} back={()=>setMode('in')}/>
  if(mode==='forgot')return <div className="login"><Lockup logo={logo} name={appName}/><h1>Forgot your password?</h1>{sent?<p>{sent}</p>:<><p>Enter your account email and we will send a link to choose a new one.</p>
    <label>Email</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})} onKeyDown={e=>e.key==='Enter'&&forgot()}/>
    <button className="btn" disabled={b||!f.email} onClick={forgot}>Send reset link</button></>}
    <button className="btn ghost" onClick={()=>{setMode('in');setSent('')}}>Back to sign in</button><Toast msg={msg}/></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>Sign in</h1><p>Use the account your institution created for you.</p>
    <label>Email</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})}/>
    <label>Password</label><input type="password" autoComplete="current-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Sign in</button>
    {canReset?<button className="btn ghost" onClick={()=>setMode('forgot')}>Forgot password?</button>:<p className="known">Forgot your password? Ask your admin to reset it.</p>}{canReg&&<button className="btn ghost" onClick={()=>setMode('register')}>Create an account</button>}<Toast msg={msg}/></div>}

function Register({onIn,toast,msg,appName,logo,back}){
  const [f,setF]=useState({name:'',institution:'',id_number:'',email:'',phone:'',password:''}),[stage,setStage]=useState('form'),[code,setCode]=useState(''),[b,setB]=useState(false),[wait,setWait]=useState(0),[info,setInfo]=useState(''),[st,setSt]=useState({domains:[]})
  useEffect(()=>{api('/register/status').then(setSt).catch(()=>{})},[])
  useEffect(()=>{if(wait<=0)return;const t=setTimeout(()=>setWait(wait-1),1000);return()=>clearTimeout(t)},[wait])
  const set=k=>e=>setF({...f,[k]:e.target.value}),ok=Object.values(f).every(v=>v.trim())
  const start=async()=>{setB(true);try{const r=await api('/register/start',{method:'POST',body:f});setInfo(r.message);setStage('code');setWait(30)}catch(e){toast(e.message)}setB(false)}
  const verify=async()=>{setB(true);try{const r=await api('/register/verify',{method:'POST',body:{email:f.email,code}});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  const resend=async()=>{try{await api('/register/resend',{method:'POST',body:{email:f.email}});toast('A new code is on its way');setWait(30);setCode('')}catch(e){toast(e.message)}}
  if(stage==='code')return <div className="login"><Lockup logo={logo} name={appName}/><h1>Enter the code</h1><p>{info}</p>
    <label htmlFor="otp">6-digit code</label><input id="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} onKeyDown={e=>e.key==='Enter'&&code.length===6&&verify()} style={{letterSpacing:'.4em',fontSize:22,textAlign:'center'}}/>
    <button className="btn" disabled={b||code.length!==6} onClick={verify}>Verify and create my account</button>
    <button className="btn ghost" disabled={wait>0} onClick={resend}>{wait>0?`Send a new code in ${wait}s`:'Send a new code'}</button>
    <button className="btn ghost" onClick={()=>{setStage('form');setCode('')}}>Change my details</button><Toast msg={msg}/></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>Create an account</h1><p>We will email you a code to confirm your address.{st.domains.length>0&&' Use your institution email ('+st.domains.map(d=>'@'+d).join(', ')+').'}</p>
    <label htmlFor="rn">Full name</label><input id="rn" autoComplete="name" value={f.name} onChange={set('name')}/>
    <label htmlFor="ri">Institution</label><input id="ri" autoComplete="organization" value={f.institution} onChange={set('institution')}/>
    <label htmlFor="rid">ID number</label><input id="rid" value={f.id_number} onChange={set('id_number')} placeholder="Roll or employee number"/>
    <label htmlFor="re">Email</label><input id="re" type="email" autoComplete="email" value={f.email} onChange={set('email')}/>
    <label htmlFor="rp">Phone</label><input id="rp" type="tel" autoComplete="tel" value={f.phone} onChange={set('phone')} placeholder="+91 98765 43210"/>
    <label htmlFor="rw">Password</label><input id="rw" type="password" autoComplete="new-password" value={f.password} onChange={set('password')} onKeyDown={e=>e.key==='Enter'&&ok&&start()}/>
    <p className="known">At least 8 characters. AI help on this account uses your own DeepSeek API key, which you add after signing in.</p>
    <button className="btn" disabled={b||!ok} onClick={start}>Send me a code</button><button className="btn ghost" onClick={back}>Back to sign in</button><Toast msg={msg}/></div>}

function MyAiKey({toast}){
  const confirm=useConfirm()
  const [d,setD]=useState(null),[key,setKey]=useState(''),[b,setB]=useState(false)
  const load=()=>api('/me/ai-key').then(setD).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  const save=async()=>{setB(true);try{await api('/me/ai-key',{method:'PUT',body:{key}});setKey('');toast('Key saved. AI help is on.');load()}catch(e){toast(e.message)}setB(false)}
  const del=async()=>{if(!await confirm({title:'Remove your key?',body:'AI help turns off for you until you add one again.',ok:'Remove key',danger:true}))return;try{await api('/me/ai-key',{method:'DELETE'});toast('Key removed');load()}catch(e){toast(e.message)}}
  return <><Bar title="My AI key" sub={d?.key_set?'AI is on · key '+d.key_hint:'AI is off · no key yet'}/><div className="main">
    <p className="known">AI explanations on your account use your own DeepSeek API key, so any usage is billed to your DeepSeek account. Create a key at platform.deepseek.com, paste it here and save. We check it with DeepSeek first, then store it encrypted. It is never shown again in full.</p>
    <label htmlFor="k">DeepSeek API key</label><input id="k" type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder={d?.key_set?'Paste a new key to replace the current one':'sk-…'}/>
    <button className="btn" disabled={b||!key.trim()} onClick={save}>{b?'Checking the key…':'Save key'}</button>
    {d?.key_set&&<button className="btn ghost" onClick={del}>Remove my key</button>}</div></>}

function PromptEditor({toast}){
  const confirm=useConfirm()
  const [items,setItems]=useState(null),[draft,setDraft]=useState({}),[busy,setBusy]=useState('')
  const load=()=>api('/admin/prompts').then(r=>{setItems(r.items);setDraft({})}).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  if(!items)return <div className="sk"/>
  const save=async x=>{const text=draft[x.kind];if(x.saved_answers>0&&!await confirm({title:'Save this prompt?',body:`Saving discards the ${pl(x.saved_answers,'saved answer')} written with the old prompt, so students get fresh ones.`,ok:'Save prompt'}))return
    setBusy(x.kind);try{const r=await api('/admin/prompts/'+x.kind,{method:'PUT',body:{text}});toast('Prompt saved'+(r.cleared?` · ${pl(r.cleared,'saved answer')} cleared`:''));load()}catch(e){toast(e.message)}setBusy('')}
  const reset=async x=>{if(!await confirm({title:'Go back to the built-in prompt?',body:x.saved_answers?`This also discards ${pl(x.saved_answers,'saved answer')}.`:null,ok:'Reset to built-in'}))return
    setBusy(x.kind);try{await api('/admin/prompts/'+x.kind,{method:'DELETE'});toast('Back to the built-in prompt');load()}catch(e){toast(e.message)}setBusy('')}
  return <><p className="known">These are the instructions the AI gets before it answers. Change the tone, depth, language or format to suit your students. Saving a prompt discards the saved answers it wrote, so the new wording applies from the next question (that costs tokens again).</p>
    {items.map(x=>{const v=draft[x.kind]??x.text,dirty=v.trim()!==x.text.trim()
      return <div key={x.kind} className="qbox"><b>{x.label}{x.custom&&<span className="chip" style={{marginLeft:8}}>Edited</span>}</b><p className="known" style={{margin:'4px 0 8px'}}>{x.help}</p>
        <textarea aria-label={x.label+' prompt'} rows={9} value={v} maxLength={4000} onChange={e=>setDraft({...draft,[x.kind]:e.target.value})}/>
        <small className="known">{v.length} / 4000 characters</small>
        <div className="two"><button className="btn" disabled={!dirty||busy===x.kind||v.trim().length<20} onClick={()=>save(x)}>Save prompt</button><button className="btn ghost" disabled={busy===x.kind||(!x.custom&&!dirty)} onClick={()=>x.custom?reset(x):setDraft({...draft,[x.kind]:x.default})}>{x.custom?'Reset to built-in':'Undo changes'}</button></div></div>})}</>}

function SelfReg({cfg,run}){
  const [dom,setDom]=useState(null);const on=!!cfg.self_registration,shown=dom??cfg.allowed_domains??''
  return <><p className="known">{on?'On. The sign-in page shows “Create an account”. People confirm their email with a code, then you place them in a program and semester or year from Users (they show as Self-registered).':'Off. Only admins can create accounts.'} {!cfg.mail_on&&'Emailing codes needs SMTP set up first (see the email section below), so registration stays closed until it is.'} {cfg.self_registered_users>0&&`${cfg.self_registered_users} people have registered themselves so far.`}</p>
    <label className="chk"><input type="checkbox" checked={on} onChange={e=>run(()=>api('/admin/settings',{method:'PUT',body:{self_registration:e.target.checked}}),e.target.checked?'Self-registration is on':'Self-registration is off')}/> Allow people to register themselves</label>
    <label htmlFor="dom">Only these email domains (optional)</label><input id="dom" value={shown} onChange={e=>setDom(e.target.value)} placeholder="college.edu, mail.college.edu"/>
    <button className="btn ghost" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{allowed_domains:shown}}).then(()=>setDom(null)),'Domains saved')}>Save domains</button>
    <p className="known">Self-registered people always use their own DeepSeek key, never yours.</p></>}

function ResetPassword({token,toast,msg,done,leave,canReset,appName,logo}){
  const [ok,setOk]=useState(null),[f,setF]=useState({password:'',again:''}),[b,setB]=useState(false)
  useEffect(()=>{api('/reset/check',{method:'POST',body:{token}}).then(r=>setOk(r.valid)).catch(()=>setOk(false))},[token])
  const go=async()=>{if(f.password.length<8)return toast('Use at least 8 characters');if(f.password!==f.again)return toast("The passwords don't match")
    setB(true);try{const r=await api('/reset',{method:'POST',body:{token,new_password:f.password}});localStorage.t=r.token;done(r.user)}catch(e){toast(e.message)}setB(false)}
  if(ok===null)return null
  if(!ok)return <div className="login"><Lockup logo={logo} name={appName}/><h1>This link has expired</h1><p>Reset links work once and only for a short time.{canReset?' Ask for a new one from the sign-in page.':' Ask your admin to reset your password.'}</p><button className="btn" onClick={leave}>Go to sign in</button></div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>Choose a new password</h1><p>Use at least 8 characters.</p>
    <label>New password</label><input type="password" autoComplete="new-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})}/>
    <label>Repeat new password</label><input type="password" autoComplete="new-password" value={f.again} onChange={e=>setF({...f,again:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Save and sign in</button><Toast msg={msg}/></div>}

function ChangePassword({forced,appName,logo,toast,msg,done,out}){
  const [f,setF]=useState({current:'',password:'',again:''}),[b,setB]=useState(false),set=k=>e=>setF({...f,[k]:e.target.value})
  const go=async()=>{if(f.password.length<8)return toast('Use at least 8 characters');if(f.password!==f.again)return toast("The new passwords don't match")
    setB(true);try{const d=await api('/me/password',{method:'POST',body:{current:f.current,new_password:f.password}});if(d.token)localStorage.t=d.token;toast('Password changed');done()}catch(e){toast(e.message)}setB(false)}
  const form=<><label>{forced?'Password your admin gave you':'Current password'}</label><input type="password" autoComplete="current-password" value={f.current} onChange={set('current')}/>
    <label>New password (8+ characters)</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/>
    <label>Repeat new password</label><input type="password" autoComplete="new-password" value={f.again} onChange={set('again')} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Change password</button></>
  if(forced)return <div className="login"><Lockup logo={logo} name={appName}/><h1>Choose your own password</h1><p>Your admin set a temporary password. Pick a new one to continue.</p>{form}<button className="btn ghost" onClick={out}>Sign out</button><Toast msg={msg}/></div>
  return <><Bar title="Change password"/><div className="main">{form}</div></>}

const Bar=({title,sub,back,right})=><div className="bar">{back&&<button className="ic" aria-label="Back" onClick={back}><ChevronLeft/></button>}
  <h1>{title}{sub&&<small>{sub}</small>}</h1>{right}</div>
// the header on every signed-in page: menu (phone), notifications, theme, the signed-in user (opens Change password) and sign out at the far right
const initials=n=>(n||'?').trim().split(/\s+/).filter(w=>!/^(dr|prof|mr|mrs|ms|miss)\.?$/i.test(w)).slice(0,2).map(w=>w[0]).join('').toUpperCase()||'?'
function TopBar({user,theme,pickTheme,onMenu,onHome,onAccount,onOut,onNote,page}){
  const {appName}=useContext(Ctx),i=THEMES.findIndex(t=>t[0]===theme),[,ThemeIcon,themeLabel]=THEMES[i<0?0:i],nextTheme=THEMES[(i+1)%THEMES.length]
  return <header className="top"><button className="ic menu" aria-label="Open menu" onClick={onMenu}><Menu/></button><button className="topname" onClick={onHome}>{appName}</button>
    <span className="topgap"/>
    <Notifications user={user} onOpen={onNote} page={page}/>
    <button className="ic" aria-label={`Theme: ${themeLabel}. Switch to ${nextTheme[2]}`} title={`Theme: ${themeLabel}`} onClick={()=>pickTheme(nextTheme[0])}><ThemeIcon size={19}/></button>
    <button className={'who'+(page==='password'?' on':'')} onClick={onAccount} title="Change password"><span className="av" aria-hidden="true">{initials(user.name)}</span><span className="whotx"><b>{user.name}</b><small>{user.role}</small></span></button>
    <button className="ic" aria-label="Sign out" title="Sign out" onClick={onOut}><LogOut size={19}/></button></header>}
// what needs doing: staff get the overview's attention list, students their overdue and due-soon topics and untried or failed tests
function Notifications({user,onOpen,page}){
  const [items,setItems]=useState(null),[open,setOpen]=useState(false),box=useRef(null)
  const load=useCallback(()=>{(user.role==='student'?api('/me/today').then(r=>(r.focus||[]).filter(x=>['overdue','due_soon','quiz_new','quiz_retake'].includes(x.kind)).map(x=>({text:x.title,sub:x.reason}))):api('/overview').then(r=>r.attention.map(x=>({text:x.text})))).then(setItems).catch(()=>setItems([]))},[user.role])
  useEffect(load,[load,page])
  useEffect(()=>{if(!open)return;const f=e=>{if(!box.current?.contains(e.target))setOpen(false)},k=e=>e.key==='Escape'&&setOpen(false);addEventListener('pointerdown',f);addEventListener('keydown',k);return()=>{removeEventListener('pointerdown',f);removeEventListener('keydown',k)}},[open])
  const n=items?.length||0
  return <div className="notes" ref={box}><button className="ic" aria-label={n?`Notifications, ${n} new`:'Notifications'} aria-expanded={open} onClick={()=>{setOpen(!open);if(!open)load()}}><Bell size={19}/>{n>0&&<em className="badge">{n>9?'9+':n}</em>}</button>
    {open&&<div className="pop" role="dialog" aria-label="Notifications"><b className="poph">Notifications</b>
      {items===null?<Skeleton/>:n?items.map((x,j)=><button key={j} className="note" onClick={()=>{setOpen(false);onOpen()}}><span>{x.text}</span>{x.sub&&<small>{x.sub}</small>}</button>):<p className="known">You're all caught up.</p>}</div>}</div>}
// the search box under the header on every page: Enter opens Search with the query
function GlobalSearch({onFind}){
  const [q,setQ]=useState('')
  return <form className="gsearch" role="search" onSubmit={e=>{e.preventDefault();if(q.trim().length>=2)onFind(q.trim())}}><div className="search"><Search size={18}/><input type="search" aria-label="Search topics" placeholder="Search topics, or ask a question" value={q} maxLength={200} onChange={e=>setQ(e.target.value)}/></div></form>}

const ARCHIVE_WHAT={programs:'every semester or year, course, unit, topic and quiz in it',semesters:'every course, unit, topic and quiz in it',courses:'its units, topics and quizzes',units:'its topics and quizzes',topics:'this topic'}
const ONE={programs:'program',semesters:'semester or year',courses:'course',units:'unit',topics:'topic'}
function ArchiveSheet({a,close,done,toast}){  // archive or restore one item; archiving takes everything under it along, nothing is deleted
  const [busy,setBusy]=useState(false)
  const go=async()=>{setBusy(true);try{await api(`/${a.kind}/${a.id}/archive`,{method:'PUT',body:{archived:a.on}});toast(a.on?'Archived':'Restored');done()}catch(e){toast(e.message);setBusy(false)}}
  return <Sheet close={close}><h3>{a.on?'Archive':'Restore'} “{a.name}”?</h3>
    <p className="known">{a.on?`This hides the ${ONE[a.kind]} and ${ARCHIVE_WHAT[a.kind]} from students, who see “unavailable right now” instead. Nothing is deleted and reading progress and quiz results are kept. You can restore it any time.`
      :`This brings back the ${ONE[a.kind]} and everything that was archived along with it. Anything you archived on its own inside it stays archived until you restore that too.`}</p>
    <button className={'btn'+(a.on?' danger':'')} disabled={busy} onClick={go}>{busy?'Working…':a.on?'Archive':'Restore'}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}
const ArchPill=({x})=>x.archived?<span className="pill off sm">{x.archived_self?'Archived':'Archived with its parent'}</span>:null
function Learn({user,toast,appName,start}){
  const isAdmin=user.role==='admin',staff=user.role!=='student'
  const [mat,setMat]=useState(false)
  const [copy,setCopy]=useState(null),[tree,setTree]=useState([]),[nav,setNav]=useState(start||[]),[sheet,setSheet]=useState(null),[cp,setCp]=useState(null),[t,setT]=useState(null),[ed,setEd]=useState(null),[del,setDel]=useState(null),[sh,setSh]=useState(null),[qz,setQz]=useState(null),[qe,setQe]=useState(null),[arch,setArch]=useState(null),[showArch,setShowArch]=useState(false),[qr,setQr]=useState(null),[gb,setGb]=useState(null)
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
  const saveShare=async()=>{try{await api(`/courses/${sh.id}/links`,{method:'PUT',body:{semester_ids:sh.sel}});toast('Sharing updated');setSh(null);load()}catch(e){toast(e.message)}}
  const remove=async()=>{try{if(del.unlink)await api(`/courses/${del.unlink.id}/links`,{method:'PUT',body:{semester_ids:del.unlink.keep}});else await api(`/${del.kind}/${del.id}`,{method:'DELETE'});toast('Deleted');setDel(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={cur?.name||appName} sub={nav.length?crumbs:'Hi '+user.name} back={nav.length>0&&(()=>setNav(nav.slice(0,-1)))}/>
   <div className="main">{unit&&mayEdit&&drafts(unit.topics)>0&&<button className="btn" style={{marginTop:0,marginBottom:12}} onClick={()=>setPub(`/units/${unit.id}/publish`,true,'All drafts published')}>Publish all {drafts(unit.topics)} drafts</button>}{!nav.length&&!(user.role==='faculty'&&myCourses.length>0)&&<div className="hero"><h2>Choose a program</h2></div>}
     {staff&&(anyArch||showArch)&&<label className="chk" style={{marginBottom:12}}><input type="checkbox" checked={showArch} onChange={e=>setShowArch(e.target.checked)}/> Show archived{!showArch&&hidden>0?` (${hidden} here)`:''}</label>}
     {isAdmin&&!sem&&<button className="btn ghost lead" onClick={()=>setSheet(prog?{type:'semester',sem:{},pid:prog.id}:{type:'program',p:{}})}>{prog?'Add '+prog.term.toLowerCase()+' to '+prog.name:'New program'}</button>}
     {isAdmin&&sem&&!co&&<button className="btn ghost lead" onClick={()=>setSheet({type:'course',c:{},pid:prog.id,sid:sem.id})}>Add course to {sem.name}</button>}
     {co&&!unit&&!staff&&<p className="known" style={{marginTop:0}}>{doneOf(co.units.flatMap(n=>n.topics))} topics completed</p>}
     {co&&!unit&&!staff&&(()=>{const ts=co.units.flatMap(n=>n.topics),k=ts.filter(x=>x.has_notes).length;return <div className="card"><button className="hit" onClick={()=>setMat(true)}><span className="dot" style={{background:COL[3]}}><FileText size={20}/></span>
       <div><b>{k?'Your notes in '+k+' of '+ts.length+' topics':'Bring your own notes'}</b><span>{k?'Add or update your material':'Upload your PDF or Word notes. They are filed under this course\'s topics, for you only.'}</span></div></button></div>})()}
     {co&&!unit&&staff&&<div className="qbox" style={{marginTop:0}}><p className="known" style={{margin:0}}>Owner: <b>{co.mine?'You':co.owner_problem||co.owner||'Not assigned'}</b>{sem.number?` · ${prog.term} no. ${sem.number}`:''}</p>
       {isAdmin&&!co.shared&&<div className="two"><button className="btn ghost" onClick={()=>setSheet({type:'course',c:co,pid:prog.id,sid:co.semester_id})}>Edit course</button><button className="btn ghost" onClick={()=>setSheet({type:'owner',c:co})}>Change owner</button></div>}</div>}
     {!nav.length&&user.role==='faculty'&&<><h3 className="sec first">My courses</h3>{myCourses.length?myCourses.map(({p,s,c},i)=><div key={c.id} className="card"><button className="hit" onClick={()=>setNav([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div><b>{c.name}<ArchPill x={c}/></b><span>{p.name} › {s.name} · {c.units.length} units</span></div></button></div>)
       :<p className="known">No course is assigned to you yet. An admin makes you the owner of a course.</p>}<h3 className="sec">All programs</h3></>}
    {mayEdit&&co&&!unit&&!co.shared&&<button className="btn ghost lead" onClick={()=>setSheet({type:'unit',un:{},cid:co.id})}>Add unit</button>}
    {mayEdit&&unit&&!co.shared&&<button className="btn ghost lead" onClick={()=>setEd({unit_id:unit.id})}>Add topic to {unit.name}</button>}
    {staff&&unit&&<button className="btn ghost lead" onClick={()=>setCopy({kind:'unit',id:unit.id,title:unit.name})}>Copy this unit to another course</button>}
    {list.map((x,i)=>x.locked?<div key={x.id} className="card" style={{opacity:.7}}><button className="hit" onClick={()=>toast('This course is unavailable right now')} aria-label={x.n+', unavailable right now'}><span className="dot" style={{background:'var(--mut)'}}><Lock size={18}/></span><div><b>{x.n}</b><span>Unavailable right now</span></div></button></div>:<div key={x.id} className="card" style={x.archived?{opacity:.75}:undefined}><button className="hit" onClick={x.go}><span className="dot" style={{background:COL[i%5]}}>{x.n[0]}</span><div><b>{x.n}<ArchPill x={x}/></b>{x.sub&&<span>{x.sub}</span>}</div>{(x.s||x.b)&&<span className="marks">{x.b&&<Bookmark className="bm" size={16} fill="currentColor"/>}{x.s&&<Mark s={x.s}/>}</span>}</button>
      <div className="acts">{staff&&x.can&&(x.archived_self||!x.archived)&&<button className="ic sm" aria-label={(x.archived_self?'Restore ':'Archive ')+x.n} onClick={()=>setArch({kind:x.kind,id:x.id,name:x.n,on:!x.archived_self})}>{x.archived_self?<ArchiveRestore size={16}/>:<Archive size={16}/>}</button>}
      {mayEdit&&<>{(x.kind==='units'||x.kind==='topics')&&list.length>1&&[[-1,ArrowUp,'up'],[1,ArrowDown,'down']].map(([d,I,w])=><button key={w} className="ic sm" aria-label={`Move ${x.n} ${w}`} disabled={i+d<0||i+d>=list.length} onClick={()=>move(list,i,d,x.kind==='units'?`/courses/${co.id}/units/order`:`/units/${unit.id}/topics/order`)}><I size={16}/></button>)}{x.pub&&<button className="ic sm" aria-label={(x.draft?'Publish ':'Unpublish ')+x.n} onClick={x.pub}>{x.draft?<Eye size={16}/>:<EyeOff size={16}/>}</button>}{x.share&&<button className="ic sm" aria-label={'Share '+x.n} onClick={x.share}><Link2 size={16}/></button>}<button className="ic sm" aria-label={'Edit '+x.n} onClick={x.edit}><Pencil size={16}/></button><button className="ic sm" aria-label={'Delete '+x.n} onClick={()=>setDel(x.unlink?{...x,unlink:x.unlink}:x)}><Trash2 size={16}/></button></>}</div></div>)}
    {co&&!unit&&(co.tests?.length>0||(mayEdit&&!co.shared))&&<><h3 className="sec">MCQ tests</h3>
      {co.tests.map((q,i)=><div key={q.id} className="card"><button className="hit" onClick={()=>setQz(q.id)}><span className="dot" style={{background:COL[(i+1)%5]}}><ClipboardList size={18}/></span><div><b>{q.title}</b><span>{q.questions} questions · pass {q.pass_percent}%{q.best!=null?' · best '+q.best+'%':''}{q.published?'':' · Draft'}</span></div>{q.best!=null&&q.best>=q.pass_percent&&<span className="marks"><Check size={16}/></span>}</button>
        {mayEdit&&<><button className="ic sm" aria-label={'Results of '+q.title} onClick={()=>setQr(q.id)}><BarChart3 size={16}/></button><button className="ic sm" aria-label={'Edit '+q.title} onClick={()=>setQe({id:q.id,course_id:co.id})}><Pencil size={16}/></button></>}</div>)}
      {mayEdit&&!co.shared&&<button className="btn ghost" onClick={()=>setQe({course_id:co.id,csvFirst:true})}><Upload size={16}/> New MCQ test from a CSV</button>}
      {mayEdit&&<button className="btn ghost" onClick={()=>setGb(co.id)}><BarChart3 size={16}/> Gradebook: final scores for every test</button>}</>}
    {unit&&(unit.quizzes.length>0||mayEdit)&&<><h3 className="sec">Quizzes</h3>
      {unit.quizzes.map((q,i)=><div key={q.id} className="card"><button className="hit" onClick={()=>setQz(q.id)}><span className="dot" style={{background:COL[(i+3)%5]}}>?</span><div><b>{q.title}</b><span>{q.questions} questions · pass {q.pass_percent}%{q.best!=null?' · best '+q.best+'%':''}{q.published?'':' · Draft'}</span></div>{q.best!=null&&q.best>=q.pass_percent&&<span className="marks"><Check size={16}/></span>}</button>
        {mayEdit&&<><button className="ic sm" aria-label={'Results of '+q.title} onClick={()=>setQr(q.id)}><BarChart3 size={16}/></button><button className="ic sm" aria-label={'Edit '+q.title} onClick={()=>setQe({id:q.id,unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}><Pencil size={16}/></button></>}</div>)}
      {mayEdit&&<button className="btn ghost" onClick={()=>setQe({unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}>Add quiz</button>}</>}
    {!list.length&&<p className="known">{(mayEdit&&co)||isAdmin?'Nothing here yet. Use the button above to add it.':!nav.length&&user.role==='student'?'You are not enrolled in a program yet. Ask your admin to add you to one.':'Nothing here yet. Your admin will add it soon.'}</p>}</div>
   {arch&&<ArchiveSheet a={arch} toast={toast} close={()=>setArch(null)} done={()=>setArch(null)}/>}
   {copy&&<CopySheet {...copy} toast={toast} close={()=>{setCopy(null);load()}}/>}
   {del&&<Sheet close={()=>setDel(null)}><h3>{del.unlink?'Remove':'Delete'} “{del.n}”{del.unlink?' from this '+(prog?.term||'semester').toLowerCase():''}?</h3>
     <p className="known">{del.unlink?'It only disappears from this '+(prog?.term||'semester').toLowerCase()+'. The course stays where it was created.':DELETES[del.kind]} This can't be undone.</p>
     <button className="btn danger" onClick={remove}>{del.unlink?'Remove':'Delete'}</button><button className="btn ghost" onClick={()=>setDel(null)}>Cancel</button></Sheet>}
   {sh&&<Sheet page close={()=>setSh(null)}><h3>Share “{sh.name}”</h3><p className="known">Tick every semester or year that should also show this course. You still edit it in one place.</p>
     {allSems.filter(x=>x.id!==sh.home).map(x=><label key={x.id} className="chk"><input type="checkbox" checked={sh.sel.includes(x.id)} onChange={e=>setSh({...sh,sel:e.target.checked?[...sh.sel,x.id]:sh.sel.filter(i=>i!==x.id)})}/> {x.label}</label>)}
     <button className="btn" onClick={saveShare}>Save</button><button className="btn ghost" onClick={()=>setSh(null)}>Cancel</button></Sheet>}
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
  const save=async()=>{setBusy(true);try{const body={name:f.name,semester_no:f.no?+f.no:null};await api(isNew?`/programs/${pid}/semesters`:'/semesters/'+sem.id,{method:isNew?'POST':'PUT',body:isNew?body:{...body,program_id:pid}});toast(isNew?term+' added':'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?'New '+term.toLowerCase():'Edit '+term.toLowerCase()}</h3>
    <label>{term} number</label><select value={f.no} onChange={pickNo}><option value="">Choose…</option>{upTo(maxOf(term)).map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>Name</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder={term+" 3"}/>
    <p className="known" style={{marginTop:10}}>The number sets the order and which students see it: a student in {term.toLowerCase()} 3 sees {term.toLowerCase()}s 1 to 3. Each number is used once per program.</p>
    <button className="btn" disabled={busy||!f.no||!f.name.trim()} onClick={save}>{isNew?'Add '+term.toLowerCase():'Save changes'}</button></Sheet>}
function CourseSheet({c,pid,sid,sems,term='Semester',close,done,toast}){
  const isNew=!c.id,faculty=useFaculty(true),[f,setF]=useState({name:c.name||'',sem:sid,owner:c.owner_id||''}),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{const owner=String(f.owner)!==String(c.owner_id||'')?{faculty_owner_id:f.owner?+f.owner:null}:{}  // unchanged owners are left alone
    await api(isNew?`/programs/${pid}/semesters/${sid}/courses`:'/courses/'+c.id,{method:isNew?'POST':'PUT',body:isNew?{name:f.name,...owner}:{name:f.name,semester_id:+f.sem,...owner}});toast(isNew?'Course added':'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?'New course in '+(sems.find(x=>x.id===sid)?.label||''):'Edit course'}</h3>
    <label>Name</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder="Thermodynamics"/>
    {!isNew&&<><label>{term}</label><select value={f.sem} onChange={e=>setF({...f,sem:+e.target.value})}>{sems.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></>}
    <label>Owner (faculty)</label><select value={f.owner} onChange={e=>setF({...f,owner:e.target.value})}><option value="">Not assigned</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner} (can't edit)</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    {!isNew&&+f.sem!==sid&&<p className="known">Moving the course takes its units, topics, quizzes and owner with it. Students placed there will see it.</p>}
    <button className="btn" disabled={busy||!f.name.trim()} onClick={save}>{isNew?'Add course':'Save changes'}</button></Sheet>}

const STUDY={not_started:'Not opened yet',in_progress:'Opened, not marked completed',completed:'Marked completed'}
const AREA_GROUPS=[['needs_study','Needs another round of study','Read these topics again, then retake the quiz.'],['getting_there','Getting there',''],['strong','Strong areas','You answered these well.']]
function AreaList({areas,onStudy,staff}){
  return <>{AREA_GROUPS.map(([k,title,hint])=>{const L=areas.filter(a=>a.status===k);if(!L.length)return null
    return <div className={'qbox area '+k} key={k}><b>{title} ({L.length})</b>{hint&&!staff&&<p className="known" style={{margin:'4px 0 8px'}}>{hint}</p>}
      {L.map(a=><div className="arow" key={a.topic_id||'u'+a.unit_id}><div><span>{a.title}</span><small>{a.correct} of {a.total} right · {a.percent}%{a.study&&!staff?' · '+STUDY[a.study]:''}{a.course?' · '+a.course:''}</small><Bar2 v={a.percent}/></div>
        {a.topic_id&&onStudy&&<button className="tool" onClick={()=>onStudy(a.topic_id)}>{k==='strong'?'Review':'Study again'}</button>}</div>)}</div>})}</>}
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
    <div className="search"><Search size={18}/><input type="search" aria-label={'Search '+title.toLowerCase()} placeholder="Search" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="qopt"><select aria-label="Sort by" value={order} onChange={e=>setOrder(e.target.value)}><option value="name">Sort: A to Z</option><option value="name_desc">Sort: Z to A</option><option value="detail">Sort: by details</option><option value="newest">Sort: newest first</option>{d?.can_recent&&<option value="recent">Sort: last active</option>}</select></div>
    {!d&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {d&&d.items.length>0&&<div className="uhead" aria-hidden="true"><span>Name</span><span>Details</span><span/></div>}
    {d?.items.map(x=><button key={x.id} className="utr" onClick={()=>setView(x)} aria-label={'Open '+x.title}>
      <span className="nm"><span className="dot" style={{background:COL[x.id%5]}}>{(x.title||'?')[0]}</span><span className="tx"><b>{x.title}</b><small className="sub">{x.sub}</small></span></span>
      <span className="pg">{x.detail||'—'}</span><span className="sn"><ChevronRight size={16}/></span></button>)}
    {d&&!d.items.length&&<p className="known">{q?'Nothing matches that search.':'Nothing here. All clear.'}</p>}
    {d&&total>RS_PAGE&&<nav className="pager" aria-label="Pages"><button className="btn ghost" disabled={page===0} onClick={()=>setPage(page-1)}><ChevronLeft size={18}/><span>Previous</span></button><small>Page {page+1} of {pages}</small><button className="btn ghost" disabled={page+1>=pages} onClick={()=>setPage(page+1)}><span>Next</span><ChevronRight size={18}/></button></nav>}
  </div></>}
function StaffHome({user,toast,open}){
  const [o,setO]=useState(null),[list,setList]=useState(null),[rep,setRep]=useState(null)
  useEffect(()=>{if(!list&&!rep)api('/overview').then(setO).catch(e=>toast(e.message))},[toast,list,rep])
  if(rep)return <StudentReport c={rep} back={()=>setRep(null)} toast={toast}/>
  if(list)return <ResultSet kind={list} user={user} back={()=>setList(null)} toast={toast} open={open}/>
  const admin=user.role==='admin',hour=new Date().getHours(),hi=hour<12?'Good morning':hour<17?'Good afternoon':'Good evening'
  const stats=o?(admin?[[o.people.students,'Active students','students'],[o.people.active_week,'Studied this week','active_week'],[o.people.faculty,'Faculty','faculty'],[o.courses,'Courses','courses']]:[[o.courses,'Your courses','courses'],[o.topics,'Topics','topics'],[o.drafts,'Drafts','drafts']]):[]
  return <><Bar title={`${hi}, ${firstName(user.name)}`} sub={admin?'Across the whole college':'Your courses'}/><div className="main">
    {!o&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {o&&<div className="stats">{stats.map(([n,l,k])=><button className="stat" key={l} style={{textAlign:'left',width:'100%'}} onClick={()=>setList(k)} aria-label={`${(n??0).toLocaleString()} ${l}. Show the list`}><b>{(n??0).toLocaleString()}</b>{l}</button>)}</div>}
    {o&&<><h3 className="sec">Needs attention</h3>
      {o.attention.length?o.attention.map(x=><button key={x.kind} className="card" style={{textAlign:'left'}} onClick={()=>setList(ATTN_GO[x.kind]||'drafts')}><div style={{flex:1}}><b>{x.text}</b></div><ChevronRight size={18}/></button>)
        :<p className="known">Nothing needs your attention right now.</p>}</>}
    {o&&!o.courses&&!admin&&<p className="known">No course is assigned to you yet. An admin makes you the owner of a course.</p>}
    {o?.courses>0&&<><h3 className="sec">{admin?'Courses':'Your courses'}</h3><CourseReports toast={toast} onOpen={setRep}/></>}
  </div></>}
const FOCUS={overdue:[AlertTriangle,'Overdue','Open it'],due_soon:[Clock,'Due soon','Open it'],weak:[Target,'Needs review','Review'],resume:[Play,'Continue','Continue'],quiz_retake:[RotateCcw,'Retake the quiz','Retake'],quiz_new:[ClipboardList,'Quiz','Take the quiz'],next:[ArrowRight,'Next up','Start']}
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
    <button className="search fake" onClick={onSearch} aria-label="Search topics"><Search size={18}/><span>Search any topic</span></button>
    {sme&&sme.courses>0&&<><h3 className="sec first">Your own courses</h3><LearnCard me={sme} compact onContinue={n=>onStudy({id:n.course_id,topic:n.topic_id})} onReview={cid=>onStudy({review:cid})}/></>}
    {sme&&!sme.courses&&tree&&!courses.length&&<button className="row rowbtn" onClick={()=>onStudy(null)}><span className="dot" style={{background:'var(--acc)'}}><Upload size={18}/></span><div>Build a course from your own notes<small>Upload a PDF or Word file and study it with quick checks, quizzes and reviews</small></div><ChevronRight size={18}/></button>}
    {!tree&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {tree&&!courses.length&&<p className="known">{user.self_registered&&!user.placed?'Your account is ready. An admin will place you in your program and semester or year, and your courses will appear here.':'You are not enrolled in a course yet. Ask your admin to add you to one.'}</p>}
    {planErr&&courses.length>0&&<p className="known" role="alert">Today's plan could not load ({planErr}). Your courses are below. If this keeps happening, tell your admin.</p>}
    {today&&courses.length>0&&<><div className="stats dstats">
      <div className="stat"><b><Flame size={20} className={'flame'+(today.streak?' on':'')} aria-hidden="true"/> {today.streak}</b>Day streak<small>{today.active_today?'Studied today':today.streak?'Study today to keep it':'Start one today'}</small></div>
      <div className="stat"><b>{today.completed_this_week}</b>Done this week<small>{pl(today.active_days_week,'active day')}</small></div>
      <div className="stat"><b>{today.percent}%</b>Completed<small>{today.topics_completed} of {today.topics_total} topics</small></div>
      <div className="stat"><b>{today.quiz_average==null?'–':today.quiz_average+'%'}</b>Quiz average<small>{today.quiz_average==null?'No quizzes yet':'best scores'}</small></div></div>
      <div className="week" role="img" aria-label={`Studied on ${today.week.filter(d=>d.active).length} of the last 7 days`}>{today.week.map(d=><span key={d.date} className={'wd'+(d.active?' on':'')+(d.today?' now':'')}><i>{d.active&&<Check size={13}/>}</i><small>{d.label}</small></span>)}</div></>}
    {top&&<><h3 className="sec first">Today's focus</h3>
      <div className="hero"><small>{top.kind==='overdue'||top.kind==='due_soon'?top.reason:FOCUS[top.kind][1]+' · '+top.reason}</small><h2 style={{fontSize:24}}>{top.title}</h2><p>{top.course} · {top.unit}</p>
        <button className="btn inv" style={{marginTop:14}} onClick={()=>act(top)}>{FOCUS[top.kind][2]}</button></div></>}
    {routine&&focus.length>0&&<h3 className="sec first">Also worth doing</h3>}{focus.slice(top?1:0).map((f,i)=>{const [I,,go]=FOCUS[f.kind];return <button key={i} className="frow" onClick={()=>act(f)}><span className={'fic '+f.kind}><I size={18}/></span><span className="ftx"><b>{f.title}</b><small>{f.reason} · {f.course}</small></span><span className="fgo">{go}</span></button>})}
    {today&&courses.length>0&&!focus.length&&!routine&&<div className="qbox" style={{marginTop:6}}><b>You are all caught up</b><p className="known" style={{margin:'6px 0 0'}}>Nothing is overdue or waiting. Search a topic you want to revisit, or try a quiz to test yourself.</p></div>}
    {courses.length>0&&<><h3 className="sec">My courses</h3>{courses.map(({p,s,c,topics},i)=>{const done=topics.filter(t=>t.status==='completed').length,pc=topics.length?Math.round(100*done/topics.length):0,late=topics.filter(t=>t.overdue).length,next=topics.find(t=>t.status==='in_progress')||topics.find(t=>t.status==='not_started')
      if(c.archived)return <div key={c.id} className="card" style={{opacity:.7}}><button className="hit" onClick={()=>toast('This course is unavailable right now')} aria-label={c.name+', unavailable right now'}><span className="dot" style={{background:'var(--mut)'}}><Lock size={18}/></span><div><b>{c.name}</b><span>Unavailable right now</span></div></button></div>
      return <div key={c.id} className="card" style={{display:'block'}}><button className="hit" style={{width:'100%'}} onClick={()=>onOpen([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div style={{flex:1}}><b>{c.name}{late>0&&<span className="pill off sm">{late} overdue</span>}</b><span>{done} of {topics.length} topics completed · {pc}%</span><Bar2 v={pc}/>{next&&<span className="nexts">{next.status==='in_progress'?'Continue':'Next'}: {next.title}</span>}</div></button></div>})}</>}
    {due.length>0&&<><h3 className="sec">Coming up</h3>{due.map(t=><button key={t.id} className="row rowbtn" onClick={()=>setTopic(t.id)}><div>{t.title}<small>{t.x.c.name} · due {new Date(t.learning_due_at).toLocaleDateString(undefined,{weekday:'short',day:'numeric',month:'short'})}</small></div>{t.overdue&&<span className="pill off sm">Overdue</span>}<ChevronRight size={18}/></button>)}</>}
    {need.length>0&&<><h3 className="sec">Worth another round of study</h3><AreaList areas={need} onStudy={setTopic}/></>}
  </div></>}
const WD=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
const nextStudyDay=days=>{for(let k=1;k<=7;k++){const d=new Date(Date.now()+k*864e5);if(days[(d.getDay()+6)%7]==='1')return k===1?'tomorrow':WD[(d.getDay()+6)%7]}return ''}
function SessionCard({toast,onRoutine,openTopic,onStudy,refresh,onLoad}){  // today's one session, from the student's own routine
  const [v,setV]=useState(null),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/me/session').then(x=>{setV(x);onLoad?.(x)}).catch(()=>{})},[refresh])
  if(!v)return null
  if(!v.routine)return <button className="row rowbtn" onClick={onRoutine}><span className="dot" style={{background:'var(--acc)'}}><Clock size={18}/></span><div>Set your study routine<small>Pick your study days and minutes. Each day you get one small session, at your own pace.</small></div><ChevronRight size={18}/></button>
  const open=x=>x.kind==='review'?onStudy({review:x.course_id}):x.src==='study'?onStudy({id:x.course_id,topic:x.id}):openTopic(x.id)
  const extra=async()=>{setBusy(true);try{const x=await api('/me/session',{method:'POST'});setV(x);onLoad?.(x)}catch(e){toast(e.message)}setBusy(false)}
  const r=v.routine,ss=v.session,left=ss?.items.filter(x=>!x.done)||[]
  return <div className="hero session"><div className="shead"><small>Today's session · {r.minutes} min{r.at?' · '+r.at:''}{v.streak>0?` · ${v.streak}-day streak`:''}</small><button className="schip" onClick={onRoutine} aria-label="Change my routine"><Clock size={14}/> Routine</button></div>
    {v.missed>=2&&!v.studied_today&&<p style={{margin:'6px 0 0'}}>Welcome back. Today is just one session, the same as always. No catching up needed.</p>}
    {!ss&&<><h2 style={{fontSize:22}}>Rest day</h2><p>Your next session is {nextStudyDay(r.days)}.</p><button className="btn inv" disabled={busy} onClick={extra}>Study anyway</button></>}
    {ss&&ss.caught_up&&<><h2 style={{fontSize:22}}>All caught up</h2><p>Nothing is left to study right now. Well done.</p></>}
    {ss&&!ss.caught_up&&<>{ss.done?<h2 style={{fontSize:22}}><Check size={22}/> Done for today</h2>:<h2 style={{fontSize:22}}>{left.length} of {ss.items.length} to go</h2>}
      <ul className="sitems">{ss.items.map((x,i)=><li key={i}><button className={'sitem'+(x.done?' done':'')} onClick={()=>open(x)}><span className="sx">{x.done?<Check size={16}/>:x.kind==='review'?<RotateCcw size={16}/>:<Play size={16}/>}</span><span><b>{x.title}</b><small>{x.course}</small></span></button></li>)}</ul>
      {!ss.done&&<button className="btn inv" onClick={()=>open(left[0])}>{left.length===ss.items.length?'Start':'Continue'}: {left[0].title}</button>}
      {ss.done&&<p>See you {nextStudyDay(r.days)}.</p>}</>}
    <p className="splan">{v.plan.left?`${v.plan.left} topics left · at this pace, done by ${new Date(v.plan.finish+'T00:00').toLocaleDateString(undefined,{day:'numeric',month:'short'})}`:'Nothing left in your courses'}{v.plan.late>0?` · ${v.plan.late} would miss their deadline. ${v.plan.advice||''}`:''}</p></div>}
function RoutinePage({toast,done}){
  const confirm=useConfirm()
  const [v,setV]=useState(null),[f,setF]=useState({days:'1111110',minutes:30,at:''}),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/me/session').then(x=>{setV(x);if(x.routine)setF({days:x.routine.days,minutes:x.routine.minutes,at:x.routine.at||''})}).catch(e=>toast(e.message))},[])
  const flip=k=>setF({...f,days:f.days.slice(0,k)+(f.days[k]==='1'?'0':'1')+f.days.slice(k+1)})
  const save=async()=>{setBusy(true);try{setV(await api('/me/routine',{method:'PUT',body:{...f,at:f.at||null}}));toast('Routine saved');done()}catch(e){toast(e.message)}setBusy(false)}
  const stop=async()=>{if(!await confirm({title:'Stop your routine?',body:'Your progress stays. Home goes back to showing what to do next.',ok:'Stop the routine'}))return;try{await api('/me/routine/stop',{method:'POST'});toast('Routine stopped');done()}catch(e){toast(e.message)}}
  const per={15:1,30:1,45:2,60:3}[f.minutes]
  return <><Bar title="My routine" sub="Study at your own pace, a little every day"/><div className="main">
    <p className="known" style={{marginTop:0}}>Pick the days you study and how long. Each study day you get one session: {per===1?'one new topic':per+' new topics'} and any reviews that are due. Miss a day and nothing piles up: the next session is the same size, and your streak only counts the days you picked.</p>
    <label>Study days</label><div className="chips wrap" role="group" aria-label="Study days">{WD.map((d,k)=><button key={d} className={'sbtn'+(f.days[k]==='1'?' on':'')} aria-pressed={f.days[k]==='1'} onClick={()=>flip(k)}><span className="lbl">{d}</span></button>)}</div>
    <label htmlFor="mins">Minutes a session</label><select id="mins" value={f.minutes} onChange={e=>setF({...f,minutes:+e.target.value})}>{[15,30,45,60].map(m=><option key={m} value={m}>{m} minutes</option>)}</select>
    <label htmlFor="at">Usual time (optional)</label><input id="at" type="time" value={f.at} onChange={e=>setF({...f,at:e.target.value})}/>
    {v?.plan&&<p className="known">{v.plan.left?`With your current routine you would finish the ${v.plan.left} topics left by ${new Date(v.plan.finish+'T00:00').toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'})}.`:'Nothing is left to study right now.'}{v.plan.late>0?` ${v.plan.late} topics would miss their deadline. ${v.plan.advice||''}`:''}</p>}
    <button className="btn" disabled={busy||!f.days.includes('1')} onClick={save}>Save routine</button>
    {v?.routine&&<button className="btn ghost" onClick={stop}>Stop the routine</button>}</div></>}
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
  return <><Bar title="Search" sub="Find a topic, or ask the AI"/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label="Search topics" autoFocus placeholder="e.g. temporary hardness of water" value={q} maxLength={200} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&submit()}/></div>
    <button className="btn" disabled={pend||aiBusy||typed.length<2} onClick={submit}>{pend?'Searching…':'Search'}</button>
    {!asked&&live&&live.results.length>0&&<><h3 className="sec">Topics in your courses</h3><p className="known">Press Enter to search properly. If nothing here fits, the AI answers.</p>{live.results.slice(0,5).map(x=><Hit key={x.id} x={x} open={setTopic}/>)}</>}
    {!asked&&typed.length>=2&&live&&!live.results.length&&<p className="known">Nothing in your courses matches yet. Press Enter and the AI will answer instead.</p>}
    {res&&<>{res.results.length>0?<><h3 className="sec">{aiNote?'Possible matches in your courses':'In your courses'}</h3>{res.results.map(x=><Hit key={x.id} x={x} open={setTopic}/>)}</>
      :<p className="known" style={{marginTop:18}}>Nothing in your courses matches “{asked}”.</p>}
      {!ai&&!aiBusy&&<button className="btn ghost" onClick={()=>askAi(asked,false)}><Sparkles size={16}/> Not what you wanted? Recheck with AI</button>}</>}
    {aiBusy&&<div className="qbox" aria-live="polite"><b>Asking the AI…</b><div className="sk"/></div>}
    {aiErr&&<div className="qbox" role="alert"><b>The AI could not answer</b><p className="known" style={{margin:'6px 0 0'}}>{aiErr}</p></div>}
    {ai&&!aiBusy&&<><h3 className="sec">AI answer</h3><div className="prose">{ai.cached&&<span className="chip">Saved answer · no tokens used</span>}<Md>{ai.text}</Md></div>
      <p className="known">AI answers can contain mistakes. Check them against your notes and textbook.</p>
      <button className="btn ghost" disabled={aiBusy} onClick={()=>askAi(ai.for,true)}><Sparkles size={16}/> Not happy? Recheck with AI</button></>}</div></>}
function Hit({x,open}){return <button className="hitrow" onClick={()=>open(x.id)}><b>{x.title}{x.in_title&&<span className="chip" style={{marginLeft:8}}>Best match</span>}</b><small>{[x.program,x.semester,x.course,x.unit].filter(Boolean).join(' › ')}</small>{x.snippet&&<span className="snip">{x.snippet}</span>}</button>}

function Insights({toast,role}){
  const [d,setD]=useState(null),[topic,setTopic]=useState(null),[sc,setSc]=useState(null)
  useEffect(()=>{if(!topic)api('/me/insights').then(setD).catch(e=>toast(e.message))},[topic])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(sc)return <ScoreCourse c={sc} back={()=>setSc(null)} toast={toast} role={role}/>
  const n=d?d.needs_study.length:0
  return <><Bar title="My progress" sub="Your scores, where you shine and what to revisit"/><div className="main">
    <MyScores onCourse={setSc}/>{d?.courses.length>0&&<h3 className="sec">Strengths and weak areas</h3>}
    {!d&&<Skeleton/>}
    {d&&!d.courses.length&&<p className="known">Take a quiz and your strengths and weak spots will show up here.</p>}
    {d?.courses.length>0&&<div className="qbox"><b>{n?`${n} ${n===1?'area needs':'areas need'} another round of study`:'Nothing needs another round of study right now'}</b><p className="known" style={{margin:'4px 0 0'}}>{d.strong.length} strong · {d.getting_there.length} getting there · based on your latest result in {d.quizzes_taken} {d.quizzes_taken===1?'quiz':'quizzes'}</p></div>}
    {d?.courses.map(c=><section key={c.course_id}><h3 className="sec">{c.course} · {c.percent}% right</h3><AreaList areas={c.areas} onStudy={setTopic}/></section>)}</div></>}

const uploadImg=async f=>{const r=await fetch('/api/uploads',{method:'POST',headers:{'Content-Type':f.type||'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');return j.url}
// one image place on a question or an answer: shows the image, the file the CSV asked for, or a small "Add image" button
function ImgSlot({url,need,label,onSet,toast,small}){
  const ref=useRef(),[busy,setBusy]=useState(false)
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;setBusy(true);try{onSet(await uploadImg(f))}catch(x){toast(x.message)}setBusy(false)}
  const input=<input ref={ref} type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden onChange={pick}/>
  if(url)return <div className={'islot'+(small?' sm':'')}>{input}<img src={url} alt={label}/><span><button className="tool" onClick={()=>ref.current.click()}>Replace</button><button className="tool" onClick={()=>onSet('')}>Remove image</button></span></div>
  if(need)return <div className="islot need" role="status">{input}<AlertTriangle size={16}/><span>Needs <b>{need}</b></span><button className="tool" disabled={busy} onClick={()=>ref.current.click()}>{busy?'Uploading…':'Upload'}</button><button className="tool" onClick={()=>onSet('',true)}>Skip</button></div>
  return <>{input}<button className="tool" disabled={busy} onClick={()=>ref.current.click()} aria-label={'Add image to '+label}>{busy?'Uploading…':small?'Image':'Add image'}</button></>}
const QImg=({src,alt})=>src?<img className="qimg" src={src} alt={alt} loading="lazy"/>:null
const OptBody=({text,img,k})=><span className="obody">{img&&<img src={img} alt={'Answer '+LET[k]}/>}{text?<Md>{text}</Md>:!img&&<span>—</span>}</span>
const LET='ABCDEF'
function QuizPlay({id,back,toast,role}){
  const [q,setQ]=useState(null),[ans,setAns]=useState([]),[res,setRes]=useState(null),[busy,setBusy]=useState(false),[topic,setTopic]=useState(null),[view,setView]=useState(null)
  const start=d=>{setQ(d);setAns(d.questions.map(()=>null));setRes(null)}
  useEffect(()=>{api('/quizzes/'+id).then(start).catch(e=>{toast(e.message);back()})},[id])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(view)return view.kind==='attempt'?<AttemptView id={view.id} back={()=>setView(null)} toast={toast} role={role}/>:view.kind==='mine'?<MyAttempts quiz={id} back={()=>setView(null)} toast={toast} role={role}/>:<QuizResults id={id} back={()=>setView(null)} toast={toast} role={role}/>
  if(!q)return <><Bar title="Quiz" back={back}/><div className="main"><Skeleton/></div></>
  const left=ans.filter(a=>a===null).length
  const submit=async()=>{setBusy(true);try{setRes(await api(`/quizzes/${id}/attempt`,{method:'POST',body:{answers:ans}}));window.scrollTo(0,0)}catch(e){toast(e.message)}setBusy(false)}
  return <><Bar title={q.title} sub={q.questions.length+' questions · pass mark '+q.pass_percent+'%'+(q.kind==='course'?' · course test':'')} back={back}/><div className="main">
    {!res&&q.can_edit&&<button className="btn ghost" style={{marginTop:0}} onClick={()=>setView({kind:'results'})}><BarChart3 size={16}/> Results and scores</button>}
    {!res&&q.attempts>0&&<p className="known" style={{marginTop:0}}>You have tried this {pl(q.attempts,'time')}. Best {q.best}% · latest {q.latest}%. <button className="tool" onClick={()=>setView({kind:'mine'})}>See your attempts</button></p>}
    {res&&<div className="qbox"><h2 style={{margin:0}}>{res.score} / {res.total} · {res.percent}%</h2><p className="known">{res.passed?'Passed. Well done!':'Not there yet. Go back over the topics and try again.'}{res.summary&&' '+res.summary}</p>
      <div className="two"><button className="btn" onClick={()=>setView({kind:'attempt',id:res.attempt_id})}>Review answers</button><button className="btn ghost" onClick={()=>start(q)}>Try again</button></div><button className="btn ghost" onClick={back}>Back</button></div>}
    {res&&res.areas?.length>0&&<><h3 className="sec">What you are good at and what to revisit</h3><AreaList areas={res.areas} onStudy={setTopic}/></>}
    {q.questions.map((x,i)=><div className="qbox" key={x.id}><b>Question {i+1}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={'Picture for question '+(i+1)}/>
      {x.options.map((o,k)=>{const r=res&&res.results[i],cls=r?(k===r.correct||(r.ok&&k===r.chosen)?' ok':k===r.chosen?' bad':''):ans[i]===k?' sel':''
        return <button key={k} className={'opt'+cls} disabled={!!res} aria-pressed={!res&&ans[i]===k} onClick={()=>setAns(ans.map((a,n)=>n===i?k:a))}><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/></button>})}
      {res&&res.results[i].explanation&&<div className="known"><Md>{res.results[i].explanation}</Md></div>}</div>)}
    {!res&&<button className="btn" disabled={busy} onClick={submit}>{busy?'Checking…':'Submit answers'}</button>}
    {!res&&left>0&&<p className="known">{left} unanswered. Blank answers count as wrong.</p>}</div></>}
// one attempt, question by question
function AttemptView({id,back,toast,role}){
  const [d,setD]=useState(null),[topic,setTopic]=useState(null)
  useEffect(()=>{api('/attempts/'+id).then(setD).catch(e=>{toast(e.message);back()})},[id])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(!d)return <><Bar title="Attempt" back={back}/><div className="main"><Skeleton/></div></>
  const staff=role!=='student',right=d.questions.filter(x=>x.ok).length
  return <><Bar title={d.quiz} sub={(staff?d.user+' · ':'')+when(d.at)} back={back}/><div className="main">
    <div className="qbox" style={{marginTop:0}}><h2 style={{margin:0}}>{d.score} / {d.total} · {d.percent}%</h2><p className="known" style={{marginBottom:0}}>{d.passed?'Passed':'Below the pass mark'} of {d.pass_percent}%.{d.summary&&' '+d.summary}</p></div>
    {d.areas.length>0&&<><h3 className="sec">{staff?'Strengths and weak areas':'What you are good at and what to revisit'}</h3><AreaList areas={d.areas} onStudy={staff?null:setTopic} staff={staff}/></>}
    {d.no_detail&&<p className="known">This attempt was made before answers were kept question by question, so only the score is known.</p>}
    {d.changed>0&&<p className="known">{pl(d.changed,'question')} of this attempt {d.changed===1?'was':'were'} changed or removed since, so {d.changed===1?'it is':'they are'} not shown.</p>}
    {!d.reveal&&d.questions.length>0&&<p className="known">You see which answers were right ({right} of {d.questions.length}). This quiz does not show the correct answers.</p>}
    {d.questions.map((x,i)=><div className="qbox" key={x.id}><b>Question {i+1} · {x.ok?'Right':'Wrong'}{x.area?' · '+x.area:''}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={'Picture for question '+(i+1)}/>
      {x.options.map((o,k)=>{const mine=x.chosen_known&&x.chosen===k,key=d.reveal&&x.correct===k,cls=key||(mine&&x.ok)?' ok':mine?' bad':''
        return <div key={k} className={'opt'+cls}><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/>{(mine||key)&&<span className="otag">{[mine&&(staff?'Their answer':'Your answer'),key&&'Correct answer'].filter(Boolean).join(' · ')}</span>}</div>})}
      {x.chosen_known&&x.chosen==null&&<p className="known">Left blank.</p>}
      {x.explanation&&<div className="known"><Md>{x.explanation}</Md></div>}</div>)}</div></>}
function MyAttempts({quiz,user,back,toast,role}){  // a person's attempts at one quiz; staff pass user to see a student's
  const [d,setD]=useState(null),[open,setOpen]=useState(null)
  useEffect(()=>{api(`/quizzes/${quiz}/attempts`+(user?'?user_id='+user:'')).then(setD).catch(e=>{toast(e.message);back()})},[quiz,user])
  if(open)return <AttemptView id={open} back={()=>setOpen(null)} toast={toast} role={role}/>
  return <><Bar title={d?.quiz||'Attempts'} sub={d?(user?d.user+' · ':'')+pl(d.items.length,'attempt'):''} back={back}/><div className="main">
    {d&&!d.items.length&&<p className="known">No attempts yet.</p>}
    {d?.items.map((a,i)=><button key={a.id} className="row rowbtn" onClick={()=>setOpen(a.id)}><div>{a.score} / {a.total} · {a.percent}%<small>{when(a.at)} · {a.passed?'Passed':'Below the pass mark'}{i===0?' · latest':''}</small><Bar2 v={a.percent}/></div><ChevronRight size={18}/></button>)}</div></>}

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
    await api(`/quizzes/${qid}/questions`,{method:'PUT',body:{questions:payload()}});toast(course?'Test saved':'Quiz saved');done()}catch(e){toast(e.message)}setBusy(false)}
  const readCsv=async(f,replace)=>{try{const r=await api('/quizzes/parse-csv',{method:'POST',body:{csv:await f.text(),...(course?{course_id:cid}:{unit_id})}});setCsv(r)
    if(!r.questions.length){toast('No questions could be read from the file');return}
    const got=r.questions.map(fromCsv);setQs(cur=>replace?got:[...cur.filter(x=>x.text.trim()||x.image),...got])
    if(replace&&!m.title)setM(v=>({...v,title:f.name.replace(/\.[^.]+$/,'').replace(/[_-]+/g,' ').slice(0,200)}))
    setStage('edit');toast(`${pl(r.questions.length,'question')} read. Check them below${r.images_needed.length?' and upload the images':''}, then save.`)}catch(e){toast(e.message)}}
  const importCsv=async e=>{const f=e.target.files[0];e.target.value='';if(f)readCsv(f,stage==='csv')}
  const bulkImages=async e=>{const files=[...e.target.files];e.target.value='';if(!files.length)return;setBusy(true);let used=0;const extra=[];let next=qs
    for(const f of files){const hits=missing(next).filter(s=>s.name.toLowerCase()===f.name.toLowerCase());if(!hits.length){extra.push(f.name);continue}
      try{const url=await uploadImg(f);used++;next=next.map((x,i)=>{const h=hits.filter(s=>s.i===i);if(!h.length)return x
        return {...x,image:h.some(s=>s.k<0)?url:x.image,option_images:x.option_images.map((v,k)=>h.some(s=>s.k===k)?url:v),need:{image:h.some(s=>s.k<0)?'':x.need.image,options:x.need.options.map((n,k)=>h.some(s=>s.k===k)?'':n)}}})}catch(x){toast(f.name+': '+x.message)}}
    setQs(next);setBusy(false);toast(`${pl(used,'image')} matched${extra.length?`. Not in the CSV: ${extra.slice(0,3).join(', ')}${extra.length>3?'…':''}`:''}`)}
  const addFromBank=picked=>{setQs(cur=>[...cur.filter(x=>x.text.trim()),...picked.map(x=>({...blankQ(),text:x.text,options:x.options,option_images:x.options.map(()=>''),correct:x.correct,explanation:x.explanation||''}))]);setBank(false);toast(`${pl(picked.length,'question')} added. Tie them to topics if you like, then save.`)}
  const toBank=async()=>{const list=qs.filter(x=>x.text.trim());let added=0,skipped=0,bad=0;setBusy(true)
    for(const x of list){if(x.image||x.option_images.some(Boolean)){bad++;continue}try{await api('/bank',{method:'POST',body:{text:x.text,options:x.options,correct:x.correct,explanation:x.explanation,tags:btags,source:m.title}});added++}catch(e){/already in the bank/.test(e.message)?skipped++:bad++}}
    setBusy(false);toast(`${added} saved to the bank${skipped?`, ${skipped} already there`:''}${bad?`, ${bad} skipped (incomplete or with images)`:''}`)}
  const del=async()=>{if(!await confirm({title:`Delete this ${course?'test':'quiz'}?`,body:"This also deletes every student attempt. This can't be undone.",ok:'Delete',danger:true}))return;try{await api('/quizzes/'+id,{method:'DELETE'});toast('Deleted');done()}catch(e){toast(e.message)}}
  const fileInputs=<><input ref={csvRef} type="file" accept=".csv,text/csv,text/plain" hidden onChange={importCsv}/><input ref={imgRef} type="file" accept="image/png,image/jpeg,image/gif,image/webp" multiple hidden onChange={bulkImages}/></>
  const csvNotes=csv&&(csv.error_count>0||csv.warnings.length>0)&&<div className="qbox" role="alert">{csv.error_count>0&&<><b>{pl(csv.error_count,'row')} could not be read and {csv.error_count===1?'was':'were'} left out</b>{csv.errors.slice(0,10).map((x,i)=><p className="known" style={{margin:'4px 0'}} key={i}>Row {x.row}: {x.error}</p>)}{csv.error_count>10&&<p className="known">…and {csv.error_count-10} more.</p>}</>}
    {csv.warnings.length>0&&<><b style={{display:'block',marginTop:csv.error_count?10:0}}>Worth a look</b>{csv.warnings.slice(0,8).map((w,i)=><p className="known" style={{margin:'4px 0'}} key={i}>{w}</p>)}{csv.warnings.length>8&&<p className="known">…and {csv.warnings.length-8} more.</p>}</>}</div>
  if(stage==='csv')return <><Bar title="New MCQ test" sub="Step 1 of 2 · attach the questions CSV" back={done}/><div className="main">{fileInputs}
    <p className="known" style={{marginTop:0}}>A course test is built from a CSV file with one question per row. In the next step you check every question, upload any pictures for questions and answer choices, then save.</p>
    <button className="btn" onClick={()=>csvRef.current.click()}><Upload size={16}/> Choose the CSV file</button><button className="btn ghost" onClick={()=>download('mcq-template.csv',MCQ_TEMPLATE)}>Download the template</button>
    {csvNotes}
    <h3 className="sec">Columns</h3>{CSV_COLS.map(([c,h])=><div className="row" key={c}><div><code>{c}</code><small>{h}</small></div></div>)}
    <p className="known">The first row names the columns. Comma, semicolon and tab separated files all work. A course test holds up to 200 questions.</p></div></>
  return <><Bar title={id?(course?'Edit test':'Edit quiz'):csvFirst?'New MCQ test':'New quiz'} sub={csvFirst&&!id?'Step 2 of 2 · check, add images, save':''} back={done}/><div className="main">{fileInputs}
    {csvNotes}
    {todo.length>0&&<div className="qbox need" role="status"><b>{pl(todo.length,'image')} still to upload</b><p className="known" style={{margin:'4px 0 8px'}}>Choose them all at once and they are matched to their questions by file name, or upload each one below. {[...new Set(todo.map(x=>x.name))].slice(0,6).join(', ')}{todo.length>6?'…':''}</p>
      <button className="btn" style={{margin:0}} disabled={busy} onClick={()=>imgRef.current.click()}><Upload size={16}/> {busy?'Uploading…':'Upload images'}</button></div>}
    <label>Title</label><input value={m.title} onChange={e=>setM({...m,title:e.target.value})} placeholder={course?'e.g. Chemistry final MCQ':'e.g. Water treatment check'}/>
    <label>Pass mark (%)</label><input type="number" min="1" max="100" value={m.pass_percent} onChange={e=>setM({...m,pass_percent:e.target.value})}/>
    <label className="chk"><input type="checkbox" checked={m.published} onChange={e=>setM({...m,published:e.target.checked})}/> Published (students can take it)</label>
    <label className="chk"><input type="checkbox" checked={m.reveal} onChange={e=>setM({...m,reveal:e.target.checked})}/> Show students the correct answers and explanations after they submit</label>
    {qs.map((x,i)=><div className="qbox" key={i}><b>Question {i+1}</b>
      <textarea placeholder="Question (Markdown and $math$ work)" value={x.text} onChange={e=>upd(i,{text:e.target.value})}/>
      <ImgSlot url={x.image} need={x.need.image} label={'question '+(i+1)} toast={toast} onSet={(v,skip)=>setQImg(i,v,skip)}/>
      {x.options.map((o,k)=><div key={k}><div className="qopt"><input type="radio" name={'c'+i} aria-label={'Answer '+LET[k]+' is correct'} checked={x.correct===k} onChange={()=>upd(i,{correct:k})}/><b className="olet">{LET[k]}</b><input value={o} placeholder={'Answer '+LET[k]+(x.option_images[k]?' (optional with an image)':'')} onChange={e=>setOpt(i,k,e.target.value)}/>
        {!x.option_images[k]&&!x.need.options[k]&&<ImgSlot small label={'answer '+LET[k]} toast={toast} onSet={v=>setOptImg(i,k,v)}/>}{x.options.length>2&&<button className="ic sm" aria-label={'Remove answer '+LET[k]} onClick={()=>delOpt(i,k)}><X size={16}/></button>}</div>
        {(x.option_images[k]||x.need.options[k])&&<div style={{paddingLeft:48}}><ImgSlot small url={x.option_images[k]} need={x.need.options[k]} label={'answer '+LET[k]} toast={toast} onSet={(v,skip)=>setOptImg(i,k,v,skip)}/></div>}</div>)}
      {x.options.length<6&&<button className="tool" onClick={()=>upd(i,{options:[...x.options,''],option_images:[...x.option_images,'']})}>Add answer</button>}
      <label>Topic this tests</label><select value={x.topic_id??''} onChange={e=>upd(i,{topic_id:e.target.value?+e.target.value:null})}><option value="">Not tied to one topic</option>{topics.map(t=><option key={t.id} value={t.id}>{t.unit?t.unit+' › ':''}{t.title}</option>)}</select>
      {x.topic_id==null&&<><label>Area or skill</label><input value={x.area} onChange={e=>upd(i,{area:e.target.value})} placeholder="e.g. Arithmetic (used for strengths when there is no topic)"/></>}
      <textarea placeholder="Explanation shown after submitting (optional)" value={x.explanation} onChange={e=>upd(i,{explanation:e.target.value})}/>
      {qs.length>1&&<button className="tool" onClick={()=>setQs(qs.filter((_,n)=>n!==i))}>Remove question</button>}</div>)}
    <p className="known">Tick the radio button beside the correct answer. Tie each question to the topic it tests, or name an area: students then see what they are good at and what needs another round of study.</p>
    <button className="btn ghost" onClick={()=>setQs([...qs,blankQ()])}>Add question</button>
    <div className="two"><button className="btn ghost" onClick={()=>csvRef.current.click()}><Upload size={16}/> Add from a CSV</button><button className="btn ghost" onClick={()=>download('mcq-template.csv',MCQ_TEMPLATE)}>CSV template</button></div>
    <button className="btn ghost" onClick={()=>setBank(true)}>Add from the question bank</button>
    <label htmlFor="bt">Share these questions in the bank</label><div className="two"><input id="bt" value={btags} onChange={e=>setBtags(e.target.value)} placeholder="Tags, e.g. water, hardness (optional)"/><button className="btn ghost" disabled={busy||!qs.some(x=>x.text.trim())} onClick={toBank}>Save to bank</button></div>
    <button className="btn" disabled={busy||todo.length>0} onClick={save}>{busy?'Saving…':todo.length?`Upload ${pl(todo.length,'image')} first`:id?'Save changes':course?'Create test':'Save quiz'}</button>{bank&&<BankSheet close={()=>setBank(false)} onAdd={addFromBank} toast={toast}/>}
    {id&&<button className="btn danger" onClick={del}>Delete {course?'test':'quiz'}</button>}</div></>}

// score spread: one series, so one hue and no legend; every bar has its count as text and a tooltip
const Spread=({rows,pass})=>{const top=Math.max(1,...rows.map(r=>r.count))
  return <figure className="spread" aria-label="How many students scored in each band"><div className="sbars">{rows.map((r,i)=><div key={r.label} className="sbar" title={`${r.label}%: ${pl(r.count,'student')}`}><em>{r.count||''}</em><i style={{height:r.count?Math.max(4,100*r.count/top)+'%':0}} className={i*10+9<pass?'below':''}/></div>)}</div>
    <div className="saxis">{rows.map(r=><span key={r.label}>{r.label.split('–')[0]}</span>)}</div><figcaption>Final score in bands of 10%. Lighter bars are below the {pass}% pass mark.</figcaption></figure>}
const PassPill=({ok})=><span className={'pill sm '+(ok?'okp':'off')}>{ok?'Passed':'Not yet'}</span>
function QuizResults({id,back,toast,role}){
  const [d,setD]=useState(null),[tab,setTab]=useState('overview'),[who,setWho]=useState(null),[sort,setSort]=useState('order')
  useEffect(()=>{api(`/quizzes/${id}/results`).then(setD).catch(e=>{toast(e.message);back()})},[id])
  if(who)return <MyAttempts quiz={id} user={who} back={()=>setWho(null)} toast={toast} role={role}/>
  if(!d)return <><Bar title="Results" back={back}/><div className="main"><Skeleton/></div></>
  const sm=d.summary,qs=sort==='hard'?[...d.questions].sort((a,b)=>(a.percent??101)-(b.percent??101)):d.questions
  return <><Bar title={d.title} sub={`Results · ${sm.took} of ${sm.students} students took it`} back={back}/><div className="main">
    <Tabs scroll label="Result sections" items={[['overview','Overview'],['students','Students'],['questions','Questions'],['areas','Strengths']]} value={tab} onChange={setTab}/>
    {tab==='overview'&&<>{!sm.took?<p className="known">Nobody has taken it yet.{d.published?'':' It is still a draft, so students cannot see it.'}</p>:<>
      <div className="stats">{[['Average final score',sm.average+'%'],['Pass rate',sm.pass_rate+'%',`${sm.passed} of ${sm.took} passed`],['Median',sm.median+'%'],['Highest · lowest',sm.highest+'% · '+sm.lowest+'%'],
        ['Took it',sm.took+' / '+sm.students,sm.not_taken?sm.not_taken+' not yet':'everyone'],['Attempts',sm.attempts,'latest average '+sm.average_latest+'%']].map(([l,v,x])=><div className="stat" key={l}><b>{v}</b>{l}{x&&<small style={{display:'block',color:'var(--mut)'}}>{x}</small>}</div>)}</div>
      <h3 className="sec">Spread of final scores</h3><Spread rows={sm.distribution} pass={d.pass_percent}/>
      <p className="known">The final score is each student's best attempt. Strengths and the question analysis use each student's latest attempt, so a retake replaces the earlier result.</p></>}
      {d.not_taken.length>0&&<><h3 className="sec">Not taken yet ({sm.not_taken})</h3><p className="known" style={{margin:0}}>{d.not_taken.map(x=>x.name).join(', ')}{sm.not_taken>d.not_taken.length?'…':''}</p></>}
      <button className="btn ghost" onClick={()=>fetchFile(`/quizzes/${id}/results?format=csv`,'results-'+d.title.replace(/\s+/g,'_')+'.csv',toast)}>Download results CSV</button></>}
    {tab==='students'&&<>{!d.students.length&&<p className="known">No results yet.</p>}
      {d.students.map(x=><button key={x.user_id} className="row rowbtn" onClick={()=>setWho(x.user_id)}><div>{x.name}<PassPill ok={x.passed}/><small>Final {x.best}% · latest {x.latest}% · {pl(x.attempts,'attempt')} · {day(x.last_at)}</small>
        {(x.strong.length>0||x.needs_study.length>0)&&<small>{x.strong.length>0&&'Good at: '+x.strong.join(', ')}{x.strong.length>0&&x.needs_study.length>0&&' · '}{x.needs_study.length>0&&'Revisit: '+x.needs_study.join(', ')}</small>}<Bar2 v={x.best}/></div><ChevronRight size={18}/></button>)}</>}
    {tab==='questions'&&<><div className="seg" style={{gridTemplateColumns:'1fr 1fr',margin:'0 0 12px'}}>{[['order','In test order'],['hard','Hardest first']].map(([k,l])=><button key={k} className={sort===k?'on':''} aria-pressed={sort===k} onClick={()=>setSort(k)}>{l}</button>)}</div>
      {qs.map(x=>{const n=x.picks.reduce((a,b)=>a+b,0)+x.blank
        return <div className="qbox" key={x.id}><b>Question {x.pos} · {x.percent==null?'no answers yet':x.percent+'% right'}{x.area?' · '+x.area:''}</b><div className="prose"><Md>{x.text}</Md></div><QImg src={x.image} alt={'Picture for question '+x.pos}/>
          {x.options.map((o,k)=>{const c=x.picks[k],pc=n?Math.round(100*c/n):0
            return <div key={k} className="pick" title={`${LET[k]}: ${pl(c,'student')}`}><div className="pickh"><b className="olet">{LET[k]}</b><OptBody text={o} img={x.option_images[k]} k={k}/>{k===x.correct&&<span className="otag ok"><Check size={14}/> Correct</span>}<span className="pickn">{c} · {pc}%</span></div><div className="meter"><i style={{width:pc+'%'}} className={k===x.correct?'ok':''}/></div></div>})}
          {x.picks_known>0&&x.blank>0&&<p className="known" style={{margin:'6px 0 0'}}>Left blank: {x.blank}</p>}
          {x.total>x.picks_known&&<p className="known" style={{margin:'6px 0 0'}}>{x.total-x.picks_known} older {x.total-x.picks_known===1?'attempt does':'attempts do'} not record which answer was picked.</p>}</div>})}</>}
    {tab==='areas'&&<>{!d.areas.length?<p className="known">No results yet.</p>:<><p className="known" style={{marginTop:0}}>Weakest first, from each student's latest attempt.</p>
      {d.areas.map(a=><div className="row" key={a.title+(a.topic_id||'')}><div>{a.title}<small>{a.percent}% right · {a.strong} strong · {a.getting_there} getting there · {a.needs_study} need another round{a.unit?' · '+a.unit:''}</small><Bar2 v={a.percent}/></div></div>)}</>}</>}</div></>}
function Gradebook({cid,back,toast,role}){
  const [d,setD]=useState(null),[open,setOpen]=useState(null),[stu,setStu]=useState(null)
  useEffect(()=>{api(`/courses/${cid}/gradebook`).then(setD).catch(e=>{toast(e.message);back()})},[cid])
  if(open)return <QuizResults id={open} back={()=>setOpen(null)} toast={toast} role={role}/>
  if(stu)return stu.quiz?<MyAttempts quiz={stu.quiz} user={stu.id} back={()=>setStu({...stu,quiz:null})} toast={toast} role={role}/>
    :<><Bar title={stu.name} sub={d.course+' · final '+(stu.final==null?'–':stu.final+'%')} back={()=>setStu(null)}/><div className="main">{d.tests.map((t,i)=><button key={t.id} className="row rowbtn" disabled={stu.scores[i]==null} onClick={()=>setStu({...stu,quiz:t.id})}><div>{t.title}{stu.scores[i]!=null&&<PassPill ok={stu.scores[i]>=t.pass_percent}/>}<small>{t.unit||'Course test'} · {stu.scores[i]==null?'not taken':'final '+stu.scores[i]+'%'} · pass {t.pass_percent}%</small>{stu.scores[i]!=null&&<Bar2 v={stu.scores[i]}/>}</div>{stu.scores[i]!=null&&<ChevronRight size={18}/>}</button>)}</div></>
  if(!d)return <><Bar title="Gradebook" back={back}/><div className="main"><Skeleton/></div></>
  return <><Bar title="Gradebook" sub={d.course+' · '+pl(d.tests.length,'test')} back={back}/><div className="main">
    {!d.tests.length?<p className="known">No published tests or quizzes in this course yet.</p>:<>
    <p className="known" style={{marginTop:0}}>Each cell is a student's final (best) score. The final course score is the average of the tests they took. Tap a student or a test to drill down.</p>
    <div className="gbwrap"><table className="gb"><thead><tr><th>Student</th>{d.tests.map(t=><th key={t.id}><button className="tool" onClick={()=>setOpen(t.id)} title={t.unit||'Course test'}>{t.title}</button><small>avg {t.average??'–'}%</small></th>)}<th>Final</th></tr></thead>
      <tbody>{d.students.map(r=><tr key={r.user_id}><td><button className="tool" onClick={()=>setStu(r)}>{r.name}</button></td>{r.scores.map((v,i)=><td key={i} className={v==null?'na':v>=d.tests[i].pass_percent?'':'low'}>{v==null?'–':v+'%'}</td>)}<td><b>{r.final==null?'–':r.final+'%'}</b><small>{r.taken}/{d.tests.length}</small></td></tr>)}</tbody></table></div>
    <p className="known">A dash means not taken. Scores below a test's pass mark are marked with a lighter background.</p>
    <button className="btn ghost" onClick={()=>fetchFile(`/courses/${cid}/gradebook?format=csv`,'gradebook-'+d.course.replace(/\s+/g,'_')+'.csv',toast)}>Download gradebook CSV</button></>}</div></>}
function ScoreCourse({c,back,toast,role}){  // one course of a student's scores: each test, then its attempts
  const [q,setQ]=useState(null)
  if(q)return <MyAttempts quiz={q} back={()=>setQ(null)} toast={toast} role={role}/>
  return <><Bar title={c.course} sub={'Final score '+(c.final==null?'–':c.final+'%')+' · '+c.taken+' of '+c.tests.length+' taken'} back={back}/><div className="main">
    {c.tests.map(t=><button key={t.id} className="row rowbtn" disabled={!t.attempts} onClick={()=>setQ(t.id)}><div>{t.title}{t.attempts>0&&<PassPill ok={t.passed}/>}<small>{t.unit||'Course test'} · {t.attempts?`best ${t.best}% · latest ${t.latest}% · ${pl(t.attempts,'attempt')}`:'not taken yet'} · pass {t.pass_percent}%</small>{t.attempts>0&&<Bar2 v={t.best}/>}</div>{t.attempts>0&&<ChevronRight size={18}/>}</button>)}
    <p className="known">Your final score in a test is your best attempt. The course score is the average of the tests you have taken.</p></div></>}
function MyScores({onCourse}){  // a student's final score per course
  const [d,setD]=useState(null)
  useEffect(()=>{api('/me/scores').then(setD).catch(()=>setD({courses:[]}))},[])
  if(!d||!d.courses.length)return null
  return <><h3 className="sec first">Scores</h3>{d.courses.map(x=><button key={x.course_id} className="row rowbtn" onClick={()=>onCourse(x)}><div>{x.course}<small>{x.final==null?'No tests taken yet':'Final score '+x.final+'%'} · {x.taken} of {x.tests.length} taken · {x.passed} passed</small>{x.final!=null&&<Bar2 v={x.final}/>}</div><ChevronRight size={18}/></button>)}</>}
// ---- courses students build from their own material ----
const Stars=({n,big})=><span className={'stars'+(big?' big':'')} role="img" aria-label={`${n} of 3 stars`}>{[1,2,3].map(i=><span key={i} className={i<=n?'on':''} aria-hidden="true">★</span>)}</span>
const STAR_HELP='★ topic completed · ★★ quiz passed · ★★★ mastered (90%+ in a quiz)'
// streak, level, this week, reviews due and the next step: the self-learner's "what now?" in one card
function LearnCard({me,onContinue,onReview,compact}){
  if(!me)return null
  const x=me.xp
  return <div className="learn"><div className={'lrow'+(compact?' one':'')}>
      {!compact&&<div className="lstat"><b><Flame size={20} className={'flame'+(me.streak?' on':'')} aria-hidden="true"/> {me.streak}</b><small>{me.active_today?'day streak · studied today':me.streak?'day streak · study today to keep it':'day streak · start one today'}</small></div>}
      <div className="lstat"><b><span className="lvl">Lv {x.level}</span> {x.total} XP</b><div className="meter" role="progressbar" aria-label="Progress to the next level" aria-valuemin={0} aria-valuemax={x.span} aria-valuenow={x.into}><i style={{width:Math.round(100*x.into/x.span)+'%'}}/></div><small>{x.span-x.into} XP to level {x.level+1}</small></div></div>
    {!compact&&<div className="week" aria-label="Days studied this week">{me.week.map(d=><span key={d.date} className={(d.active?'on':'')+(d.today?' today':'')} title={d.date}>{d.label}</span>)}</div>}
    {me.reviews_due>0&&<button className="btn" onClick={()=>onReview(me.review_courses[0].course_id)}><RotateCcw size={16}/> Review {pl(me.reviews_due,'topic')} due{me.review_courses.length>1?' (start with '+me.review_courses[0].course+')':''}</button>}
    {me.next&&<button className={'btn'+(me.reviews_due?' ghost':'')} onClick={()=>onContinue(me.next)}><Play size={16}/> {me.next.done?'Continue':'Start'}: {me.next.topic}<small className="sub">{me.next.course} · {me.next.done} of {me.next.topics} done</small></button>}</div>}
const STEPS=['Name','Material','Slice','Preview'],AREA_LABEL={strong:'Strong',getting_there:'Getting there',needs_study:'Revisit'}
const Steps=({at})=><ol className="steps" aria-label="Setup steps">{STEPS.map((s,i)=><li key={s} className={i<at?'done':i===at?'on':''} aria-current={i===at?'step':undefined}><span>{i<at?<Check size={14}/>:i+1}</span>{s}</li>)}</ol>
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
    <div>{c.title}{c.status!=='ready'&&<span className="pill sm" style={{marginLeft:6}}>Setup not finished</span>}{c.mine&&c.share==='program'&&<span className="pill sm okp" style={{marginLeft:6}}>Shared</span>}
      <small>{c.status==='ready'?`${c.completed} of ${c.topics} topics completed`:'Continue the setup'}{!c.mine?' · by '+c.owner:''}</small>{c.status==='ready'&&c.topics>0&&<Bar2 v={100*c.completed/c.topics}/>}</div><ChevronRight size={18}/></button>
  return <><Bar title="Build a course" sub="Turn your own notes into a course"/><div className="main">
    {me&&me.courses>0&&<LearnCard me={me} onContinue={n=>setOpen({id:n.course_id,topic:n.topic_id})} onReview={review}/>}
    <p className="known" style={{marginTop:me&&me.courses>0?16:0}}>Upload your notes, textbook chapters or handouts. The AI slices them into units and small topics, you check and adjust the outline, and then you study it with explanations, practice MCQs and quizzes.</p>
    <button className="btn lead" onClick={()=>setMake(true)}><Upload size={16}/> New course from my material</button>
    {!d?<Skeleton/>:<>{d.mine.length>0&&<><h3 className="sec">My courses</h3>{d.mine.map(card)}</>}
      {d.shared.length>0&&<><h3 className="sec">Shared by classmates</h3>{d.shared.map(card)}</>}
      {!d.mine.length&&!d.shared.length&&<p className="known">You have not built a course yet.</p>}</>}
    {make&&<Sheet close={()=>setMake(false)}><h3>New course</h3><label htmlFor="sct">Course name</label><input id="sct" autoFocus value={title} onChange={e=>setTitle(e.target.value)} onKeyDown={e=>e.key==='Enter'&&title.trim()&&create()} placeholder="e.g. Islamic Education · Unit 4"/>
      <button className="btn" disabled={busy||!title.trim()} onClick={create}>Next: add material</button><button className="btn ghost" onClick={()=>setMake(false)}>Cancel</button></Sheet>}</div></>}
function StudyWizard({id,toast,back,done}){
  const confirm=useConfirm()
  const [c,setC]=useState(null),[step,setStep]=useState(null),[text,setText]=useState(''),[busy,setBusy]=useState(''),[notes,setNotes]=useState(''),[plan,setPlan]=useState(null),[dirty,setDirty]=useState(false),[peek,setPeek]=useState(null),fileRef=useRef()
  const load=async(go)=>{try{const d=await api('/study/courses/'+id);setC(d);setNotes(d.notes);setPlan(d.plan);setDirty(false);setStep(go??(d.plan?3:d.sources.length?2:1));return d}catch(e){toast(e.message);back()}}
  useEffect(()=>{load()},[id]);usePoll(!!c?.reading,()=>api('/study/courses/'+id).then(d=>setC(d)).catch(()=>{}))  // only the file list refreshes; the step and outline stay
  if(!c||step==null)return <><Bar title="Set up your course" back={back}/><div className="main"><Skeleton/></div></>
  const files=async e=>{const fs=[...e.target.files];e.target.value='';for(const f of fs){if(tooBig(f)){toast(`${f.name} is over ${MAX_FILE_MB} MB. Split it into smaller files.`);continue}setBusy('Reading '+f.name+'…')
      try{const r=await fetch(`/api/study/courses/${id}/files?name=${encodeURIComponent(f.name)}`,{method:'POST',headers:{'Content-Type':'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');toast(j.status==='reading'?`${f.name} is scanned pages. Reading them now…`:`${f.name}: ${pl(j.words,'word')} read`)}catch(x){toast(f.name+': '+x.message)}}
    setBusy('');load(1)}
  const paste=async()=>{setBusy('Adding…');try{const r=await api(`/study/courses/${id}/text`,{method:'POST',body:{text}});setText('');toast(pl(r.words,'word')+' added')}catch(e){toast(e.message)}setBusy('');load(1)}
  const dropSrc=async i=>{if(!await confirm({title:'Remove this material?',body:'Its text is taken out of the course. Any outline already made is cleared.',ok:'Remove',danger:true}))return;try{await api(`/study/courses/${id}/sources/${i}`,{method:'DELETE'});load(1)}catch(e){toast(e.message)}}
  const slice=async method=>{if(dirty&&!await confirm({title:'Slice again?',body:'Your renames, merges and removals in the current outline are replaced.',ok:'Slice again'}))return
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
        setBusy('');if(!await confirm({title:'Replace the course\'s topics?',body:'Finishing again builds the topics from this outline. Progress and quiz results on the old topics are removed.',ok:'Replace topics',danger:true}))return
        setBusy('Building your course…');await api(`/study/courses/${id}/finish`,{method:'POST',body:{replace:true}})}
      toast('Your course is ready');done()}catch(e){toast(e.message)}setBusy('')}
  const words=c.sources.reduce((a,x)=>a+x.words,0)
  return <><Bar title={c.title} sub={'Set up · step '+(step+1)+' of 4'} back={back}/><div className="main">
    <Steps at={step}/>
    {busy&&<div className="qbox" role="status" style={{marginTop:0}}><b>{busy}</b></div>}
    {step===1&&<>
      <h3 className="sec first">Add your material</h3><p className="known" style={{marginTop:0}}>PDF, Word (.docx), or .txt and .md files, up to {MAX_FILE_MB} MB each. Add several and they are joined in the order you add them. You can also paste text.{c.ocr_available?' Scanned PDFs are read with text recognition, a few seconds a page.':' Scanned PDFs can\'t be read on this server yet.'}</p>
      <input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown" onChange={files}/>
      <button className="btn" disabled={!!busy} onClick={()=>fileRef.current.click()}><Upload size={16}/> Choose files</button>
      <label htmlFor="pst">Or paste text</label><textarea id="pst" value={text} onChange={e=>setText(e.target.value)} placeholder="Paste notes here. Leave an empty line between paragraphs; lines starting with # become headings."/>
      <button className="btn ghost" disabled={!!busy||!text.trim()} onClick={paste}>Add this text</button>
      {c.sources.length>0&&<><h3 className="sec">Your material · {pl(words,'word')}</h3>{c.sources.map((x,i)=><div className="row" key={i}><div>{x.name}<small role={x.status==='reading'?'status':undefined}>{x.status?srcLine(x):<>{x.kind.toUpperCase()} · {pl(x.words,'word')} · {pl(x.paras,'paragraph')}</>}</small></div><div className="acts"><button className="ic sm" aria-label={'Remove '+x.name} onClick={()=>dropSrc(i)}><Trash2 size={16}/></button></div></div>)}
        <button className="btn" disabled={!!c.reading} onClick={()=>setStep(2)}>{c.reading?'Reading scanned pages…':'Next: slice it into topics'}</button></>}</>}
    {step===2&&<>
      <h3 className="sec first">How should it be sliced?</h3><p className="known" style={{marginTop:0}}>The AI groups your {pl(c.paragraphs,'paragraph')} into units and the smallest topics that make sense on their own. It keeps your own words; it only decides where each topic starts and ends and what to call it.</p>
      <label htmlFor="nts">Notes for the AI</label><textarea id="nts" value={notes} onChange={e=>setNotes(e.target.value)} placeholder={NOTES_HINT}/>
      <AiNote o={c}/>
      <button className={'btn'+(c.ai_available&&c.ai_left!==0?'':' ghost')} disabled={!!busy||!c.ai_available||c.ai_left===0} onClick={()=>slice('ai')}><Sparkles size={16}/> Slice with AI</button>
      <button className={'btn'+(c.ai_available&&c.ai_left!==0?' ghost':'')} disabled={!!busy} onClick={()=>slice('headings')}>Slice by headings instead (no AI)</button>
      <button className="btn ghost" onClick={()=>setStep(1)}>Back to material</button></>}
    {step===3&&plan&&<>
      <h3 className="sec first">Check the outline</h3><p className="known" style={{marginTop:0}}>{pl(plan.units.length,'unit')}, {pl(flat.length,'topic')}{c.sliced_by==='headings'?' · sliced by headings':''}. Rename anything, merge a topic into the next one, or remove one you don't need. Not right? Change the notes and slice again.</p>
      {plan.units.map((u,ui)=><section key={ui} className="qbox"><label className="sr" htmlFor={'u'+ui}>Unit {ui+1} title</label><input id={'u'+ui} className="utitle" value={u.title} onChange={e=>rename(ui,null,e.target.value)}/>
        {u.topics.map((t,ti)=>{const last=ui===plan.units.length-1&&ti===u.topics.length-1
          return <div key={t.from} className="ptopic"><label className="sr" htmlFor={`t${ui}-${ti}`}>Topic title</label><input id={`t${ui}-${ti}`} value={t.title} onChange={e=>rename(ui,ti,e.target.value)}/>
            <small className="known">{t.summary?t.summary+' · ':''}{pl(t.words||0,'word')}</small><p className="excerpt">{t.excerpt}{t.excerpt&&t.excerpt.length>=280?'…':''}</p>
            <div className="acts"><button className="tool" onClick={async()=>{try{setPeek({title:t.title,...(await api(`/study/courses/${id}/preview?start=${t.from}&end=${t.to}`))})}catch(e){toast(e.message)}}}>Read it all</button>
              {!last&&<button className="tool" onClick={()=>merge(ui,ti)}>Merge with next</button>}{flat.length>1&&<button className="tool" onClick={()=>remove(ui,ti)}>Remove</button>}</div></div>})}</section>)}
      <h3 className="sec">Slice it differently</h3><label htmlFor="nts2">Notes for the AI</label><textarea id="nts2" value={notes} onChange={e=>setNotes(e.target.value)} placeholder={NOTES_HINT}/>
      <div className="two"><button className="btn ghost" disabled={!!busy} onClick={()=>slice('ai')}><Sparkles size={16}/> Slice again with AI</button><button className="btn ghost" disabled={!!busy} onClick={()=>setStep(1)}>Change material</button></div>
      <button className="btn" disabled={!!busy} onClick={finish}><Check size={16}/> Finish: build my course</button>
      {dirty&&<button className="btn ghost" disabled={!!busy} onClick={async()=>{try{await savePlan();toast('Outline saved')}catch(e){toast(e.message)}}}>Save outline and finish later</button>}</>}
    {peek&&<Sheet close={()=>setPeek(null)}><h3>{peek.title}</h3><div className="prose"><Md>{peek.content}</Md></div><button className="btn ghost" onClick={()=>setPeek(null)}>Close</button></Sheet>}</div></>}
function StudyCourse({id,topic:first,toast,back,setup}){
  const confirm=useConfirm()
  const [c,setC]=useState(null),[p,setP]=useState(null),[topic,setTopic]=useState(first||null),[ren,setRen]=useState(null),[rev,setRev]=useState(null),[find,setFind]=useState('')
  const load=()=>{api('/study/courses/'+id).then(setC).catch(e=>{toast(e.message);back()});api(`/study/courses/${id}/progress`).then(setP).catch(()=>{})}
  useEffect(()=>{if(!topic&&!rev)load()},[id,topic,rev])
  if(rev)return <StudyQuizPlay quiz={rev} toast={toast} back={()=>setRev(null)}/>
  if(topic)return <StudyTopicPage id={topic} toast={toast} back={()=>setTopic(null)} go={setTopic}/>
  if(!c)return <><Bar title="Course" back={back}/><div className="main"><Skeleton/></div></>
  if(c.status!=='ready')return <><Bar title={c.title} back={back}/><div className="main"><p className="known">This course is being set up.</p>{c.can_edit&&<button className="btn" onClick={setup}>Continue the setup</button>}</div></>
  const all=c.units.flatMap(u=>u.topics),done=all.filter(t=>t.status==='completed').length
  const share=async v=>{try{await api('/study/courses/'+id,{method:'PUT',body:{share:v}});toast(v==='program'?'Classmates in your program can now study it':'Only you can see it now');load()}catch(e){toast(e.message)}}
  const del=async()=>{if(!await confirm({title:`Delete “${c.title}”?`,body:'Its topics, your progress and your quiz results are removed. This can\'t be undone.',ok:'Delete course',danger:true}))return;try{await api('/study/courses/'+id,{method:'DELETE'});toast('Course deleted');back()}catch(e){toast(e.message)}}
  const reopen=async()=>{if(!await confirm({title:'Change the setup?',body:'You go back to the outline. Your topics stay as they are until you finish the setup again.',ok:'Change the setup'}))return;try{await api(`/study/courses/${id}/reopen`,{method:'POST'});setup()}catch(e){toast(e.message)}}
  const next=all.find(t=>t.status!=='completed')
  return <><Bar title={c.title} sub={c.mine?'Your course':'Shared by '+c.owner} back={back}/><div className="main">
    <div className="qbox" style={{marginTop:0}}><div className="mast"><div><b>{c.mastery}% mastered</b><small>{done} of {all.length} topics completed</small></div><Stars n={c.mastery>=90?3:c.mastery>=60?2:c.mastery>0?1:0} big/></div><Bar2 v={c.mastery}/>
      {c.reviews_due>0&&<button className="btn" onClick={async()=>{try{setRev(await api(`/study/courses/${id}/review`,{method:'POST'}))}catch(e){toast(e.message)}}}><RotateCcw size={16}/> Review {pl(c.reviews_due,'topic')} due</button>}
      {p&&p.quizzed>0&&<p className="known" style={{margin:'8px 0 0'}}>Quiz average {p.average}% over {pl(p.quizzed,'topic')}.{p.summary&&' '+p.summary}</p>}
      {next&&<button className={'btn'+(c.reviews_due?' ghost':'')} onClick={()=>setTopic(next.id)}><Play size={16}/> {done?'Continue':'Start'}: {next.title}</button>}<p className="known" style={{margin:'8px 0 0'}}>{STAR_HELP}</p></div>
    {all.length>12&&<div className="search" style={{marginTop:14}}><Search size={18}/><input type="search" aria-label="Find a topic" placeholder="Find a topic" value={find} onChange={e=>setFind(e.target.value)}/></div>}
    {c.units.map(u=>({...u,topics:u.topics.filter(t=>!find.trim()||(t.title+' '+(t.summary||'')).toLowerCase().includes(find.trim().toLowerCase()))})).filter(u=>u.topics.length).map((u,ui)=><section key={u.id}><h3 className={'sec'+(ui?'':' first')}>{u.title}</h3>
      {u.topics.map(t=><button key={t.id} className="row rowbtn" onClick={()=>setTopic(t.id)}><div>{t.title}{t.due&&<span className="pill sm" style={{marginLeft:6}}>Review due</span>}<small>{t.summary||''}{t.best!=null?(t.summary?' · ':'')+'best quiz '+t.best+'%':''}</small></div><Stars n={t.stars}/><ChevronRight size={18}/></button>)}</section>)}
    {p&&p.areas.length>0&&<><h3 className="sec">From your quizzes</h3><p className="known" style={{marginTop:0}}>Your best quiz score in each topic, weakest first.</p>
      {p.areas.map(a=><button key={a.topic_id} className="row rowbtn" onClick={()=>setTopic(a.topic_id)}><div>{a.title}<span className={'pill sm '+(a.status==='strong'?'okp':a.status==='needs_study'?'off':'')} style={{marginLeft:6}}>{AREA_LABEL[a.status]}</span><small>Best quiz {a.percent}%</small><Bar2 v={a.percent}/></div><ChevronRight size={18}/></button>)}</>}
    {c.can_edit&&<><h3 className="sec">Course settings</h3>
      <label id="shr">Who can study it</label><div className="seg" role="group" aria-labelledby="shr" style={{gridTemplateColumns:'1fr 1fr',margin:'0 0 8px'}}>{[['private','Only me'],['program','My classmates']].map(([k,l])=><button key={k} className={c.share===k?'on':''} aria-pressed={c.share===k} onClick={()=>c.share!==k&&share(k)}>{l}</button>)}</div>
      <p className="known" style={{marginTop:0}}>{c.share==='program'?'Students in your program can open it and take their own quizzes. Only you can change it.':'Private: only you can see it.'}</p>
      <div className="two"><button className="btn ghost" onClick={()=>setRen(c.title)}><Pencil size={16}/> Rename</button><button className="btn ghost" onClick={reopen}>Change the setup</button></div>
      <button className="btn danger" onClick={del}>Delete course</button></>}
    {ren!=null&&<Sheet close={()=>setRen(null)}><h3>Rename course</h3><label htmlFor="rnm">Course name</label><input id="rnm" autoFocus value={ren} onChange={e=>setRen(e.target.value)}/>
      <button className="btn" disabled={!ren.trim()} onClick={async()=>{try{await api('/study/courses/'+id,{method:'PUT',body:{title:ren}});setRen(null);load()}catch(e){toast(e.message)}}}>Save</button><button className="btn ghost" onClick={()=>setRen(null)}>Cancel</button></Sheet>}</div></>}
const AiNote=({o})=>!o?null:!o.ai_available?<p className="known" role="note">{o.ai_own_key?'Add your own DeepSeek API key under “My AI key” in the menu to use explanations, quick checks and quizzes.':'AI help is switched off right now. Ask your admin to add an AI key.'}</p>
  :o.ai_left!=null&&o.ai_left<=10?<p className="known" role="note">{o.ai_left?`${pl(o.ai_left,'AI request')} left today for your own courses.`:'You have used today\'s AI requests for your own courses. Reviews still work; new questions come back tomorrow.'}</p>:null
function StudyTopicPage({id,toast,back,go}){
  const confirm=useConfirm()
  const [t,setT]=useState(null),[tab,setTab]=useState('notes'),[ex,setEx]=useState(null),[busy,setBusy]=useState(''),[quiz,setQuiz]=useState(null),[ed,setEd]=useState(null)
  const load=()=>api('/study/topics/'+id).then(setT).catch(e=>{toast(e.message);back()})
  useEffect(()=>{setT(null);setEx(null);setTab('notes');load();window.scrollTo(0,0)},[id])
  useEffect(()=>{if(!quiz&&t)load()},[quiz])
  if(quiz)return <StudyQuizPlay quiz={quiz} toast={toast} back={()=>setQuiz(null)} again={k=>make(k)} next={t?.next&&{title:t.next.title,go:()=>{setQuiz(null);go(t.next.id)}}}/>
  if(!t)return <><Bar title="Topic" back={back}/><div className="main"><Skeleton/></div></>
  const explain=async()=>{setBusy('explain');try{setEx(await api(`/study/topics/${id}/explain`))}catch(e){toast(e.message)}setBusy('')}
  async function make(kind){setBusy(kind);try{setQuiz(await api(`/study/topics/${id}/quizzes`,{method:'POST',body:{kind}}))}catch(e){toast(e.message)}setBusy('')}
  const done=async on=>{try{await api(`/study/topics/${id}/progress`,{method:'PUT',body:{completed:on}});setT({...t,completed:on});toast(on?'Marked as completed':'Marked as not completed')}catch(e){toast(e.message)}}
  const saveEd=async()=>{try{await api('/study/topics/'+id,{method:'PUT',body:ed});setEd(null);setEx(null);toast('Topic saved');load()}catch(e){toast(e.message)}}
  const delTopic=async()=>{if(!await confirm({title:`Delete “${t.title}”?`,body:'The topic, your progress and your checks on it are removed. This can\'t be undone.',ok:'Delete topic',danger:true}))return
    try{await api('/study/topics/'+id,{method:'DELETE'});toast('Topic deleted');back()}catch(e){toast(e.message)}}
  const noAi=!t.ai_available||t.ai_left===0
  return <><Bar title={t.title} sub={t.course+' › '+t.unit+' · '+t.position+' of '+t.total} back={back}/><div className="main">
    <div className="mast" style={{marginBottom:10}}><Stars n={t.stars} big/><small className="known">{['Not started yet','Completed','Quiz passed','Mastered'][t.stars]} · {STAR_HELP}</small></div>
    <Tabs label="Topic sections" items={[['notes','Notes'],['explain','Explain']]} value={tab} onChange={setTab}/>
    {tab==='notes'&&<div className="prose"><Md>{t.content}</Md></div>}
    {tab==='explain'&&(ex?<div className="prose">{ex.cached&&<span className="chip">Saved explanation · no AI request used</span>}<Md>{ex.text}</Md></div>
      :t.has_explain||!noAi?<button className="btn" disabled={!!busy} onClick={explain}><Sparkles size={16}/> {busy==='explain'?'Thinking…':'Explain it to me'}</button>:<AiNote o={t}/>)}
    <h3 className="sec">Check yourself</h3>
    <AiNote o={t}/>
    <div className="two"><button className="btn" disabled={!!busy||noAi} onClick={()=>make('mcq')}><ClipboardList size={16}/> {busy==='mcq'?'Writing questions…':'Quick check · 5'}</button><button className="btn ghost" disabled={!!busy||noAi} onClick={()=>make('quiz')}><Target size={16}/> {busy==='quiz'?'Writing the quiz…':'Full quiz · 10'}</button></div>
    <p className="known">Quick check: 5 practice MCQs with the answer right after each one; 4 right marks the topic completed. Full quiz: 10 questions scored at the end; pass it for ★★, score 90% for ★★★. New questions every time, and the topic comes back for review before you forget it.</p>
    {t.attempts.length>0&&<><h3 className="sec">Your results here</h3>{t.attempts.slice(0,5).map(a=><div className="row" key={a.id}><div>{a.kind==='quiz'?'Quiz':'Practice MCQs'} · {a.score} / {a.total} · {a.percent}%<small>{when(a.at)}</small><Bar2 v={a.percent}/></div></div>)}</>}
    <div style={{marginTop:16}}>{t.completed?<button className="btn ghost" onClick={()=>done(false)}>Mark as not completed</button>:<button className="btn" onClick={()=>done(true)}><Check size={16}/> Mark as completed</button>}</div>
    <div className="two">{t.prev?<button className="btn ghost" onClick={()=>go(t.prev.id)}><ChevronLeft size={16}/> Previous</button>:<span/>}{t.next&&<button className="btn ghost" onClick={()=>go(t.next.id)}>Next <ChevronRight size={16}/></button>}</div>
    {t.can_edit&&<div className="two"><button className="btn ghost" onClick={()=>setEd({title:t.title,content:t.content})}><Pencil size={16}/> Edit topic</button><button className="btn ghost" onClick={delTopic}><Trash2 size={16}/> Delete topic</button></div>}
    {ed&&<Sheet close={()=>setEd(null)}><h3>Edit topic</h3><label htmlFor="ett">Title</label><input id="ett" value={ed.title} onChange={e=>setEd({...ed,title:e.target.value})}/>
      <label htmlFor="etc">Text</label><textarea id="etc" style={{minHeight:260}} value={ed.content} onChange={e=>setEd({...ed,content:e.target.value})}/>
      <p className="known">Markdown works: # for headings, - for lists, **bold**. Your progress and stars stay.</p>
      <button className="btn" disabled={!ed.title.trim()||!ed.content.trim()} onClick={saveEd}>Save</button><button className="btn ghost" onClick={()=>setEd(null)}>Cancel</button></Sheet>}</div></>}
function StudyQuizPlay({quiz,toast,back,again,next}){
  const mcq=quiz.kind!=='quiz',[ans,setAns]=useState(quiz.questions.map(()=>null)),[fb,setFb]=useState({}),[res,setRes]=useState(null),[busy,setBusy]=useState(false)
  const [flagged,setFlagged]=useState({})
  const flag=async i=>{try{await api(`/study/quizzes/${quiz.id}/flag`,{method:'POST',body:{index:i}});setFlagged(f=>({...f,[i]:true}));toast('Thanks. That question won\'t come back in your reviews.')}catch(e){toast(e.message)}}
  const pick=async(i,k)=>{if(res||(mcq&&fb[i]))return;setAns(a=>a.map((v,n)=>n===i?k:v));if(!mcq)return
    try{const r=await api(`/study/quizzes/${quiz.id}/check`,{method:'POST',body:{index:i,answer:k}});setFb(f=>({...f,[i]:r}))}catch(e){toast(e.message)}}
  const submit=async()=>{setBusy(true);try{setRes(await api(`/study/quizzes/${quiz.id}/attempt`,{method:'POST',body:{answers:ans}}));window.scrollTo(0,0)}catch(e){toast(e.message)}setBusy(false)}
  const left=ans.filter(a=>a==null).length,review=quiz.kind==='review',label=review?'Review':mcq?'Quick check':'Full quiz'
  const cheer=res&&[res.xp.level_up&&`Level ${res.xp.level}!`,res.stars.after>res.stars.before&&['','Topic completed','Quiz passed','Mastered!'][res.stars.after],res.completed_now&&res.stars.after<2&&'Topic completed'].filter((x,i,all)=>x&&all.indexOf(x)===i)
  return <><Bar title={label} sub={quiz.topic+' · '+pl(quiz.questions.length,'question')} back={back}/><div className="main">
    {res&&<div className={'qbox score'+(cheer.length?' win':'')} style={{marginTop:0}} role="status">
      {cheer.length>0&&<div className="cheer"><span aria-hidden="true">🎉</span> {cheer.join(' · ')}</div>}
      <h2 style={{margin:0}}>{res.score} / {res.total} · {res.percent}%</h2>
      <p className="known" style={{margin:'6px 0'}}><b className="xp">+{res.xp.gained} XP</b> · level {res.xp.level}{res.stars.after>0&&<> · <Stars n={res.stars.after}/></>}</p>
      <p className="known">{review?'Review done.':mcq?(res.percent>=80?'Nicely done.':'Practice done. Read the tricky parts again.'):res.passed?'Passed. Well done!':`Below ${res.pass_percent}%. Read the topic again and try a new quiz.`}{res.summary&&' '+res.summary}{res.next_review&&' '+res.next_review+'.'}</p>
      {next&&<button className="btn" onClick={next.go}>Next topic: {next.title} <ChevronRight size={16}/></button>}
      <div className="two">{again&&<button className={'btn'+(next?' ghost':'')} onClick={()=>again(quiz.kind)}>New {mcq?'questions':'quiz'}</button>}<button className={'btn'+(again||next?' ghost':'')} onClick={back}>{review?'Done':'Back to the topic'}</button></div></div>}
    {res&&!mcq&&res.areas.length>0&&<><h3 className="sec">What you know well and what to revisit</h3><AreaList areas={res.areas} onStudy={null} staff/></>}
    {quiz.questions.map((x,i)=>{const f=mcq?fb[i]:res&&res.results[i]
      return <div className="qbox" key={i}><b>Question {i+1}{f?(f.ok?' · Right':' · Wrong'):''}</b>{x.topic&&<small className="known" style={{display:'block'}}>{x.topic}</small>}<div className="prose"><Md>{x.text}</Md></div>
        {x.options.map((o,k)=>{const cls=f?(k===f.correct?' ok':k===ans[i]?' bad':''):ans[i]===k?' sel':''
          return <button key={k} className={'opt'+cls} disabled={!!f||!!res} aria-pressed={ans[i]===k} onClick={()=>pick(i,k)}><b className="olet">{LET[k]}</b><span className="obody"><Md>{o}</Md></span>{f&&k===f.correct&&<span className="otag ok"><Check size={14}/> Correct</span>}</button>})}
        {f&&f.explanation&&<div className="known"><Md>{f.explanation}</Md></div>}
        {f&&(flagged[i]?<p className="known" style={{margin:'4px 0 0'}}>Reported.</p>:<button className="tool" onClick={()=>flag(i)}>This question is wrong</button>)}</div>})}
    {!res&&<><button className="btn" disabled={busy||(mcq&&Object.keys(fb).length<quiz.questions.length)} onClick={submit}>{busy?'Checking…':mcq?'See my score':'Submit answers'}</button>
      {mcq?<p className="known">Pick an answer to see right away if it is right.{Object.keys(fb).length<quiz.questions.length?` ${quiz.questions.length-Object.keys(fb).length} to go.`:''}</p>:left>0&&<p className="known">{left} unanswered. Blank answers count as wrong.</p>}</>}</div></>}
function BankSheet({close,onAdd,toast}){
  const confirm=useConfirm()
  const [q,setQ]=useState(''),[tag,setTag]=useState(''),[mine,setMine]=useState(false),[d,setD]=useState(null),[sel,setSel]=useState({}),[n,setN]=useState(0)
  useEffect(()=>{const t=setTimeout(()=>api('/bank?limit=30&q='+encodeURIComponent(q)+'&tag='+encodeURIComponent(tag)+(mine?'&mine=true':'')).then(setD).catch(e=>toast(e.message)),250);return()=>clearTimeout(t)},[q,tag,mine,n,toast])
  const picked=Object.values(sel),more=async()=>{try{const r=await api('/bank?limit=30&offset='+d.items.length+'&q='+encodeURIComponent(q)+'&tag='+encodeURIComponent(tag)+(mine?'&mine=true':''));setD({...d,items:[...d.items,...r.items]})}catch(e){toast(e.message)}}
  const flip=x=>{const c={...sel};c[x.id]?delete c[x.id]:c[x.id]=x;setSel(c)}
  const del=async x=>{if(!await confirm({title:'Delete this question from the bank?',body:'It disappears for everyone. Quizzes that already use it keep their copy.',ok:'Delete',danger:true}))return;try{await api('/bank/'+x.id,{method:'DELETE'});const c={...sel};delete c[x.id];setSel(c);setN(n+1)}catch(e){toast(e.message)}}
  return <Sheet close={close}><h3>Question bank</h3><p className="known">Questions shared by every teacher. Adding one puts a copy in this quiz, so later changes to the bank never alter a quiz students are taking.</p>
    <div className="search"><Search size={18}/><input type="search" aria-label="Search the bank" placeholder="Search questions, tags or source" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label="Filter by tag" value={tag} onChange={e=>setTag(e.target.value)}><option value="">All tags</option>{(d?.tags||[]).map(t=><option key={t} value={t}>{t}</option>)}</select>
      <label className="chk" style={{padding:0}}><input type="checkbox" checked={mine} onChange={e=>setMine(e.target.checked)}/> Only mine</label></div>
    {!d?<div className="sk"/>:!d.items.length?<p className="known">{q||tag||mine?'Nothing matches that.':'The bank is empty. Use “Save to bank” in any quiz to start it.'}</p>:d.items.map(x=><div key={x.id} className="row"><label className="chk" style={{alignItems:'flex-start',flex:1}}><input type="checkbox" checked={!!sel[x.id]} onChange={()=>flip(x)}/><span><span style={{display:'block'}}>{x.text.length>180?x.text.slice(0,180)+'…':x.text}</span><small>{x.options.length} answers{x.tags.length>0&&' · '+x.tags.join(', ')} · by {x.owner||'someone'}{x.uses>0&&' · used '+pl(x.uses,'time')}</small></span></label>{x.can_edit&&<button className="ic sm" aria-label="Delete from the bank" onClick={()=>del(x)}><Trash2 size={16}/></button>}</div>)}
    {d&&d.items.length<d.total&&<ShowMore left={d.total-d.items.length} onClick={more}/>}
    <button className="btn" disabled={!picked.length} onClick={()=>onAdd(picked)}>{picked.length?`Add ${pl(picked.length,'question')}`:'Choose questions to add'}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}

function CopySheet({kind,id,title,close,toast}){
  const [tree,setTree]=useState(null),[cid,setCid]=useState(''),[uid,setUid]=useState(''),[wq,setWq]=useState(true),[busy,setBusy]=useState(false),[res,setRes]=useState(null)
  useEffect(()=>{api('/tree').then(setTree).catch(e=>{toast(e.message);close()})},[toast,close])
  const courses=(tree||[]).flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>c.editable&&!c.shared).map(c=>({...c,label:`${p.name} › ${s.name} › ${c.name}`}))))
  const dest=courses.find(c=>String(c.id)===cid)
  const run=async()=>{setBusy(true);try{setRes(await api(`/${kind==='topic'?'topics':'units'}/${id}/copy`,{method:'POST',body:kind==='topic'?{unit_id:+uid}:{course_id:+cid,with_quizzes:wq}}))}catch(e){toast(e.message)}setBusy(false)}
  if(res)return <Sheet close={close}><h3>Copied</h3><p className="known">{kind==='topic'?`“${res.title}” is a draft in ${dest.label} › ${dest.units.find(u=>u.id===res.unit_id)?.name}.`:`“${res.name}” is in ${dest.label} with ${pl(res.topics,'topic')}${res.quizzes?` and ${pl(res.quizzes,'quiz')}`:''}.`} Everything arrives as a draft, so students see nothing until you publish it.</p><button className="btn" onClick={close}>Done</button></Sheet>
  return <Sheet close={close}><h3>Copy {kind==='topic'?'topic':'unit'}</h3><p className="known">Makes a copy of “{title}”{kind==='unit'?' with its topics'+(' and, if you may edit the original, its quizzes'):''} in a course you can edit. The original is not changed. Reading progress and bookmarks are not copied.</p>
    {!tree?<div className="sk"/>:!courses.length?<p className="known">You do not own a course to copy into. An admin makes you the owner of a course.</p>:<>
      <label htmlFor="cc">Copy into course</label><select id="cc" value={cid} onChange={e=>{setCid(e.target.value);setUid('')}}><option value="">Choose a course</option>{courses.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select>
      {kind==='topic'&&dest&&<><label htmlFor="cu">Unit</label><select id="cu" value={uid} onChange={e=>setUid(e.target.value)}><option value="">Choose a unit</option>{dest.units.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select>{!dest.units.length&&<p className="known">That course has no units yet. Add a unit first.</p>}</>}
      {kind==='unit'&&<label className="chk"><input type="checkbox" checked={wq} onChange={e=>setWq(e.target.checked)}/> Include its quizzes (as drafts)</label>}</>}
    <button className="btn" disabled={busy||!dest||(kind==='topic'&&!uid)} onClick={run}>{busy?'Copying…':'Copy'}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}
const FIELD_LABEL={title:'Title',content:'Notes',content_format:'Content format',sample_content:'Sample answer',question_pattern:'Question pattern',guideline:'Answer guideline'}
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
  const restore=async()=>{if(!await confirm({title:'Put this version back?',body:'What is there now stays in the history, so you can undo it.',ok:'Restore version'}))return;setBusy(true)
    try{await api(`/topic-versions/${v.id}/restore`,{method:'POST'});toast('Version restored');done()}catch(e){toast(e.message);setBusy(false)}}
  if(v){const changed=Object.keys(FIELD_LABEL).filter(k=>v[k]!==v.now[k])
    return <Sheet close={close}><button className="link" onClick={()=>setV(null)}><ChevronLeft size={16}/> All versions</button>
      <h3>{v.saved_at?when(v.saved_at):'Earlier version'}</h3><p className="known">{v.note}{v.current?' · this is the current text':''}</p>
      {!changed.length&&<p className="known">Same as the current text.</p>}
      {changed.map(k=><div key={k} className="qbox"><b>{FIELD_LABEL[k]}</b><p className="known" style={{margin:'2px 0 8px'}}>Red lines are in this version only. Green lines are in the current text.</p>
        <div className="diff">{lineDiff(v[k],v.now[k]).map((l,i)=><div key={i} className={'dl '+l.k}>{l.t||'\u00a0'}</div>)}</div></div>)}
      {!v.current&&<button className="btn" disabled={busy} onClick={restore}>Restore this version</button>}<button className="btn ghost" onClick={close}>Close</button></Sheet>}
  return <Sheet close={close}><h3>Version history</h3><p className="known">Every save is kept (the latest {100}). Pick one to compare it with the current text.</p>
    {!list?<div className="sk"/>:!list.length?<p className="known">No versions recorded yet. They appear the next time this topic is saved.</p>
      :list.map(x=><button key={x.id} className="row" style={{width:'100%',textAlign:'left',background:'none'}} onClick={()=>open(x)}><div>{x.saved_at&&!(x.by===null&&x.note.startsWith('Before'))?when(x.saved_at):'Before history began'}<small>{x.note}{x.by?' · '+x.by:''}</small></div>{x.current&&<span className="pill">Current</span>}<ChevronRight size={16}/></button>)}
    <button className="btn ghost" onClick={close}>Close</button></Sheet>}
function Topic({id:first,back,toast,role}){
  const [practice,setPractice]=useState(null),[checking,setChecking]=useState('')
  const [id,setId]=useState(first),[editing,setEditing]=useState(false),[v,setV]=useState(0),[t,setT]=useState(null),[tab,setTab]=useState('notes'),[known,setKnown]=useState([]),[ai,setAi]=useState({}),[aiOk,setAiOk]=useState(null),[ownKey,setOwnKey]=useState(false),[aiMsg,setAiMsg]=useState(''),[busy,setBusy]=useState(false),[bm,setBm]=useState(false),[pv,setPv]=useState(false),[hist,setHist]=useState(false),[cp,setCp]=useState(false),[gone,setGone]=useState('')
  const [mat,setMat]=useState(false),[upNext,setUpNext]=useState(null),opened=useRef(false),jump=nid=>{opened.current=false;setUpNext(null);setGone('');setT(null);setTab('notes');setAi({});setAiMsg('');setKnown([]);setEditing(false);setId(nid);window.scrollTo(0,0)},learn=r=>setT(p=>({...p,status:r.status,overdue:r.overdue,late:r.late,completed_at:r.completed_at}))
  useEffect(()=>{api('/topics/'+id).then(x=>{setT(x);setBm(!!x.bookmarked)
    if(!opened.current){opened.current=true;api(`/topics/${id}/read`,{method:'POST'}).then(r=>{setKnown(r.known);learn(r)}).catch(()=>{})}}).catch(e=>{toast(e.message);if(/unavailable right now/.test(e.message))setGone(e.message)})},[id,v])  // opening starts it, after the page has loaded
  const setDone=async on=>{try{learn(await api(`/topics/${id}/complete`,{method:on?'PUT':'DELETE'}));toast(on?'Marked as completed':'Marked as not completed')}catch(e){toast(e.message);return}
    setUpNext(null);if(!on||role!=='student')return
    try{const items=(await api('/me/session')).session?.items||[];if(items.some(x=>x.id===id&&x.kind!=='review'&&x.src!=='study'))setUpNext({items,next:items.find(x=>!x.done)})}catch{/* no session today: nothing to lead on to */}}
  useEffect(()=>{api('/ai/status').then(r=>{setAiOk(r.available);setOwnKey(!!r.own_key)}).catch(()=>{})},[id])
  const ask=async k=>{setBusy(true);setAiMsg('');try{const r=await api(`/topics/${id}/ai/${k}`);setAi(a=>({...a,[k]:r}))}catch(e){setAiMsg(e.message)}setBusy(false)}
  async function practise(kind){setChecking(kind);try{setPractice(await api(`/topics/${id}/practice`,{method:'POST',body:{kind}}))}catch(e){toast(e.message)}setChecking('')}
  if(mat&&t)return <MyMaterial cid={t.course_id} name={t.course} back={()=>{setMat(false);setAi({});setAiMsg('');setV(v+1)}} toast={toast}/>  // clear saved answers: the notes may have changed, so Explain must be asked again
  if(practice)return <StudyQuizPlay quiz={practice} toast={toast} back={()=>setPractice(null)} again={k=>practise(k)}/>
  if(editing)return <TopicEditor role={role} toast={toast} edit={{id}} done={()=>{setEditing(false);setV(v+1)}} cancel={()=>setEditing(false)}/>
  if(gone)return <><Bar title="Unavailable" back={back}/><div className="main"><div className="hero"><h2>{gone}</h2><p>It has been archived. Check back later or ask your teacher.</p></div></div></>
  if(!t)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const flip=async()=>{const on=!bm;setBm(on);try{await api(`/topics/${id}/bookmark`,{method:on?'PUT':'DELETE'});toast(on?'Bookmarked':'Bookmark removed')}catch(e){setBm(!on);toast(e.message)}}
  const view=k=>ai[k]?<div className="prose">{ai[k].cached&&<span className="chip">Saved answer · no tokens used</span>}{ai[k].own_notes&&<span className="chip">Written with your own notes</span>}<Md>{ai[k].text}</Md></div>
    :aiOk===false?<p className="known">{ownKey?'Add your own DeepSeek API key under “My AI key” in the menu to use AI help.':'AI unavailable. Try again later.'}</p>
    :<><button className="btn" disabled={busy} onClick={()=>ask(k)}><Sparkles size={16}/> {busy?'Thinking…':k==='explain'?'Explain it to me':'Show a sample answer'}</button>{t.my_notes&&<p className="known">Uses your own notes too. It counts toward your daily AI requests.</p>}{aiMsg&&<p className="known">{aiMsg}</p>}</>
  return <><Bar title={t.title} sub={[t.program,t.semester,t.course,t.unit].filter(Boolean).join(' › ')} back={back} right={role!=='admin'&&<button className={'ic'+(bm?' on':'')} aria-label={bm?'Remove bookmark':'Bookmark this topic'} aria-pressed={bm} onClick={flip}><Bookmark fill={bm?'currentColor':'none'}/></button>}/><div className="main">
    {t.can_edit&&pv&&<div className="qbox" style={{marginTop:0}}><b>Previewing as a student</b><p className="known" style={{margin:'4px 0 8px'}}>This is what students see: no editing buttons, and drafts show as unavailable to them.</p><button className="btn ghost" style={{marginTop:0}} onClick={()=>setPv(false)}>Back to editing</button></div>}
    {t.can_edit&&!pv&&<div className="two" style={{marginBottom:12}}><button className="btn ghost" style={{marginTop:0}} onClick={()=>setEditing(true)}><Pencil size={16}/> Edit topic</button>
      <button className="btn ghost" style={{marginTop:0}} onClick={async()=>{try{await api(`/topics/${id}/publish`,{method:'PUT',body:{published:!t.published}});toast(t.published?'Moved to drafts':'Published');setV(v+1)}catch(e){toast(e.message)}}}>{t.published?<><EyeOff size={16}/> Unpublish</>:<><Eye size={16}/> Publish</>}</button></div>}
    <div className="qbox" style={{marginTop:0}}><div className="row"><div>{t.learning_due_at?when(t.learning_due_at):'No deadline'}<small>Learn by</small></div>{t.overdue&&role==='student'&&<span className="pill off sm">Overdue</span>}</div>
      {role==='student'&&<><div className="row"><div>{STATUS[t.status]}{t.status==='completed'&&t.completed_at&&' on '+when(t.completed_at)+(t.late?', after the deadline':'')}<small>Your status</small></div></div>
        {t.status==='completed'?<button className="btn ghost" onClick={()=>setDone(false)}>Mark as not completed</button>:<button className="btn" onClick={()=>setDone(true)}><Check size={16}/> Mark as completed</button>}</>}</div>
    {upNext&&<div className="qbox" role="status"><b>Today's session · {upNext.items.filter(x=>x.done).length} of {upNext.items.length} done</b>
      {!upNext.next?<p className="known" style={{margin:'4px 0 0'}}>That's today's session done. See you next study day.</p>
        :upNext.next.kind!=='review'&&upNext.next.src!=='study'?<button className="btn" onClick={()=>jump(upNext.next.id)}>Next: {upNext.next.title}<ChevronRight size={16}/></button>
        :<button className="btn ghost" onClick={back}>Back for the next part: {upNext.next.title}</button>}</div>}
    {t.can_edit&&!pv&&<><button className="tool" onClick={()=>setPv(true)}><Eye size={14}/> Preview as student</button><button className="tool" onClick={()=>setHist(true)}><History size={14}/> Version history</button></>}
    {role!=='student'&&!pv&&<button className="tool" onClick={()=>setCp(true)}><Copy size={14}/> Copy to another course</button>}
    {cp&&<CopySheet kind="topic" id={id} title={t.title} toast={toast} close={()=>setCp(false)}/>}
    {hist&&<HistorySheet tid={id} toast={toast} close={()=>setHist(false)} done={()=>{setHist(false);setV(v+1)}}/>}
    {t.can_edit&&!t.published&&<p className="known" style={{marginTop:0}}>Draft · students cannot see it</p>}
    <Tabs label="Topic sections" items={[['notes','Notes'],['explain','Explain'],['answer','Sample answer']]} value={tab} onChange={setTab}/>
    {known.length>0&&tab==='explain'&&<p className="known">You’ve already covered: {known.join(', ')}</p>}
    {tab==='notes'&&<div className="prose">{t.content?<Body text={t.content} format={t.content_format}/>:!t.my_notes&&<Md>No notes yet.</Md>}{t.my_notes&&<>{t.content&&<h3>Your notes</h3>}{!t.content&&<span className="chip">Your notes</span>}<Md>{t.my_notes}</Md></>}{t.question_pattern&&<><h3>Question pattern</h3><Md>{t.question_pattern}</Md></>}{t.guideline&&<><h3>Answer guideline</h3><Md>{t.guideline}</Md></>}{role==='student'&&<button className="tool" onClick={()=>setMat(true)}><FileText size={14}/> {t.my_notes?'Update your notes for this course':'Add your own notes for this topic'}</button>}</div>}
    {tab==='explain'&&view('explain')}{tab==='answer'&&view('answer')}
    {role==='student'&&aiOk!==false&&<><h3 className="sec">Check yourself</h3><div className="two"><button className="btn ghost" disabled={!!checking} onClick={()=>practise('mcq')}><ClipboardList size={16}/> {checking==='mcq'?'Writing questions…':'Quick check · 5'}</button><button className="btn ghost" disabled={!!checking} onClick={()=>practise('quiz')}><Target size={16}/> {checking==='quiz'?'Writing the quiz…':'Full quiz · 10'}</button></div>
      <p className="known" style={{marginTop:4}}>The AI writes new questions from this topic's notes each time. Quick check: the answer right after each question. Full quiz: scored at the end.</p></>}
    {t.nav&&t.nav.total>1&&<nav className="pager" aria-label="Topics in this unit"><button className="btn ghost" disabled={!t.nav.prev} onClick={()=>jump(t.nav.prev.id)} aria-label={t.nav.prev?'Previous topic: '+t.nav.prev.title:'No previous topic'}><ChevronLeft size={18}/><span>{t.nav.prev?t.nav.prev.title:'Previous'}</span></button>
      <small>{t.nav.position} of {t.nav.total}</small>
      <button className={'btn'+(t.nav.next?'':' ghost')} disabled={!t.nav.next} onClick={()=>jump(t.nav.next.id)} aria-label={t.nav.next?'Next topic: '+t.nav.next.title:'No next topic'}><span>{t.nav.next?t.nav.next.title:'Next'}</span><ChevronRight size={18}/></button></nav>}</div></>}

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
const FILES_HELP='Pick the HTML file for the content and a config .md file for the title and the other boxes, together with any images the HTML uses. The form fills in; check it, then save.'
function TopicEditor({role,toast,done,cancel,edit,unitId}){  // edit = {id} of a topic, or null for a new one in unitId
  const confirm=useConfirm()
  const fac=role==='faculty',[prev,setPrev]=useState(false),[up,setUp]=useState(false),fileRef=useRef(null),taRef=useRef(null),filesRef=useRef(null),[busy,setBusy]=useState(false)
  const [tree,setTree]=useState([]),[f,setF]=useState({title:'',unit_id:unitId||'',content:'',content_format:'markdown',sample_content:'',question_pattern:'',guideline:'',published:!fac,due:''}),[cid,setCid]=useState(null)
  const [fromFiles,setFromFiles]=useState(null),[shown,setShown]=useState(''),[imp,setImp]=useState(false)
  useEffect(()=>{api('/tree').then(setTree).catch(()=>{});if(edit)api('/topics/'+edit.id).then(t=>{setCid(t.course_id);setF({title:t.title,unit_id:t.unit_id||'',content:t.content||'',content_format:t.content_format||'markdown',sample_content:t.sample_content||'',question_pattern:t.question_pattern||'',guideline:t.guideline||'',published:t.published!==false,due:localInput(t.learning_due_at)})}).catch(e=>toast(e.message))},[])
  const html=f.content_format==='html'
  useEffect(()=>{if(!prev||!html)return;let live=true;api('/topics/clean-html',{method:'POST',body:{html:f.content}}).then(r=>live&&setShown(r.html)).catch(e=>toast(e.message));return()=>{live=false}},[prev,html,f.content])
  const set=k=>e=>setF({...f,[k]:e.target.value})
  const pickFiles=async e=>{const files=[...e.target.files];e.target.value='';if(!files.length)return
    const ext=x=>(x.name.split('.').pop()||'').toLowerCase(),htmlF=files.filter(x=>['html','htm'].includes(ext(x))),cfgF=files.filter(x=>['md','markdown','txt'].includes(ext(x))),imgs=files.filter(x=>/^image\//.test(x.type))
    if(htmlF.length>1||cfgF.length>1)return toast('Choose one HTML file and one config file at a time')
    if(!htmlF.length&&!cfgF.length)return toast('Choose an HTML file, a config .md file, or both')
    if((f.content.trim()||f.question_pattern.trim()||f.sample_content.trim()||f.guideline.trim())&&!await confirm({title:'Replace what is in the form?',body:'The boxes the files fill in are replaced. Nothing is saved until you save.',ok:'Fill from files'}))return
    setBusy(true);try{const images={};for(const x of imgs)images[x.name]=await uploadImg(x)
      const r=await api('/topics/from-files',{method:'POST',body:{unit_id:+(f.unit_id||unitId),html:htmlF.length?await htmlF[0].text():'',config:cfgF.length?await cfgF[0].text():'',images}})
      setF(cur=>({...cur,...['title','content','content_format','question_pattern','sample_content','guideline'].reduce((o,k)=>r[k]!==undefined?{...o,[k]:r[k]}:o,{}),...(r.published!==undefined?{published:r.published}:{}),...(r.learning_due_at?{due:r.learning_due_at}:{})}))
      setFromFiles({names:[...htmlF,...cfgF].map(x=>x.name),warnings:r.warnings,images:r.images_saved+imgs.length});setPrev(!!r.content&&r.content_format==='html');toast('Filled from '+[...htmlF,...cfgF].map(x=>x.name).join(' and ')+'. Check it, then save.')}catch(er){toast(er.message)}setBusy(false)}
  const pickImg=async e=>{const file=e.target.files[0];e.target.value='';if(!file)return;if(file.size>3*1024*1024)return toast('Image is too large. Keep it under 3 MB.')
    setUp(true);try{const r=await fetch('/api/uploads',{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:file});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Upload failed')
      const pos=taRef.current?.selectionStart??f.content.length,tag=html?`\n<p><img src="${d.url}" alt="Describe the image"></p>\n`:`\n\n![Describe the image](${d.url})\n\n`;setF({...f,content:f.content.slice(0,pos)+tag+f.content.slice(pos)});toast('Image added')}catch(er){toast(er.message)}setUp(false)}
  const all=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared&&c.editable).flatMap(c=>c.units.map(n=>({...n,course_id:c.id,label:`${c.name} › ${n.name}`})))))
  const units=role==='admin'?all:all.filter(n=>n.course_id===cid)  // faculty move a topic only between units of its own course
  const here=all.find(n=>n.id===+f.unit_id)
  const save=async()=>{setBusy(true);try{await api(edit?'/topics/'+edit.id:'/topics',{method:edit?'PUT':'POST',body:{...f,due:undefined,unit_id:+f.unit_id,published:f.published!==false,learning_due_at:f.due?new Date(f.due).toISOString():null}});toast(edit?'Changes saved':'Topic added');done()}catch(e){toast(e.message)}setBusy(false)}
  const T=(k,l,ph)=><><label>{l}</label><textarea placeholder={ph} value={f[k]} onChange={set(k)}/></>
  return <><Bar title={edit?'Edit topic':'New topic'} sub={here?.label} back={cancel}/><div className="main">
    {!imp&&!fromFiles&&<button className="tool" style={{marginTop:0}} onClick={()=>setImp(true)}><Upload size={14}/> Fill from files (HTML and config)</button>}
    {(imp||fromFiles)&&<div className="qbox" style={{marginTop:0}}><b>Fill from files</b><p className="known" style={{margin:'4px 0 8px'}}>{FILES_HELP}</p>
      <input ref={filesRef} type="file" hidden multiple accept=".html,.htm,.md,.markdown,.txt,text/html,text/markdown,image/png,image/jpeg,image/gif,image/webp" onChange={pickFiles}/>
      <div className="two"><button className="btn" style={{margin:0}} disabled={busy} onClick={()=>filesRef.current.click()}><Upload size={16}/> {busy?'Reading…':'Choose files'}</button><button className="btn ghost" style={{margin:0}} onClick={()=>download('topic-config.md',TOPIC_CONFIG_TEMPLATE)}>Config template</button></div>
      {fromFiles&&<div role="status" style={{marginTop:10}}><p className="known" style={{margin:0}}>Filled from {fromFiles.names.join(' and ')}{fromFiles.images?` · ${pl(fromFiles.images,'image')}`:''}.</p>
        {fromFiles.warnings.map((w,i)=><p key={i} className="known" style={{margin:'4px 0 0',color:'var(--warn)'}}>{w}</p>)}</div>}</div>}
    {edit&&units.length>1&&<><label>Unit</label><select value={f.unit_id} onChange={set('unit_id')}>{units.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></>}
    <label>Topic title</label><input value={f.title} onChange={set('title')} placeholder="First law of thermodynamics"/>
    <label>Topic content</label><div className="seg" style={{gridTemplateColumns:'1fr 1fr',margin:'0 0 8px'}} role="group" aria-label="Content format">{[['markdown','Markdown'],['html','HTML']].map(([k,l])=><button key={k} type="button" className={f.content_format===k?'on':''} aria-pressed={f.content_format===k} onClick={()=>setF({...f,content_format:k})}>{l}</button>)}</div>
    <div className="tools"><button type="button" disabled={up} onClick={()=>fileRef.current.click()}>{up?'Uploading…':'Add image'}</button><button type="button" onClick={()=>setPrev(!prev)}>{prev?'Back to editing':'Preview'}</button></div>
    <input ref={fileRef} type="file" hidden accept="image/png,image/jpeg,image/gif,image/webp" onChange={pickImg}/>
    {prev?<div className="prose">{!f.content?<Md>Nothing to preview yet.</Md>:html?<Body text={shown} format="html"/>:<Md>{f.content}</Md>}</div>:<textarea ref={taRef} className={html?'code':''} placeholder={html?'HTML (or choose an HTML file above)':'Paste notes or syllabus text'} value={f.content} onChange={set('content')}/>}
    <p className="known">{html?'HTML content shows as it is laid out in the file. Scripts, styles, forms and outside frames are removed when you save, so the page takes the app\'s look in light and dark mode.':'Equations: $x^2$ inline. For a centred block, put $$ on its own line above and below the equation. Chemistry: $\\ce{CaCO3 + CO2 + H2O -> Ca(HCO3)2}$'}</p>{T('question_pattern','Question pattern','e.g. 2 marks: define · 13 marks: derive + numerical')}
    <label>Learning deadline</label><div className="qopt"><input type="datetime-local" aria-label="Learning deadline" value={f.due} onChange={set('due')}/>{f.due&&<button type="button" className="tool" onClick={()=>setF({...f,due:''})}>No deadline</button>}</div>
    <p className="known" style={{marginTop:4}}>{f.due?'Students should have learnt this topic by then. They can still open it afterwards.':'No deadline'}</p>
    <label className="chk"><input type="checkbox" checked={f.published!==false} onChange={e=>setF({...f,published:e.target.checked})}/> Published (students can see this topic)</label>
    {T('sample_content','Sample content','A sample question and answer')}{T('guideline','How an answer should be','Intro, labelled diagram, steps, units, conclusion')}
    <button className="btn" disabled={busy||!f.title.trim()} onClick={save}>{edit?'Save changes':'Save topic'}</button></div></>}
function UnitSheet({un,cid,courses,close,done,toast}){  // courses is given to admins only: moving a unit to another course is theirs to do
  const isNew=!un.id,[f,setF]=useState({name:un.name||'',course:cid}),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{await api(isNew?'/units':'/units/'+un.id,{method:isNew?'POST':'PUT',body:{name:f.name,course_id:+f.course}});toast(isNew?'Unit added':'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?'New unit':'Edit unit'}</h3>
    <label>Name</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} onKeyDown={e=>e.key==='Enter'&&f.name.trim()&&save()} placeholder="Unit 1: Basic concepts" autoFocus/>
    {!isNew&&courses&&<><label>Course</label><select value={f.course} onChange={e=>setF({...f,course:+e.target.value})}>{courses.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select></>}
    <button className="btn" disabled={busy||!f.name.trim()} onClick={save}>{isNew?'Add unit':'Save changes'}</button></Sheet>}

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
  const upload=async e=>{const fs=[...e.target.files];e.target.value='';for(const f of fs)if(tooBig(f))toast(`${f.name} is over ${MAX_FILE_MB} MB. Split it into smaller files.`);else await run('file',async()=>{const r=await fetch('/api'+base+'/files?name='+encodeURIComponent(f.name),{method:'POST',headers:{'Content-Type':'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');if(j.status==='reading')toast(f.name+' is scanned pages. Reading them now; you can stay or come back later.')},f.name.toLowerCase().endsWith('.pdf')?'':'Added '+f.name)}
  const match=m=>run(m,()=>api(base+'/match',{method:'POST',body:{method:m}}),'Matched to the syllabus. Check it below, then save.')
  const file=(i,tid)=>{setPick(null);return run('sec',()=>api(base+'/sections',{method:'PUT',body:{sections:v.sections.map((x,k)=>({from:x.from,to:x.to,topic_id:k===i?(tid?+tid:null):x.topic_id}))}}))}
  const read=async x=>{const k=x.from;if(open[k]!==undefined)return setOpen({...open,[k]:undefined});try{const r=await api(`${base}/preview?start=${x.from}&end=${x.to}`);setOpen({...open,[k]:r.content})}catch(e){toast(e.message)}}
  if(!v)return <><Bar title="Your material" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const names=new Map(v.syllabus.flatMap(u=>u.topics.map(x=>[x.id,x.title]))),filed=new Set(v.sections.map(x=>x.topic_id).filter(Boolean)),missing=v.syllabus.flatMap(u=>u.topics.filter(x=>!filed.has(x.id)).map(x=>x.title)),noAi=!v.ai_available||v.ai_left===0
  return <><Bar title="Your material" sub={name} back={back}/><div className="main">
    <p className="known" style={{marginTop:0}}>Your college sets the course, units and topics. Bring your own notes or book chapters and they are filed under the right topics, so you study the syllabus in your own words. Only you see them.</p>
    <h3>1. Your files</h3>
    {v.sources.length?v.sources.map((x,i)=><div className="row" key={i}><div>{x.name}<small role={x.status==='reading'?'status':undefined}>{srcLine(x)}</small></div><button className="ic sm" aria-label={'Remove '+x.name} disabled={!!busy} onClick={()=>run('drop',()=>api(base+'/sources/'+i,{method:'DELETE'}))}><X size={16}/></button></div>):<p className="known">No files yet. PDFs, Word (.docx) and text files work, up to {MAX_FILE_MB} MB each.{v.ocr_available?' Scanned PDFs are read too; that takes a few seconds a page.':' Scanned PDFs can\'t be read on this server yet.'}</p>}
    <div className="two"><button className="btn ghost" disabled={!!busy} onClick={()=>fileRef.current.click()}><Upload size={16}/> {busy==='file'?'Reading…':'Add a file'}</button><button className="btn ghost" disabled={!!busy} onClick={()=>setPaste({text:''})}>Paste text</button></div>
    <input ref={fileRef} type="file" hidden multiple accept=".pdf,.docx,.txt,.md" onChange={upload}/>
    {v.sources.length>0&&<><h3>2. File it under the syllabus</h3>
      {v.reading&&<p className="known" role="status">Your scanned pages are still being read. Matching starts once they are done.</p>}
      {v.ai_available&&<button className={'btn'+(noAi?' ghost':'')} disabled={!!busy||noAi||v.reading} onClick={()=>match('ai')}><Sparkles size={16}/> {busy==='ai'?'Matching…':'Match with AI'}</button>}
      <button className={'btn'+(noAi?'':' ghost')} disabled={!!busy||v.reading} onClick={()=>match('headings')}>{busy==='headings'?'Matching…':v.ai_available?'Match by headings (no AI)':'Match by headings'}</button>
      {noAi&&<p className="known">{v.ai_available?'No AI requests are left today. ':''}Matching by headings works best when your notes use the topic names as headings.</p>}</>}
    {v.sections.length>0&&<><h3>3. Check where each part goes</h3>
      <p className="known">Your notes cover {v.covered} of {v.topics} topics.{missing.length>0&&' Not covered yet: '+missing.slice(0,6).join(', ')+(missing.length>6?' and '+(missing.length-6)+' more':'')+'.'}</p>
      {v.sections.map((x,i)=><div className="qbox" key={x.from}>{x.heading?<b>{x.heading}</b>:<span style={{display:'block'}}>“{x.excerpt.slice(0,80)+(x.excerpt.length>80?'…':'')}”</span>}<small className="known" style={{display:'block'}}>Part {i+1} · {x.words} words</small>
        <div className="sfile">{x.topic_id?<span className="chip">{names.get(x.topic_id)||'Topic'}</span>:<span className="chip none">Left out</span>}<button className="tool" disabled={!!busy} aria-expanded={pick===i} onClick={()=>setPick(pick===i?null:i)}>{pick===i?'Cancel':x.topic_id?'Change':'File it'}</button></div>
        {pick===i&&<select aria-label={'Topic for part '+(i+1)} autoFocus value={x.topic_id||''} disabled={!!busy} onChange={e=>file(i,e.target.value)}><option value="">Not in the syllabus (left out)</option>{v.syllabus.map(u=><optgroup key={u.id} label={u.name}>{u.topics.map(tp=><option key={tp.id} value={tp.id}>{tp.title}</option>)}</optgroup>)}</select>}
        <button className="tool" onClick={()=>read(x)}>{open[x.from]!==undefined?'Hide':'Read it'}</button>{open[x.from]!==undefined&&<div className="prose"><Md>{open[x.from]}</Md></div>}</div>)}
      <button className="btn" disabled={!!busy||!filed.size} onClick={()=>run('save',()=>api(base+'/save',{method:'POST'}),'Saved. Open a topic to study your notes.')}>{v.saved_at?'Save again to my topics':'Save to my topics'}</button>
      {v.saved_at&&<p className="known">Last saved {when(v.saved_at)}. Saving again rebuilds your notes from this material; your progress and quiz results stay.</p>}</>}
    {v.sources.length>0&&<p style={{marginTop:28}}><button className="link" style={{color:"var(--bad)"}} disabled={!!busy} onClick={async()=>{if(await confirm({title:'Remove your material?',body:'The notes it made in this course are removed too. Your progress and quiz results stay.',ok:'Remove',danger:true}))run('del',()=>api(base,{method:'DELETE'}),'Your material was removed')}}>Remove my material from this course</button></p>}</div>
    {paste&&<Sheet close={()=>setPaste(null)}><h3>Paste text</h3><textarea aria-label="Text to add" value={paste.text} onChange={e=>setPaste({text:e.target.value})} placeholder="Paste your notes. Lines starting with # are headings."/>
      <button className="btn" disabled={!paste.text.trim()||!!busy} onClick={async()=>{await run('paste',()=>api(base+'/text',{method:'POST',body:{text:paste.text}}),'Added');setPaste(null)}}>Add</button></Sheet>}</>}

function Bookmarks({toast,role}){
  const [tree,setTree]=useState(null),[sem,setSem]=useState(null),[course,setCourse]=useState(null),[t,setT]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t])
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast} role={role}/>
  if(!tree)return <><Bar title="Bookmarks"/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const marks=u=>u.topics.filter(x=>x.bookmarked),cnt=c=>c.units.reduce((n,u)=>n+marks(u).length,0)
  const sems=tree.flatMap(p=>p.semesters.map(sm=>({...sm,prog:p.name,courses:sm.courses.filter(c=>cnt(c)>0)}))).filter(sm=>sm.courses.length)
    .sort((a,b)=>a.prog.localeCompare(b.prog)||(a.number??99)-(b.number??99)||a.id-b.id)
  const multi=new Set(sems.map(x=>x.prog)).size>1,total=sems.reduce((n,x)=>n+x.courses.reduce((m,c)=>m+cnt(c),0),0)
  const sm=sems.find(x=>x.id===sem)||sems[0],co=sm?.courses.find(x=>x.id===course)||sm?.courses[0]
  const drop=async id=>{try{await api(`/topics/${id}/bookmark`,{method:'DELETE'});setTree(unmarked(tree,id));toast('Bookmark removed')}catch(e){toast(e.message)}}
  return <><Bar title="Bookmarks" sub={total?total+(total===1?' topic saved':' topics saved'):'Nothing saved yet'}/><div className="main">
    {!sm&&<p className="known">Open any topic and tap the bookmark icon to save it here. It shows only the topics you saved, grouped by semester or year, course and unit.</p>}
    {sm&&<>
      <div className="chips" role="group" aria-label="Semester or year">{sems.map(x=><button key={x.id} className={'sbtn'+(x.id===sm.id?' on':'')} aria-pressed={x.id===sm.id} onClick={e=>{setSem(x.id);setCourse(null);tabTo(e)}}>
        <span className="lbl">{multi&&x.prog+' · '}{x.name}</span><em>{x.courses.reduce((n,c)=>n+cnt(c),0)}</em></button>)}</div>
      <div className="tabs scroll" role="tablist" aria-label="Course">{sm.courses.map(c=><button key={c.id} role="tab" aria-selected={c.id===co.id} className={c.id===co.id?'on':''} onClick={e=>{setCourse(c.id);tabTo(e)}}>
        <span className="lbl">{c.name}</span><em>{cnt(c)}</em></button>)}</div>
      {co.units.filter(u=>marks(u).length).map(u=><div key={u.id}><h3 className="sec">{u.name}</h3>
        {marks(u).map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={()=>setT(x.id)}><span className="dot" style={{background:COL[i%5]}}>{x.title[0]}</span><div><b>{x.title}</b></div><Mark s={x.status}/></button>
          <button className="ic sm on" aria-label={'Remove bookmark: '+x.title} onClick={()=>drop(x.id)}><Bookmark size={16} fill="currentColor"/></button></div>)}</div>)}
    </>}</div></>}

const sheets=[]  // open sheets, topmost last, so Escape closes only the one on top
// a pop-up for short questions; with page set, a form that takes over the content area like a page of its own, with a way back
function Sheet({close,children,page}){
  const box=useRef(null),cb=useRef(close);cb.current=close
  useEffect(()=>{const me={},was=document.activeElement;sheets.push(me)
    const k=e=>{if(e.key==='Escape'&&sheets[sheets.length-1]===me)cb.current()}
    addEventListener('keydown',k);if(box.current&&!box.current.contains(document.activeElement))box.current.focus()
    return()=>{sheets.splice(sheets.indexOf(me),1);removeEventListener('keydown',k);if(was&&was.isConnected)was.focus?.()}},[])
  if(page)return <div className="scrim full"><div className="sheet page" ref={box} tabIndex={-1} role="dialog" aria-modal="true"><button className="link" onClick={()=>cb.current()}><ChevronLeft size={16}/> Back</button>{children}</div></div>
  return <div className="scrim" onClick={()=>cb.current()}><div className="sheet" ref={box} tabIndex={-1} role="dialog" aria-modal="true" onClick={e=>e.stopPropagation()}>{children}</div></div>}
const Confirm=({o,answer})=><Sheet close={()=>answer(false)}><h3>{o.title}</h3>{o.body&&<p className="known">{o.body}</p>}
  <button className={'btn'+(o.danger?' danger':'')} onClick={()=>answer(true)}>{o.ok||'Confirm'}</button><button className="btn ghost" onClick={()=>answer(false)}>Cancel</button></Sheet>
const useConfirm=()=>useContext(Ctx).confirm
const Toast=({msg})=>msg?<div className="toast" role="status">{msg}</div>:null
const Skeleton=({rows=3})=><div aria-busy="true" aria-label="Loading">{Array.from({length:rows},(_,i)=><div className="sk" key={i}/>)}</div>
// numbered pages under a list: Previous, page numbers (with … in long lists), Next, and which rows are shown
const PAGE=25
const pageList=(n,at)=>n<=7?[...Array(n).keys()]:[...new Set([0,1,at-1,at,at+1,n-2,n-1].filter(i=>i>=0&&i<n))].sort((a,b)=>a-b).flatMap((i,j,a)=>j&&i-a[j-1]>1?['…'+i,i]:[i])
function Pager({page,total,onPage,size=PAGE}){
  const n=Math.ceil(total/size);if(n<=1)return null
  const go=i=>{onPage(i);scrollTo({top:0})}
  return <nav className="pgr" aria-label="Pages"><small>{page*size+1}–{Math.min(total,(page+1)*size)} of {total}</small>
    <span className="pgb"><button className="tool" disabled={page===0} onClick={()=>go(page-1)} aria-label="Previous page"><ChevronLeft size={16}/></button>
      {pageList(n,page).map(i=>typeof i==='string'?<span key={i} className="gap">…</span>:<button key={i} className={'tool'+(i===page?' on':'')} aria-current={i===page?'page':undefined} onClick={()=>go(i)}>{i+1}</button>)}
      <button className="tool" disabled={page>=n-1} onClick={()=>go(page+1)} aria-label="Next page"><ChevronRight size={16}/></button></span></nav>}
// the list's rows for the current page; a filter change goes back to page 1, and a page left empty (say after a delete) steps back one
function usePaged(url,deps,toast){
  const [page,setPage]=useState(0),[items,setItems]=useState([]),[total,setTotal]=useState(0),[n,setN]=useState(0)
  useEffect(()=>{setPage(0)},deps)
  useEffect(()=>{const t=setTimeout(()=>api(url(page*PAGE)).then(r=>{if(!r.items.length&&page>0)setPage(page-1);else{setItems(r.items);setTotal(r.total)}}).catch(e=>toast(e.message)),250);return()=>clearTimeout(t)},[...deps,page,n])
  return {items,total,page,setPage,reload:()=>setN(x=>x+1)}}
const ShowMore=({left,onClick,busy})=><button className="btn ghost" disabled={busy} onClick={onClick}>Show more ({left} left)</button>
const Tabs=({items,value,onChange,scroll,label})=><div className={'tabs'+(scroll?' scroll':'')} role="tablist" aria-label={label}>{items.map(([k,l])=><button key={k} role="tab" aria-selected={value===k} className={value===k?'on':''} onClick={()=>onChange(k)}>{l}</button>)}</div>
const useRun=(toast,load)=>async(fn,m)=>{try{await fn();toast(m);load&&load()}catch(e){toast(e.message)}}

const download=(name,text)=>{const l=document.createElement('a');l.href=URL.createObjectURL(new Blob([text],{type:'text/csv'}));l.download=name;l.click()}
const USER_TEMPLATE=`name,email,password,role,program,semester
Asha Kumar,asha@example.com,,student,B.E. Mechanical Engineering,3
Ravi S,ravi@example.com,Welcome#2026,student,B.E. Mechanical Engineering,1
`
const TERM_MAX={Grade:12},maxOf=term=>TERM_MAX[term]||8,upTo=n=>Array.from({length:n},(_,i)=>i+1)
const termOf=(progs,id)=>progs.find(p=>String(p.id)===String(id))?.term||'Semester',semsOf=(progs,id)=>upTo(id?maxOf(termOf(progs,id)):Math.max(8,...progs.map(p=>maxOf(p.term))))
const PATTERN={semester:['Semesters','Semester',8,'Semester pattern, for example B.E., B.Tech or M.E. Students move up one semester at a time.'],
  year:['Years','Year',4,'Annual pattern, for example M.B.B.S, B.Sc or law degrees, up to 8 years. For a school, choose School grades. Students move up one year at a time.'],
  grade:['School grades','Grade',12,'School pattern, Grade 1 to Grade 12. Students move up one grade at a time.']}

const BULK_TEXT={disable:['Disable these accounts?','They can no longer sign in. Their progress and quiz results are kept, and you can enable them again.','Disable'],
  enable:['Enable these accounts?','They can sign in again.','Enable'],reset_passwords:['Reset these passwords?','Each person gets a new one-time password and must choose their own at next sign-in. Anyone signed in is signed out. You download the list once; it is not shown again.','Reset passwords']}
function BulkSheet({act,ids,progs,toast,close,done}){
  const [p,setP]=useState(''),[s,setS]=useState(''),[busy,setBusy]=useState(false)
  if(act.kind==='result'){const r=act.r,cell=v=>'"'+String(v).replace(/"/g,'""')+'"'
    return <Sheet close={close}><h3>{pl(r.changed,'account')} updated</h3>
      {r.courses_needing_owner>0&&<p className="known">{pl(r.courses_needing_owner,'course')} now {r.courses_needing_owner===1?'has':'have'} no active owner. Assign new owners under Programs.</p>}
      {r.skipped_count>0&&<div className="qbox"><b>{r.skipped_count} skipped</b>{r.skipped.slice(0,10).map(x=><p className="known" style={{margin:'4px 0'}} key={x.id}>{x.name}: {x.reason}</p>)}{r.skipped_count>10&&<p className="known">…and {r.skipped_count-10} more.</p>}</div>}
      {r.credentials&&<button className="btn" onClick={()=>download('new-passwords.csv','name,email,password\n'+r.credentials.map(c=>[c.name,c.email,c.password].map(cell).join(',')).join('\n')+'\n')}>Download the new passwords</button>}
      <button className="btn ghost" onClick={close}>Close</button></Sheet>}
  const run=async()=>{setBusy(true);try{done(await api('/admin/users/bulk',{method:'POST',body:{ids,action:act.kind,...(act.kind==='set_placement'?{program_id:+p,semester:s?+s:null}:{})}}))}catch(e){toast(e.message);setBusy(false)}}
  if(act.kind==='set_placement')return <Sheet close={close}><h3>Move {pl(ids.length,'user')}</h3><p className="known">Sets the program and semester, year or grade of the selected students. Faculty and admins in the selection are skipped.</p>
    <label htmlFor="bp">Program</label><select id="bp" value={p} onChange={e=>{const id=e.target.value;setP(id);if(+s>semsOf(progs,id).length)setS('')}}><option value="">Choose a program</option>{progs.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    <label htmlFor="bs">{termOf(progs,p)}</label><select id="bs" value={s} onChange={e=>setS(e.target.value)}><option value="">Not set</option>{semsOf(progs,p).map(n=><option key={n} value={n}>{termOf(progs,p)} {n}</option>)}</select>
    <button className="btn" disabled={busy||!p} onClick={run}>{busy?'Working…':'Move'}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>
  const [t,d,l]=BULK_TEXT[act.kind]
  return <Sheet close={close}><h3>{t.replace('these',ids.length===1?'this':'these')}</h3><p className="known">{pl(ids.length,'account')} selected. {d}</p>
    <button className={'btn'+(act.kind==='disable'?' danger':'')} disabled={busy} onClick={run}>{busy?'Working…':l}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}
function Users({toast,me}){
  const [q,setQ]=useState(''),[prog,setProg]=useState(''),[sem,setSem]=useState(''),[order,setOrder]=useState('role'),[progs,setProgs]=useState([])
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef(),[selMode,setSelMode]=useState(false),[sel,setSel]=useState([]),[act,setAct]=useState(null)
  const {items,total,page,setPage,reload:load}=usePaged(offset=>`/admin/users?q=${encodeURIComponent(q)}&order=${order}&limit=${PAGE}&offset=${offset}`+(prog?'&program_id='+prog:'')+(sem?'&semester='+sem:''),[q,prog,sem,order],toast)
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name,term:p.term})))).catch(()=>{})},[])
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/users/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/users/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const cell=v=>'"'+String(v).replace(/"/g,'""')+'"',r=bulk?.res,filtered=q||prog||sem,lab=prog?termOf(progs,prog):progs.every(x=>x.term==='Semester')?'Semester':progs.length&&progs.every(x=>x.term==='Grade')?'Grade':'Term'
  if(view)return <UserDetail id={view} me={me} progs={progs} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title="Users" sub={filtered?matches(total):pl(total,'account')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label="Search users" placeholder="Search name, email, ID, program, semester, year or grade" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters">
      <select aria-label="Filter by program" value={prog} onChange={e=>{const id=e.target.value;setProg(id);if(+sem>semsOf(progs,id).length)setSem('')}}><option value="">All programs</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select aria-label="Filter by semester, year or grade" value={sem} onChange={e=>setSem(e.target.value)}><option value="">{lab==='Term'?'All terms':'All '+lab.toLowerCase()+'s'}</option>{semsOf(progs,prog).map(n=><option key={n} value={n}>{lab} {n}</option>)}</select>
      <select aria-label="Sort by" value={order} onChange={e=>setOrder(e.target.value)}><option value="role">Sort: role, then name</option><option value="name">Sort: name</option><option value="program">Sort: program</option><option value="semester">Sort: {lab.toLowerCase()}</option><option value="newest">Sort: newest first</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>New user</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>Bulk upload</button></div>
    <button className="btn ghost" style={{marginTop:10}} aria-pressed={selMode} onClick={()=>{setSelMode(!selMode);setSel([])}}>{selMode?'Done selecting':'Select several users'}</button>
    {selMode&&items.length>0&&<div className="selbar"><button className="tool" onClick={()=>setSel(items.map(u=>u.id))}>Select all {items.length} shown</button>{sel.length>0&&<button className="tool" onClick={()=>setSel([])}>Clear</button>}</div>}
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead" aria-hidden="true"><span>Name</span><span>Program</span><span>{lab==='Semester'?'Sem':lab}</span></div>}
    {items.map(u=><button key={u.id} className={'utr'+(selMode?' sel':'')+(sel.includes(u.id)?' on':'')} onClick={()=>selMode?setSel(sel.includes(u.id)?sel.filter(i=>i!==u.id):[...sel,u.id]):setView(u.id)} aria-label={(selMode?(sel.includes(u.id)?'Deselect ':'Select '):'Open ')+u.name} aria-pressed={selMode?sel.includes(u.id):undefined}>
      <span className="nm">{selMode&&<span className="tick" aria-hidden="true">{sel.includes(u.id)&&<Check size={14}/>}</span>}<span className="dot" style={{background:COL[u.id%5]}}>{(u.name||'?')[0]}</span><span className="tx"><b>{u.name}</b>{(u.role!=='student'||!u.active||u.self_registered)&&<span className="tags">{u.role!=='student'&&<span className="pill">{u.role==='admin'?'Admin':'Faculty'}</span>}{u.self_registered&&<span className="pill">Self-registered</span>}{!u.active&&<span className="pill off">Disabled</span>}</span>}</span></span>
      <span className="pg">{u.program||'—'}</span><span className="sn">{u.semester||'—'}</span></button>)}
    {!items.length&&<p className="known">{filtered?'No one matches that search.':'No users yet.'}</p>}
    <Pager page={page} total={total} onPage={setPage}/>
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {selMode&&sel.length>0&&<div className="actbar" role="toolbar" aria-label="Actions for selected users"><b>{sel.length} selected</b>
      <button className="tool" onClick={()=>setAct({kind:'set_placement'})}>Move…</button><button className="tool" onClick={()=>setAct({kind:'disable'})}>Disable</button><button className="tool" onClick={()=>setAct({kind:'enable'})}>Enable</button><button className="tool" onClick={()=>setAct({kind:'reset_passwords'})}>Reset passwords</button></div>}
    {act&&<BulkSheet act={act} ids={sel} progs={progs} toast={toast} close={()=>setAct(null)} done={r=>{setAct({kind:'result',r});setSel([]);load()}}/>}
    {ed&&<UserSheet u={ed} me={me} progs={progs} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet page close={()=>setBulk(null)}>
      {bulk.stage==='pick'&&<><h3>Bulk upload users</h3><p className="known">One row per person with the columns name, email, password, role, program and semester (the year number for annual programs such as M.B.B.S). Leave the password blank to generate one. Role is student or admin and defaults to student. Program must match a name on the Programs tab, and semester is a number from 1 to 8. Emails that already exist are updated, and blank program or semester cells leave the current value alone.</p>
        <button className="btn ghost" onClick={()=>download('users-template.csv',USER_TEMPLATE)}>Download template</button><button className="btn" onClick={()=>fileRef.current.click()}>Choose CSV file</button></>}
      {bulk.stage==='preview'&&<><h3>Ready to upload</h3><p className="known">{r.valid_rows} of {r.rows} rows are valid: {r.created} new, {r.updated} updated.{r.generated>0&&` ${r.generated} passwords will be generated.`}</p>
        {r.error_count>0&&<div className="prose" style={{maxHeight:'28vh',overflow:'auto',fontSize:14}}><b>{r.error_count} rows will be skipped</b>{r.errors.map(e=><div key={e.row}>Row {e.row}: {e.error}</div>)}</div>}
        <button className="btn" disabled={!r.valid_rows} onClick={commit}>Upload {r.valid_rows} rows</button><button className="btn ghost" onClick={()=>setBulk(null)}>Cancel</button></>}
      {bulk.stage==='done'&&<><h3>Upload complete</h3><p className="known">{r.created} users created, {r.updated} updated.{r.credentials.length>0&&' Download the generated passwords now. They are not shown again.'}</p>
        {r.credentials.length>0&&<button className="btn" onClick={()=>download('new-user-passwords.csv','name,email,password\n'+r.credentials.map(c=>[c.name,c.email,c.password].map(cell).join(',')).join('\n')+'\n')}>Download passwords</button>}
        <button className="btn ghost" onClick={()=>setBulk(null)}>Close</button></>}
    </Sheet>}</>}

function UserDetail({id,me,progs,back,toast}){
  const confirm=useConfirm()
  const [u,setU]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[pw,setPw]=useState(null),[busy,setBusy]=useState(false),[asg,setAsg]=useState(null),[ctree,setCtree]=useState([])
  const load=()=>api('/admin/users/'+id).then(setU).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id]);useEffect(()=>{if(u?.role==='faculty')api('/tree').then(setCtree)},[u?.role])
  if(!u)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const reset=async()=>{setBusy(true);try{const r=await api(`/admin/users/${u.id}/reset-password`,{method:'POST'});setAsk(false);setPw(r.password)}catch(e){toast(e.message)}setBusy(false)}
  const remove=async()=>{if(!await confirm({title:`Delete ${u.name}?`,body:`This permanently removes the account and ${u.role==='student'?'their progress, test results and bookmarks':'their own records'}. Content they created stays.${u.role==='faculty'?' Courses they own will have no owner.':''} To keep their history, edit the user and set Status to Disabled instead.`,ok:'Delete user',danger:true}))return
    try{await api('/admin/users/'+u.id,{method:'DELETE'});toast(u.name+' deleted');back()}catch(e){toast(e.message)}}
  const copy=async()=>{try{await navigator.clipboard.writeText(pw);toast('Copied')}catch{toast('Press and hold the password to copy it')}}
  const row=(v,l)=><div className="row"><div>{v}<small>{l}</small></div></div>
  const allCourses=ctree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared).map(c=>({id:c.id,owner_id:c.owner_id,owner:c.owner,label:`${p.name} › ${s.name} › ${c.name}`}))))
  const saveAsg=async()=>{try{await api(`/admin/users/${u.id}/courses`,{method:'PUT',body:{course_ids:asg}});toast('Courses updated');setAsg(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={u.name} sub={u.email} back={back}/><div className="main">
    <div className="stats"><div className="stat"><b>{u.topics_read}</b>Topics read</div><div className="stat"><b>{u.reads}</b>Total reads</div></div>
    <h3 className="sec">Profile</h3>
    {row({admin:'Admin',faculty:'Faculty'}[u.role]||'Student','Role')}{row(u.active?'Active':'Disabled','Status')}{row(u.program||'Not set','Program')}{row(u.semester||'Not set',termOf(progs,u.program_id))}{u.self_registered&&<>{row(u.institution||'—','Institution')}{row(u.id_number||'—','ID number')}{row(u.phone||'—','Phone')}{row(u.own_ai_key?'Has added their own key':'No key yet · AI is off for them','AI (self-registered, uses their own key)')}</>}{row(day(u.last_active),'Last active')}
    {u.role==='faculty'&&<><h3 className="sec">Courses they own</h3>{(u.course_ids||[]).length?allCourses.filter(c=>u.course_ids.includes(c.id)).map(c=><div className="row" key={c.id}><div>{c.label}</div></div>):<p className="known">None yet. They can read published content but edit nothing until they own a course.</p>}<button className="btn ghost" onClick={()=>setAsg([...(u.course_ids||[])])}>Assign courses</button></>}
    <h3 className="sec">Recently read</h3>
    {u.recent.length?u.recent.map((x,i)=><div className="row" key={i}><div>{x.title}<small>{x.reads} reads, last {day(x.last_read)}</small></div></div>):<p className="known">No reading activity yet.</p>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>Edit</button><button className="btn" onClick={()=>setAsk(true)}>Reset password</button></div>
    {u.id!==me.id&&<button className="btn danger" onClick={remove}>Delete user</button>}</div>
    {ed&&<UserSheet u={u} me={me} progs={progs} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>Reset password?</h3><p className="known">This gives {u.name} a new password and replaces the old one straight away. You will see the new password once.</p>
      <button className="btn danger" disabled={busy} onClick={reset}>Reset password</button><button className="btn ghost" onClick={()=>setAsk(false)}>Cancel</button></Sheet>}
    {pw&&<Sheet close={()=>setPw(null)}><h3>New password</h3><p className="known">Share this with {u.name} now. It is not shown again.</p><div className="pw">{pw}</div>
      <button className="btn" onClick={copy}>Copy password</button><button className="btn ghost" onClick={()=>setPw(null)}>Done</button></Sheet>}
    {asg&&<Sheet page close={()=>setAsg(null)}><h3>Courses {u.name} owns</h3><p className="known">The owner adds and edits the units, topics and quizzes of a course. Each course has one owner, so ticking a course another person owns moves it to {u.name}.</p>{allCourses.map(c=><label key={c.id} className="chk"><input type="checkbox" checked={asg.includes(c.id)} onChange={e=>setAsg(e.target.checked?[...asg,c.id]:asg.filter(i=>i!==c.id))}/> {c.label}{c.owner_id&&c.owner_id!==u.id?` (now ${c.owner})`:''}</label>)}<button className="btn" onClick={saveAsg}>Save</button><button className="btn ghost" onClick={()=>setAsg(null)}>Cancel</button></Sheet>}</>}

function UserSheet({u,me,progs,close,done,toast}){
  const isNew=!u.id,self=u.id===me.id,[busy,setBusy]=useState(false)
  const [f,setF]=useState({name:u.name||'',email:u.email||'',role:u.role||'student',active:u.active??true,password:'',program_id:u.program_id||'',semester:u.semester||''}),set=k=>e=>setF({...f,[k]:e.target.value})
  const save=async()=>{setBusy(true);try{
    const enrol={program_id:f.program_id?+f.program_id:null,semester:f.semester?+f.semester:null}
    if(isNew)await api('/admin/users',{method:'POST',body:{...f,...enrol}})
    const r=isNew?null:await api('/admin/users/'+u.id,{method:'PATCH',body:{name:f.name,email:f.email,...enrol,...(self?{}:{role:f.role,active:f.active})}})
    toast(isNew?'User added':r.courses_needing_owner?`Saved. ${r.courses_needing_owner} course(s) they own need a new owner.`:'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?'New user':'Edit user'}</h3>
    <label>Name</label><input value={f.name} onChange={set('name')}/><label>Email</label><input type="email" value={f.email} onChange={set('email')}/>
    <label>Program</label><select value={f.program_id} onChange={e=>{const id=e.target.value;setF({...f,program_id:id,semester:+f.semester>semsOf(progs,id).length?'':f.semester})}}><option value="">Not set</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <label>{termOf(progs,f.program_id)}</label><select value={f.semester} onChange={set('semester')}><option value="">Not set</option>{semsOf(progs,f.program_id).map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>Role</label><select disabled={self} value={f.role} onChange={set('role')}><option value="student">Student</option><option value="faculty">Faculty</option><option value="admin">Admin</option></select>
    <label>Status</label><select disabled={self} value={f.active?'1':'0'} onChange={e=>setF({...f,active:e.target.value==='1'})}><option value="1">Active</option><option value="0">Disabled</option></select>
    {isNew?<><label>Password (8+ characters)</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/></>
      :<p className="known" style={{marginTop:14}}>To give this person a new password, use Reset password on their page.</p>}
    {self&&<p className="known">You can't change your own role or status.</p>}
    <button className="btn" disabled={busy} onClick={save}>{isNew?'Add user':'Save changes'}</button></Sheet>}

// every course for admins: search, a program filter, sorting and pages; add, edit or delete here, or open a course for its units and topics
function AdminCourses({toast,onOpen}){
  const confirm=useConfirm(),[q,setQ]=useState(''),[prog,setProg]=useState(''),[order,setOrder]=useState('name'),[status,setStatus]=useState('active'),[tree,setTree]=useState([]),[ed,setEd]=useState(null)
  useEffect(()=>{api('/tree').then(setTree).catch(()=>{})},[])
  const {items,total,page,setPage,reload}=usePaged(offset=>`/admin/courses?q=${encodeURIComponent(q)}&order=${order}&status=${status}&limit=${PAGE}&offset=${offset}`+(prog?'&program_id='+prog:''),[q,prog,order,status],toast)
  const sems=tree.flatMap(p=>p.semesters.map(x=>({id:x.id,label:p.name+' › '+x.name}))),done=()=>{setEd(null);reload()}
  const del=async c=>{if(!await confirm({title:`Delete “${c.name}”?`,body:`This permanently deletes its ${pl(c.units,'unit')}, ${pl(c.topics,'topic')} and quizzes, with students' progress in them. To hide it instead, archive it from the course page.`,ok:'Delete course',danger:true}))return
    try{await api('/courses/'+c.id,{method:'DELETE'});toast('Course deleted');reload()}catch(e){toast(e.message)}}
  return <><Bar title="Courses" sub={q||prog?matches(total):pl(total,'course')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label="Search courses" placeholder="Search course, program, semester or owner" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label="Filter by program" value={prog} onChange={e=>setProg(e.target.value)}><option value="">All programs</option>{tree.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select aria-label="Sort by" value={order} onChange={e=>setOrder(e.target.value)}><option value="name">Sort: name A to Z</option><option value="name_desc">Sort: name Z to A</option><option value="program">Sort: program, then term</option><option value="topics">Sort: most topics</option><option value="newest">Sort: newest first</option></select>
      <select aria-label="Show" value={status} onChange={e=>setStatus(e.target.value)}><option value="active">Active courses</option><option value="archived">Archived courses</option><option value="all">All courses</option></select></div>
    <button className="btn" onClick={()=>setEd({})}>New course</button>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead c" aria-hidden="true"><span>Course</span><span>Program › term</span><span>Topics</span><span/></div>}
    {items.map(c=><div key={c.id} className="utr c"><button className="nm" onClick={()=>onOpen([c.program_id,c.semester_id,c.id].filter(x=>x!=null))} aria-label={'Open '+c.name}><span className="dot" style={{background:COL[c.id%5]}}>{(c.name||'?')[0]}</span><span className="tx"><b>{c.name}{c.archived&&<span className="pill off sm">Archived</span>}</b><small className="sub">{c.owner_problem||'Owner: '+c.owner}</small></span></button>
      <span className="pg">{[c.program,c.semester].filter(Boolean).join(' › ')||'—'}</span><span className="sn">{c.topics}</span>
      <span className="rowacts"><button className="ic sm" aria-label={'Edit '+c.name} title="Edit" onClick={()=>setEd(c)}><Pencil size={17}/></button><button className="ic sm" aria-label={'Delete '+c.name} title="Delete" onClick={()=>del(c)}><Trash2 size={17}/></button></span></div>)}
    {!items.length&&<p className="known">{q||prog?'No course matches that search.':status==='archived'?'No archived courses.':'No courses yet. Add one, or bulk upload a CSV under Programs.'}</p>}
    <Pager page={page} total={total} onPage={setPage}/></div>
    {ed&&(ed.id?<CourseSheet c={{id:ed.id,name:ed.name,owner_id:ed.owner_id,owner:ed.owner}} pid={ed.program_id} sid={ed.semester_id} sems={sems} term={ed.term} toast={toast} close={()=>setEd(null)} done={done}/>
      :<NewCourseSheet tree={tree} toast={toast} close={()=>setEd(null)} done={done}/>)}</>}
function NewCourseSheet({tree,toast,close,done}){  // a course is made inside a program's semester or year: pick both, then name it and, optionally, its owner
  const faculty=useFaculty(true),[f,setF]=useState({pid:tree.length===1?String(tree[0].id):'',sid:'',name:'',owner:''}),[busy,setBusy]=useState(false)
  const p=tree.find(x=>String(x.id)===f.pid),sems=p?.semesters||[],term=p?.term||'Semester'
  const save=async()=>{setBusy(true);try{await api(`/programs/${f.pid}/semesters/${f.sid}/courses`,{method:'POST',body:{name:f.name,...(f.owner?{faculty_owner_id:+f.owner}:{})}});toast('Course added');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>New course</h3>
    <label htmlFor="ncp">Program</label><select id="ncp" value={f.pid} onChange={e=>setF({...f,pid:e.target.value,sid:''})}><option value="">{tree.length?'Choose a program':'Add a program first'}</option>{tree.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    <label htmlFor="ncs">{term}</label><select id="ncs" value={f.sid} disabled={!p} onChange={e=>setF({...f,sid:e.target.value})}><option value="">Choose a {term.toLowerCase()}</option>{sems.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    {p&&!sems.length&&<p className="known">{p.name} has no {term.toLowerCase()} yet. Add one under Programs first.</p>}
    <label htmlFor="ncn">Name</label><input id="ncn" value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder="Thermodynamics"/>
    <label htmlFor="nco">Owner (faculty)</label><select id="nco" value={f.owner} onChange={e=>setF({...f,owner:e.target.value})}><option value="">Not assigned</option>{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    <button className="btn" disabled={busy||!f.sid||!f.name.trim()} onClick={save}>Add course</button></Sheet>}
function Programs({toast,onOpen}){
  const [q,setQ]=useState(''),[order,setOrder]=useState('name'),[status,setStatus]=useState('active')
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef()
  const {items,total,page,setPage,reload:load}=usePaged(offset=>`/admin/programs?q=${encodeURIComponent(q)}&order=${order}&status=${status}&limit=${PAGE}&offset=${offset}`,[q,order,status],toast)
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const r=bulk?.res,made=r&&Object.entries(r.created).filter(([,v])=>v).map(([k,v])=>v+' '+k).join(', ')||'nothing new'
  if(view)return <ProgramDetail id={view} onOpen={onOpen} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title="Programs" sub={q?matches(total):pl(total,'program')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label="Search programs" placeholder="Search program, semester, year or course" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label="Sort by" value={order} onChange={e=>setOrder(e.target.value)}><option value="name">Sort: name</option><option value="students">Sort: most students</option><option value="newest">Sort: newest first</option></select><select aria-label="Show" value={status} onChange={e=>setStatus(e.target.value)}><option value="active">Active programs</option><option value="archived">Archived programs</option><option value="all">All programs</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>New program</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>Bulk upload</button></div>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead p" aria-hidden="true"><span>Program</span><span>Courses</span><span>Students</span></div>}
    {items.map(x=><button key={x.id} className="utr p" onClick={()=>setView(x.id)} aria-label={'Open '+x.name}>
      <span className="nm"><span className="dot" style={{background:COL[x.id%5]}}>{(x.name||'?')[0]}</span><span className="tx"><b>{x.name}{x.archived&&<span className="pill off sm">Archived</span>}</b><small className="sub">{pl(x.semesters,x.term.toLowerCase())}, {x.topics} topics</small></span></span>
      <span className="sn">{x.courses}</span><span className="sn">{x.students}</span></button>)}
    {!items.length&&<p className="known">{q?'No program matches that search.':status==='archived'?'No archived programs.':'No programs yet. Add one or bulk upload a CSV.'}</p>}
    <Pager page={page} total={total} onPage={setPage}/>
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {ed&&<ProgramSheet p={ed} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet page close={()=>setBulk(null)}>
      {bulk.stage==='pick'&&<><h3>Bulk upload content</h3><p className="known">One row per topic, with the columns program, semester, course, unit and topic, plus optional content, question_pattern, sample_content and guideline. Blank program, semester, course or unit cells repeat the row above. Existing names are reused and existing topics are updated. Programs that don't exist yet are created.</p>
        <button className="btn ghost" onClick={()=>download('template.csv',TEMPLATE)}>Download template</button><button className="btn" onClick={()=>fileRef.current.click()}>Choose CSV file</button></>}
      {bulk.stage==='preview'&&<><h3>Ready to upload</h3><p className="known">{r.valid_rows} of {r.rows} rows are valid. New: {made}. Topics updated: {r.updated_topics}.</p>
        {r.error_count>0&&<div className="prose" style={{maxHeight:'28vh',overflow:'auto',fontSize:14}}><b>{r.error_count} rows will be skipped</b>{r.errors.map(e=><div key={e.row}>Row {e.row}: {e.error}</div>)}</div>}
        <button className="btn" disabled={!r.valid_rows} onClick={commit}>Upload {r.valid_rows} rows</button><button className="btn ghost" onClick={()=>setBulk(null)}>Cancel</button></>}
      {bulk.stage==='done'&&<><h3>Upload complete</h3><p className="known">Created {made}. {r.updated_topics} topics updated.{r.error_count>0&&` ${r.error_count} rows were skipped.`}</p>
        <button className="btn ghost" onClick={()=>setBulk(null)}>Close</button></>}
    </Sheet>}</>}

function RolloverSheet({p,close,done,toast}){
  const [fin,setFin]=useState('keep'),[r,setR]=useState(null),[busy,setBusy]=useState(false)
  const url=`/admin/programs/${p.id}/rollover`
  useEffect(()=>{setR(null);api(url,{method:'POST',body:{dry_run:true,finishing:fin}}).then(setR).catch(e=>{toast(e.message);close()})},[fin]) 
  const go=async()=>{setBusy(true);try{const x=await api(url,{method:'POST',body:{dry_run:false,finishing:fin}});toast(`${x.moved} students moved up`+(fin==='deactivate'&&x.finishing?`, ${x.finishing} accounts switched off`:''));done()}catch(e){toast(e.message);setBusy(false)}}
  return <Sheet page close={close}><h3>Start a new term</h3><p className="known">Moves every active student of {p.name} up one {p.term?.toLowerCase()||'semester'}. Do this once, when the new term begins.</p>
    {!r?<div className="sk"/>:<div className="qbox" style={{marginTop:0}}>
      <div className="row"><div>{pl(r.moved,'student')}<small>{r.moved===1?'moves':'move'} up one {r.term.toLowerCase()}</small></div></div>
      <div className="row"><div>{pl(r.finishing,'student')}<small>{r.finishing===1?'is':'are'} in the last {r.term.toLowerCase()} ({r.term} {r.last_semester}){r.finishing_names.length?': '+r.finishing_names.join(', ')+(r.finishing>r.finishing_names.length?'…':''):''}</small></div></div>
      {r.unplaced>0&&<div className="row"><div>{pl(r.unplaced,'student')}<small>{r.unplaced===1?'has':'have'} no {r.term.toLowerCase()} set and are left alone: {r.unplaced_names.join(', ')}</small></div></div>}</div>}
    <label htmlFor="fin">Students finishing the program</label><select id="fin" value={fin} onChange={e=>setFin(e.target.value)}><option value="keep">Leave them as they are</option><option value="deactivate">Switch their accounts off</option></select>
    <button className="btn" disabled={busy||!r||(!r.moved&&!(fin==='deactivate'&&r.finishing))} onClick={go}>{busy?'Working…':'Apply'}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}
function ProgramDetail({id,back,onOpen,toast}){
  const [p,setP]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[busy,setBusy]=useState(false),[addSem,setAddSem]=useState(false),[term,setTerm]=useState(false),[arch,setArch]=useState(null)
  const load=()=>api('/admin/programs/'+id).then(setP).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id])
  if(!p)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const del=async()=>{setBusy(true);try{await api('/programs/'+p.id,{method:'DELETE'});toast('Program deleted');back()}catch(e){toast(e.message);setBusy(false)}}
  const row=(v,l,k)=><div className="row" key={k}><div>{v}<small>{l}</small></div></div>
  return <><Bar title={p.name} sub={pl(p.semesters,p.term.toLowerCase())+(p.pattern==='year'?' · annual':p.pattern==='grade'?' · school':'')+(p.archived?' · archived':'')} back={back}/><div className="main">
    {p.archived&&<p className="known" style={{marginTop:0}}>This program is archived. Students see its courses as unavailable right now. Restore it to bring everything back.</p>}
    <button className="btn ghost lead" onClick={()=>setArch({kind:'programs',id:p.id,name:p.name,on:!p.archived})}>{p.archived?'Restore program':'Archive program'}</button>
    <div className="stats">{[['semesters',p.term+'s'],['courses','Courses'],['topics','Topics'],['students','Students']].map(([k,l])=><div className="stat" key={k}><b>{p[k]}</b>{l}</div>)}</div>
    <h3 className="sec">{p.term}s</h3>
    {p.semester_list.length?p.semester_list.map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={()=>onOpen([p.id,x.id])}><span className="dot" style={{background:COL[i%5]}}>{x.number||'?'}</span><div><b>{x.name}<ArchPill x={x}/></b><span>{(x.number?'':'No '+p.term.toLowerCase()+' number set · ')+x.courses+' courses, '+x.topics+' topics'}</span></div></button>{!p.archived&&<button className="ic sm" aria-label={(x.archived_self?'Restore ':'Archive ')+x.name} onClick={()=>setArch({kind:'semesters',id:x.id,name:x.name,on:!x.archived_self})}>{x.archived_self?<ArchiveRestore size={16}/>:<Archive size={16}/>}</button>}</div>):<p className="known">No {p.term.toLowerCase()}s yet.</p>}
    <button className="btn ghost" onClick={()=>setAddSem(true)}>Add {p.term.toLowerCase()}</button>
    <h3 className="sec">Students</h3>
    {p.student_list.length?p.student_list.map(u=>row(u.name,(u.semester?p.term+' '+u.semester:p.term+' not set')+(u.active?'':', disabled'),u.id)):<p className="known">No students are enrolled yet. Set a program on a user's page.</p>}
    {p.students>p.student_list.length&&<p className="known">Showing {p.student_list.length} of {p.students}. Use Users to see everyone.</p>}
    {p.students>0&&<button className="btn ghost" onClick={()=>setTerm(true)}>Start a new term (move students up)</button>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>Edit</button><button className="btn danger" onClick={()=>setAsk(true)}>Delete</button></div>
    <button className="btn ghost" onClick={()=>onOpen([p.id])}>Open {p.term.toLowerCase()}s and courses</button></div>
    {term&&<RolloverSheet p={p} toast={toast} close={()=>setTerm(false)} done={()=>{setTerm(false);load()}}/>}
    {ed&&<ProgramSheet p={p} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {arch&&<ArchiveSheet a={arch} toast={toast} close={()=>setArch(null)} done={()=>{setArch(null);load()}}/>}
    {addSem&&<SemesterSheet sem={{}} pid={p.id} term={p.term} toast={toast} close={()=>setAddSem(false)} done={()=>{setAddSem(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>Delete “{p.name}”?</h3><p className="known">This permanently deletes {pl(p.semesters,p.term.toLowerCase())}, {p.courses} courses, {p.units} units and {p.topics} topics, including their saved AI answers.{p.students>0&&` The ${p.students} enrolled students keep their accounts but lose their program.`}</p>
      <button className="btn danger" disabled={busy} onClick={del}>Delete program</button><button className="btn ghost" onClick={()=>setAsk(false)}>Cancel</button></Sheet>}</>}

function OwnerSheet({c,close,done,toast}){
  const faculty=useFaculty(true),[sel,setSel]=useState(c.owner_id||''),[busy,setBusy]=useState(false)
  const save=async()=>{if(String(sel)===String(c.owner_id||''))return close();setBusy(true);try{await api(`/courses/${c.id}/owner`,{method:'PUT',body:{user_id:sel?+sel:null}});toast('Owner updated');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>Owner of “{c.name}”</h3><p className="known">The owner adds and edits this course's units, topics and quizzes. Changing the owner keeps all content and student progress.{c.owner_problem&&c.owner_id?' '+c.owner_problem+'.':''}</p>
    <label>Owner (faculty)</label><select value={sel} onChange={e=>setSel(e.target.value)}><option value="">Not assigned</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner} (can't edit)</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    <button className="btn" disabled={busy} onClick={save}>Save</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}

function ProgramSheet({p,close,done,toast}){
  const isNew=!p.id,[name,setName]=useState(p.name||''),[pat,setPat]=useState(p.pattern||'semester'),[terms,setTerms]=useState(PATTERN[pat][2]),[touched,setTouched]=useState(false),[busy,setBusy]=useState(false)
  const lab=PATTERN[pat][1],pick=k=>{setPat(k);setTerms(touched?Math.min(terms,maxOf(PATTERN[k][1])):PATTERN[k][2])}
  const save=async()=>{setBusy(true);try{const r=await api(isNew?'/programs':'/programs/'+p.id,{method:isNew?'POST':'PUT',body:{name,pattern:pat,...(isNew?{terms}:{})}});toast(isNew?(r.terms?`Program added with ${r.terms} ${lab.toLowerCase()}${r.terms===1?'':'s'}`:'Program added'):'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet page close={close}><h3>{isNew?'New program':'Edit program'}</h3>
    <label>Name</label><input value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==='Enter'&&save()} placeholder="B.E. Mechanical Engineering" autoFocus/>
    <p className="known" style={{marginTop:10}}>Names must be unique. The users CSV import matches programs by name.</p>
    <label id="pat">How is the program divided?</label><div role="group" aria-labelledby="pat" className="seg" style={{marginTop:0}}>{Object.entries(PATTERN).map(([k,[l]])=><button key={k} className={pat===k?'on':''} aria-pressed={pat===k} onClick={()=>pick(k)}>{l}</button>)}</div>
    <p className="known" style={{marginTop:6}}>{PATTERN[pat][3]}</p>
    {isNew?<><label htmlFor="nt">How many {lab.toLowerCase()}s?</label><select id="nt" value={terms} onChange={e=>{setTerms(+e.target.value);setTouched(true)}}>{[0,...upTo(maxOf(lab))].map(n=><option key={n} value={n}>{n===0?'None yet, I will add them myself':n}</option>)}</select>
      <p className="known" style={{marginTop:6}}>{terms?`${lab} 1${terms>1?` to ${lab} ${terms}`:''} ${terms>1?'are':'is'} created for you, so you can go straight to adding courses.`:'You can add them one by one later.'}</p></>
      :p.pattern&&pat!==p.pattern&&<p className="known" style={{marginTop:6}}>Terms still named “{PATTERN[p.pattern]?.[1]||'Semester'} n” are renamed to “{lab} n”. Terms you named yourself keep their names.{pat==='grade'&&' Any of Grade 1 to Grade 12 the program does not have yet are added.'}</p>}
    <button className="btn" disabled={busy||!name.trim()} onClick={save}>{isNew?'Add program':'Save changes'}</button></Sheet>}

function Branding({toast,onSaved}){
  const [name,setName]=useState(''),[logo,setLogo]=useState(null),[busy,setBusy]=useState(false),file=useRef(null)
  useEffect(()=>{api('/config').then(c=>{setName(c.name);setLogo(c.logo)}).catch(()=>{})},[])
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;setBusy(true)
    try{const r=await fetch('/api/uploads',{method:'POST',headers:{Authorization:'Bearer '+localStorage.t,'Content-Type':f.type},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');setLogo(j.url)}catch(x){toast(x.message)}setBusy(false)}
  const save=async body=>{setBusy(true);try{await api('/admin/branding',{method:'PUT',body});toast('Saved');onSaved()}catch(e){toast(e.message)}setBusy(false)}
  return <><h3 className="sec first">Institution name and logo</h3><p className="known">Shown on the sign-in page and in the menu. Use a square PNG, JPG or WebP under 3 MB.</p>
    <div className="lpreview"><Logo src={logo} size={48}/><b>{name||'Name'}</b></div>
    <label htmlFor="inst">Name</label><input id="inst" value={name} maxLength={60} onChange={e=>setName(e.target.value)}/>
    <input ref={file} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={pick}/>
    <div className="two"><button className="btn ghost" disabled={busy} onClick={()=>file.current.click()}><Upload size={16}/> {logo?'Replace logo':'Upload logo'}</button>
      <button className="btn ghost" disabled={busy||!logo} onClick={()=>{setLogo(null);save({remove_logo:true,name})}}>Remove logo</button></div>
    <button className="btn" disabled={busy} onClick={()=>save({name,logo_url:logo||undefined})}>Save name and logo</button></>}
function AiConfig({toast,onBrand}){
  const confirm=useConfirm()
  const [cfg,setCfg]=useState({}),[key,setKey]=useState(''),[model,setModel]=useState(''),[st,setSt]=useState({}),[tab,setTab]=useState('ai')
  const load=()=>{api('/admin/settings').then(c=>{setCfg(c);setModel(c.model)});api('/admin/stats').then(setSt)};useEffect(load,[])
  const run=useRun(toast,load)
  return <><Bar title="Settings" sub={cfg.key_set?'AI is on · key '+cfg.key_hint:'AI is off · no key yet'}/><div className="main"><Tabs label="Settings sections" scroll items={[['ai','AI'],['prompts','AI prompts'],['school','Institution'],['access','Sign-in']]} value={tab} onChange={setTab}/>
    {tab==='school'&&<Branding toast={toast} onSaved={onBrand}/>}{tab==='ai'&&<>
    <label>DeepSeek API key</label><input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder={cfg.key_set?'Leave blank to keep the current key':'sk-…'}/>
    <label>Model</label><input value={model} onChange={e=>setModel(e.target.value)} placeholder="deepseek-chat"/>
    <button className="btn" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{deepseek_key:key,model}}).then(()=>setKey('')),'AI settings saved')}>Save</button>
    {cfg.key_set&&<><button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/ai/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>Test the key</button>
      <button className="btn ghost" onClick={async()=>{if(await confirm({title:'Turn AI off for everyone?',body:'Students will see “AI unavailable” until you save a key again.',ok:'Turn AI off',danger:true}))run(()=>api('/admin/settings',{method:'PUT',body:{remove_key:true}}),'AI is off')}}>Remove the key (turn AI off)</button></>}
    <p className="known" style={{marginTop:20}}>One key serves every student added by staff (people who register themselves use their own key). Until a key is saved, students see “AI unavailable. Try again later.” Each topic is explained once and the answer is shared with every student. {(st.cached??0).toLocaleString()} answers are saved so far, which has saved about {(st.tokens_saved??0).toLocaleString()} tokens.</p>
    </>}{tab==='prompts'&&<PromptEditor toast={toast}/>}
    {tab==='access'&&<><h3 className="sec first">Self-registration</h3><SelfReg cfg={cfg} run={run}/>
    <h3 className="sec">Password reset email</h3><p className="known">{cfg.mail_on?'On. People can reset their own password from the sign-in page.':'Off. The sign-in page tells people to ask an admin. To turn it on, set SMTP_HOST, SMTP_FROM and APP_URL in .env and restart (see .env.example).'}</p>
    {cfg.mail_on&&<button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/mail/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>Send a test email to me</button>}</>}</div></>}

const VERB={POST:'Created',PUT:'Changed',PATCH:'Edited',DELETE:'Deleted'}
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
  return <><Bar title="Activity log" sub="Who changed what"/><div className="main"><div className="search"><Search size={18}/><input type="search" aria-label="Search the activity log" placeholder="Search by person or action" value={q} onChange={e=>setQ(e.target.value)}/></div>
    {rows.length?rows.map(x=><div className="row" key={x.id}><div>{describe(x.method,x.path)}{x.status>=400&&<span className="pill off sm">{x.status===403?'Not allowed':'Failed'}</span>}<small>{x.user} · {when(x.at)}</small></div></div>):busy?<Skeleton/>:<p className="known">No activity yet.</p>}
    {rows.length<total&&<ShowMore left={total-rows.length} busy={busy} onClick={()=>load(true)}/>}</div></>}
const day=d=>d?new Date(d).toLocaleDateString(undefined,{day:'numeric',month:'short'}):'never'
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
  return <>{!few&&<div className="qopt"><select value={f.p} onChange={e=>{const p=+e.target.value,x=progs.find(y=>y.id===p);setF({p,s:x&&f.s>x.max?0:f.s})}}><option value={0}>All programs</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <select aria-label={'Filter by '+lab.toLowerCase()} value={f.s} onChange={e=>setF({...f,s:+e.target.value})}><option value={0}>{lab==='Term'?'All terms':'All '+lab.toLowerCase()+'s'}</option>{Array.from({length:top},(_,i)=>i+1).map(n=><option key={n} value={n}>{lab} {n}</option>)}</select></div>}
    {rows&&!rows.length&&<p className="known">No courses match.</p>}
    {rows?.map(x=><button className="row rowbtn" key={x.course_id} onClick={()=>onOpen(x)}><div>{x.course}<small>{x.program} · {x.semester} · {x.students} students · {x.topics} topics · {x.avg_completion}% completed · {x.avg_opened}% opened{x.quizzes?' · quiz avg '+(x.avg_quiz_percent??'–')+'%':''}</small><Bar2 v={x.avg_completion}/></div><ChevronRight size={18}/></button>)}
    {rows?.length>0&&<button className="btn ghost" onClick={()=>fetchFile('/reports/courses?format=csv&program_id='+f.p+'&semester='+f.s,'courses.csv',toast)}>Download courses CSV</button>}</>}
function StudentReport({c,back,toast}){
  const [d,setD]=useState(null),[w,setW]=useState(null);useEffect(()=>{api(`/reports/courses/${c.course_id}/students`).then(setD).catch(e=>toast(e.message));api(`/reports/courses/${c.course_id}/weak-areas`).then(setW).catch(()=>{})},[])
  return <><Bar title={c.course} sub={c.program+' · '+c.semester} back={back}/><div className="main">
    {w&&w.areas.length>0&&<><h3 className="sec first">Topics the class finds hard</h3><p className="known" style={{margin:'0 0 8px'}}>From each student's latest quiz results, weakest first.</p>{w.areas.slice(0,8).map(a=><div className="row" key={a.topic_id||'u'+a.unit_id}><div>{a.title}<small>{a.percent}% right overall · {a.needs_study} of {a.students} students need another round of study</small><Bar2 v={a.percent}/></div></div>)}<h3 className="sec">Students</h3></>}
    {d&&!d.students.length&&<p className="known">No students are enrolled for this course yet.</p>}
    {d?.students.map(x=><div className="row" key={x.email}><div>{x.name}{!x.active&&<span className="pill off sm">Disabled</span>}<small>{x.completion}% completed · {x.topics_completed}/{x.topics} done, {x.topics_read} opened{c.quizzes?' · quizzes '+x.quizzes_taken+'/'+x.quizzes+(x.avg_quiz_percent!=null?', avg '+x.avg_quiz_percent+'%':''):''} · last active {day(x.last_active)}</small>{(x.strong.length>0||x.needs_study.length>0)&&<small>{x.strong.length>0&&'Strong: '+x.strong.join(', ')}{x.strong.length>0&&x.needs_study.length>0&&' · '}{x.needs_study.length>0&&'Needs another round: '+x.needs_study.join(', ')}</small>}<Bar2 v={x.completion}/></div></div>)}
    {d?.students.length>0&&<button className="btn ghost" onClick={()=>fetchFile(`/reports/courses/${c.course_id}/students?format=csv`,'students-'+c.course.replace(/\s+/g,'_')+'.csv',toast)}>Download students CSV</button>}</div></>}
function Reports({role,toast}){
  const [st,setSt]=useState({}),[r,setR]=useState(null),[open,setOpen]=useState(null)
  useEffect(()=>{if(role==='faculty')return;api('/admin/stats').then(setSt);api('/admin/reports').then(setR)},[])
  if(open)return <StudentReport c={open} back={()=>setOpen(null)} toast={toast}/>
  if(role==='faculty')return <><Bar title="Reports" sub="Your courses"/><div className="main"><CourseReports toast={toast} onOpen={setOpen}/></div></>
  const list=(rows,empty,f)=>rows?.length?rows.map((x,i)=><div className="row" key={i}>{f(x)}</div>):<p className="known">{empty}</p>
  return <><Bar title="Reports"/><div className="main"><div className="stats">
    {[['students','Students'],['topics','Topics'],['cached','Saved AI answers'],['tokens_saved','Tokens saved']].map(([k,l])=><div className="stat" key={k}><b>{(st[k]??0).toLocaleString()}</b>{l}</div>)}</div>
    <h3 className="sec">Courses</h3><CourseReports toast={toast} onOpen={setOpen}/>
    <h3 className="sec">Most read topics</h3>
    {list(r?.top_topics,'No reading activity yet.',x=><div>{x.title}<small>{x.readers} students, {x.reads} reads</small></div>)}
    <h3 className="sec">Students</h3>
    {list(r?.students,'No students yet.',x=><div>{x.name}<small>{x.topics_read} topics read, last active {day(x.last_active)}{!x.active&&', disabled'}</small></div>)}
    <h3 className="sec">Saved AI answers</h3>
    {list(r?.ai,'Nothing saved yet.',x=><div>{x.title}<small>{x.kind==='explain'?'Explanation':'Sample answer'}, reused {x.hits} times, {x.saved.toLocaleString()} tokens saved</small></div>)}</div></>}

function About({user}){
  const {appName}=useContext(Ctx),[c,setC]=useState({});useEffect(()=>{api('/config').then(setC)},[])
  return <><Bar title="About"/><div className="main"><div className="hero"><h2>{appName}</h2><p>Version {c.version||''}</p></div>
    <div className="prose"><p>A study companion for engineering students. Your admin adds programs, semesters, courses, units and topics along with the question pattern and answer guideline. Open a topic to get a clear explanation and a sample answer that follows the guideline.</p>
    <p>The app remembers which topics you have read. Explanations and sample answers are generated once with DeepSeek and shared, so they open instantly.</p>
    <p>Signed in as <strong>{user.name}</strong> ({user.role}).</p></div></div></>}
