import {useState,useEffect,useCallback} from 'react'
import Markdown from 'react-markdown'
import {House,Plus,Shield,LogOut,ChevronLeft,Sparkles,Check} from 'lucide-react'
import './styles.css'

const api=async(p,o={})=>{const t=localStorage.t
  const r=await fetch('/api'+p,{...o,headers:{'Content-Type':'application/json',...(t&&{Authorization:'Bearer '+t})},body:o.body&&JSON.stringify(o.body)})
  const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Something went wrong');return j}
const COL=['#8b5cf6','#ff4d9d','#ffb547','#3ee6b0','#4cc9ff']

export default function App(){
  const [user,setUser]=useState(null),[ready,setReady]=useState(false),[tab,setTab]=useState('home'),[msg,setMsg]=useState('')
  const toast=useCallback(m=>{setMsg(m);setTimeout(()=>setMsg(''),2800)},[])
  useEffect(()=>{localStorage.t?api('/me').then(setUser).catch(()=>localStorage.removeItem('t')).finally(()=>setReady(true)):setReady(true)},[])
  if(!ready)return null
  if(!user)return <Login onIn={u=>setUser(u)} toast={toast} msg={msg}/>
  const admin=user.role==='admin'
  const tabs=[['home',House,'Learn'],['add',Plus,'Add'],...(admin?[['admin',Shield,'Admin']]:[]),['out',LogOut,'Sign out']]
  return <>
    {tab==='home'&&<Learn user={user} toast={toast}/>}
    {tab==='add'&&<Add toast={toast} done={()=>setTab('home')}/>}
    {tab==='admin'&&<Admin toast={toast}/>}
    <nav className="nav">{tabs.map(([k,I,l])=><button key={k} className={tab===k?'on':''} onClick={()=>k==='out'?(localStorage.removeItem('t'),setUser(null)):setTab(k)}><i><I size={20}/></i>{l}</button>)}</nav>
    {msg&&<div className="toast" role="status">{msg}</div>}
  </>}

function Login({onIn,toast,msg}){
  const [f,setF]=useState({email:'',password:''}),[b,setB]=useState(false)
  const go=async()=>{setB(true);try{const r=await api('/login',{method:'POST',body:f});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  return <div className="login"><h1>Engineering,<br/>finally clear.</h1><p>Sign in with the account your admin created.</p>
    <label>Email</label><input type="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})}/>
    <label>Password</label><input type="password" value={f.password} onChange={e=>setF({...f,password:e.target.value})}/>
    <button className="btn" disabled={b} onClick={go}>Sign in</button>{msg&&<div className="toast">{msg}</div>}</div>}

const Bar=({title,sub,back})=><header className="bar">{back&&<button className="ic" aria-label="Back" onClick={back}><ChevronLeft/></button>}<h1>{title}{sub&&<small>{sub}</small>}</h1></header>

function Learn({user,toast}){
  const [tree,setTree]=useState([]),[c,setC]=useState(null),[s,setS]=useState(null),[t,setT]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t])
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast}/>
  const course=tree.find(x=>x.id===c),sub=course?.subjects.find(x=>x.id===s)
  const list=sub?sub.topics.map(x=>({id:x.id,n:x.title,d:x.read,go:()=>setT(x.id)})):course?course.subjects.map(x=>({id:x.id,n:x.name,sub:x.topics.length+' topics',go:()=>setS(x.id)})):tree.map(x=>({id:x.id,n:x.name,sub:x.subjects.length+' subjects',go:()=>setC(x.id)}))
  return <><Bar title={sub?.name||course?.name||'Learn'} sub={!course&&'Hi '+user.name} back={course&&(()=>sub?setS(null):setC(null))}/>
   <div className="main">{!course&&<div className="hero"><h2>Pick a course.<br/>We’ll remember where you stopped.</h2></div>}
    {list.map((x,i)=><button key={x.id} className="card" onClick={x.go}><span className="dot" style={{background:COL[i%5]}}>{x.n[0]}</span><div><b>{x.n}</b>{x.sub&&<span>{x.sub}</span>}</div>{x.d&&<Check className="done"/>}</button>)}
    {!list.length&&<p className="known">Nothing here yet. Tap Add to create it.</p>}</div></>}

function Topic({id,back,toast}){
  const [t,setT]=useState(null),[tab,setTab]=useState('notes'),[known,setKnown]=useState([]),[ai,setAi]=useState({}),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/topics/'+id).then(setT).catch(e=>toast(e.message));api(`/topics/${id}/read`,{method:'POST'}).then(r=>setKnown(r.known)).catch(()=>{})},[id])
  const ask=async k=>{setBusy(true);try{const r=await api(`/topics/${id}/ai/${k}`);setAi(a=>({...a,[k]:r}))}catch(e){toast(e.message)}setBusy(false)}
  if(!t)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const view=k=>ai[k]?<div className="prose">{ai[k].cached&&<span className="chip">Saved answer · no tokens used</span>}<Markdown>{ai[k].text}</Markdown></div>
    :<button className="btn" disabled={busy} onClick={()=>ask(k)}><Sparkles size={16}/> {busy?'Thinking…':k==='explain'?'Explain it to me':'Show a sample answer'}</button>
  return <><Bar title={t.title} sub={`${t.course} · ${t.subject}`} back={back}/><div className="main">
    <div className="tabs">{[['notes','Notes'],['explain','Explain'],['answer','Sample answer']].map(([k,l])=><button key={k} className={tab===k?'on':''} onClick={()=>setTab(k)}>{l}</button>)}</div>
    {known.length>0&&tab==='explain'&&<p className="known">You’ve already covered: {known.join(', ')}</p>}
    {tab==='notes'&&<div className="prose"><Markdown>{t.content||'No notes yet.'}</Markdown>{t.question_pattern&&<><h3>Question pattern</h3><Markdown>{t.question_pattern}</Markdown></>}{t.guideline&&<><h3>Answer guideline</h3><Markdown>{t.guideline}</Markdown></>}</div>}
    {tab==='explain'&&view('explain')}{tab==='answer'&&view('answer')}</div></>}

