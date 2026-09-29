import {useState,useEffect,useCallback,useRef,createContext,useContext} from 'react'
import Markdown from 'react-markdown'
import {Home,Users as UsersIcon,GraduationCap,Sparkles,BarChart3,Info,LogOut,Menu,Plus,X,ChevronLeft,Check,Pencil,Trash2} from 'lucide-react'
import './styles.css'

const api=async(p,o={})=>{const t=localStorage.t
  const r=await fetch('/api'+p,{...o,headers:{'Content-Type':'application/json',...(t&&{Authorization:'Bearer '+t})},body:o.body&&JSON.stringify(o.body)})
  const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.detail||'Something went wrong');return j}
const TEMPLATE=`program,semester,course,unit,topic,content,question_pattern,sample_content,guideline
B.E. Mechanical Engineering,Semester 3,Thermodynamics,Unit 1: Basic concepts,First law of thermodynamics,"Energy can change form but is never created or destroyed.","2 marks: define. 13 marks: derive and solve a numerical.","Q: State the first law for a closed system.","Introduction, labelled diagram, steps, units, conclusion"
,,,,Zeroth law of thermodynamics,"If A and B are each in equilibrium with C, they are in equilibrium with each other.","2 marks: state the law.","Q: State the zeroth law.","Definition, one example, significance"
`
const COL=['#8b5cf6','#ff4d9d','#ffb547','#3ee6b0','#4cc9ff']

const Ctx=createContext({})

export default function App(){
  const [user,setUser]=useState(null),[ready,setReady]=useState(false),[page,setPage]=useState('learn'),[msg,setMsg]=useState(''),[open,setOpen]=useState(false),[name,setName]=useState('Eng Tutor')
  const toast=useCallback(m=>{setMsg(m);setTimeout(()=>setMsg(''),2800)},[])
  useEffect(()=>{Promise.allSettled([api('/config').then(c=>{setName(c.name);document.title=c.name}),localStorage.t?api('/me').then(setUser).catch(()=>localStorage.removeItem('t')):null]).then(()=>setReady(true))},[])
  useEffect(()=>{const k=e=>e.key==='Escape'&&setOpen(false);addEventListener('keydown',k);return()=>removeEventListener('keydown',k)},[])
  useEffect(()=>{document.body.style.overflow=open?'hidden':''},[open])
  if(!ready)return null
  if(!user)return <Login onIn={setUser} toast={toast} msg={msg} appName={name}/>
  const admin=user.role==='admin',go=k=>{setPage(k);setOpen(false)}
  const links=[['learn',Home,'Learn'],...(admin?[['users',UsersIcon,'Users'],['programs',GraduationCap,'Programs'],['ai',Sparkles,'AI config'],['reports',BarChart3,'Reports']]:[]),['about',Info,'About']]
  return <Ctx.Provider value={{menu:()=>setOpen(true),appName:name}}>
    {page==='learn'&&<Learn user={user} toast={toast} onAdd={()=>go('add')} appName={name}/>}
    {page==='add'&&admin&&<Add toast={toast} done={()=>go('learn')}/>}
    {page==='users'&&admin&&<Users toast={toast}/>}{page==='programs'&&admin&&<Programs toast={toast} onAdd={()=>go('add')}/>}
    {page==='ai'&&admin&&<AiConfig toast={toast}/>}{page==='reports'&&admin&&<Reports/>}{page==='about'&&<About user={user}/>}
    <div className={'drawer'+(open?' open':'')}><div className="dscrim" onClick={()=>setOpen(false)}/>
      <nav className="panel" aria-label="Main menu">
        <div className="dhead"><div><b>{name}</b><small>{user.name}, {user.role}</small></div><button className="ic" aria-label="Close menu" onClick={()=>setOpen(false)}><X/></button></div>
        {links.map(([k,I,l])=><button key={k} className={'dlink'+(page===k||(k==='learn'&&page==='add')?' on':'')} onClick={()=>go(k)}><I size={20}/>{l}</button>)}
        <button className="dlink out" onClick={()=>{localStorage.removeItem('t');setOpen(false);setPage('learn');setUser(null)}}><LogOut size={20}/>Sign out</button>
      </nav></div>
    {msg&&<div className="toast" role="status">{msg}</div>}
  </Ctx.Provider>}

