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
import {Home,Users as UsersIcon,GraduationCap,Sparkles,BarChart3,Info,LogOut,Menu,X,ArrowUp,ArrowDown,Search,ChevronLeft,ChevronRight,Sun,Moon,Monitor,Upload,Copy,Check,Pencil,Trash2,Bookmark,KeyRound,Link2,Eye,EyeOff,History,TrendingUp} from 'lucide-react'
import '@fontsource/bricolage-grotesque/600.css'
import '@fontsource/bricolage-grotesque/800.css'
import '@fontsource/instrument-sans/400.css'
import '@fontsource/instrument-sans/500.css'
import '@fontsource/instrument-sans/600.css'
import './styles.css'

const api=async(p,o={})=>{const t=localStorage.t
  const r=await fetch('/api'+p,{...o,headers:{'Content-Type':'application/json',...(t&&{Authorization:'Bearer '+t})},body:o.body&&JSON.stringify(o.body)})
  const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Something went wrong');return j}
const TEMPLATE=`program,semester,course,unit,topic,content,question_pattern,sample_content,guideline
B.E. Mechanical Engineering,Semester 3,Thermodynamics,Unit 1: Basic concepts,First law of thermodynamics,"Energy can change form but is never created or destroyed.","2 marks: define. 13 marks: derive and solve a numerical.","Q: State the first law for a closed system.","Introduction, labelled diagram, steps, units, conclusion"
,,,,Zeroth law of thermodynamics,"If A and B are each in equilibrium with C, they are in equilibrium with each other.","2 marks: state the law.","Q: State the zeroth law.","Definition, one example, significance"
`
const COL=['#3d63c9','#2b8a7e','#a86a2a','#7655b3','#3b7ea6']
const when=iso=>new Date(iso).toLocaleString(undefined,{day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'})  // shown in the viewer's own time zone
const localInput=iso=>{if(!iso)return '';const d=new Date(iso),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`}
const STATUS={not_started:'Not started',in_progress:'In progress',completed:'Completed'}
const doneOf=ts=>`${ts.filter(x=>x.status==='completed').length} / ${ts.length}`  // worked out from each topic's state, never stored
const Mark=({s})=>s==='completed'?<Check className="done" aria-label="Completed"/>:<span className="st" aria-label={STATUS[s]}>{s==='in_progress'?'●':'—'}</span>
const ownerLine=c=>c.mine?'Your course':c.owner_problem||(c.owner?'Owner: '+c.owner:'Owner not assigned')
const useFaculty=on=>{const [l,setL]=useState([]);useEffect(()=>{if(on)api('/admin/users?role=faculty&limit=100').then(r=>setL(r.items.filter(u=>u.active))).catch(()=>{})},[on]);return l}

const pl=(n,w)=>`${n} ${w}${n===1?'':'s'}`
const Ctx=createContext({})
const THEMES=[['system',Monitor,'Auto'],['light',Sun,'Light'],['dark',Moon,'Dark']]
const readTheme=()=>{try{return localStorage.theme||'system'}catch{return 'system'}}
const applyTheme=t=>{const r=document.documentElement;if(t==='light'||t==='dark')r.dataset.theme=t;else delete r.dataset.theme;const dark=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);document.querySelector('meta[name=theme-color]')?.setAttribute('content',dark?'#0f1319':'#f4f5f8')}
const Logo=({src,size=40})=>src?<img className="logo" src={src} alt="" width={size} height={size} style={{width:size,height:size}}/>:<span className="logomark" style={{width:size,height:size}} aria-hidden="true"><GraduationCap size={size*.55}/></span>
const Lockup=({logo,name,size=40})=><div className="lockup"><Logo src={logo} size={size}/><b>{name}</b></div>

export default function App(){
  const [user,setUser]=useState(null),[ready,setReady]=useState(false),[pageSel,setPage]=useState(null),[msg,setMsg]=useState(''),[open,setOpen]=useState(false),[name,setName]=useState('Eng Tutor'),[canReset,setCanReset]=useState(false),[canReg,setCanReg]=useState(false),[resetTok,setResetTok]=useState(()=>(/^#reset=([\w-]+)$/.exec(location.hash)||[])[1]||null),[start,setStart]=useState(null),[logo,setLogo]=useState(null),[theme,setTheme]=useState(readTheme)
  const toast=useCallback(m=>{setMsg(m);setTimeout(()=>setMsg(''),2800)},[])
  useEffect(()=>{Promise.allSettled([api('/config').then(c=>{setName(c.name);setLogo(c.logo||null);setCanReset(!!c.email_reset);setCanReg(!!c.self_registration);document.title=c.name}),localStorage.t?api('/me').then(setUser).catch(()=>localStorage.removeItem('t')):null]).then(()=>setReady(true))},[])
  useEffect(()=>{applyTheme(theme);if(theme!=='system')return;const m=matchMedia('(prefers-color-scheme: dark)'),f=()=>applyTheme('system');m.addEventListener('change',f);return()=>m.removeEventListener('change',f)},[theme])
  const pickTheme=t=>{setTheme(t);try{t==='system'?localStorage.removeItem('theme'):localStorage.theme=t}catch{/* private mode: the choice lasts until the page closes */}}
  useEffect(()=>{const k=e=>e.key==='Escape'&&setOpen(false);addEventListener('keydown',k);return()=>removeEventListener('keydown',k)},[])
  useEffect(()=>{document.body.style.overflow=open?'hidden':''},[open])
  if(!ready)return null
  if(resetTok)return <ResetPassword token={resetTok} toast={toast} msg={msg} canReset={canReset} appName={name} logo={logo} done={u=>{history.replaceState(null,'',location.pathname);setResetTok(null);setUser(u);toast('Password changed. You are signed in.')}} leave={()=>{history.replaceState(null,'',location.pathname);setResetTok(null)}}/>
  if(!user)return <Login onIn={setUser} toast={toast} msg={msg} appName={name} logo={logo} canReset={canReset} canReg={canReg}/>
  if(user.must_change)return <ChangePassword forced appName={name} logo={logo} toast={toast} msg={msg} done={()=>setUser({...user,must_change:false})} out={()=>{localStorage.removeItem('t');setUser(null)}}/>
  const student=user.role==='student',page=pageSel||'home',admin=user.role==='admin',go=k=>{setPage(k);setOpen(false)},openIn=nav=>{setStart(nav);go('learn')}
  const links=[['home',Home,'Home'],['learn',GraduationCap,student?'My courses':'Courses'],...(user.role==='student'?[['progress',TrendingUp,'My progress']]:[]),['bookmarks',Bookmark,'Bookmarks'],...(admin?[['users',UsersIcon,'Users'],['programs',GraduationCap,'Programs'],["ai",Sparkles,"Settings"],['reports',BarChart3,'Reports'],['activity',History,'Activity log']]:user.role==='faculty'?[['reports',BarChart3,'Reports']]:[]),...(user.self_registered?[['aikey',Sparkles,'My AI key']]:[]),['password',KeyRound,'Change password'],['about',Info,'About']]
  return <Ctx.Provider value={{menu:()=>setOpen(true),appName:name}}>
    {page==='home'&&student&&<Dashboard user={user} toast={toast} onOpen={openIn}/>}
    {page==='home'&&!student&&<StaffHome user={user} toast={toast} open={openIn}/>}
    {page==='learn'&&<Learn key={String(start)} start={start} user={user} toast={toast} appName={name}/>}
    {page==='progress'&&user.role==='student'&&<Insights toast={toast} role={user.role}/>}
    {page==='bookmarks'&&<Bookmarks toast={toast} role={user.role}/>}
    {page==='users'&&admin&&<Users toast={toast} me={user}/>}{page==='programs'&&admin&&<Programs toast={toast} onOpen={openIn}/>}
    {page==='ai'&&admin&&<AiConfig toast={toast} onBrand={()=>api('/config').then(c=>{setName(c.name);setLogo(c.logo||null);document.title=c.name})}/>}{page==='reports'&&(admin||user.role==='faculty')&&<Reports role={user.role} toast={toast}/>}{page==='activity'&&admin&&<Activity/>}{page==='aikey'&&user.self_registered&&<MyAiKey toast={toast}/>}{page==='password'&&<ChangePassword toast={toast} done={()=>go('learn')}/>}{page==='about'&&<About user={user}/>}
    <div className={'drawer'+(open?' open':'')}><div className="dscrim" onClick={()=>setOpen(false)}/>
      <nav className="panel" aria-label="Main menu">
        <div className="dhead"><Logo src={logo} size={36}/><div><b>{name}</b><small>{user.name}, {user.role}</small></div><button className="ic" aria-label="Close menu" onClick={()=>setOpen(false)}><X/></button></div>
        {links.map(([k,I,l])=><button key={k} className={'dlink'+(page===k?' on':'')} onClick={()=>{if(k==='learn')setStart(null);go(k)}}><I size={20}/>{l}</button>)}
        <div role="group" aria-label="Appearance" className="seg" style={{marginTop:"auto"}}>{THEMES.map(([k,I,l])=><button key={k} className={theme===k?"on":""} aria-pressed={theme===k} onClick={()=>pickTheme(k)}><I size={15}/>{l}</button>)}</div>
        <button className="dlink" onClick={()=>{localStorage.removeItem('t');setOpen(false);setPage(null);setUser(null)}}><LogOut size={20}/>Sign out</button>
      </nav></div>
    {msg&&<div className="toast" role="status">{msg}</div>}
  </Ctx.Provider>}

function Login({onIn,toast,msg,appName,logo,canReset,canReg}){
  const [f,setF]=useState({email:'',password:''}),[b,setB]=useState(false),[mode,setMode]=useState('in'),[sent,setSent]=useState('')
  const go=async()=>{setB(true);try{const r=await api('/login',{method:'POST',body:f});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  const forgot=async()=>{setB(true);try{setSent((await api('/forgot',{method:'POST',body:{email:f.email}})).message)}catch(e){toast(e.message)}setB(false)}
  if(mode==='register')return <Register onIn={onIn} toast={toast} msg={msg} appName={appName} logo={logo} back={()=>setMode('in')}/>
  if(mode==='forgot')return <div className="login"><Lockup logo={logo} name={appName}/><h1>Forgot your password?</h1>{sent?<p>{sent}</p>:<><p>Enter your account email and we will send a link to choose a new one.</p>
    <label>Email</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})} onKeyDown={e=>e.key==='Enter'&&forgot()}/>
    <button className="btn" disabled={b||!f.email} onClick={forgot}>Send reset link</button></>}
    <button className="btn ghost" onClick={()=>{setMode('in');setSent('')}}>Back to sign in</button>{msg&&<div className="toast">{msg}</div>}</div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>Sign in</h1><p>Use the account your institution created for you.</p>
    <label>Email</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})}/>
    <label>Password</label><input type="password" autoComplete="current-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Sign in</button>
    {canReset?<button className="btn ghost" onClick={()=>setMode('forgot')}>Forgot password?</button>:<p className="known">Forgot your password? Ask your admin to reset it.</p>}{canReg&&<button className="btn ghost" onClick={()=>setMode('register')}>Create an account</button>}{msg&&<div className="toast">{msg}</div>}</div>}

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
    <button className="btn ghost" onClick={()=>{setStage('form');setCode('')}}>Change my details</button>{msg&&<div className="toast">{msg}</div>}</div>
  return <div className="login"><Lockup logo={logo} name={appName}/><h1>Create an account</h1><p>We will email you a code to confirm your address.{st.domains.length>0&&' Use your institution email ('+st.domains.map(d=>'@'+d).join(', ')+').'}</p>
    <label htmlFor="rn">Full name</label><input id="rn" autoComplete="name" value={f.name} onChange={set('name')}/>
    <label htmlFor="ri">Institution</label><input id="ri" autoComplete="organization" value={f.institution} onChange={set('institution')}/>
    <label htmlFor="rid">ID number</label><input id="rid" value={f.id_number} onChange={set('id_number')} placeholder="Roll or employee number"/>
    <label htmlFor="re">Email</label><input id="re" type="email" autoComplete="email" value={f.email} onChange={set('email')}/>
    <label htmlFor="rp">Phone</label><input id="rp" type="tel" autoComplete="tel" value={f.phone} onChange={set('phone')} placeholder="+91 98765 43210"/>
    <label htmlFor="rw">Password</label><input id="rw" type="password" autoComplete="new-password" value={f.password} onChange={set('password')} onKeyDown={e=>e.key==='Enter'&&ok&&start()}/>
    <p className="known">At least 8 characters. AI help on this account uses your own DeepSeek API key, which you add after signing in.</p>
    <button className="btn" disabled={b||!ok} onClick={start}>Send me a code</button><button className="btn ghost" onClick={back}>Back to sign in</button>{msg&&<div className="toast">{msg}</div>}</div>}

function MyAiKey({toast}){
  const [d,setD]=useState(null),[key,setKey]=useState(''),[b,setB]=useState(false)
  const load=()=>api('/me/ai-key').then(setD).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  const save=async()=>{setB(true);try{await api('/me/ai-key',{method:'PUT',body:{key}});setKey('');toast('Key saved. AI help is on.');load()}catch(e){toast(e.message)}setB(false)}
  const del=async()=>{if(!confirm('Remove your key? AI help turns off for you until you add one again.'))return;try{await api('/me/ai-key',{method:'DELETE'});toast('Key removed');load()}catch(e){toast(e.message)}}
  return <><Bar title="My AI key" sub={d?.key_set?'AI is on · key '+d.key_hint:'AI is off · no key yet'}/><div className="main">
    <p className="known">AI explanations on your account use your own DeepSeek API key, so any usage is billed to your DeepSeek account. Create a key at platform.deepseek.com, paste it here and save. We check it with DeepSeek first, then store it encrypted. It is never shown again in full.</p>
    <label htmlFor="k">DeepSeek API key</label><input id="k" type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder={d?.key_set?'Paste a new key to replace the current one':'sk-…'}/>
    <button className="btn" disabled={b||!key.trim()} onClick={save}>{b?'Checking the key…':'Save key'}</button>
    {d?.key_set&&<button className="btn ghost" onClick={del}>Remove my key</button>}</div></>}

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
    <button className="btn" disabled={b} onClick={go}>Save and sign in</button>{msg&&<div className="toast">{msg}</div>}</div>}

function ChangePassword({forced,appName,logo,toast,msg,done,out}){
  const [f,setF]=useState({current:'',password:'',again:''}),[b,setB]=useState(false),set=k=>e=>setF({...f,[k]:e.target.value})
  const go=async()=>{if(f.password.length<8)return toast('Use at least 8 characters');if(f.password!==f.again)return toast("The new passwords don't match")
    setB(true);try{const d=await api('/me/password',{method:'POST',body:{current:f.current,new_password:f.password}});if(d.token)localStorage.t=d.token;toast('Password changed');done()}catch(e){toast(e.message)}setB(false)}
  const form=<><label>{forced?'Password your admin gave you':'Current password'}</label><input type="password" autoComplete="current-password" value={f.current} onChange={set('current')}/>
    <label>New password (8+ characters)</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/>
    <label>Repeat new password</label><input type="password" autoComplete="new-password" value={f.again} onChange={set('again')} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Change password</button></>
  if(forced)return <div className="login"><Lockup logo={logo} name={appName}/><h1>Choose your own password</h1><p>Your admin set a temporary password. Pick a new one to continue.</p>{form}<button className="btn ghost" onClick={out}>Sign out</button>{msg&&<div className="toast">{msg}</div>}</div>
  return <><Bar title="Change password"/><div className="main">{form}</div></>}

const Bar=({title,sub,back,right})=>{const {menu}=useContext(Ctx);return <header className="bar">
  <button className="ic menu" aria-label="Open menu" onClick={menu}><Menu/></button>{back&&<button className="ic" aria-label="Back" onClick={back}><ChevronLeft/></button>}
  <h1>{title}{sub&&<small>{sub}</small>}</h1>{right}</header>}

function Learn({user,toast,appName,start}){
  const isAdmin=user.role==='admin',staff=user.role!=='student'
  const [copy,setCopy]=useState(null),[tree,setTree]=useState([]),[nav,setNav]=useState(start||[]),[sheet,setSheet]=useState(null),[cp,setCp]=useState(null),[t,setT]=useState(null),[ed,setEd]=useState(null),[del,setDel]=useState(null),[sh,setSh]=useState(null),[qz,setQz]=useState(null),[qe,setQe]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t,ed,qz,qe,sheet])
  const landed=useRef(false);useEffect(()=>{if(landed.current||user.role!=='student'||tree.length!==1)return;landed.current=true;const p=tree[0],c=p.semesters.find(x=>x.current)||(p.semesters.length===1?p.semesters[0]:null);setNav(c?[p.id,c.id]:[p.id])},[tree])
  const prog=tree.find(x=>x.id===nav[0]),sem=prog?.semesters.find(x=>x.id===nav[1]),co=sem?.courses.find(x=>x.id===nav[2]),unit=co?.units.find(x=>x.id===nav[3])
  const mayEdit=isAdmin||(user.role==='faculty'&&!!co?.editable)
  useEffect(()=>{setCp(null);if(co&&mayEdit&&!co.shared)api(`/courses/${co.id}/progress`).then(setCp).catch(()=>{})},[co?.id,mayEdit,t])
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast} role={user.role}/>
  if(qz)return <QuizPlay id={qz} back={()=>setQz(null)} toast={toast} role={user.role}/>
  if(qe)return <QuizEditor {...qe} done={()=>setQe(null)} toast={toast}/>
  if(ed)return <TopicEditor role={user.role} toast={toast} edit={ed.id?ed:null} unitId={ed.unit_id} done={()=>setEd(null)} cancel={()=>setEd(null)}/>
  const tsub=x=>[x.published===false&&'Draft · students cannot see it',x.learning_due_at?'Due '+when(x.learning_due_at):!staff&&'No deadline',x.overdue&&!staff&&'Overdue',
    cp?.topics[x.id]&&`${cp.topics[x.id].completed}/${cp.students} completed`+(cp.topics[x.id].overdue?` · ${cp.topics[x.id].overdue} overdue`:'')].filter(Boolean).join(' · ')
  const row=(x,kind,one,sub,extra={})=>({id:x.id,n:x.name,sub,kind,go:()=>setNav([...nav,x.id]),edit:()=>setEd({kind:one,id:x.id,name:x.name,...extra})})
  const drafts=t=>t.filter(x=>x.published===false).length
  const setPub=async(url,published,msg)=>{try{await api(url,{method:'PUT',body:{published}});toast(msg);load()}catch(e){toast(e.message)}}
  const move=async(items,i,d,url)=>{const ids=items.map(x=>x.id),j=i+d;if(j<0||j>=ids.length)return;[ids[i],ids[j]]=[ids[j],ids[i]];try{await api(url,{method:'PUT',body:{ids}});load()}catch(e){toast(e.message)}}
  const list=unit?unit.topics.map(x=>({id:x.id,n:x.title,s:x.status,b:x.bookmarked,kind:'topics',sub:tsub(x),late:x.overdue,draft:x.published===false,go:()=>setT(x.id),edit:()=>setEd({id:x.id}),pub:()=>setPub(`/topics/${x.id}/publish`,x.published===false,x.published===false?'Published':'Moved to drafts')}))
    :co?co.units.map(x=>({...row(x,'units','unit',staff?x.topics.length+' topics'+(mayEdit&&drafts(x.topics)?' · '+drafts(x.topics)+' draft':''):doneOf(x.topics)+' topics completed'),edit:()=>setSheet({type:'unit',un:x,cid:co.id})}))
    :sem?sem.courses.map(x=>({...row(x,'courses','course',(staff?x.units.length+' units':doneOf(x.units.flatMap(n=>n.topics))+' topics completed')+(x.shared?' · shared from '+x.home:x.shared_with?' · shared with '+x.shared_with+' more':'')+(staff?' · '+ownerLine(x):'')),edit:()=>setSheet({type:'course',c:x,pid:prog.id,sid:x.semester_id}),share:()=>setSh({id:x.id,name:x.name,home:x.semester_id,sel:x.link_ids||[]}),unlink:x.shared?{id:x.id,keep:(x.link_ids||[]).filter(i=>i!==sem.id)}:null}))
    :prog?prog.semesters.map(x=>({...row(x,'semesters','semester',(isAdmin?(x.number?prog.term+' no. '+x.number:'No '+prog.term.toLowerCase()+' number set')+' · ':'')+x.courses.length+' courses'),edit:()=>setSheet({type:'semester',sem:x,pid:prog.id})}))
    :tree.map(x=>({...row(x,'programs','program',x.semesters.length+' '+x.term.toLowerCase()+(x.semesters.length===1?'':'s')),edit:()=>setSheet({type:'program',p:x})}))
  const cur=unit||co||sem||prog,crumbs=[prog,sem,co,unit].filter(Boolean).slice(0,-1).map(x=>x.name).join(' › ')
  const allSems=tree.flatMap(p=>p.semesters.map(s=>({id:s.id,label:p.name+' › '+s.name})))
  const myCourses=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>c.mine&&!c.shared).map(c=>({p,s,c}))))
  const saveShare=async()=>{try{await api(`/courses/${sh.id}/links`,{method:'PUT',body:{semester_ids:sh.sel}});toast('Sharing updated');setSh(null);load()}catch(e){toast(e.message)}}
  const remove=async()=>{try{if(del.unlink)await api(`/courses/${del.unlink.id}/links`,{method:'PUT',body:{semester_ids:del.unlink.keep}});else await api(`/${del.kind}/${del.id}`,{method:'DELETE'});toast('Deleted');setDel(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={cur?.name||appName} sub={nav.length?crumbs:'Hi '+user.name} back={nav.length>0&&(()=>setNav(nav.slice(0,-1)))}/>
   <div className="main">{unit&&mayEdit&&drafts(unit.topics)>0&&<button className="btn" style={{marginTop:0}} onClick={()=>setPub(`/units/${unit.id}/publish`,true,'All drafts published')}>Publish all {drafts(unit.topics)} drafts</button>}{!nav.length&&<div className="hero"><h2>Choose a program</h2></div>}
     {isAdmin&&!sem&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setSheet(prog?{type:'semester',sem:{},pid:prog.id}:{type:'program',p:{}})}>{prog?'Add '+prog.term.toLowerCase()+' to '+prog.name:'New program'}</button>}
     {isAdmin&&sem&&!co&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setSheet({type:'course',c:{},pid:prog.id,sid:sem.id})}>Add course to {sem.name}</button>}
     {co&&!unit&&!staff&&<p className="known" style={{marginTop:0}}>{doneOf(co.units.flatMap(n=>n.topics))} topics completed</p>}
     {co&&!unit&&staff&&<div className="qbox" style={{marginTop:0}}>{[['Program',prog.name],[prog.term,sem.name+(sem.number?' (no. '+sem.number+')':'')],['Owner',co.mine?'You':co.owner_problem||co.owner||'Not assigned']].map(([l,v])=><div className="row" key={l}><div>{v}<small>{l}</small></div></div>)}
       {isAdmin&&!co.shared&&<div className="two"><button className="btn ghost" onClick={()=>setSheet({type:'course',c:co,pid:prog.id,sid:co.semester_id})}>Edit course</button><button className="btn ghost" onClick={()=>setSheet({type:'owner',c:co})}>Change owner</button></div>}</div>}
     {!nav.length&&user.role==='faculty'&&<><h3 style={{margin:'0 0 8px'}}>My courses</h3>{myCourses.length?myCourses.map(({p,s,c},i)=><div key={c.id} className="card"><button className="hit" onClick={()=>setNav([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div><b>{c.name}</b><span>{p.name} › {s.name} · {c.units.length} units</span></div></button></div>)
       :<p className="known">No course is assigned to you yet. An admin makes you the owner of a course.</p>}<h3 style={{margin:'20px 0 8px'}}>All programs</h3></>}
    {mayEdit&&co&&!unit&&!co.shared&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setSheet({type:'unit',un:{},cid:co.id})}>Add unit</button>}
    {mayEdit&&unit&&!co.shared&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setEd({unit_id:unit.id})}>Add topic to {unit.name}</button>}
    {staff&&unit&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setCopy({kind:'unit',id:unit.id,title:unit.name})}>Copy this unit to another course</button>}
    {list.map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={x.go}><span className="dot" style={{background:COL[i%5]}}>{x.n[0]}</span><div><b>{x.n}</b>{x.sub&&<span>{x.sub}</span>}</div>{(x.s||x.b)&&<span className="marks">{x.b&&<Bookmark className="bm" size={16} fill="currentColor"/>}{x.s&&<Mark s={x.s}/>}</span>}</button>
      {mayEdit&&<>{(x.kind==='units'||x.kind==='topics')&&list.length>1&&[[-1,ArrowUp,'up'],[1,ArrowDown,'down']].map(([d,I,w])=><button key={w} className="ic sm" aria-label={`Move ${x.n} ${w}`} disabled={i+d<0||i+d>=list.length} onClick={()=>move(list,i,d,x.kind==='units'?`/courses/${co.id}/units/order`:`/units/${unit.id}/topics/order`)}><I size={16}/></button>)}{x.pub&&<button className="ic sm" aria-label={(x.draft?'Publish ':'Unpublish ')+x.n} onClick={x.pub}>{x.draft?<Eye size={16}/>:<EyeOff size={16}/>}</button>}{x.share&&<button className="ic sm" aria-label={'Share '+x.n} onClick={x.share}><Link2 size={16}/></button>}<button className="ic sm" aria-label={'Edit '+x.n} onClick={x.edit}><Pencil size={16}/></button><button className="ic sm" aria-label={'Delete '+x.n} onClick={()=>setDel(x.unlink?{...x,unlink:x.unlink}:x)}><Trash2 size={16}/></button></>}</div>)}
    {unit&&(unit.quizzes.length>0||mayEdit)&&<><h3 style={{margin:'28px 0 8px'}}>Quizzes</h3>
      {unit.quizzes.map((q,i)=><div key={q.id} className="card"><button className="hit" onClick={()=>setQz(q.id)}><span className="dot" style={{background:COL[(i+3)%5]}}>?</span><div><b>{q.title}</b><span>{q.questions} questions · pass {q.pass_percent}%{q.best!=null?' · best '+q.best+'%':''}{q.published?'':' · Draft'}</span></div>{q.best!=null&&q.best>=q.pass_percent&&<span className="marks"><Check size={16}/></span>}</button>
        {mayEdit&&<button className="ic sm" aria-label={'Edit '+q.title} onClick={()=>setQe({id:q.id,unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}><Pencil size={16}/></button>}</div>)}
      {mayEdit&&<button className="btn ghost" onClick={()=>setQe({unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}>Add quiz</button>}</>}
    {!list.length&&<p className="known">{(mayEdit&&co)||isAdmin?'Nothing here yet. Use the button above to add it.':!nav.length&&user.role==='student'?'You are not enrolled in a program yet. Ask your admin to add you to one.':'Nothing here yet. Your admin will add it soon.'}</p>}</div>
   {copy&&<CopySheet {...copy} toast={toast} close={()=>{setCopy(null);load()}}/>}
   {del&&<div className="scrim" onClick={()=>setDel(null)}><div className="sheet" onClick={e=>e.stopPropagation()}><h3>{del.unlink?'Remove':'Delete'} “{del.n}”{del.unlink?' from this '+(prog?.term||'semester').toLowerCase():''}?</h3>
     <p className="known">{del.unlink?'It only disappears from this '+(prog?.term||'semester').toLowerCase()+'. The course stays where it was created.':DELETES[del.kind]} This can't be undone.</p>
     <button className="btn danger" onClick={remove}>{del.unlink?'Remove':'Delete'}</button><button className="btn ghost" onClick={()=>setDel(null)}>Keep it</button></div></div>}
   {sh&&<div className="scrim" onClick={()=>setSh(null)}><div className="sheet" onClick={e=>e.stopPropagation()}><h3>Share “{sh.name}”</h3><p className="known">Tick every semester or year that should also show this course. You still edit it in one place.</p>
     {allSems.filter(x=>x.id!==sh.home).map(x=><label key={x.id} className="chk"><input type="checkbox" checked={sh.sel.includes(x.id)} onChange={e=>setSh({...sh,sel:e.target.checked?[...sh.sel,x.id]:sh.sel.filter(i=>i!==x.id)})}/> {x.label}</label>)}
     <button className="btn" onClick={saveShare}>Save</button><button className="btn ghost" onClick={()=>setSh(null)}>Cancel</button></div></div>}
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
  const pickNo=e=>{const no=e.target.value;setF({no,name:!f.name||/^(Semester|Year) \d+$/.test(f.name)?(no?term+' '+no:''):f.name})}
  const save=async()=>{setBusy(true);try{const body={name:f.name,semester_no:f.no?+f.no:null};await api(isNew?`/programs/${pid}/semesters`:'/semesters/'+sem.id,{method:isNew?'POST':'PUT',body:isNew?body:{...body,program_id:pid}});toast(isNew?term+' added':'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?'New '+term.toLowerCase():'Edit '+term.toLowerCase()}</h3>
    <label>{term} number</label><select value={f.no} onChange={pickNo}><option value="">Choose…</option>{SEMS.map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>Name</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder={term+" 3"}/>
    <p className="known" style={{marginTop:10}}>The number sets the order and which students see it: a student in {term.toLowerCase()} 3 sees {term.toLowerCase()}s 1 to 3. Each number is used once per program.</p>
    <button className="btn" disabled={busy||!f.no||!f.name.trim()} onClick={save}>{isNew?'Add '+term.toLowerCase():'Save changes'}</button></Sheet>}
function CourseSheet({c,pid,sid,sems,term='Semester',close,done,toast}){
  const isNew=!c.id,faculty=useFaculty(true),[f,setF]=useState({name:c.name||'',sem:sid,owner:c.owner_id||''}),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{const owner=String(f.owner)!==String(c.owner_id||'')?{faculty_owner_id:f.owner?+f.owner:null}:{}  // unchanged owners are left alone
    await api(isNew?`/programs/${pid}/semesters/${sid}/courses`:'/courses/'+c.id,{method:isNew?'POST':'PUT',body:isNew?{name:f.name,...owner}:{name:f.name,semester_id:+f.sem,...owner}});toast(isNew?'Course added':'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?'New course in '+(sems.find(x=>x.id===sid)?.label||''):'Edit course'}</h3>
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
  return <><Bar title={`${hi}, ${user.name.split(' ')[0]}`} sub={admin?'Across the whole college':'Your courses'}/><div className="main">
    {!o&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {o&&<div className="stats">{stats.map(([n,l,k])=><button className="stat" key={l} style={{textAlign:'left',width:'100%'}} onClick={()=>setList(k)} aria-label={`${(n??0).toLocaleString()} ${l}. Show the list`}><b>{(n??0).toLocaleString()}</b>{l}</button>)}</div>}
    {o&&<><h3 style={{margin:'24px 0 8px'}}>Needs attention</h3>
      {o.attention.length?o.attention.map(x=><button key={x.kind} className="card" style={{textAlign:'left'}} onClick={()=>setList(ATTN_GO[x.kind]||'drafts')}><div style={{flex:1}}><b>{x.text}</b></div><ChevronRight size={18}/></button>)
        :<p className="known">Nothing needs your attention right now.</p>}</>}
    {o&&!o.courses&&!admin&&<p className="known">No course is assigned to you yet. An admin makes you the owner of a course.</p>}
    {o?.courses>0&&<><h3 style={{margin:'28px 0 4px'}}>{admin?'Courses':'Your courses'}</h3><CourseReports toast={toast} onOpen={setRep}/></>}
  </div></>}
function Dashboard({user,toast,onOpen}){
  const [tree,setTree]=useState(null),[ins,setIns]=useState(null),[topic,setTopic]=useState(null)
  useEffect(()=>{if(topic)return;api('/tree').then(setTree).catch(e=>toast(e.message));api('/me/insights').then(setIns).catch(()=>{})},[topic,toast])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={user.role}/>
  const hour=new Date().getHours(),hi=hour<12?'Good morning':hour<17?'Good afternoon':'Good evening'
  const seen=new Set(),courses=[]
  for(const p of tree||[])for(const s of p.semesters)for(const c of s.courses)if(!seen.has(c.id)){seen.add(c.id);courses.push({p,s,c,topics:c.units.flatMap(un=>un.topics.map(t=>({...t,unit:un})))})}
  const all=courses.flatMap(x=>x.topics.map(t=>({...t,x})))
  const resume=all.filter(t=>t.status==='in_progress').sort((a,b)=>(b.last_read||'').localeCompare(a.last_read||''))[0]||all.find(t=>t.status==='not_started')
  const due=all.filter(t=>t.learning_due_at&&t.status!=='completed').sort((a,b)=>a.learning_due_at.localeCompare(b.learning_due_at)).slice(0,5)
  const quizzes=courses.flatMap(x=>x.c.units.flatMap(un=>un.quizzes.filter(q=>q.best==null).map(q=>({...q,x,un})))).slice(0,4)
  const need=ins?.needs_study.slice(0,3)||[]
  return <><Bar title={`${hi}, ${user.name.split(' ')[0]}`} sub="Here is where you are today"/><div className="main">
    {!tree&&<><div className="sk"/><div className="sk"/><div className="sk"/></>}
    {tree&&!courses.length&&<p className="known">{user.self_registered&&!user.placed?'Your account is ready. An admin will place you in your program and semester or year, and your courses will appear here.':'You are not enrolled in a course yet. Ask your admin to add you to one.'}</p>}
    {resume&&<div className="hero"><small>{resume.status==='in_progress'?'Continue where you left off':'Start your first topic'}</small><h2 style={{fontSize:24}}>{resume.title}</h2><p>{resume.x.c.name} · {resume.unit.name}</p>
      <button className="btn inv" style={{marginTop:14}} onClick={()=>setTopic(resume.id)}>{resume.status==='in_progress'?'Continue':'Start'}</button></div>}
    {courses.length>0&&<><h3 style={{margin:'8px 0'}}>My courses</h3>{courses.map(({p,s,c,topics},i)=>{const done=topics.filter(t=>t.status==='completed').length,pc=topics.length?Math.round(100*done/topics.length):0
      return <div key={c.id} className="card" style={{display:'block'}}><button className="hit" style={{width:'100%'}} onClick={()=>onOpen([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div style={{flex:1}}><b>{c.name}</b><span>{done} of {topics.length} topics completed · {pc}%</span><Bar2 v={pc}/></div></button></div>})}</>}
    {due.length>0&&<><h3 style={{margin:'24px 0 8px'}}>Coming up</h3>{due.map(t=><div key={t.id} className="row" style={{cursor:'pointer'}} onClick={()=>setTopic(t.id)}><div>{t.title}<small>{t.x.c.name} · due {when(t.learning_due_at)}</small></div>{t.overdue&&<span className="pill off">Overdue</span>}</div>)}</>}
    {quizzes.length>0&&<><h3 style={{margin:'24px 0 8px'}}>Quizzes to try</h3>{quizzes.map(q=><div key={q.id} className="row" style={{cursor:'pointer'}} onClick={()=>onOpen([q.x.p.id,q.x.s.id,q.x.c.id,q.un.id])}><div>{q.title}<small>{q.x.c.name} · {q.questions} questions</small></div></div>)}</>}
    {need.length>0&&<><h3 style={{margin:'24px 0 4px'}}>Worth another round of study</h3><AreaList areas={need} onStudy={setTopic}/></>}
  </div></>}
function Insights({toast,role}){
  const [d,setD]=useState(null),[topic,setTopic]=useState(null)
  useEffect(()=>{if(!topic)api('/me/insights').then(setD).catch(e=>toast(e.message))},[topic])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  const n=d?d.needs_study.length:0
  return <><Bar title="My progress" sub="Where you shine and what to revisit"/><div className="main">
    {!d&&<p className="known">Loading…</p>}
    {d&&!d.courses.length&&<p className="known">Take a quiz and your strengths and weak spots will show up here.</p>}
    {d?.courses.length>0&&<div className="qbox"><b>{n?`${n} ${n===1?'area needs':'areas need'} another round of study`:'Nothing needs another round of study right now'}</b><p className="known" style={{margin:'4px 0 0'}}>{d.strong.length} strong · {d.getting_there.length} getting there · based on your latest result in {d.quizzes_taken} {d.quizzes_taken===1?'quiz':'quizzes'}</p></div>}
    {d?.courses.map(c=><section key={c.course_id}><h3 style={{margin:'24px 0 4px'}}>{c.course} · {c.percent}% right</h3><AreaList areas={c.areas} onStudy={setTopic}/></section>)}</div></>}

function QuizPlay({id,back,toast,role}){
  const [q,setQ]=useState(null),[ans,setAns]=useState([]),[res,setRes]=useState(null),[busy,setBusy]=useState(false),[topic,setTopic]=useState(null)
  const start=d=>{setQ(d);setAns(d.questions.map(()=>null));setRes(null)}
  useEffect(()=>{api('/quizzes/'+id).then(start).catch(e=>{toast(e.message);back()})},[id])
  if(topic)return <Topic id={topic} back={()=>setTopic(null)} toast={toast} role={role}/>
  if(!q)return <><Bar title="Quiz" back={back}/><div className="main"><p className="known">Loading…</p></div></>
  const left=ans.filter(a=>a===null).length
  const submit=async()=>{setBusy(true);try{setRes(await api(`/quizzes/${id}/attempt`,{method:'POST',body:{answers:ans}}));window.scrollTo(0,0)}catch(e){toast(e.message)}setBusy(false)}
  return <><Bar title={q.title} sub={q.questions.length+' questions · pass mark '+q.pass_percent+'%'} back={back}/><div className="main">
    {res&&<div className="qbox"><h2 style={{margin:0}}>{res.score} / {res.total} · {res.percent}%</h2><p className="known">{res.passed?'Passed. Well done!':'Not there yet. Go back over the topics and try again.'}</p>
      <button className="btn" onClick={()=>start(q)}>Try again</button><button className="btn ghost" onClick={back}>Back to the unit</button></div>}
    {res&&res.areas?.length>0&&<><h3 style={{margin:'20px 0 4px'}}>How you did by topic</h3><AreaList areas={res.areas} onStudy={setTopic}/></>}
    {q.questions.map((x,i)=><div className="qbox" key={x.id}><b>Question {i+1}</b><div className="prose"><Md>{x.text}</Md></div>
      {x.options.map((o,k)=>{const r=res&&res.results[i],cls=r?(k===r.correct||(r.ok&&k===r.chosen)?' ok':k===r.chosen?' bad':''):ans[i]===k?' sel':''
        return <button key={k} className={'opt'+cls} disabled={!!res} onClick={()=>setAns(ans.map((a,n)=>n===i?k:a))}><Md>{o}</Md></button>})}
      {res&&res.results[i].explanation&&<div className="known"><Md>{res.results[i].explanation}</Md></div>}</div>)}
    {!res&&<button className="btn" disabled={busy} onClick={submit}>{busy?'Checking…':'Submit answers'}</button>}
    {!res&&left>0&&<p className="known">{left} unanswered. Blank answers count as wrong.</p>}</div></>}

const parseCsv=text=>{const rows=[];let row=[],cell='',q=false;const t=text.replace(/^\ufeff/,'')
  for(let i=0;i<t.length;i++){const ch=t[i]
    if(q){if(ch==='"'&&t[i+1]==='"'){cell+='"';i++}else if(ch==='"')q=false;else cell+=ch}
    else if(ch==='"')q=true;else if(ch===','||ch===';'||ch==='\t'){row.push(cell);cell=''}
    else if(ch==='\n'||ch==='\r'){if(ch==='\r'&&t[i+1]==='\n')i++;row.push(cell);cell='';if(row.some(x=>x.trim()))rows.push(row);row=[]}
    else cell+=ch}
  row.push(cell);if(row.some(x=>x.trim()))rows.push(row);return rows}
const QUIZ_TEMPLATE='question,a,b,c,d,correct,explanation,topic\n"Which ion makes water hard?",Na+,Ca2+,Cl-,K+,B,"Calcium and magnesium salts cause hardness.",1. Water Treatment\n'
// rows of a questions CSV -> {questions, errors}; "correct" is a letter (A-F) or a 1-based number; "topic" is matched against this unit's topic titles
const quizFromCsv=(text,topics)=>{const rows=parseCsv(text),head=(rows.shift()||[]).map(h=>h.trim().toLowerCase().replace(/[^a-z0-9]+/g,'_')),col=n=>head.indexOf(n),errors=[],questions=[]
  const al=head.map((h,i)=>/^(option_|answer_)?[a-f]$/.test(h)?i:-1).filter(i=>i>=0)
  if(col('question')<0||al.length<2)return {questions,errors:['The first row must name the columns: question, a, b, c, d, correct (and optionally explanation, topic).']}
  rows.forEach((r,n)=>{const line=n+2,text=(r[col('question')]||'').trim(),opts=al.map(i=>(r[i]||'').trim()).filter(Boolean),raw=(r[col('correct')]||'').trim().toUpperCase()
    const k=/^[A-F]$/.test(raw)?raw.charCodeAt(0)-65:/^[1-6]$/.test(raw)?+raw-1:-1
    if(!text)return errors.push(`Row ${line}: no question text`);if(opts.length<2)return errors.push(`Row ${line}: needs at least two answers`)
    if(k<0||k>=opts.length)return errors.push(`Row ${line}: "correct" must be a letter such as B that points at one of the answers`)
    const tn=(r[col('topic')]||'').trim().toLowerCase(),tp=tn&&topics.find(t=>t.title.trim().toLowerCase()===tn)
    if(tn&&!tp)errors.push(`Row ${line}: no topic called "${r[col('topic')].trim()}" in this unit, so it is not tied to a topic`)
    questions.push({text,options:opts,correct:k,explanation:(r[col('explanation')]||'').trim(),topic_id:tp?tp.id:null})})
  return {questions,errors}}
function QuizEditor({id,unit_id,unitTopics,done,toast}){
  const blank=()=>({text:'',options:['',''],correct:0,explanation:'',topic_id:null})
  const [m,setM]=useState({title:'',pass_percent:50,published:false}),[qs,setQs]=useState([blank()]),[busy,setBusy]=useState(false),[topics,setTopics]=useState(unitTopics||[]),csvRef=useRef(null),[csvMsg,setCsvMsg]=useState([]),[bank,setBank]=useState(false),[btags,setBtags]=useState('')
  useEffect(()=>{if(id)api('/quizzes/'+id).then(d=>{setM({title:d.title,pass_percent:d.pass_percent,published:d.published});setTopics(d.topics||[]);setQs(d.questions.length?d.questions.map(x=>({text:x.text,options:x.options,correct:x.correct,explanation:x.explanation||'',topic_id:x.topic_id??null})):[blank()])}).catch(e=>{toast(e.message);done()})},[id])
  const upd=(i,p)=>setQs(qs.map((x,n)=>n===i?{...x,...p}:x))
  const setOpt=(i,k,v)=>upd(i,{options:qs[i].options.map((o,n)=>n===k?v:o)})
  const delOpt=(i,k)=>upd(i,{options:qs[i].options.filter((_,n)=>n!==k),correct:qs[i].correct===k?0:qs[i].correct>k?qs[i].correct-1:qs[i].correct})
  const save=async()=>{setBusy(true);try{const qid=id||(await api('/quizzes',{method:'POST',body:{unit_id,...m,pass_percent:+m.pass_percent}})).id
    if(id)await api('/quizzes/'+id,{method:'PUT',body:{unit_id,...m,pass_percent:+m.pass_percent}})
    await api(`/quizzes/${qid}/questions`,{method:'PUT',body:{questions:qs.filter(x=>x.text.trim())}});toast('Quiz saved');done()}catch(e){toast(e.message)}setBusy(false)}
  const importCsv=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;const {questions,errors}=quizFromCsv(await f.text(),topics);setCsvMsg(errors)
    if(questions.length){setQs(cur=>[...cur.filter(x=>x.text.trim()),...questions]);toast(`${questions.length} questions added. Review them, then save.`)}else toast('No questions were added')}
  const addFromBank=picked=>{setQs(cur=>[...cur.filter(x=>x.text.trim()),...picked.map(x=>({text:x.text,options:x.options,correct:x.correct,explanation:x.explanation||'',topic_id:null}))]);setBank(false);toast(`${pl(picked.length,'question')} added. Tie them to topics if you like, then save.`)}
  const toBank=async()=>{const list=qs.filter(x=>x.text.trim());let added=0,skipped=0,bad=0;setBusy(true)
    for(const x of list){try{await api('/bank',{method:'POST',body:{text:x.text,options:x.options,correct:x.correct,explanation:x.explanation,tags:btags,source:m.title}});added++}catch(e){/already in the bank/.test(e.message)?skipped++:bad++}}
    setBusy(false);toast(`${added} saved to the bank${skipped?`, ${skipped} already there`:''}${bad?`, ${bad} skipped (incomplete)`:''}`)}
  const del=async()=>{if(!confirm('Delete this quiz and every student attempt?'))return;try{await api('/quizzes/'+id,{method:'DELETE'});toast('Quiz deleted');done()}catch(e){toast(e.message)}}
  return <><Bar title={id?'Edit quiz':'New quiz'} back={done}/><div className="main">
    <label>Title</label><input value={m.title} onChange={e=>setM({...m,title:e.target.value})} placeholder="e.g. Water treatment check"/>
    <label>Pass mark (%)</label><input type="number" min="1" max="100" value={m.pass_percent} onChange={e=>setM({...m,pass_percent:e.target.value})}/>
    <label className="chk"><input type="checkbox" checked={m.published} onChange={e=>setM({...m,published:e.target.checked})}/> Published (students can take it)</label>
    {qs.map((x,i)=><div className="qbox" key={i}><b>Question {i+1}</b>
      <textarea placeholder="Question (Markdown and $math$ work)" value={x.text} onChange={e=>upd(i,{text:e.target.value})}/>
      {x.options.map((o,k)=><div className="qopt" key={k}><input type="radio" name={'c'+i} aria-label="Correct answer" checked={x.correct===k} onChange={()=>upd(i,{correct:k})}/><input value={o} placeholder={'Answer '+(k+1)} onChange={e=>setOpt(i,k,e.target.value)}/>{x.options.length>2&&<button className="ic sm" aria-label="Remove answer" onClick={()=>delOpt(i,k)}><X size={16}/></button>}</div>)}
      {x.options.length<6&&<button className="tool" onClick={()=>upd(i,{options:[...x.options,'']})}>Add answer</button>}
      <label>Topic this tests</label><select value={x.topic_id??''} onChange={e=>upd(i,{topic_id:e.target.value?+e.target.value:null})}><option value="">Not tied to one topic</option>{topics.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}</select>
      <textarea placeholder="Explanation shown after submitting (optional)" value={x.explanation} onChange={e=>upd(i,{explanation:e.target.value})}/>
      {qs.length>1&&<button className="tool" onClick={()=>setQs(qs.filter((_,n)=>n!==i))}>Remove question</button>}</div>)}
    <p className="known">Tick the radio button beside the correct answer. Tie each question to the topic it tests: students then see which topics they know well and which need another round of study.</p>
    <button className="btn ghost" onClick={()=>setQs([...qs,blank()])}>Add question</button>
    <input ref={csvRef} type="file" accept=".csv,text/csv" hidden onChange={importCsv}/>
    <div className="two"><button className="btn ghost" onClick={()=>csvRef.current.click()}><Upload size={16}/> Import from CSV</button><button className="btn ghost" onClick={()=>download('quiz-template.csv',QUIZ_TEMPLATE)}>CSV template</button></div>
    {csvMsg.length>0&&<div className="qbox" role="alert"><b>{csvMsg.length} {csvMsg.length===1?'row needs':'rows need'} a look</b>{csvMsg.slice(0,8).map((m,i)=><p className="known" style={{margin:'4px 0'}} key={i}>{m}</p>)}{csvMsg.length>8&&<p className="known">…and {csvMsg.length-8} more.</p>}</div>}
    <button className="btn ghost" onClick={()=>setBank(true)}>Add from the question bank</button>
    <label htmlFor="bt">Share these questions in the bank</label><div className="two"><input id="bt" value={btags} onChange={e=>setBtags(e.target.value)} placeholder="Tags, e.g. water, hardness (optional)"/><button className="btn ghost" disabled={busy||!qs.some(x=>x.text.trim())} onClick={toBank}>Save to bank</button></div>
    <button className="btn" disabled={busy} onClick={save}>{busy?'Saving…':'Save quiz'}</button>{bank&&<BankSheet close={()=>setBank(false)} onAdd={addFromBank} toast={toast}/>}
    {id&&<button className="btn danger" onClick={del}>Delete quiz</button>}</div></>}

function BankSheet({close,onAdd,toast}){
  const [q,setQ]=useState(''),[tag,setTag]=useState(''),[mine,setMine]=useState(false),[d,setD]=useState(null),[sel,setSel]=useState({}),[n,setN]=useState(0)
  useEffect(()=>{const t=setTimeout(()=>api('/bank?limit=30&q='+encodeURIComponent(q)+'&tag='+encodeURIComponent(tag)+(mine?'&mine=true':'')).then(setD).catch(e=>toast(e.message)),250);return()=>clearTimeout(t)},[q,tag,mine,n,toast])
  const picked=Object.values(sel),more=async()=>{try{const r=await api('/bank?limit=30&offset='+d.items.length+'&q='+encodeURIComponent(q)+'&tag='+encodeURIComponent(tag)+(mine?'&mine=true':''));setD({...d,items:[...d.items,...r.items]})}catch(e){toast(e.message)}}
  const flip=x=>{const c={...sel};c[x.id]?delete c[x.id]:c[x.id]=x;setSel(c)}
  const del=async x=>{if(!confirm('Delete this question from the bank for everyone? Quizzes that already use it keep their copy.'))return;try{await api('/bank/'+x.id,{method:'DELETE'});const c={...sel};delete c[x.id];setSel(c);setN(n+1)}catch(e){toast(e.message)}}
  return <Sheet close={close}><h3>Question bank</h3><p className="known">Questions shared by every teacher. Adding one puts a copy in this quiz, so later changes to the bank never alter a quiz students are taking.</p>
    <div className="search"><Search size={18}/><input type="search" aria-label="Search the bank" placeholder="Search questions, tags or source" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label="Filter by tag" value={tag} onChange={e=>setTag(e.target.value)}><option value="">All tags</option>{(d?.tags||[]).map(t=><option key={t} value={t}>{t}</option>)}</select>
      <label className="chk" style={{padding:0}}><input type="checkbox" checked={mine} onChange={e=>setMine(e.target.checked)}/> Only mine</label></div>
    {!d?<div className="sk"/>:!d.items.length?<p className="known">{q||tag||mine?'Nothing matches that.':'The bank is empty. Use “Save to bank” in any quiz to start it.'}</p>:d.items.map(x=><div key={x.id} className="row"><label className="chk" style={{alignItems:'flex-start',flex:1}}><input type="checkbox" checked={!!sel[x.id]} onChange={()=>flip(x)}/><span><span style={{display:'block'}}>{x.text.length>180?x.text.slice(0,180)+'…':x.text}</span><small>{x.options.length} answers{x.tags.length>0&&' · '+x.tags.join(', ')} · by {x.owner||'someone'}{x.uses>0&&' · used '+pl(x.uses,'time')}</small></span></label>{x.can_edit&&<button className="ic sm" aria-label="Delete from the bank" onClick={()=>del(x)}><Trash2 size={16}/></button>}</div>)}
    {d&&d.items.length<d.total&&<button className="btn ghost" onClick={more}>Show more ({d.total-d.items.length} left)</button>}
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
const FIELD_LABEL={title:'Title',content:'Notes',sample_content:'Sample answer',question_pattern:'Question pattern',guideline:'Answer guideline'}
const lineDiff=(a,b)=>{const x=a.split('\n'),y=b.split('\n'),n=x.length,m=y.length
  if(n*m>250000)return [...x.map(t=>({k:'del',t})),...y.map(t=>({k:'add',t}))]  // very long texts: show both rather than spend the time
  const L=Array.from({length:n+1},()=>new Uint16Array(m+1))
  for(let i=n-1;i>=0;i--)for(let j=m-1;j>=0;j--)L[i][j]=x[i]===y[j]?L[i+1][j+1]+1:Math.max(L[i+1][j],L[i][j+1])
  const out=[];let i=0,j=0
  while(i<n&&j<m){if(x[i]===y[j]){out.push({k:'same',t:x[i]});i++;j++}else if(L[i+1][j]>=L[i][j+1])out.push({k:'del',t:x[i++]});else out.push({k:'add',t:y[j++]})}
  while(i<n)out.push({k:'del',t:x[i++]});while(j<m)out.push({k:'add',t:y[j++]});return out}
function HistorySheet({tid,close,done,toast}){
  const [list,setList]=useState(null),[v,setV]=useState(null),[busy,setBusy]=useState(false)
  useEffect(()=>{api(`/topics/${tid}/versions`).then(setList).catch(e=>{toast(e.message);close()})},[tid,toast,close])
  const open=async x=>{try{setV({...(await api('/topic-versions/'+x.id)),current:x.current})}catch(e){toast(e.message)}}
  const restore=async()=>{if(!confirm('Put this version back? What is there now stays in the history, so you can undo it.'))return;setBusy(true)
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
  const [id,setId]=useState(first),[editing,setEditing]=useState(false),[v,setV]=useState(0),[t,setT]=useState(null),[tab,setTab]=useState('notes'),[known,setKnown]=useState([]),[ai,setAi]=useState({}),[aiOk,setAiOk]=useState(null),[ownKey,setOwnKey]=useState(false),[aiMsg,setAiMsg]=useState(''),[busy,setBusy]=useState(false),[bm,setBm]=useState(false),[pv,setPv]=useState(false),[hist,setHist]=useState(false),[cp,setCp]=useState(false)
  const opened=useRef(false),jump=nid=>{opened.current=false;setT(null);setTab('notes');setAi({});setAiMsg('');setKnown([]);setEditing(false);setId(nid);window.scrollTo(0,0)},learn=r=>setT(p=>({...p,status:r.status,overdue:r.overdue,late:r.late,completed_at:r.completed_at}))
  useEffect(()=>{api('/topics/'+id).then(x=>{setT(x);setBm(!!x.bookmarked)
    if(!opened.current){opened.current=true;api(`/topics/${id}/read`,{method:'POST'}).then(r=>{setKnown(r.known);learn(r)}).catch(()=>{})}}).catch(e=>toast(e.message))},[id,v])  // opening starts it, after the page has loaded
  const setDone=async on=>{try{learn(await api(`/topics/${id}/complete`,{method:on?'PUT':'DELETE'}));toast(on?'Marked as completed':'Marked as not completed')}catch(e){toast(e.message)}}
  useEffect(()=>{api('/ai/status').then(r=>{setAiOk(r.available);setOwnKey(!!r.own_key)}).catch(()=>{})},[id])
  const ask=async k=>{setBusy(true);setAiMsg('');try{const r=await api(`/topics/${id}/ai/${k}`);setAi(a=>({...a,[k]:r}))}catch(e){setAiMsg(e.message)}setBusy(false)}
  if(editing)return <TopicEditor role={role} toast={toast} edit={{id}} done={()=>{setEditing(false);setV(v+1)}} cancel={()=>setEditing(false)}/>
  if(!t)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const flip=async()=>{const on=!bm;setBm(on);try{await api(`/topics/${id}/bookmark`,{method:on?'PUT':'DELETE'});toast(on?'Bookmarked':'Bookmark removed')}catch(e){setBm(!on);toast(e.message)}}
  const view=k=>ai[k]?<div className="prose">{ai[k].cached&&<span className="chip">Saved answer · no tokens used</span>}<Md>{ai[k].text}</Md></div>
    :aiOk===false?<p className="known">{ownKey?'Add your own DeepSeek API key under “My AI key” in the menu to use AI help.':'AI unavailable. Try again later.'}</p>
    :<><button className="btn" disabled={busy} onClick={()=>ask(k)}><Sparkles size={16}/> {busy?'Thinking…':k==='explain'?'Explain it to me':'Show a sample answer'}</button>{aiMsg&&<p className="known">{aiMsg}</p>}</>
  return <><Bar title={t.title} sub={[t.program,t.semester,t.course,t.unit].filter(Boolean).join(' › ')} back={back} right={<button className={'ic'+(bm?' on':'')} aria-label={bm?'Remove bookmark':'Bookmark this topic'} aria-pressed={bm} onClick={flip}><Bookmark fill={bm?'currentColor':'none'}/></button>}/><div className="main">
    {t.can_edit&&pv&&<div className="qbox" style={{marginTop:0}}><b>Previewing as a student</b><p className="known" style={{margin:'4px 0 8px'}}>This is what students see: no editing buttons, and drafts show as unavailable to them.</p><button className="btn ghost" style={{marginTop:0}} onClick={()=>setPv(false)}>Back to editing</button></div>}
    {t.can_edit&&!pv&&<div className="two" style={{marginBottom:12}}><button className="btn ghost" style={{marginTop:0}} onClick={()=>setEditing(true)}><Pencil size={16}/> Edit topic</button>
      <button className="btn ghost" style={{marginTop:0}} onClick={async()=>{try{await api(`/topics/${id}/publish`,{method:'PUT',body:{published:!t.published}});toast(t.published?'Moved to drafts':'Published');setV(v+1)}catch(e){toast(e.message)}}}>{t.published?<><EyeOff size={16}/> Unpublish</>:<><Eye size={16}/> Publish</>}</button></div>}
    <div className="qbox" style={{marginTop:0}}><div className="row"><div>{t.learning_due_at?when(t.learning_due_at):'No deadline'}<small>Learn by</small></div>{t.overdue&&role==='student'&&<span className="pill off">Overdue</span>}</div>
      {role==='student'&&<><div className="row"><div>{STATUS[t.status]}{t.status==='completed'&&t.completed_at&&' on '+when(t.completed_at)+(t.late?', after the deadline':'')}<small>Your status</small></div></div>
        {t.status==='completed'?<button className="btn ghost" onClick={()=>setDone(false)}>Mark as not completed</button>:<button className="btn" onClick={()=>setDone(true)}><Check size={16}/> Mark as completed</button>}</>}</div>
    {t.can_edit&&!pv&&<><button className="tool" onClick={()=>setPv(true)}><Eye size={14}/> Preview as student</button><button className="tool" onClick={()=>setHist(true)}><History size={14}/> Version history</button></>}
    {role!=='student'&&!pv&&<button className="tool" onClick={()=>setCp(true)}><Copy size={14}/> Copy to another course</button>}
    {cp&&<CopySheet kind="topic" id={id} title={t.title} toast={toast} close={()=>setCp(false)}/>}
    {hist&&<HistorySheet tid={id} toast={toast} close={()=>setHist(false)} done={()=>{setHist(false);setV(v+1)}}/>}
    {t.can_edit&&!t.published&&<p className="known" style={{marginTop:0}}>Draft · students cannot see it</p>}
    <div className="tabs">{[['notes','Notes'],['explain','Explain'],['answer','Sample answer']].map(([k,l])=><button key={k} className={tab===k?'on':''} onClick={()=>setTab(k)}>{l}</button>)}</div>
    {known.length>0&&tab==='explain'&&<p className="known">You’ve already covered: {known.join(', ')}</p>}
    {tab==='notes'&&<div className="prose"><Md>{t.content||'No notes yet.'}</Md>{t.question_pattern&&<><h3>Question pattern</h3><Md>{t.question_pattern}</Md></>}{t.guideline&&<><h3>Answer guideline</h3><Md>{t.guideline}</Md></>}</div>}
    {tab==='explain'&&view('explain')}{tab==='answer'&&view('answer')}
    {t.nav&&t.nav.total>1&&<nav className="pager" aria-label="Topics in this unit"><button className="btn ghost" disabled={!t.nav.prev} onClick={()=>jump(t.nav.prev.id)} aria-label={t.nav.prev?'Previous topic: '+t.nav.prev.title:'No previous topic'}><ChevronLeft size={18}/><span>{t.nav.prev?t.nav.prev.title:'Previous'}</span></button>
      <small>{t.nav.position} of {t.nav.total}</small>
      <button className={'btn'+(t.nav.next?'':' ghost')} disabled={!t.nav.next} onClick={()=>jump(t.nav.next.id)} aria-label={t.nav.next?'Next topic: '+t.nav.next.title:'No next topic'}><span>{t.nav.next?t.nav.next.title:'Next'}</span><ChevronRight size={18}/></button></nav>}</div></>}

function TopicEditor({role,toast,done,cancel,edit,unitId}){  // edit = {id} of a topic, or null for a new one in unitId
  const fac=role==='faculty',[prev,setPrev]=useState(false),[up,setUp]=useState(false),fileRef=useRef(null),taRef=useRef(null),[busy,setBusy]=useState(false)
  const [tree,setTree]=useState([]),[f,setF]=useState({title:'',unit_id:unitId||'',content:'',sample_content:'',question_pattern:'',guideline:'',published:!fac,due:''}),[cid,setCid]=useState(null)
  useEffect(()=>{api('/tree').then(setTree).catch(()=>{});if(edit)api('/topics/'+edit.id).then(t=>{setCid(t.course_id);setF({title:t.title,unit_id:t.unit_id||'',content:t.content||'',sample_content:t.sample_content||'',question_pattern:t.question_pattern||'',guideline:t.guideline||'',published:t.published!==false,due:localInput(t.learning_due_at)})}).catch(e=>toast(e.message))},[])
  const set=k=>e=>setF({...f,[k]:e.target.value})
  const pickImg=async e=>{const file=e.target.files[0];e.target.value='';if(!file)return;if(file.size>3*1024*1024)return toast('Image is too large. Keep it under 3 MB.')
    setUp(true);try{const r=await fetch('/api/uploads',{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream',Authorization:'Bearer '+localStorage.t},body:file});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Upload failed')
      const pos=taRef.current?.selectionStart??f.content.length;setF({...f,content:f.content.slice(0,pos)+`\n\n![Describe the image](${d.url})\n\n`+f.content.slice(pos)});toast('Image added')}catch(er){toast(er.message)}setUp(false)}
  const all=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared&&c.editable).flatMap(c=>c.units.map(n=>({...n,course_id:c.id,label:`${c.name} › ${n.name}`})))))
  const units=role==='admin'?all:all.filter(n=>n.course_id===cid)  // faculty move a topic only between units of its own course
  const here=all.find(n=>n.id===+f.unit_id)
  const save=async()=>{setBusy(true);try{await api(edit?'/topics/'+edit.id:'/topics',{method:edit?'PUT':'POST',body:{...f,due:undefined,unit_id:+f.unit_id,published:f.published!==false,learning_due_at:f.due?new Date(f.due).toISOString():null}});toast(edit?'Changes saved':'Topic added');done()}catch(e){toast(e.message)}setBusy(false)}
  const T=(k,l,ph)=><><label>{l}</label><textarea placeholder={ph} value={f[k]} onChange={set(k)}/></>
  return <><Bar title={edit?'Edit topic':'New topic'} sub={here?.label} back={cancel}/><div className="main">
    {edit&&units.length>1&&<><label>Unit</label><select value={f.unit_id} onChange={set('unit_id')}>{units.map(o=><option key={o.id} value={o.id}>{o.label}</option>)}</select></>}
    <label>Topic title</label><input value={f.title} onChange={set('title')} placeholder="First law of thermodynamics"/>
    <label>Topic content</label><div className="tools"><button type="button" disabled={up} onClick={()=>fileRef.current.click()}>{up?'Uploading…':'Add image'}</button><button type="button" onClick={()=>setPrev(!prev)}>{prev?'Back to editing':'Preview'}</button></div>
    <input ref={fileRef} type="file" hidden accept="image/png,image/jpeg,image/gif,image/webp" onChange={pickImg}/>
    {prev?<div className="prose"><Md>{f.content||'Nothing to preview yet.'}</Md></div>:<textarea ref={taRef} placeholder="Paste notes or syllabus text" value={f.content} onChange={set('content')}/>}
    <p className="known">{'Equations: $x^2$ inline. For a centred block, put $$ on its own line above and below the equation. Chemistry: $\\ce{CaCO3 + CO2 + H2O -> Ca(HCO3)2}$'}</p>{T('question_pattern','Question pattern','e.g. 2 marks: define · 13 marks: derive + numerical')}
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

function Bookmarks({toast,role}){
  const [tree,setTree]=useState(null),[sem,setSem]=useState(null),[course,setCourse]=useState(null),[unit,setUnit]=useState(null),[t,setT]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t])
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast} role={role}/>
  if(!tree)return <><Bar title="Bookmarks"/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const marks=u=>u.topics.filter(x=>x.bookmarked),cnt=c=>c.units.reduce((n,u)=>n+marks(u).length,0)
  const sems=tree.flatMap(p=>p.semesters.map(sm=>({...sm,prog:p.name,courses:sm.courses.filter(c=>cnt(c)>0)}))).filter(sm=>sm.courses.length)
    .sort((a,b)=>a.prog.localeCompare(b.prog)||(a.number??99)-(b.number??99)||a.id-b.id)
  const multi=new Set(sems.map(x=>x.prog)).size>1,total=sems.reduce((n,x)=>n+x.courses.reduce((m,c)=>m+cnt(c),0),0)
  const sm=sems.find(x=>x.id===sem)||sems[0],co=sm?.courses.find(x=>x.id===course)||sm?.courses[0],un=co?.units.find(x=>x.id===unit)
  const drop=async id=>{try{await api(`/topics/${id}/bookmark`,{method:'DELETE'});setTree(unmarked(tree,id));toast('Bookmark removed')}catch(e){toast(e.message)}}
  return <><Bar title="Bookmarks" sub={total?total+(total===1?' topic saved':' topics saved'):'Nothing saved yet'}/><div className="main">
    {!sm&&<p className="known">Open any topic and tap the bookmark icon to save it here. Your list is arranged by semester or year, course and unit.</p>}
    {sm&&<>
      <div className="chips" role="group" aria-label="Semester or year">{sems.map(x=><button key={x.id} className={'sbtn'+(x.id===sm.id?' on':'')} aria-pressed={x.id===sm.id} onClick={e=>{setSem(x.id);setCourse(null);setUnit(null);tabTo(e)}}>
        <span className="lbl">{multi&&x.prog+' · '}{x.name}</span><em>{x.courses.reduce((n,c)=>n+cnt(c),0)}</em></button>)}</div>
      <div className="tabs scroll" role="tablist" aria-label="Course">{sm.courses.map(c=><button key={c.id} role="tab" aria-selected={c.id===co.id} className={c.id===co.id?'on':''} onClick={e=>{setCourse(c.id);setUnit(null);tabTo(e)}}>
        <span className="lbl">{c.name}</span><em>{cnt(c)}</em></button>)}</div>
      {!un&&co.units.map((u,i)=><div key={u.id} className="card"><button className="hit" onClick={()=>setUnit(u.id)}><span className="dot" style={{background:COL[i%5]}}>{i+1}</span>
        <div><b>{u.name}</b><span>{marks(u).length?marks(u).length+(marks(u).length===1?' bookmarked topic':' bookmarked topics'):'Nothing bookmarked'}</span></div></button></div>)}
      {un&&<><button className="link" onClick={()=>setUnit(null)}><ChevronLeft size={16}/>All units in {co.name}</button>
        <div className="tabs scroll" role="tablist" aria-label="Unit">{co.units.map(u=><button key={u.id} role="tab" aria-selected={u.id===un.id} className={u.id===un.id?'on':''} onClick={e=>{setUnit(u.id);tabTo(e)}}>
          <span className="lbl">{u.name}</span><em>{marks(u).length}</em></button>)}</div>
        {marks(un).map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={()=>setT(x.id)}><span className="dot" style={{background:COL[i%5]}}>{x.title[0]}</span><div><b>{x.title}</b></div><Mark s={x.status}/></button>
          <button className="ic sm on" aria-label={'Remove bookmark: '+x.title} onClick={()=>drop(x.id)}><Bookmark size={16} fill="currentColor"/></button></div>)}
        {!marks(un).length&&<p className="known">No bookmarked topics in this unit.</p>}</>}
    </>}</div></>}

const Sheet=({close,children})=><div className="scrim" onClick={close}><div className="sheet" onClick={e=>e.stopPropagation()}>{children}</div></div>
const useRun=(toast,load)=>async(fn,m)=>{try{await fn();toast(m);load&&load()}catch(e){toast(e.message)}}

const download=(name,text)=>{const l=document.createElement('a');l.href=URL.createObjectURL(new Blob([text],{type:'text/csv'}));l.download=name;l.click()}
const USER_TEMPLATE=`name,email,password,role,program,semester
Asha Kumar,asha@example.com,,student,B.E. Mechanical Engineering,3
Ravi S,ravi@example.com,Welcome#2026,student,B.E. Mechanical Engineering,1
`
const SEMS=[1,2,3,4,5,6,7,8],termOf=(progs,id)=>progs.find(p=>String(p.id)===String(id))?.term||'Semester'

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
  if(act.kind==='set_placement')return <Sheet close={close}><h3>Move {pl(ids.length,'user')}</h3><p className="known">Sets the program and semester or year of the selected students. Faculty and admins in the selection are skipped.</p>
    <label htmlFor="bp">Program</label><select id="bp" value={p} onChange={e=>setP(e.target.value)}><option value="">Choose a program</option>{progs.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select>
    <label htmlFor="bs">{termOf(progs,p)}</label><select id="bs" value={s} onChange={e=>setS(e.target.value)}><option value="">Not set</option>{SEMS.map(n=><option key={n} value={n}>{termOf(progs,p)} {n}</option>)}</select>
    <button className="btn" disabled={busy||!p} onClick={run}>{busy?'Working…':'Move'}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>
  const [t,d,l]=BULK_TEXT[act.kind]
  return <Sheet close={close}><h3>{t.replace('these',ids.length===1?'this':'these')}</h3><p className="known">{pl(ids.length,'account')} selected. {d}</p>
    <button className={'btn'+(act.kind==='disable'?' danger':'')} disabled={busy} onClick={run}>{busy?'Working…':l}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}
function Users({toast,me}){
  const [items,setItems]=useState([]),[total,setTotal]=useState(0),[q,setQ]=useState(''),[prog,setProg]=useState(''),[sem,setSem]=useState(''),[order,setOrder]=useState('role'),[progs,setProgs]=useState([])
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef(),[selMode,setSelMode]=useState(false),[sel,setSel]=useState([]),[act,setAct]=useState(null)
  const url=offset=>`/admin/users?q=${encodeURIComponent(q)}&order=${order}&limit=50&offset=${offset}`+(prog?'&program_id='+prog:'')+(sem?'&semester='+sem:'')
  const load=()=>api(url(0)).then(r=>{setItems(r.items);setTotal(r.total)}).catch(e=>toast(e.message))
  useEffect(()=>{const t=setTimeout(load,250);return()=>clearTimeout(t)},[q,prog,sem,order])
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name,term:p.term})))).catch(()=>{})},[])
  const more=()=>api(url(items.length)).then(r=>{setItems([...items,...r.items]);setTotal(r.total)}).catch(e=>toast(e.message))
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/users/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/users/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const cell=v=>'"'+String(v).replace(/"/g,'""')+'"',r=bulk?.res,filtered=q||prog||sem,lab=prog?termOf(progs,prog):progs.every(x=>x.term==='Semester')?'Semester':'Term'
  if(view)return <UserDetail id={view} me={me} progs={progs} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title="Users" sub={total+(filtered?' matches':' accounts')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label="Search users" placeholder="Search name, email, ID, program, semester or year" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters">
      <select aria-label="Filter by program" value={prog} onChange={e=>setProg(e.target.value)}><option value="">All programs</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select aria-label="Filter by semester or year" value={sem} onChange={e=>setSem(e.target.value)}><option value="">{lab==='Term'?'All terms':'All '+lab.toLowerCase()+'s'}</option>{SEMS.map(n=><option key={n} value={n}>{lab} {n}</option>)}</select>
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
    {items.length<total&&<button className="btn ghost" onClick={more}>Show more</button>}
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {selMode&&sel.length>0&&<div className="actbar" role="toolbar" aria-label="Actions for selected users"><b>{sel.length} selected</b>
      <button className="tool" onClick={()=>setAct({kind:'set_placement'})}>Move…</button><button className="tool" onClick={()=>setAct({kind:'disable'})}>Disable</button><button className="tool" onClick={()=>setAct({kind:'enable'})}>Enable</button><button className="tool" onClick={()=>setAct({kind:'reset_passwords'})}>Reset passwords</button></div>}
    {act&&<BulkSheet act={act} ids={sel} progs={progs} toast={toast} close={()=>setAct(null)} done={r=>{setAct({kind:'result',r});setSel([]);load()}}/>}
    {ed&&<UserSheet u={ed} me={me} progs={progs} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet close={()=>setBulk(null)}>
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
  const [u,setU]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[pw,setPw]=useState(null),[busy,setBusy]=useState(false),[asg,setAsg]=useState(null),[ctree,setCtree]=useState([])
  const load=()=>api('/admin/users/'+id).then(setU).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id]);useEffect(()=>{if(u?.role==='faculty')api('/tree').then(setCtree)},[u?.role])
  if(!u)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const reset=async()=>{setBusy(true);try{const r=await api(`/admin/users/${u.id}/reset-password`,{method:'POST'});setAsk(false);setPw(r.password)}catch(e){toast(e.message)}setBusy(false)}
  const copy=async()=>{try{await navigator.clipboard.writeText(pw);toast('Copied')}catch{toast('Press and hold the password to copy it')}}
  const row=(v,l)=><div className="row"><div>{v}<small>{l}</small></div></div>
  const allCourses=ctree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared).map(c=>({id:c.id,owner_id:c.owner_id,owner:c.owner,label:`${p.name} › ${s.name} › ${c.name}`}))))
  const saveAsg=async()=>{try{await api(`/admin/users/${u.id}/courses`,{method:'PUT',body:{course_ids:asg}});toast('Courses updated');setAsg(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={u.name} sub={u.email} back={back}/><div className="main">
    <div className="stats"><div className="stat"><b>{u.topics_read}</b>Topics read</div><div className="stat"><b>{u.reads}</b>Total reads</div></div>
    <h3 style={{margin:'24px 0 4px'}}>Profile</h3>
    {row({admin:'Admin',faculty:'Faculty'}[u.role]||'Student','Role')}{row(u.active?'Active':'Disabled','Status')}{row(u.program||'Not set','Program')}{row(u.semester||'Not set',termOf(progs,u.program_id))}{u.self_registered&&<>{row(u.institution||'—','Institution')}{row(u.id_number||'—','ID number')}{row(u.phone||'—','Phone')}{row(u.own_ai_key?'Has added their own key':'No key yet · AI is off for them','AI (self-registered, uses their own key)')}</>}{row(day(u.last_active),'Last active')}
    {u.role==='faculty'&&<><h3 style={{margin:'28px 0 4px'}}>Courses they own</h3>{(u.course_ids||[]).length?allCourses.filter(c=>u.course_ids.includes(c.id)).map(c=><div className="row" key={c.id}><div>{c.label}</div></div>):<p className="known">None yet. They can read published content but edit nothing until they own a course.</p>}<button className="btn ghost" onClick={()=>setAsg([...(u.course_ids||[])])}>Assign courses</button></>}
    <h3 style={{margin:'28px 0 4px'}}>Recently read</h3>
    {u.recent.length?u.recent.map((x,i)=><div className="row" key={i}><div>{x.title}<small>{x.reads} reads, last {day(x.last_read)}</small></div></div>):<p className="known">No reading activity yet.</p>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>Edit</button><button className="btn" onClick={()=>setAsk(true)}>Reset password</button></div></div>
    {ed&&<UserSheet u={u} me={me} progs={progs} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>Reset password?</h3><p className="known">This gives {u.name} a new password and replaces the old one straight away. You will see the new password once.</p>
      <button className="btn danger" disabled={busy} onClick={reset}>Reset password</button><button className="btn ghost" onClick={()=>setAsk(false)}>Cancel</button></Sheet>}
    {pw&&<Sheet close={()=>setPw(null)}><h3>New password</h3><p className="known">Share this with {u.name} now. It is not shown again.</p><div className="pw">{pw}</div>
      <button className="btn" onClick={copy}>Copy password</button><button className="btn ghost" onClick={()=>setPw(null)}>Done</button></Sheet>}
    {asg&&<Sheet close={()=>setAsg(null)}><h3>Courses {u.name} owns</h3><p className="known">The owner adds and edits the units, topics and quizzes of a course. Each course has one owner, so ticking a course another person owns moves it to {u.name}.</p>{allCourses.map(c=><label key={c.id} className="chk"><input type="checkbox" checked={asg.includes(c.id)} onChange={e=>setAsg(e.target.checked?[...asg,c.id]:asg.filter(i=>i!==c.id))}/> {c.label}{c.owner_id&&c.owner_id!==u.id?` (now ${c.owner})`:''}</label>)}<button className="btn" onClick={saveAsg}>Save</button><button className="btn ghost" onClick={()=>setAsg(null)}>Cancel</button></Sheet>}</>}

function UserSheet({u,me,progs,close,done,toast}){
  const isNew=!u.id,self=u.id===me.id,[busy,setBusy]=useState(false)
  const [f,setF]=useState({name:u.name||'',email:u.email||'',role:u.role||'student',active:u.active??true,password:'',program_id:u.program_id||'',semester:u.semester||''}),set=k=>e=>setF({...f,[k]:e.target.value})
  const save=async()=>{setBusy(true);try{
    const enrol={program_id:f.program_id?+f.program_id:null,semester:f.semester?+f.semester:null}
    if(isNew)await api('/admin/users',{method:'POST',body:{...f,...enrol}})
    const r=isNew?null:await api('/admin/users/'+u.id,{method:'PATCH',body:{name:f.name,email:f.email,...enrol,...(self?{}:{role:f.role,active:f.active})}})
    toast(isNew?'User added':r.courses_needing_owner?`Saved. ${r.courses_needing_owner} course(s) they own need a new owner.`:'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?'New user':'Edit user'}</h3>
    <label>Name</label><input value={f.name} onChange={set('name')}/><label>Email</label><input type="email" value={f.email} onChange={set('email')}/>
    <label>Program</label><select value={f.program_id} onChange={set('program_id')}><option value="">Not set</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <label>{termOf(progs,f.program_id)}</label><select value={f.semester} onChange={set('semester')}><option value="">Not set</option>{SEMS.map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>Role</label><select disabled={self} value={f.role} onChange={set('role')}><option value="student">Student</option><option value="faculty">Faculty</option><option value="admin">Admin</option></select>
    <label>Status</label><select disabled={self} value={f.active?'1':'0'} onChange={e=>setF({...f,active:e.target.value==='1'})}><option value="1">Active</option><option value="0">Disabled</option></select>
    {isNew?<><label>Password (8+ characters)</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/></>
      :<p className="known" style={{marginTop:14}}>To give this person a new password, use Reset password on their page.</p>}
    {self&&<p className="known">You can't change your own role or status.</p>}
    <button className="btn" disabled={busy} onClick={save}>{isNew?'Add user':'Save changes'}</button></Sheet>}

function Programs({toast,onOpen}){
  const [items,setItems]=useState([]),[total,setTotal]=useState(0),[q,setQ]=useState(''),[order,setOrder]=useState('name')
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef()
  const url=offset=>`/admin/programs?q=${encodeURIComponent(q)}&order=${order}&limit=50&offset=${offset}`
  const load=()=>api(url(0)).then(r=>{setItems(r.items);setTotal(r.total)}).catch(e=>toast(e.message))
  useEffect(()=>{const t=setTimeout(load,250);return()=>clearTimeout(t)},[q,order])
  const more=()=>api(url(items.length)).then(r=>{setItems([...items,...r.items]);setTotal(r.total)}).catch(e=>toast(e.message))
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const r=bulk?.res,made=r&&Object.entries(r.created).filter(([,v])=>v).map(([k,v])=>v+' '+k).join(', ')||'nothing new'
  if(view)return <ProgramDetail id={view} onOpen={onOpen} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title="Programs" sub={total+(q?' matches':' programs')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label="Search programs" placeholder="Search program, semester, year or course" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label="Sort by" value={order} onChange={e=>setOrder(e.target.value)}><option value="name">Sort: name</option><option value="students">Sort: most students</option><option value="newest">Sort: newest first</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>New program</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>Bulk upload</button></div>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead p" aria-hidden="true"><span>Program</span><span>Courses</span><span>Students</span></div>}
    {items.map(x=><button key={x.id} className="utr p" onClick={()=>setView(x.id)} aria-label={'Open '+x.name}>
      <span className="nm"><span className="dot" style={{background:COL[x.id%5]}}>{(x.name||'?')[0]}</span><span className="tx"><b>{x.name}</b><small className="sub">{pl(x.semesters,x.term.toLowerCase())}, {x.topics} topics</small></span></span>
      <span className="sn">{x.courses}</span><span className="sn">{x.students}</span></button>)}
    {!items.length&&<p className="known">{q?'No program matches that search.':'No programs yet. Add one or bulk upload a CSV.'}</p>}
    {items.length<total&&<button className="btn ghost" onClick={more}>Show more</button>}
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {ed&&<ProgramSheet p={ed} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet close={()=>setBulk(null)}>
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
  return <Sheet close={close}><h3>Start a new term</h3><p className="known">Moves every active student of {p.name} up one {p.term?.toLowerCase()||'semester'}. Do this once, when the new term begins.</p>
    {!r?<div className="sk"/>:<div className="qbox" style={{marginTop:0}}>
      <div className="row"><div>{pl(r.moved,'student')}<small>{r.moved===1?'moves':'move'} up one {r.term.toLowerCase()}</small></div></div>
      <div className="row"><div>{pl(r.finishing,'student')}<small>{r.finishing===1?'is':'are'} in the last {r.term.toLowerCase()} ({r.term} {r.last_semester}){r.finishing_names.length?': '+r.finishing_names.join(', ')+(r.finishing>r.finishing_names.length?'…':''):''}</small></div></div>
      {r.unplaced>0&&<div className="row"><div>{pl(r.unplaced,'student')}<small>{r.unplaced===1?'has':'have'} no {r.term.toLowerCase()} set and are left alone: {r.unplaced_names.join(', ')}</small></div></div>}</div>}
    <label htmlFor="fin">Students finishing the program</label><select id="fin" value={fin} onChange={e=>setFin(e.target.value)}><option value="keep">Leave them as they are</option><option value="deactivate">Switch their accounts off</option></select>
    <button className="btn" disabled={busy||!r||(!r.moved&&!(fin==='deactivate'&&r.finishing))} onClick={go}>{busy?'Working…':'Apply'}</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}
function ProgramDetail({id,back,onOpen,toast}){
  const [p,setP]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[busy,setBusy]=useState(false),[addSem,setAddSem]=useState(false),[term,setTerm]=useState(false)
  const load=()=>api('/admin/programs/'+id).then(setP).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id])
  if(!p)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const del=async()=>{setBusy(true);try{await api('/programs/'+p.id,{method:'DELETE'});toast('Program deleted');back()}catch(e){toast(e.message);setBusy(false)}}
  const row=(v,l,k)=><div className="row" key={k}><div>{v}<small>{l}</small></div></div>
  return <><Bar title={p.name} sub={pl(p.semesters,p.term.toLowerCase())+(p.pattern==='year'?' · annual':'')} back={back}/><div className="main">
    <div className="stats">{[['semesters',p.term+'s'],['courses','Courses'],['topics','Topics'],['students','Students']].map(([k,l])=><div className="stat" key={k}><b>{p[k]}</b>{l}</div>)}</div>
    <h3 style={{margin:'24px 0 4px'}}>{p.term}s</h3>
    {p.semester_list.length?p.semester_list.map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={()=>onOpen([p.id,x.id])}><span className="dot" style={{background:COL[i%5]}}>{x.number||'?'}</span><div><b>{x.name}</b><span>{(x.number?'':'No '+p.term.toLowerCase()+' number set · ')+x.courses+' courses, '+x.topics+' topics'}</span></div></button></div>):<p className="known">No {p.term.toLowerCase()}s yet.</p>}
    <button className="btn ghost" onClick={()=>setAddSem(true)}>Add {p.term.toLowerCase()}</button>
    <h3 style={{margin:'28px 0 4px'}}>Students</h3>
    {p.student_list.length?p.student_list.map(u=>row(u.name,(u.semester?p.term+' '+u.semester:p.term+' not set')+(u.active?'':', disabled'),u.id)):<p className="known">No students are enrolled yet. Set a program on a user's page.</p>}
    {p.students>p.student_list.length&&<p className="known">Showing {p.student_list.length} of {p.students}. Use Users to see everyone.</p>}
    {p.students>0&&<button className="btn ghost" onClick={()=>setTerm(true)}>Start a new term (move students up)</button>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>Edit</button><button className="btn danger" onClick={()=>setAsk(true)}>Delete</button></div>
    <button className="btn ghost" onClick={()=>onOpen([p.id])}>Open {p.term.toLowerCase()}s and courses</button></div>
    {term&&<RolloverSheet p={p} toast={toast} close={()=>setTerm(false)} done={()=>{setTerm(false);load()}}/>}
    {ed&&<ProgramSheet p={p} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {addSem&&<SemesterSheet sem={{}} pid={p.id} term={p.term} toast={toast} close={()=>setAddSem(false)} done={()=>{setAddSem(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>Delete “{p.name}”?</h3><p className="known">This permanently deletes {pl(p.semesters,p.term.toLowerCase())}, {p.courses} courses, {p.units} units and {p.topics} topics, including their saved AI answers.{p.students>0&&` The ${p.students} enrolled students keep their accounts but lose their program.`}</p>
      <button className="btn danger" disabled={busy} onClick={del}>Delete program</button><button className="btn ghost" onClick={()=>setAsk(false)}>Keep it</button></Sheet>}</>}

function OwnerSheet({c,close,done,toast}){
  const faculty=useFaculty(true),[sel,setSel]=useState(c.owner_id||''),[busy,setBusy]=useState(false)
  const save=async()=>{if(String(sel)===String(c.owner_id||''))return close();setBusy(true);try{await api(`/courses/${c.id}/owner`,{method:'PUT',body:{user_id:sel?+sel:null}});toast('Owner updated');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>Owner of “{c.name}”</h3><p className="known">The owner adds and edits this course's units, topics and quizzes. Changing the owner keeps all content and student progress.{c.owner_problem&&c.owner_id?' '+c.owner_problem+'.':''}</p>
    <label>Owner (faculty)</label><select value={sel} onChange={e=>setSel(e.target.value)}><option value="">Not assigned</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner} (can't edit)</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    <button className="btn" disabled={busy} onClick={save}>Save</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}

function ProgramSheet({p,close,done,toast}){
  const isNew=!p.id,[name,setName]=useState(p.name||''),[pat,setPat]=useState(p.pattern||'semester'),[terms,setTerms]=useState(pat==='year'?4:8),[touched,setTouched]=useState(false),[busy,setBusy]=useState(false)
  const lab=pat==='year'?'Year':'Semester',pick=k=>{setPat(k);if(!touched)setTerms(k==='year'?4:8)}
  const save=async()=>{setBusy(true);try{const r=await api(isNew?'/programs':'/programs/'+p.id,{method:isNew?'POST':'PUT',body:{name,pattern:pat,...(isNew?{terms}:{})}});toast(isNew?(r.terms?`Program added with ${r.terms} ${lab.toLowerCase()}${r.terms===1?'':'s'}`:'Program added'):'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?'New program':'Edit program'}</h3>
    <label>Name</label><input value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==='Enter'&&save()} placeholder="B.E. Mechanical Engineering" autoFocus/>
    <p className="known" style={{marginTop:10}}>Names must be unique. The users CSV import matches programs by name.</p>
    <label id="pat">How is the program divided?</label><div role="group" aria-labelledby="pat" className="seg" style={{marginTop:0}}>{[['semester','Semesters','B.E., B.Tech, M.E.'],['year','Years','M.B.B.S, B.Sc, annual courses']].map(([k,l])=><button key={k} className={pat===k?'on':''} aria-pressed={pat===k} onClick={()=>pick(k)}>{l}</button>)}</div>
    <p className="known" style={{marginTop:6}}>{pat==='year'?'Annual pattern, for example M.B.B.S, B.Sc or law degrees. Students move up one year at a time.':'Semester pattern, for example B.E., B.Tech or M.E. Students move up one semester at a time.'}</p>
    {isNew?<><label htmlFor="nt">How many {lab.toLowerCase()}s?</label><select id="nt" value={terms} onChange={e=>{setTerms(+e.target.value);setTouched(true)}}>{[0,1,2,3,4,5,6,7,8].map(n=><option key={n} value={n}>{n===0?'None yet, I will add them myself':n}</option>)}</select>
      <p className="known" style={{marginTop:6}}>{terms?`${lab} 1${terms>1?` to ${lab} ${terms}`:''} ${terms>1?'are':'is'} created for you, so you can go straight to adding courses.`:'You can add them one by one later.'}</p></>
      :p.pattern&&pat!==p.pattern&&<p className="known" style={{marginTop:6}}>Terms still named “{p.pattern==='year'?'Year':'Semester'} n” are renamed to “{lab} n”. Terms you named yourself keep their names.</p>}
    <button className="btn" disabled={busy||!name.trim()} onClick={save}>{isNew?'Add program':'Save changes'}</button></Sheet>}

function Branding({toast,onSaved}){
  const [name,setName]=useState(''),[logo,setLogo]=useState(null),[busy,setBusy]=useState(false),file=useRef(null)
  useEffect(()=>{api('/config').then(c=>{setName(c.name);setLogo(c.logo)}).catch(()=>{})},[])
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;setBusy(true)
    try{const r=await fetch('/api/uploads',{method:'POST',headers:{Authorization:'Bearer '+localStorage.t,'Content-Type':f.type},body:f}),j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Upload failed');setLogo(j.url)}catch(x){toast(x.message)}setBusy(false)}
  const save=async body=>{setBusy(true);try{await api('/admin/branding',{method:'PUT',body});toast('Saved');onSaved()}catch(e){toast(e.message)}setBusy(false)}
  return <><h3 style={{margin:'0 0 4px'}}>Institution name and logo</h3><p className="known">Shown on the sign-in page and in the menu. Use a square PNG, JPG or WebP under 3 MB.</p>
    <div className="lpreview"><Logo src={logo} size={48}/><b>{name||'Name'}</b></div>
    <label htmlFor="inst">Name</label><input id="inst" value={name} maxLength={60} onChange={e=>setName(e.target.value)}/>
    <input ref={file} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={pick}/>
    <div className="two"><button className="btn ghost" disabled={busy} onClick={()=>file.current.click()}><Upload size={16}/> {logo?'Replace logo':'Upload logo'}</button>
      <button className="btn ghost" disabled={busy||!logo} onClick={()=>{setLogo(null);save({remove_logo:true,name})}}>Remove logo</button></div>
    <button className="btn" disabled={busy} onClick={()=>save({name,logo_url:logo||undefined})}>Save name and logo</button></>}
function AiConfig({toast,onBrand}){
  const [cfg,setCfg]=useState({}),[key,setKey]=useState(''),[model,setModel]=useState(''),[st,setSt]=useState({})
  const load=()=>{api('/admin/settings').then(c=>{setCfg(c);setModel(c.model)});api('/admin/stats').then(setSt)};useEffect(load,[])
  const run=useRun(toast,load)
  return <><Bar title="Settings" sub={cfg.key_set?'AI is on · key '+cfg.key_hint:'AI is off · no key yet'}/><div className="main"><Branding toast={toast} onSaved={onBrand}/><h3 style={{margin:'32px 0 4px'}}>AI</h3>
    <label>DeepSeek API key</label><input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder={cfg.key_set?'Leave blank to keep the current key':'sk-…'}/>
    <label>Model</label><input value={model} onChange={e=>setModel(e.target.value)} placeholder="deepseek-chat"/>
    <button className="btn" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{deepseek_key:key,model}}).then(()=>setKey('')),'AI settings saved')}>Save</button>
    {cfg.key_set&&<><button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/ai/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>Test the key</button>
      <button className="btn ghost" onClick={()=>confirm('Turn AI off for everyone? Students will see "AI unavailable" until you save a key again.')&&run(()=>api('/admin/settings',{method:'PUT',body:{remove_key:true}}),'AI is off')}>Remove the key (turn AI off)</button></>}
    <p className="known" style={{marginTop:20}}>One key serves every student added by staff (people who register themselves use their own key). Until a key is saved, students see “AI unavailable. Try again later.” Each topic is explained once and the answer is shared with every student. {(st.cached??0).toLocaleString()} answers are saved so far, which has saved about {(st.tokens_saved??0).toLocaleString()} tokens.</p>
    <h3 style={{margin:'28px 0 4px'}}>Self-registration</h3><SelfReg cfg={cfg} run={run}/>
    <h3 style={{margin:'28px 0 4px'}}>Password reset email</h3><p className="known">{cfg.mail_on?'On. People can reset their own password from the sign-in page.':'Off. The sign-in page tells people to ask an admin. To turn it on, set SMTP_HOST, SMTP_FROM and APP_URL in .env and restart (see .env.example).'}</p>
    {cfg.mail_on&&<button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/mail/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>Send a test email to me</button>}</div></>}

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
  return <><Bar title="Activity log" sub="Who changed what"/><div className="main"><input placeholder="Search by person or action" value={q} onChange={e=>setQ(e.target.value)}/>
    {rows.length?rows.map(x=><div className="row" key={x.id}><div>{describe(x.method,x.path)}{x.status>=400&&<span className="pill off" style={{marginLeft:8}}>{x.status===403?'Not allowed':'Failed'}</span>}<small>{x.user} · {new Date(x.at).toLocaleString()}</small></div></div>):<p className="known">{busy?'Loading…':'No activity yet.'}</p>}
    {rows.length<total&&<button className="btn ghost" disabled={busy} onClick={()=>load(true)}>Show more ({total-rows.length} older)</button>}</div></>}
const day=d=>d?new Date(d).toLocaleDateString(undefined,{day:'numeric',month:'short'}):'never'
const fetchFile=async(url,name,toast)=>{try{const r=await fetch('/api'+url,{headers:{Authorization:'Bearer '+localStorage.t}});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||'Download failed')
  const a=document.createElement('a');a.href=URL.createObjectURL(await r.blob());a.download=name;a.click();URL.revokeObjectURL(a.href)}catch(e){toast(e.message)}}
const Bar2=({v})=><div className="meter"><i style={{width:Math.min(100,v||0)+'%'}}/></div>
function CourseReports({toast,onOpen}){
  const [f,setF]=useState({p:0,s:0}),[rows,setRows]=useState(null),[progs,setProgs]=useState([])
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name,term:p.term,max:Math.max(0,...p.semesters.map(x=>x.number||0))||(p.term==='Year'?4:8)})))).catch(()=>{})},[])
  const pr=progs.find(x=>x.id===f.p),lab=pr?pr.term:progs.length&&progs.every(x=>x.term==='Semester')?'Semester':progs.length&&progs.every(x=>x.term==='Year')?'Year':'Term',top=pr?pr.max:Math.max(8,...progs.map(x=>x.max))
  const qs=`?program_id=${f.p}&semester=${f.s}`
  useEffect(()=>{setRows(null);api('/reports/courses'+qs).then(setRows).catch(e=>toast(e.message))},[f.p,f.s])
  return <><div className="qopt"><select value={f.p} onChange={e=>{const p=+e.target.value,x=progs.find(y=>y.id===p);setF({p,s:x&&f.s>x.max?0:f.s})}}><option value={0}>All programs</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <select aria-label={'Filter by '+lab.toLowerCase()} value={f.s} onChange={e=>setF({...f,s:+e.target.value})}><option value={0}>{lab==='Term'?'All terms':'All '+lab.toLowerCase()+'s'}</option>{Array.from({length:top},(_,i)=>i+1).map(n=><option key={n} value={n}>{lab} {n}</option>)}</select></div>
    {rows&&!rows.length&&<p className="known">No courses match.</p>}
    {rows?.map(x=><div className="row" key={x.course_id} style={{cursor:'pointer'}} onClick={()=>onOpen(x)}><div>{x.course}<small>{x.program} · {x.semester} · {x.students} students · {x.topics} topics · {x.avg_completion}% read{x.quizzes?' · quiz avg '+(x.avg_quiz_percent??'–')+'%':''}</small><Bar2 v={x.avg_completion}/></div></div>)}
    {rows?.length>0&&<button className="btn ghost" onClick={()=>fetchFile('/reports/courses?format=csv&program_id='+f.p+'&semester='+f.s,'courses.csv',toast)}>Download courses CSV</button>}</>}
function StudentReport({c,back,toast}){
  const [d,setD]=useState(null),[w,setW]=useState(null);useEffect(()=>{api(`/reports/courses/${c.course_id}/students`).then(setD).catch(e=>toast(e.message));api(`/reports/courses/${c.course_id}/weak-areas`).then(setW).catch(()=>{})},[])
  return <><Bar title={c.course} sub={c.program+' · '+c.semester} back={back}/><div className="main">
    {w&&w.areas.length>0&&<><h3 style={{margin:'0 0 4px'}}>Topics the class finds hard</h3><p className="known" style={{margin:'0 0 8px'}}>From each student's latest quiz results, weakest first.</p>{w.areas.slice(0,8).map(a=><div className="row" key={a.topic_id||'u'+a.unit_id}><div>{a.title}<small>{a.percent}% right overall · {a.needs_study} of {a.students} students need another round of study</small><Bar2 v={a.percent}/></div></div>)}<h3 style={{margin:'24px 0 4px'}}>Students</h3></>}
    {d&&!d.students.length&&<p className="known">No students are enrolled for this course yet.</p>}
    {d?.students.map(x=><div className="row" key={x.email}><div>{x.name}{!x.active&&<span className="pill off" style={{marginLeft:8}}>Disabled</span>}<small>{x.completion}% · {x.topics_read}/{x.topics} topics{c.quizzes?' · quizzes '+x.quizzes_taken+'/'+x.quizzes+(x.avg_quiz_percent!=null?', avg '+x.avg_quiz_percent+'%':''):''} · last active {day(x.last_active)}</small>{(x.strong.length>0||x.needs_study.length>0)&&<small>{x.strong.length>0&&'Strong: '+x.strong.join(', ')}{x.strong.length>0&&x.needs_study.length>0&&' · '}{x.needs_study.length>0&&'Needs another round: '+x.needs_study.join(', ')}</small>}<Bar2 v={x.completion}/></div></div>)}
    {d?.students.length>0&&<button className="btn ghost" onClick={()=>fetchFile(`/reports/courses/${c.course_id}/students?format=csv`,'students-'+c.course.replace(/\s+/g,'_')+'.csv',toast)}>Download students CSV</button>}</div></>}
function Reports({role,toast}){
  const [st,setSt]=useState({}),[r,setR]=useState(null),[open,setOpen]=useState(null)
  useEffect(()=>{if(role==='faculty')return;api('/admin/stats').then(setSt);api('/admin/reports').then(setR)},[])
  if(open)return <StudentReport c={open} back={()=>setOpen(null)} toast={toast}/>
  if(role==='faculty')return <><Bar title="Reports" sub="Your courses"/><div className="main"><CourseReports toast={toast} onOpen={setOpen}/></div></>
  const list=(rows,empty,f)=>rows?.length?rows.map((x,i)=><div className="row" key={i}>{f(x)}</div>):<p className="known">{empty}</p>
  return <><Bar title="Reports"/><div className="main"><div className="stats">
    {[['students','Students'],['topics','Topics'],['cached','Saved AI answers'],['tokens_saved','Tokens saved']].map(([k,l])=><div className="stat" key={k}><b>{(st[k]??0).toLocaleString()}</b>{l}</div>)}</div>
    <h3 style={{margin:'28px 0 4px'}}>Courses</h3><CourseReports toast={toast} onOpen={setOpen}/>
    <h3 style={{margin:'28px 0 4px'}}>Most read topics</h3>
    {list(r?.top_topics,'No reading activity yet.',x=><div>{x.title}<small>{x.readers} students, {x.reads} reads</small></div>)}
    <h3 style={{margin:'28px 0 4px'}}>Students</h3>
    {list(r?.students,'No students yet.',x=><div>{x.name}<small>{x.topics_read} topics read, last active {day(x.last_active)}{!x.active&&', disabled'}</small></div>)}
    <h3 style={{margin:'28px 0 4px'}}>Saved AI answers</h3>
    {list(r?.ai,'Nothing saved yet.',x=><div>{x.title}<small>{x.kind==='explain'?'Explanation':'Sample answer'}, reused {x.hits} times, {x.saved.toLocaleString()} tokens saved</small></div>)}</div></>}

function About({user}){
  const {appName}=useContext(Ctx),[c,setC]=useState({});useEffect(()=>{api('/config').then(setC)},[])
  return <><Bar title="About"/><div className="main"><div className="hero"><h2>{appName}</h2><p>Version {c.version||''}</p></div>
    <div className="prose"><p>A study companion for engineering students. Your admin adds programs, semesters, courses, units and topics along with the question pattern and answer guideline. Open a topic to get a clear explanation and a sample answer that follows the guideline.</p>
    <p>The app remembers which topics you have read. Explanations and sample answers are generated once with DeepSeek and shared, so they open instantly.</p>
    <p>Signed in as <strong>{user.name}</strong> ({user.role}).</p></div></div></>}