function Add({toast,done}){
  const [kind,setKind]=useState('topic'),[tree,setTree]=useState([]),[f,setF]=useState({name:'',title:'',course_id:'',subject_id:'',content:'',sample_content:'',question_pattern:'',guideline:''})
  useEffect(()=>{api('/tree').then(setTree)},[]);const set=k=>e=>setF({...f,[k]:e.target.value})
  const subs=tree.flatMap(c=>c.subjects.map(s=>({...s,label:c.name+' › '+s.name})))
  const save=async()=>{try{
    if(kind==='course')await api('/courses',{method:'POST',body:{name:f.name}})
    if(kind==='subject')await api('/subjects',{method:'POST',body:{name:f.name,course_id:+f.course_id}})
    if(kind==='topic')await api('/topics',{method:'POST',body:{title:f.title,subject_id:+f.subject_id,content:f.content,sample_content:f.sample_content,question_pattern:f.question_pattern,guideline:f.guideline}})
    toast('Saved');done()}catch(e){toast(e.message)}}
  const T=(k,l,ph)=><><label>{l}</label><textarea placeholder={ph} value={f[k]} onChange={set(k)}/></>
  return <><Bar title="Add content"/><div className="main"><div className="tabs">{['course','subject','topic'].map(k=><button key={k} className={kind===k?'on':''} onClick={()=>setKind(k)}>{k[0].toUpperCase()+k.slice(1)}</button>)}</div>
    {kind==='subject'&&<><label>Course</label><select value={f.course_id} onChange={set('course_id')}><option value="">Choose…</option>{tree.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></>}
    {kind==='topic'&&<><label>Subject</label><select value={f.subject_id} onChange={set('subject_id')}><option value="">Choose…</option>{subs.map(s=><option key={s.id} value={s.id}>{s.label}</option>)}</select></>}
    {kind!=='topic'&&<><label>Name</label><input value={f.name} onChange={set('name')} placeholder={kind==='course'?'B.E. Mechanical Engineering':'Thermodynamics'}/></>}
    {kind==='topic'&&<><label>Topic title</label><input value={f.title} onChange={set('title')} placeholder="First law of thermodynamics"/>
      {T('content','Topic content','Paste notes or syllabus text')}{T('question_pattern','Question pattern','e.g. 2 marks: define · 13 marks: derive + numerical')}
      {T('sample_content','Sample content','A sample question and answer')}{T('guideline','How an answer should be','Intro, labelled diagram, steps, units, conclusion')}</>}
    <button className="btn" onClick={save}>Save {kind}</button></div></>}

function Admin({toast}){
  const [st,setSt]=useState({}),[cfg,setCfg]=useState({}),[us,setUs]=useState([]),[key,setKey]=useState(''),[n,setN]=useState({name:'',email:'',password:''})
  const load=()=>{api('/admin/stats').then(setSt);api('/admin/settings').then(setCfg);api('/admin/users').then(setUs)};useEffect(load,[])
  const run=async(fn,m)=>{try{await fn();toast(m);load()}catch(e){toast(e.message)}}
  return <><Bar title="Admin"/><div className="main"><div className="stats">
    {[['students','Students'],['topics','Topics'],['cached','Saved AI answers'],['tokens_saved','Tokens saved']].map(([k,l])=><div className="stat" key={k}><b>{(st[k]??0).toLocaleString()}</b>{l}</div>)}</div>
    <label>DeepSeek API key {cfg.key_set&&`(saved ${cfg.key_hint})`}</label><input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder="sk-…"/>
    <button className="btn" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{deepseek_key:key}}).then(()=>setKey('')),'API key saved')}>Save key</button>
    <h3 style={{margin:'28px 0 4px'}}>Students</h3>
    {us.map(u=><div className="row" key={u.id}><div>{u.name}<small>{u.email} · {u.role}</small></div>{u.role!=='admin'&&<button className="pill" onClick={()=>run(()=>api('/admin/users/'+u.id,{method:'PATCH',body:{active:!u.active}}),u.active?'Disabled':'Enabled')}>{u.active?'Disable':'Enable'}</button>}</div>)}
    <label>New student</label><input placeholder="Name" value={n.name} onChange={e=>setN({...n,name:e.target.value})}/><input style={{marginTop:8}} placeholder="Email" value={n.email} onChange={e=>setN({...n,email:e.target.value})}/><input style={{marginTop:8}} type="password" placeholder="Password" value={n.password} onChange={e=>setN({...n,password:e.target.value})}/>
    <button className="btn ghost" onClick={()=>run(()=>api('/admin/users',{method:'POST',body:n}).then(()=>setN({name:'',email:'',password:''})),'Student added')}>Add student</button></div></>}