function Login({onIn,toast,msg,appName}){
  const [f,setF]=useState({email:'',password:''}),[b,setB]=useState(false)
  const go=async()=>{setB(true);try{const r=await api('/login',{method:'POST',body:f});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  return <div className="login"><p className="brand">{appName}</p><h1>Engineering,<br/>finally clear.</h1><p>Sign in with the account your admin created.</p>
    <label>Email</label><input type="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})}/>
    <label>Password</label><input type="password" value={f.password} onChange={e=>setF({...f,password:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Sign in</button>{msg&&<div className="toast">{msg}</div>}</div>}

const Bar=({title,sub,back})=>{const {menu}=useContext(Ctx);return <header className="bar">
  {back?<button className="ic" aria-label="Back" onClick={back}><ChevronLeft/></button>:<button className="ic" aria-label="Open menu" onClick={menu}><Menu/></button>}
  <h1>{title}{sub&&<small>{sub}</small>}</h1></header>}

function Learn({user,toast,onAdd,appName}){
  const isAdmin=user.role==='admin'
  const [tree,setTree]=useState([]),[nav,setNav]=useState([]),[t,setT]=useState(null),[ed,setEd]=useState(null),[del,setDel]=useState(null)
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[t,ed])
  if(t)return <Topic id={t} back={()=>setT(null)} toast={toast}/>
  if(ed)return <Add toast={toast} edit={ed} done={()=>setEd(null)} cancel={()=>setEd(null)}/>
  const prog=tree.find(x=>x.id===nav[0]),sem=prog?.semesters.find(x=>x.id===nav[1]),co=sem?.courses.find(x=>x.id===nav[2]),unit=co?.units.find(x=>x.id===nav[3])
  const row=(x,kind,one,sub,extra={})=>({id:x.id,n:x.name,sub,kind,go:()=>setNav([...nav,x.id]),edit:()=>setEd({kind:one,id:x.id,name:x.name,...extra})})
  const list=unit?unit.topics.map(x=>({id:x.id,n:x.title,d:x.read,kind:'topics',go:()=>setT(x.id),edit:()=>setEd({kind:'topic',id:x.id})}))
    :co?co.units.map(x=>row(x,'units','unit',x.topics.length+' topics',{course_id:co.id}))
    :sem?sem.courses.map(x=>row(x,'courses','course',x.units.length+' units',{semester_id:sem.id}))
    :prog?prog.semesters.map(x=>row(x,'semesters','semester',x.courses.length+' courses',{program_id:prog.id}))
    :tree.map(x=>row(x,'programs','program',x.semesters.length+' semesters'))
  const cur=unit||co||sem||prog,crumbs=[prog,sem,co,unit].filter(Boolean).slice(0,-1).map(x=>x.name).join(' › ')
  const remove=async()=>{try{await api(`/${del.kind}/${del.id}`,{method:'DELETE'});toast('Deleted');setDel(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={cur?.name||appName} sub={nav.length?crumbs:'Hi '+user.name} back={nav.length>0&&(()=>setNav(nav.slice(0,-1)))}/>
   <div className="main">{!nav.length&&<div className="hero"><h2>Pick a program.<br/>We’ll remember where you stopped.</h2></div>}
    {list.map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={x.go}><span className="dot" style={{background:COL[i%5]}}>{x.n[0]}</span><div><b>{x.n}</b>{x.sub&&<span>{x.sub}</span>}</div>{x.d&&<Check className="done"/>}</button>
      {isAdmin&&<><button className="ic sm" aria-label={'Edit '+x.n} onClick={x.edit}><Pencil size={16}/></button><button className="ic sm" aria-label={'Delete '+x.n} onClick={()=>setDel(x)}><Trash2 size={16}/></button></>}</div>)}
    {!list.length&&<p className="known">{isAdmin?'Nothing here yet. Tap Add to create it.':'Nothing here yet. Your admin will add it soon.'}</p>}</div>
   {del&&<div className="scrim" onClick={()=>setDel(null)}><div className="sheet" onClick={e=>e.stopPropagation()}><h3>Delete “{del.n}”?</h3>
     <p className="known">{del.kind==='topics'?'This removes the topic and its saved AI answers.':'This also removes everything inside it.'}</p>
     <button className="btn danger" onClick={remove}>Delete</button><button className="btn ghost" onClick={()=>setDel(null)}>Keep it</button></div></div>}
   {isAdmin&&<button className="fab" aria-label="Add content" onClick={onAdd}><Plus/></button>}</>}

function Topic({id,back,toast}){
  const [t,setT]=useState(null),[tab,setTab]=useState('notes'),[known,setKnown]=useState([]),[ai,setAi]=useState({}),[busy,setBusy]=useState(false)
  useEffect(()=>{api('/topics/'+id).then(setT).catch(e=>toast(e.message));api(`/topics/${id}/read`,{method:'POST'}).then(r=>setKnown(r.known)).catch(()=>{})},[id])
  const ask=async k=>{setBusy(true);try{const r=await api(`/topics/${id}/ai/${k}`);setAi(a=>({...a,[k]:r}))}catch(e){toast(e.message)}setBusy(false)}
  if(!t)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const view=k=>ai[k]?<div className="prose">{ai[k].cached&&<span className="chip">Saved answer · no tokens used</span>}<Markdown>{ai[k].text}</Markdown></div>
    :<button className="btn" disabled={busy} onClick={()=>ask(k)}><Sparkles size={16}/> {busy?'Thinking…':k==='explain'?'Explain it to me':'Show a sample answer'}</button>
  return <><Bar title={t.title} sub={[t.program,t.semester,t.course,t.unit].filter(Boolean).join(' › ')} back={back}/><div className="main">
    <div className="tabs">{[['notes','Notes'],['explain','Explain'],['answer','Sample answer']].map(([k,l])=><button key={k} className={tab===k?'on':''} onClick={()=>setTab(k)}>{l}</button>)}</div>
    {known.length>0&&tab==='explain'&&<p className="known">You’ve already covered: {known.join(', ')}</p>}
    {tab==='notes'&&<div className="prose"><Markdown>{t.content||'No notes yet.'}</Markdown>{t.question_pattern&&<><h3>Question pattern</h3><Markdown>{t.question_pattern}</Markdown></>}{t.guideline&&<><h3>Answer guideline</h3><Markdown>{t.guideline}</Markdown></>}</div>}
    {tab==='explain'&&view('explain')}{tab==='answer'&&view('answer')}</div></>}

function Add({toast,done,edit,cancel}){
  const blank={name:'',title:'',program_id:'',semester_id:'',course_id:'',unit_id:'',content:'',sample_content:'',question_pattern:'',guideline:''}
  const [kind,setKind]=useState(edit?.kind||'topic'),[tree,setTree]=useState([]),[f,setF]=useState(edit?{...blank,name:edit.name||'',program_id:edit.program_id||'',semester_id:edit.semester_id||'',course_id:edit.course_id||''}:blank)
  useEffect(()=>{api('/tree').then(setTree);if(edit?.kind==='topic')api('/topics/'+edit.id).then(t=>setF({...blank,title:t.title,unit_id:t.unit_id||'',content:t.content||'',sample_content:t.sample_content||'',question_pattern:t.question_pattern||'',guideline:t.guideline||''})).catch(e=>toast(e.message))},[])
  const set=k=>e=>setF({...f,[k]:e.target.value})
  const sems=tree.flatMap(p=>p.semesters.map(s=>({...s,label:`${p.name} › ${s.name}`})))
  const courses=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.map(c=>({...c,label:`${p.name} › ${s.name} › ${c.name}`}))))
  const units=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.flatMap(c=>c.units.map(n=>({...n,label:`${p.name} › ${s.name} › ${c.name} › ${n.name}`})))))
  const save=async()=>{try{
    const path='/'+kind+'s'+(edit?'/'+edit.id:''),method=edit?'PUT':'POST'
    const body={program:{name:f.name},semester:{name:f.name,program_id:+f.program_id},course:{name:f.name,semester_id:+f.semester_id},unit:{name:f.name,course_id:+f.course_id},
      topic:{title:f.title,unit_id:+f.unit_id,content:f.content,sample_content:f.sample_content,question_pattern:f.question_pattern,guideline:f.guideline}}[kind]
    await api(path,{method,body});toast(edit?'Changes saved':'Saved');done()}catch(e){toast(e.message)}}
  const T=(k,l,ph)=><><label>{l}</label><textarea placeholder={ph} value={f[k]} onChange={set(k)}/></>
  const pick=(l,k,opts)=><><label>{l}</label><select value={f[k]} onChange={set(k)}><option value="">Choose…</option>{opts.map(o=><option key={o.id} value={o.id}>{o.label||o.name}</option>)}</select></>
  return <><Bar title={edit?'Edit '+kind:'Add content'} back={edit&&cancel}/><div className="main">{!edit&&<div className="tabs">{['program','semester','course','unit','topic'].map(k=><button key={k} className={kind===k?'on':''} onClick={()=>setKind(k)}>{k[0].toUpperCase()+k.slice(1)}</button>)}</div>}
    {kind==='semester'&&pick('Program','program_id',tree)}{kind==='course'&&pick('Semester','semester_id',sems)}{kind==='unit'&&pick('Course','course_id',courses)}{kind==='topic'&&pick('Unit','unit_id',units)}
    {kind!=='topic'&&<><label>Name</label><input value={f.name} onChange={set('name')} placeholder={{program:'B.E. Mechanical Engineering',semester:'Semester 3',course:'Thermodynamics',unit:'Unit 1: Basic concepts'}[kind]}/></>}
    {kind==='topic'&&<><label>Topic title</label><input value={f.title} onChange={set('title')} placeholder="First law of thermodynamics"/>
      {T('content','Topic content','Paste notes or syllabus text')}{T('question_pattern','Question pattern','e.g. 2 marks: define · 13 marks: derive + numerical')}
      {T('sample_content','Sample content','A sample question and answer')}{T('guideline','How an answer should be','Intro, labelled diagram, steps, units, conclusion')}</>}
    <button className="btn" onClick={save}>{edit?'Save changes':'Save '+kind}</button></div></>}

const Sheet=({close,children})=><div className="scrim" onClick={close}><div className="sheet" onClick={e=>e.stopPropagation()}>{children}</div></div>
const useRun=(toast,load)=>async(fn,m)=>{try{await fn();toast(m);load&&load()}catch(e){toast(e.message)}}

function Users({toast}){
  const [us,setUs]=useState([]),[n,setN]=useState({name:'',email:'',password:'',role:'student'}),[rp,setRp]=useState(null),[np,setNp]=useState('')
  const load=()=>api('/admin/users').then(setUs).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  const run=useRun(toast,load),set=k=>e=>setN({...n,[k]:e.target.value})
  return <><Bar title="Users" sub={us.length+' accounts'}/><div className="main">
    {us.map(u=><div className="row" key={u.id}><div>{u.name}<small>{u.email}, {u.role}{!u.active&&', disabled'}</small></div>
      <button className="pill" aria-label={'Reset password for '+u.email} onClick={()=>setRp(u)}>Reset</button>
      {u.role!=='admin'&&<button className="pill" onClick={()=>run(()=>api('/admin/users/'+u.id,{method:'PATCH',body:{active:!u.active}}),u.active?'Disabled':'Enabled')}>{u.active?'Disable':'Enable'}</button>}</div>)}
    <h3 style={{margin:'28px 0 0'}}>New user</h3>
    <label>Name</label><input value={n.name} onChange={set('name')}/><label>Email</label><input type="email" value={n.email} onChange={set('email')}/>
    <label>Password (8+ characters)</label><input type="password" value={n.password} onChange={set('password')}/>
    <label>Role</label><select value={n.role} onChange={set('role')}><option value="student">Student</option><option value="admin">Admin</option></select>
    <button className="btn" onClick={()=>run(()=>api('/admin/users',{method:'POST',body:n}).then(()=>setN({name:'',email:'',password:'',role:'student'})),'User added')}>Add user</button></div>
    {rp&&<Sheet close={()=>setRp(null)}><h3>Reset password</h3><p className="known">{rp.email}</p>
      <input type="password" placeholder="New password (8+ characters)" value={np} onChange={e=>setNp(e.target.value)}/>
      <button className="btn" onClick={()=>run(()=>api('/admin/users/'+rp.id,{method:'PATCH',body:{password:np}}).then(()=>{setRp(null);setNp('')}),'Password reset')}>Reset password</button></Sheet>}</>}

function Programs({toast,onAdd}){
  const [tree,setTree]=useState([]),[imp,setImp]=useState(null),fileRef=useRef()
  const load=()=>api('/tree').then(setTree).catch(e=>toast(e.message));useEffect(()=>{load()},[])
  const run=useRun(toast,load)
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setImp({text,res:await api('/admin/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const tpl=()=>{const l=document.createElement('a');l.href=URL.createObjectURL(new Blob([TEMPLATE],{type:'text/csv'}));l.download='template.csv';l.click()}
  const cnt=p=>{let c=0,u=0,t=0;p.semesters.forEach(s=>s.courses.forEach(x=>{c++;x.units.forEach(n=>{u++;t+=n.topics.length})}));return `${p.semesters.length} semesters, ${c} courses, ${u} units, ${t} topics`}
  return <><Bar title="Programs" sub={tree.length+' programs'}/><div className="main">
    {tree.map((p,i)=><div className="card" key={p.id}><span className="dot" style={{background:COL[i%5]}}>{p.name[0]}</span><div><b>{p.name}</b><span>{cnt(p)}</span></div></div>)}
    {!tree.length&&<p className="known">No programs yet. Add one or import a CSV.</p>}
    <p className="known">To rename or delete, open Learn and use the pencil and bin icons.</p>
    <button className="btn" onClick={onAdd}>Add content</button>
    <h3 style={{margin:'28px 0 4px'}}>Import from CSV</h3><p className="known">One row per topic. Blank program, semester, course or unit cells repeat the row above. Existing names are reused, existing topics are updated.</p>
    <button className="btn ghost" style={{marginTop:0}} onClick={tpl}>Download template</button>
    <button className="btn" onClick={()=>fileRef.current.click()}>Choose CSV file</button><input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {imp&&<Sheet close={()=>setImp(null)}><h3>Ready to import</h3>
      <p className="known">{imp.res.valid_rows} of {imp.res.rows} rows are valid. New: {Object.entries(imp.res.created).map(([k,v])=>v+' '+k).join(', ')}. Topics updated: {imp.res.updated_topics}.</p>
      {imp.res.error_count>0&&<div className="prose" style={{maxHeight:'28vh',overflow:'auto',fontSize:14}}><b>{imp.res.error_count} rows will be skipped</b>{imp.res.errors.map(e=><div key={e.row}>Row {e.row}: {e.error}</div>)}</div>}
      <button className="btn" disabled={!imp.res.valid_rows} onClick={()=>run(()=>api('/admin/import',{method:'POST',body:{csv:imp.text,dry_run:false}}).then(()=>setImp(null)),'Import complete')}>Import {imp.res.valid_rows} rows</button>
      <button className="btn ghost" onClick={()=>setImp(null)}>Cancel</button></Sheet>}</>}

function AiConfig({toast}){
  const [cfg,setCfg]=useState({}),[key,setKey]=useState(''),[model,setModel]=useState(''),[st,setSt]=useState({})
  const load=()=>{api('/admin/settings').then(c=>{setCfg(c);setModel(c.model)});api('/admin/stats').then(setSt)};useEffect(load,[])
  const run=useRun(toast,load)
  return <><Bar title="AI config" sub={cfg.key_set?'DeepSeek key saved '+cfg.key_hint:'No key yet'}/><div className="main">
    <label>DeepSeek API key</label><input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder={cfg.key_set?'Leave blank to keep the current key':'sk-…'}/>
    <label>Model</label><input value={model} onChange={e=>setModel(e.target.value)} placeholder="deepseek-chat"/>
    <button className="btn" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{deepseek_key:key,model}}).then(()=>setKey('')),'AI settings saved')}>Save</button>
    <p className="known" style={{marginTop:20}}>Each topic is explained once and the answer is shared with every student. {(st.cached??0).toLocaleString()} answers are saved so far, which has saved about {(st.tokens_saved??0).toLocaleString()} tokens.</p></div></>}

const day=d=>d?new Date(d).toLocaleDateString(undefined,{day:'numeric',month:'short'}):'never'
function Reports({}){
  const [st,setSt]=useState({}),[r,setR]=useState(null)
  useEffect(()=>{api('/admin/stats').then(setSt);api('/admin/reports').then(setR)},[])
  const list=(rows,empty,f)=>rows?.length?rows.map((x,i)=><div className="row" key={i}>{f(x)}</div>):<p className="known">{empty}</p>
  return <><Bar title="Reports"/><div className="main"><div className="stats">
    {[['students','Students'],['topics','Topics'],['cached','Saved AI answers'],['tokens_saved','Tokens saved']].map(([k,l])=><div className="stat" key={k}><b>{(st[k]??0).toLocaleString()}</b>{l}</div>)}</div>
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
