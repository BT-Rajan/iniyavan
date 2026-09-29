import {useState,useEffect,useCallback} from 'react'
import Markdown from 'react-markdown'
import {Home,Plus,Shield,LogOut,ChevronLeft,Sparkles,Check,Pencil,Trash2} from 'lucide-react'
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
  const tabs=[['home',Home,'Learn'],...(admin?[['add',Plus,'Add'],['admin',Shield,'Admin']]:[]),['out',LogOut,'Sign out']]
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
  const isAdmin=user.role==='admin'
  const [tree,setTree]=useState([]),[c,setC]=useState(null),[s,setS]=useState(null),[u,setU]=useState(null),[t,setT]=useState(null),[ed,setEd]=useState(null),[del,setDel]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t,ed])
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast}/>
  if(ed)return <Add toast={toast} edit={ed} done={()=>setEd(null)} cancel={()=>setEd(null)}/>
  const course=tree.find(x=>x.id===c),sub=course?.subjects.find(x=>x.id===s),unit=sub?.units.find(x=>x.id===u)
  const list=unit?unit.topics.map(x=>({id:x.id,n:x.title,d:x.read,kind:'topics',go:()=>setT(x.id),edit:()=>setEd({kind:'topic',id:x.id})}))
    :sub?sub.units.map(x=>({id:x.id,n:x.name,sub:x.topics.length+' topics',kind:'units',go:()=>setU(x.id),edit:()=>setEd({kind:'unit',id:x.id,name:x.name,subject_id:sub.id})}))
    :course?course.subjects.map(x=>({id:x.id,n:x.name,sub:x.units.length+' units',kind:'subjects',go:()=>setS(x.id),edit:()=>setEd({kind:'subject',id:x.id,name:x.name,course_id:course.id})}))
    :tree.map(x=>({id:x.id,n:x.name,sub:x.subjects.length+' subjects',kind:'courses',go:()=>setC(x.id),edit:()=>setEd({kind:'course',id:x.id,name:x.name})}))
  const remove=async()=>{try{await api(`/${del.kind}/${del.id}`,{method:'DELETE'});toast('Deleted');setDel(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={unit?.name||sub?.name||course?.name||'Learn'} sub={!course&&'Hi '+user.name} back={course&&(()=>unit?setU(null):sub?setS(null):setC(null))}/>
   <div className="main">{!course&&<div className="hero"><h2>Pick a course.<br/>We’ll remember where you stopped.</h2></div>}
    {list.map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={x.go}><span className="dot" style={{background:COL[i%5]}}>{x.n[0]}</span><div><b>{x.n}</b>{x.sub&&<span>{x.sub}</span>}</div>{x.d&&<Check className="done"/>}</button>
      {isAdmin&&<><button className="ic sm" aria-label={'Edit '+x.n} onClick={x.edit}><Pencil size={16}/></button><button className="ic sm" aria-label={'Delete '+x.n} onClick={()=>setDel(x)}><Trash2 size={16}/></button></>}</div>)}
    {!list.length&&<p className="known">{isAdmin?'Nothing here yet. Tap Add to create it.':'Nothing here yet. Your admin will add it soon.'}</p>}</div>
   {del&&<div className="scrim" onClick={()=>setDel(null)}><div className="sheet" onClick={e=>e.stopPropagation()}><h3>Delete “{del.n}”?</h3>
     <p className="known">{del.kind==='topics'?'This removes the topic and its saved AI answers.':'This also removes everything inside it.'}</p>
     <button className="btn danger" onClick={remove}>Delete</button><button className="btn ghost" onClick={()=>setDel(null)}>Keep it</button></div></div>}</>}

function Topic({id,back,toast}){
  const [t,setT]=useState(null),[tab,setTab]=useState('notes'),[known,setKnown]=useState([]),[ai,setAi]=useState({}),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/topics/'+id).then(setT).catch(e=>toast(e.message));api(`/topics/${id}/read`,{method:'POST'}).then(r=>setKnown(r.known)).catch(()=>{})},[id])
  const ask=async k=>{setBusy(true);try{const r=await api(`/topics/${id}/ai/${k}`);setAi(a=>({...a,[k]:r}))}catch(e){toast(e.message)}setBusy(false)}
  if(!t)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const view=k=>ai[k]?<div className="prose">{ai[k].cached&&<span className="chip">Saved answer · no tokens used</span>}<Markdown>{ai[k].text}</Markdown></div>
    :<button className="btn" disabled={busy} onClick={()=>ask(k)}><Sparkles size={16}/> {busy?'Thinking…':k==='explain'?'Explain it to me':'Show a sample answer'}</button>
  return <><Bar title={t.title} sub={[t.course,t.subject,t.unit].filter(Boolean).join(' › ')} back={back}/><div className="main">
    <div className="tabs">{[['notes','Notes'],['explain','Explain'],['answer','Sample answer']].map(([k,l])=><button key={k} className={tab===k?'on':''} onClick={()=>setTab(k)}>{l}</button>)}</div>
    {known.length>0&&tab==='explain'&&<p className="known">You’ve already covered: {known.join(', ')}</p>}
    {tab==='notes'&&<div className="prose"><Markdown>{t.content||'No notes yet.'}</Markdown>{t.question_pattern&&<><h3>Question pattern</h3><Markdown>{t.question_pattern}</Markdown></>}{t.guideline&&<><h3>Answer guideline</h3><Markdown>{t.guideline}</Markdown></>}</div>}
    {tab==='explain'&&view('explain')}{tab==='answer'&&view('answer')}</div></>}

function Add({toast,done,edit,cancel}){
  const blank={name:'',title:'',course_id:'',subject_id:'',unit_id:'',content:'',sample_content:'',question_pattern:'',guideline:''}
  const [kind,setKind]=useState(edit?.kind||'topic'),[tree,setTree]=useState([]),[f,setF]=useState(edit?{...blank,name:edit.name||'',course_id:edit.course_id||'',subject_id:edit.subject_id||''}:blank)
  useEffect(()=>{api('/tree').then(setTree);if(edit?.kind==='topic')api('/topics/'+edit.id).then(t=>setF({...blank,title:t.title,unit_id:t.unit_id||'',content:t.content||'',sample_content:t.sample_content||'',question_pattern:t.question_pattern||'',guideline:t.guideline||''})).catch(e=>toast(e.message))},[])
  const set=k=>e=>setF({...f,[k]:e.target.value})
  const subs=tree.flatMap(c=>c.subjects.map(s=>({...s,label:c.name+' › '+s.name}))),units=tree.flatMap(c=>c.subjects.flatMap(s=>s.units.map(n=>({...n,label:`${c.name} › ${s.name} › ${n.name}`}))))
  const save=async()=>{try{
    const path='/'+kind+'s'+(edit?'/'+edit.id:''),method=edit?'PUT':'POST'
    const body={course:{name:f.name},subject:{name:f.name,course_id:+f.course_id},unit:{name:f.name,subject_id:+f.subject_id},
      topic:{title:f.title,unit_id:+f.unit_id,content:f.content,sample_content:f.sample_content,question_pattern:f.question_pattern,guideline:f.guideline}}[kind]
    await api(path,{method,body});toast(edit?'Changes saved':'Saved');done()}catch(e){toast(e.message)}}
  const T=(k,l,ph)=><><label>{l}</label><textarea placeholder={ph} value={f[k]} onChange={set(k)}/></>
  const pick=(l,k,opts)=><><label>{l}</label><select value={f[k]} onChange={set(k)}><option value="">Choose…</option>{opts.map(o=><option key={o.id} value={o.id}>{o.label||o.name}</option>)}</select></>
  return <><Bar title={edit?'Edit '+kind:'Add content'} back={edit&&cancel}/><div className="main">{!edit&&<div className="tabs">{['course','subject','unit','topic'].map(k=><button key={k} className={kind===k?'on':''} onClick={()=>setKind(k)}>{k[0].toUpperCase()+k.slice(1)}</button>)}</div>}
    {kind==='subject'&&pick('Course','course_id',tree)}{kind==='unit'&&pick('Subject','subject_id',subs)}{kind==='topic'&&pick('Unit','unit_id',units)}
    {kind!=='topic'&&<><label>Name</label><input value={f.name} onChange={set('name')} placeholder={{course:'B.E. Mechanical Engineering',subject:'Thermodynamics',unit:'Unit 1: Basic concepts'}[kind]}/></>}
    {kind==='topic'&&<><label>Topic title</label><input value={f.title} onChange={set('title')} placeholder="First law of thermodynamics"/>
      {T('content','Topic content','Paste notes or syllabus text')}{T('question_pattern','Question pattern','e.g. 2 marks: define · 13 marks: derive + numerical')}
      {T('sample_content','Sample content','A sample question and answer')}{T('guideline','How an answer should be','Intro, labelled diagram, steps, units, conclusion')}</>}
    <button className="btn" onClick={save}>{edit?'Save changes':'Save '+kind}</button></div></>}

function Admin({toast}){
  const [st,setSt]=useState({}),[cfg,setCfg]=useState({}),[us,setUs]=useState([]),[key,setKey]=useState(''),[n,setN]=useState({name:'',email:'',password:''}),[rp,setRp]=useState(null),[np,setNp]=useState('')
  const load=()=>{api('/admin/stats').then(setSt);api('/admin/settings').then(setCfg);api('/admin/users').then(setUs)};useEffect(load,[])
  const run=async(fn,m)=>{try{await fn();toast(m);load()}catch(e){toast(e.message)}}
  return <><Bar title="Admin"/><div className="main"><div className="stats">
    {[['students','Students'],['topics','Topics'],['cached','Saved AI answers'],['tokens_saved','Tokens saved']].map(([k,l])=><div className="stat" key={k}><b>{(st[k]??0).toLocaleString()}</b>{l}</div>)}</div>
    <label>DeepSeek API key {cfg.key_set&&`(saved ${cfg.key_hint})`}</label><input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder="sk-…"/>
    <button className="btn" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{deepseek_key:key}}).then(()=>setKey('')),'API key saved')}>Save key</button>
    <h3 style={{margin:'28px 0 4px'}}>Students</h3>
    {us.map(u=><div className="row" key={u.id}><div>{u.name}<small>{u.email} · {u.role}</small></div><button className="pill" aria-label={'Reset password for '+u.email} onClick={()=>setRp(u)}>Reset</button>{u.role!=='admin'&&<button className="pill" onClick={()=>run(()=>api('/admin/users/'+u.id,{method:'PATCH',body:{active:!u.active}}),u.active?'Disabled':'Enabled')}>{u.active?'Disable':'Enable'}</button>}</div>)}
    <label>New student</label><input placeholder="Name" value={n.name} onChange={e=>setN({...n,name:e.target.value})}/><input style={{marginTop:8}} placeholder="Email" value={n.email} onChange={e=>setN({...n,email:e.target.value})}/><input style={{marginTop:8}} type="password" placeholder="Password" value={n.password} onChange={e=>setN({...n,password:e.target.value})}/>
    <button className="btn ghost" onClick={()=>run(()=>api('/admin/users',{method:'POST',body:n}).then(()=>setN({name:'',email:'',password:''})),'Student added')}>Add student</button>{rp&&<div className="scrim" onClick={()=>setRp(null)}><div className="sheet" onClick={e=>e.stopPropagation()}><h3>Reset password</h3><p className="known">{rp.email}</p>
      <input type="password" placeholder="New password (8+ characters)" value={np} onChange={e=>setNp(e.target.value)}/>
      <button className="btn" onClick={()=>run(()=>api('/admin/users/'+rp.id,{method:'PATCH',body:{password:np}}).then(()=>{setRp(null);setNp('')}),'Password reset')}>Reset password</button></div></div>}</div></>}
