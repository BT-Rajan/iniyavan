import {useState,useEffect,useCallback,useRef,createContext,useContext} from 'react'
import Markdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import 'katex/contrib/mhchem'
const Md=({children})=><Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{children}</Markdown>
import {Home,Users as UsersIcon,GraduationCap,Sparkles,BarChart3,Info,LogOut,Menu,X,ArrowUp,ArrowDown,Search,ChevronLeft,Check,Pencil,Trash2,Bookmark,KeyRound,Link2,Eye,EyeOff,History,TrendingUp} from 'lucide-react'
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
const COL=['#8b5cf6','#ff4d9d','#ffb547','#3ee6b0','#4cc9ff']
const when=iso=>new Date(iso).toLocaleString(undefined,{day:'numeric',month:'short',year:'numeric',hour:'numeric',minute:'2-digit'})  // shown in the viewer's own time zone
const localInput=iso=>{if(!iso)return '';const d=new Date(iso),z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`}
const STATUS={not_started:'Not started',in_progress:'In progress',completed:'Completed'}
const doneOf=ts=>`${ts.filter(x=>x.status==='completed').length} / ${ts.length}`  // worked out from each topic's state, never stored
const Mark=({s})=>s==='completed'?<Check className="done" aria-label="Completed"/>:<span className="st" aria-label={STATUS[s]}>{s==='in_progress'?'●':'—'}</span>
const ownerLine=c=>c.mine?'Your course':c.owner_problem||(c.owner?'Owner: '+c.owner:'Owner not assigned')
const useFaculty=on=>{const [l,setL]=useState([]);useEffect(()=>{if(on)api('/admin/users?role=faculty&limit=100').then(r=>setL(r.items.filter(u=>u.active))).catch(()=>{})},[on]);return l}

const Ctx=createContext({})

export default function App(){
  const [user,setUser]=useState(null),[ready,setReady]=useState(false),[pageSel,setPage]=useState(null),[msg,setMsg]=useState(''),[open,setOpen]=useState(false),[name,setName]=useState('Eng Tutor'),[canReset,setCanReset]=useState(false),[resetTok,setResetTok]=useState(()=>(/^#reset=([\w-]+)$/.exec(location.hash)||[])[1]||null),[start,setStart]=useState(null)
  const toast=useCallback(m=>{setMsg(m);setTimeout(()=>setMsg(''),2800)},[])
  useEffect(()=>{Promise.allSettled([api('/config').then(c=>{setName(c.name);setCanReset(!!c.email_reset);document.title=c.name}),localStorage.t?api('/me').then(setUser).catch(()=>localStorage.removeItem('t')):null]).then(()=>setReady(true))},[])
  useEffect(()=>{const k=e=>e.key==='Escape'&&setOpen(false);addEventListener('keydown',k);return()=>removeEventListener('keydown',k)},[])
  useEffect(()=>{document.body.style.overflow=open?'hidden':''},[open])
  if(!ready)return null
  if(resetTok)return <ResetPassword token={resetTok} toast={toast} msg={msg} canReset={canReset} done={u=>{history.replaceState(null,'',location.pathname);setResetTok(null);setUser(u);toast('Password changed. You are signed in.')}} leave={()=>{history.replaceState(null,'',location.pathname);setResetTok(null)}}/>
  if(!user)return <Login onIn={setUser} toast={toast} msg={msg} appName={name} canReset={canReset}/>
  if(user.must_change)return <ChangePassword forced toast={toast} msg={msg} done={()=>setUser({...user,must_change:false})} out={()=>{localStorage.removeItem('t');setUser(null)}}/>
  const student=user.role==='student',page=pageSel||(student?'home':'learn'),admin=user.role==='admin',go=k=>{setPage(k);setOpen(false)},openIn=nav=>{setStart(nav);go('learn')}
  const links=[...(student?[['home',Home,'Home'],['learn',GraduationCap,'My courses']]:[['learn',Home,'Learn']]),...(user.role==='student'?[['progress',TrendingUp,'My progress']]:[]),['bookmarks',Bookmark,'Bookmarks'],...(admin?[['users',UsersIcon,'Users'],['programs',GraduationCap,'Programs'],['ai',Sparkles,'AI & email'],['reports',BarChart3,'Reports'],['activity',History,'Activity log']]:user.role==='faculty'?[['reports',BarChart3,'Reports']]:[]),['password',KeyRound,'Change password'],['about',Info,'About']]
  return <Ctx.Provider value={{menu:()=>setOpen(true),appName:name}}>
    {page==='home'&&student&&<Dashboard user={user} toast={toast} onOpen={openIn}/>}
    {page==='learn'&&<Learn key={String(start)} start={start} user={user} toast={toast} appName={name}/>}
    {page==='progress'&&user.role==='student'&&<Insights toast={toast} role={user.role}/>}
    {page==='bookmarks'&&<Bookmarks toast={toast} role={user.role}/>}
    {page==='users'&&admin&&<Users toast={toast} me={user}/>}{page==='programs'&&admin&&<Programs toast={toast} onOpen={openIn}/>}
    {page==='ai'&&admin&&<AiConfig toast={toast}/>}{page==='reports'&&(admin||user.role==='faculty')&&<Reports role={user.role} toast={toast}/>}{page==='activity'&&admin&&<Activity/>}{page==='password'&&<ChangePassword toast={toast} done={()=>go('learn')}/>}{page==='about'&&<About user={user}/>}
    <div className={'drawer'+(open?' open':'')}><div className="dscrim" onClick={()=>setOpen(false)}/>
      <nav className="panel" aria-label="Main menu">
        <div className="dhead"><div><b>{name}</b><small>{user.name}, {user.role}</small></div><button className="ic" aria-label="Close menu" onClick={()=>setOpen(false)}><X/></button></div>
        {links.map(([k,I,l])=><button key={k} className={'dlink'+(page===k?' on':'')} onClick={()=>{if(k==='learn')setStart(null);go(k)}}><I size={20}/>{l}</button>)}
        <button className="dlink out" onClick={()=>{localStorage.removeItem('t');setOpen(false);setPage(null);setUser(null)}}><LogOut size={20}/>Sign out</button>
      </nav></div>
    {msg&&<div className="toast" role="status">{msg}</div>}
  </Ctx.Provider>}

function Login({onIn,toast,msg,appName,canReset}){
  const [f,setF]=useState({email:'',password:''}),[b,setB]=useState(false),[mode,setMode]=useState('in'),[sent,setSent]=useState('')
  const go=async()=>{setB(true);try{const r=await api('/login',{method:'POST',body:f});localStorage.t=r.token;onIn(r.user)}catch(e){toast(e.message)}setB(false)}
  const forgot=async()=>{setB(true);try{setSent((await api('/forgot',{method:'POST',body:{email:f.email}})).message)}catch(e){toast(e.message)}setB(false)}
  if(mode==='forgot')return <div className="login"><p className="brand">{appName}</p><h1>Forgot your<br/>password?</h1>{sent?<p>{sent}</p>:<><p>Enter your account email and we will send a link to choose a new one.</p>
    <label>Email</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})} onKeyDown={e=>e.key==='Enter'&&forgot()}/>
    <button className="btn" disabled={b||!f.email} onClick={forgot}>Send reset link</button></>}
    <button className="btn ghost" onClick={()=>{setMode('in');setSent('')}}>Back to sign in</button>{msg&&<div className="toast">{msg}</div>}</div>
  return <div className="login"><p className="brand">{appName}</p><h1>Engineering,<br/>finally clear.</h1><p>Sign in with the account your admin created.</p>
    <label>Email</label><input type="email" autoComplete="email" value={f.email} onChange={e=>setF({...f,email:e.target.value})}/>
    <label>Password</label><input type="password" autoComplete="current-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Sign in</button>
    {canReset?<button className="btn ghost" onClick={()=>setMode('forgot')}>Forgot password?</button>:<p className="known">Forgot your password? Ask your admin to reset it.</p>}{msg&&<div className="toast">{msg}</div>}</div>}

function ResetPassword({token,toast,msg,done,leave,canReset}){
  const [ok,setOk]=useState(null),[f,setF]=useState({password:'',again:''}),[b,setB]=useState(false)
  useEffect(()=>{api('/reset/check',{method:'POST',body:{token}}).then(r=>setOk(r.valid)).catch(()=>setOk(false))},[token])
  const go=async()=>{if(f.password.length<8)return toast('Use at least 8 characters');if(f.password!==f.again)return toast("The passwords don't match")
    setB(true);try{const r=await api('/reset',{method:'POST',body:{token,new_password:f.password}});localStorage.t=r.token;done(r.user)}catch(e){toast(e.message)}setB(false)}
  if(ok===null)return null
  if(!ok)return <div className="login"><h1>This link<br/>has expired.</h1><p>Reset links work once and only for a short time.{canReset?' Ask for a new one from the sign-in page.':' Ask your admin to reset your password.'}</p><button className="btn" onClick={leave}>Go to sign in</button></div>
  return <div className="login"><h1>Choose a<br/>new password.</h1><p>Use at least 8 characters.</p>
    <label>New password</label><input type="password" autoComplete="new-password" value={f.password} onChange={e=>setF({...f,password:e.target.value})}/>
    <label>Repeat new password</label><input type="password" autoComplete="new-password" value={f.again} onChange={e=>setF({...f,again:e.target.value})} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Save and sign in</button>{msg&&<div className="toast">{msg}</div>}</div>}

function ChangePassword({forced,toast,msg,done,out}){
  const [f,setF]=useState({current:'',password:'',again:''}),[b,setB]=useState(false),set=k=>e=>setF({...f,[k]:e.target.value})
  const go=async()=>{if(f.password.length<8)return toast('Use at least 8 characters');if(f.password!==f.again)return toast("The new passwords don't match")
    setB(true);try{const d=await api('/me/password',{method:'POST',body:{current:f.current,new_password:f.password}});if(d.token)localStorage.t=d.token;toast('Password changed');done()}catch(e){toast(e.message)}setB(false)}
  const form=<><label>{forced?'Password your admin gave you':'Current password'}</label><input type="password" autoComplete="current-password" value={f.current} onChange={set('current')}/>
    <label>New password (8+ characters)</label><input type="password" autoComplete="new-password" value={f.password} onChange={set('password')}/>
    <label>Repeat new password</label><input type="password" autoComplete="new-password" value={f.again} onChange={set('again')} onKeyDown={e=>e.key==='Enter'&&go()}/>
    <button className="btn" disabled={b} onClick={go}>Change password</button></>
  if(forced)return <div className="login"><h1>Choose your<br/>own password.</h1><p>Your admin set a temporary password. Pick a new one to continue.</p>{form}<button className="btn ghost" onClick={out}>Sign out</button>{msg&&<div className="toast">{msg}</div>}</div>
  return <><Bar title="Change password"/><div className="main">{form}</div></>}

const Bar=({title,sub,back,right})=>{const {menu}=useContext(Ctx);return <header className="bar">
  <button className="ic menu" aria-label="Open menu" onClick={menu}><Menu/></button>{back&&<button className="ic" aria-label="Back" onClick={back}><ChevronLeft/></button>}
  <h1>{title}{sub&&<small>{sub}</small>}</h1>{right}</header>}

function Learn({user,toast,appName,start}){
  const isAdmin=user.role==='admin',staff=user.role!=='student'
  const [tree,setTree]=useState([]),[nav,setNav]=useState(start||[]),[sheet,setSheet]=useState(null),[cp,setCp]=useState(null),[t,setT]=useState(null),[ed,setEd]=useState(null),[del,setDel]=useState(null),[sh,setSh]=useState(null),[qz,setQz]=useState(null),[qe,setQe]=useState(null)
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
    :prog?prog.semesters.map(x=>({...row(x,'semesters','semester',(isAdmin?(x.number?'Semester no. '+x.number:'No semester number set')+' · ':'')+x.courses.length+' courses'),edit:()=>setSheet({type:'semester',sem:x,pid:prog.id})}))
    :tree.map(x=>({...row(x,'programs','program',x.semesters.length+' semesters'),edit:()=>setSheet({type:'program',p:x})}))
  const cur=unit||co||sem||prog,crumbs=[prog,sem,co,unit].filter(Boolean).slice(0,-1).map(x=>x.name).join(' › ')
  const allSems=tree.flatMap(p=>p.semesters.map(s=>({id:s.id,label:p.name+' › '+s.name})))
  const myCourses=tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>c.mine&&!c.shared).map(c=>({p,s,c}))))
  const saveShare=async()=>{try{await api(`/courses/${sh.id}/links`,{method:'PUT',body:{semester_ids:sh.sel}});toast('Sharing updated');setSh(null);load()}catch(e){toast(e.message)}}
  const remove=async()=>{try{if(del.unlink)await api(`/courses/${del.unlink.id}/links`,{method:'PUT',body:{semester_ids:del.unlink.keep}});else await api(`/${del.kind}/${del.id}`,{method:'DELETE'});toast('Deleted');setDel(null);load()}catch(e){toast(e.message)}}
  return <><Bar title={cur?.name||appName} sub={nav.length?crumbs:'Hi '+user.name} back={nav.length>0&&(()=>setNav(nav.slice(0,-1)))}/>
   <div className="main">{unit&&mayEdit&&drafts(unit.topics)>0&&<button className="btn" style={{marginTop:0}} onClick={()=>setPub(`/units/${unit.id}/publish`,true,'All drafts published')}>Publish all {drafts(unit.topics)} drafts</button>}{!nav.length&&<div className="hero"><h2>Pick a program.<br/>We’ll remember where you stopped.</h2></div>}
     {isAdmin&&!sem&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setSheet(prog?{type:'semester',sem:{},pid:prog.id}:{type:'program',p:{}})}>{prog?'Add semester to '+prog.name:'New program'}</button>}
     {isAdmin&&sem&&!co&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setSheet({type:'course',c:{},pid:prog.id,sid:sem.id})}>Add course to {sem.name}</button>}
     {co&&!unit&&!staff&&<p className="known" style={{marginTop:0}}>{doneOf(co.units.flatMap(n=>n.topics))} topics completed</p>}
     {co&&!unit&&staff&&<div className="qbox" style={{marginTop:0}}>{[['Program',prog.name],['Semester',sem.name+(sem.number?' (no. '+sem.number+')':'')],['Owner',co.mine?'You':co.owner_problem||co.owner||'Not assigned']].map(([l,v])=><div className="row" key={l}><div>{v}<small>{l}</small></div></div>)}
       {isAdmin&&!co.shared&&<div className="two"><button className="btn ghost" onClick={()=>setSheet({type:'course',c:co,pid:prog.id,sid:co.semester_id})}>Edit course</button><button className="btn ghost" onClick={()=>setSheet({type:'owner',c:co})}>Change owner</button></div>}</div>}
     {!nav.length&&user.role==='faculty'&&<><h3 style={{margin:'0 0 8px'}}>My courses</h3>{myCourses.length?myCourses.map(({p,s,c},i)=><div key={c.id} className="card"><button className="hit" onClick={()=>setNav([p.id,s.id,c.id])}><span className="dot" style={{background:COL[i%5]}}>{c.name[0]}</span><div><b>{c.name}</b><span>{p.name} › {s.name} · {c.units.length} units</span></div></button></div>)
       :<p className="known">No course is assigned to you yet. An admin makes you the owner of a course.</p>}<h3 style={{margin:'20px 0 8px'}}>All programs</h3></>}
    {mayEdit&&co&&!unit&&!co.shared&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setSheet({type:'unit',un:{},cid:co.id})}>Add unit</button>}
    {mayEdit&&unit&&!co.shared&&<button className="btn ghost" style={{marginTop:0,marginBottom:14}} onClick={()=>setEd({unit_id:unit.id})}>Add topic to {unit.name}</button>}
    {list.map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={x.go}><span className="dot" style={{background:COL[i%5]}}>{x.n[0]}</span><div><b>{x.n}</b>{x.sub&&<span>{x.sub}</span>}</div>{(x.s||x.b)&&<span className="marks">{x.b&&<Bookmark className="bm" size={16} fill="currentColor"/>}{x.s&&<Mark s={x.s}/>}</span>}</button>
      {mayEdit&&<>{(x.kind==='units'||x.kind==='topics')&&list.length>1&&[[-1,ArrowUp,'up'],[1,ArrowDown,'down']].map(([d,I,w])=><button key={w} className="ic sm" aria-label={`Move ${x.n} ${w}`} disabled={i+d<0||i+d>=list.length} onClick={()=>move(list,i,d,x.kind==='units'?`/courses/${co.id}/units/order`:`/units/${unit.id}/topics/order`)}><I size={16}/></button>)}{x.pub&&<button className="ic sm" aria-label={(x.draft?'Publish ':'Unpublish ')+x.n} onClick={x.pub}>{x.draft?<Eye size={16}/>:<EyeOff size={16}/>}</button>}{x.share&&<button className="ic sm" aria-label={'Share '+x.n} onClick={x.share}><Link2 size={16}/></button>}<button className="ic sm" aria-label={'Edit '+x.n} onClick={x.edit}><Pencil size={16}/></button><button className="ic sm" aria-label={'Delete '+x.n} onClick={()=>setDel(x.unlink?{...x,unlink:x.unlink}:x)}><Trash2 size={16}/></button></>}</div>)}
    {unit&&(unit.quizzes.length>0||mayEdit)&&<><h3 style={{margin:'28px 0 8px'}}>Quizzes</h3>
      {unit.quizzes.map((q,i)=><div key={q.id} className="card"><button className="hit" onClick={()=>setQz(q.id)}><span className="dot" style={{background:COL[(i+3)%5]}}>?</span><div><b>{q.title}</b><span>{q.questions} questions · pass {q.pass_percent}%{q.best!=null?' · best '+q.best+'%':''}{q.published?'':' · Draft'}</span></div>{q.best!=null&&q.best>=q.pass_percent&&<span className="marks"><Check size={16}/></span>}</button>
        {mayEdit&&<button className="ic sm" aria-label={'Edit '+q.title} onClick={()=>setQe({id:q.id,unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}><Pencil size={16}/></button>}</div>)}
      {mayEdit&&<button className="btn ghost" onClick={()=>setQe({unit_id:unit.id,unitTopics:unit.topics.map(t=>({id:t.id,title:t.title}))})}>Add quiz</button>}</>}
    {!list.length&&<p className="known">{(mayEdit&&co)||isAdmin?'Nothing here yet. Use the button above to add it.':!nav.length&&user.role==='student'?'You are not enrolled in a program yet. Ask your admin to add you to one.':'Nothing here yet. Your admin will add it soon.'}</p>}</div>
   {del&&<div className="scrim" onClick={()=>setDel(null)}><div className="sheet" onClick={e=>e.stopPropagation()}><h3>{del.unlink?'Remove':'Delete'} “{del.n}”{del.unlink?' from this semester':''}?</h3>
     <p className="known">{del.unlink?'It only disappears from this semester. The course stays where it was created.':DELETES[del.kind]} This can't be undone.</p>
     <button className="btn danger" onClick={remove}>{del.unlink?'Remove':'Delete'}</button><button className="btn ghost" onClick={()=>setDel(null)}>Keep it</button></div></div>}
   {sh&&<div className="scrim" onClick={()=>setSh(null)}><div className="sheet" onClick={e=>e.stopPropagation()}><h3>Share “{sh.name}”</h3><p className="known">Tick every semester that should also show this course. You still edit it in one place.</p>
     {allSems.filter(x=>x.id!==sh.home).map(x=><label key={x.id} className="chk"><input type="checkbox" checked={sh.sel.includes(x.id)} onChange={e=>setSh({...sh,sel:e.target.checked?[...sh.sel,x.id]:sh.sel.filter(i=>i!==x.id)})}/> {x.label}</label>)}
     <button className="btn" onClick={saveShare}>Save</button><button className="btn ghost" onClick={()=>setSh(null)}>Cancel</button></div></div>}
   {sheet?.type==='program'&&<ProgramSheet p={sheet.p} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
   {sheet?.type==='semester'&&<SemesterSheet sem={sheet.sem} pid={sheet.pid} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
   {sheet?.type==='course'&&<CourseSheet c={sheet.c} pid={sheet.pid} sid={sheet.sid} sems={tree.flatMap(p=>p.semesters.map(s=>({id:s.id,label:p.name+' › '+s.name})))} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
   {sheet?.type==='unit'&&<UnitSheet un={sheet.un} cid={sheet.cid} courses={isAdmin?tree.flatMap(p=>p.semesters.flatMap(s=>s.courses.filter(c=>!c.shared).map(c=>({id:c.id,label:`${p.name} › ${s.name} › ${c.name}`})))):null} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
   {sheet?.type==='owner'&&<OwnerSheet c={sheet.c} toast={toast} close={()=>setSheet(null)} done={()=>setSheet(null)}/>}
</>}
const DELETES={programs:"This deletes its semesters and courses with their units, topics and quizzes, and the students' reading progress, bookmarks and quiz attempts in them. Enrolled students keep their accounts but lose their program.",
  semesters:"This deletes its courses with their units, topics and quizzes, and the students' reading progress, bookmarks and quiz attempts in them. Courses shared into it from elsewhere are only unlinked.",
  courses:"This deletes its units, topics and quizzes, and the students' reading progress, bookmarks and quiz attempts in them. The owner keeps their account.",
  units:"This deletes its topics and quizzes, and the students' reading progress, bookmarks and quiz attempts in them.",
  topics:"This deletes the topic, its saved AI answers, and the students' reading progress and bookmarks for it."}
function SemesterSheet({sem,pid,close,done,toast}){
  const isNew=!sem.id,[f,setF]=useState({name:sem.name||'',no:sem.number||''}),[busy,setBusy]=useState(false)
  const pickNo=e=>{const no=e.target.value;setF({no,name:!f.name||/^Semester \d+$/.test(f.name)?(no?'Semester '+no:''):f.name})}
  const save=async()=>{setBusy(true);try{const body={name:f.name,semester_no:f.no?+f.no:null};await api(isNew?`/programs/${pid}/semesters`:'/semesters/'+sem.id,{method:isNew?'POST':'PUT',body:isNew?body:{...body,program_id:pid}});toast(isNew?'Semester added':'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?'New semester':'Edit semester'}</h3>
    <label>Semester number</label><select value={f.no} onChange={pickNo}><option value="">Choose…</option>{SEMS.map(n=><option key={n} value={n}>{n}</option>)}</select>
    <label>Name</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder="Semester 3"/>
    <p className="known" style={{marginTop:10}}>The number sets the order and which students see it: a student in semester 3 sees semesters 1 to 3. Each number is used once per program.</p>
    <button className="btn" disabled={busy||!f.no||!f.name.trim()} onClick={save}>{isNew?'Add semester':'Save changes'}</button></Sheet>}
function CourseSheet({c,pid,sid,sems,close,done,toast}){
  const isNew=!c.id,faculty=useFaculty(true),[f,setF]=useState({name:c.name||'',sem:sid,owner:c.owner_id||''}),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{const owner=String(f.owner)!==String(c.owner_id||'')?{faculty_owner_id:f.owner?+f.owner:null}:{}  // unchanged owners are left alone
    await api(isNew?`/programs/${pid}/semesters/${sid}/courses`:'/courses/'+c.id,{method:isNew?'POST':'PUT',body:isNew?{name:f.name,...owner}:{name:f.name,semester_id:+f.sem,...owner}});toast(isNew?'Course added':'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?'New course in '+(sems.find(x=>x.id===sid)?.label||''):'Edit course'}</h3>
    <label>Name</label><input value={f.name} onChange={e=>setF({...f,name:e.target.value})} placeholder="Thermodynamics"/>
    {!isNew&&<><label>Semester</label><select value={f.sem} onChange={e=>setF({...f,sem:+e.target.value})}>{sems.map(x=><option key={x.id} value={x.id}>{x.label}</option>)}</select></>}
    <label>Owner (faculty)</label><select value={f.owner} onChange={e=>setF({...f,owner:e.target.value})}><option value="">Not assigned</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner} (can't edit)</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    {!isNew&&+f.sem!==sid&&<p className="known">Moving the course takes its units, topics, quizzes and owner with it. Students of the new semester will see it.</p>}
    <button className="btn" disabled={busy||!f.name.trim()} onClick={save}>{isNew?'Add course':'Save changes'}</button></Sheet>}

const STUDY={not_started:'Not opened yet',in_progress:'Opened, not marked completed',completed:'Marked completed'}
const AREA_GROUPS=[['needs_study','Needs another round of study','Read these topics again, then retake the quiz.'],['getting_there','Getting there',''],['strong','Strong areas','You answered these well.']]
function AreaList({areas,onStudy,staff}){
  return <>{AREA_GROUPS.map(([k,title,hint])=>{const L=areas.filter(a=>a.status===k);if(!L.length)return null
    return <div className={'qbox area '+k} key={k}><b>{title} ({L.length})</b>{hint&&!staff&&<p className="known" style={{margin:'4px 0 8px'}}>{hint}</p>}
      {L.map(a=><div className="arow" key={a.topic_id||'u'+a.unit_id}><div><span>{a.title}</span><small>{a.correct} of {a.total} right · {a.percent}%{a.study&&!staff?' · '+STUDY[a.study]:''}{a.course?' · '+a.course:''}</small><Bar2 v={a.percent}/></div>
        {a.topic_id&&onStudy&&<button className="tool" onClick={()=>onStudy(a.topic_id)}>{k==='strong'?'Review':'Study again'}</button>}</div>)}</div>})}</>}
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
    {tree&&!courses.length&&<p className="known">You are not enrolled in a course yet. Ask your admin to add you to one.</p>}
    {resume&&<div className="hero"><small>{resume.status==='in_progress'?'Continue where you left off':'Start your first topic'}</small><h2 style={{fontSize:24}}>{resume.title}</h2><p>{resume.x.c.name} · {resume.unit.name}</p>
      <button className="btn" style={{background:'#160d2e',marginTop:14}} onClick={()=>setTopic(resume.id)}>{resume.status==='in_progress'?'Continue':'Start'}</button></div>}
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

function QuizEditor({id,unit_id,unitTopics,done,toast}){
  const blank=()=>({text:'',options:['',''],correct:0,explanation:'',topic_id:null})
  const [m,setM]=useState({title:'',pass_percent:50,published:false}),[qs,setQs]=useState([blank()]),[busy,setBusy]=useState(false),[topics,setTopics]=useState(unitTopics||[])
  useEffect(()=>{if(id)api('/quizzes/'+id).then(d=>{setM({title:d.title,pass_percent:d.pass_percent,published:d.published});setTopics(d.topics||[]);setQs(d.questions.length?d.questions.map(x=>({text:x.text,options:x.options,correct:x.correct,explanation:x.explanation||'',topic_id:x.topic_id??null})):[blank()])}).catch(e=>{toast(e.message);done()})},[id])
  const upd=(i,p)=>setQs(qs.map((x,n)=>n===i?{...x,...p}:x))
  const setOpt=(i,k,v)=>upd(i,{options:qs[i].options.map((o,n)=>n===k?v:o)})
  const delOpt=(i,k)=>upd(i,{options:qs[i].options.filter((_,n)=>n!==k),correct:qs[i].correct===k?0:qs[i].correct>k?qs[i].correct-1:qs[i].correct})
  const save=async()=>{setBusy(true);try{const qid=id||(await api('/quizzes',{method:'POST',body:{unit_id,...m,pass_percent:+m.pass_percent}})).id
    if(id)await api('/quizzes/'+id,{method:'PUT',body:{unit_id,...m,pass_percent:+m.pass_percent}})
    await api(`/quizzes/${qid}/questions`,{method:'PUT',body:{questions:qs.filter(x=>x.text.trim())}});toast('Quiz saved');done()}catch(e){toast(e.message)}setBusy(false)}
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
    <button className="btn" disabled={busy} onClick={save}>{busy?'Saving…':'Save quiz'}</button>
    {id&&<button className="btn danger" onClick={del}>Delete quiz</button>}</div></>}

function Topic({id,back,toast,role}){
  const [editing,setEditing]=useState(false),[v,setV]=useState(0),[t,setT]=useState(null),[tab,setTab]=useState('notes'),[known,setKnown]=useState([]),[ai,setAi]=useState({}),[aiOk,setAiOk]=useState(null),[aiMsg,setAiMsg]=useState(''),[busy,setBusy]=useState(false),[bm,setBm]=useState(false)
  const opened=useRef(false),learn=r=>setT(p=>({...p,status:r.status,overdue:r.overdue,late:r.late,completed_at:r.completed_at}))
  useEffect(()=>{api('/topics/'+id).then(x=>{setT(x);setBm(!!x.bookmarked)
    if(!opened.current){opened.current=true;api(`/topics/${id}/read`,{method:'POST'}).then(r=>{setKnown(r.known);learn(r)}).catch(()=>{})}}).catch(e=>toast(e.message))},[id,v])  // opening starts it, after the page has loaded
  const setDone=async on=>{try{learn(await api(`/topics/${id}/complete`,{method:on?'PUT':'DELETE'}));toast(on?'Marked as completed':'Marked as not completed')}catch(e){toast(e.message)}}
  useEffect(()=>{api('/ai/status').then(r=>setAiOk(r.available)).catch(()=>{})},[id])
  const ask=async k=>{setBusy(true);setAiMsg('');try{const r=await api(`/topics/${id}/ai/${k}`);setAi(a=>({...a,[k]:r}))}catch(e){setAiMsg(e.message)}setBusy(false)}
  if(editing)return <TopicEditor role={role} toast={toast} edit={{id}} done={()=>{setEditing(false);setV(v+1)}} cancel={()=>setEditing(false)}/>
  if(!t)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const flip=async()=>{const on=!bm;setBm(on);try{await api(`/topics/${id}/bookmark`,{method:on?'PUT':'DELETE'});toast(on?'Bookmarked':'Bookmark removed')}catch(e){setBm(!on);toast(e.message)}}
  const view=k=>ai[k]?<div className="prose">{ai[k].cached&&<span className="chip">Saved answer · no tokens used</span>}<Md>{ai[k].text}</Md></div>
    :aiOk===false?<p className="known">AI unavailable. Try again later.</p>
    :<><button className="btn" disabled={busy} onClick={()=>ask(k)}><Sparkles size={16}/> {busy?'Thinking…':k==='explain'?'Explain it to me':'Show a sample answer'}</button>{aiMsg&&<p className="known">{aiMsg}</p>}</>
  return <><Bar title={t.title} sub={[t.program,t.semester,t.course,t.unit].filter(Boolean).join(' › ')} back={back} right={<button className={'ic'+(bm?' on':'')} aria-label={bm?'Remove bookmark':'Bookmark this topic'} aria-pressed={bm} onClick={flip}><Bookmark fill={bm?'currentColor':'none'}/></button>}/><div className="main">
    {t.can_edit&&<div className="two" style={{marginBottom:12}}><button className="btn ghost" style={{marginTop:0}} onClick={()=>setEditing(true)}><Pencil size={16}/> Edit topic</button>
      <button className="btn ghost" style={{marginTop:0}} onClick={async()=>{try{await api(`/topics/${id}/publish`,{method:'PUT',body:{published:!t.published}});toast(t.published?'Moved to drafts':'Published');setV(v+1)}catch(e){toast(e.message)}}}>{t.published?<><EyeOff size={16}/> Unpublish</>:<><Eye size={16}/> Publish</>}</button></div>}
    <div className="qbox" style={{marginTop:0}}><div className="row"><div>{t.learning_due_at?when(t.learning_due_at):'No deadline'}<small>Learn by</small></div>{t.overdue&&role==='student'&&<span className="pill off">Overdue</span>}</div>
      {role==='student'&&<><div className="row"><div>{STATUS[t.status]}{t.status==='completed'&&t.completed_at&&' on '+when(t.completed_at)+(t.late?', after the deadline':'')}<small>Your status</small></div></div>
        {t.status==='completed'?<button className="btn ghost" onClick={()=>setDone(false)}>Mark as not completed</button>:<button className="btn" onClick={()=>setDone(true)}><Check size={16}/> Mark as completed</button>}</>}</div>
    {t.can_edit&&!t.published&&<p className="known" style={{marginTop:0}}>Draft · students cannot see it</p>}
    <div className="tabs">{[['notes','Notes'],['explain','Explain'],['answer','Sample answer']].map(([k,l])=><button key={k} className={tab===k?'on':''} onClick={()=>setTab(k)}>{l}</button>)}</div>
    {known.length>0&&tab==='explain'&&<p className="known">You’ve already covered: {known.join(', ')}</p>}
    {tab==='notes'&&<div className="prose"><Md>{t.content||'No notes yet.'}</Md>{t.question_pattern&&<><h3>Question pattern</h3><Md>{t.question_pattern}</Md></>}{t.guideline&&<><h3>Answer guideline</h3><Md>{t.guideline}</Md></>}</div>}
    {tab==='explain'&&view('explain')}{tab==='answer'&&view('answer')}</div></>}

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
    {!sm&&<p className="known">Open any topic and tap the bookmark icon to save it here. Your list is arranged by semester, course and unit.</p>}
    {sm&&<>
      <div className="chips" role="group" aria-label="Semester">{sems.map(x=><button key={x.id} className={'sbtn'+(x.id===sm.id?' on':'')} aria-pressed={x.id===sm.id} onClick={e=>{setSem(x.id);setCourse(null);setUnit(null);tabTo(e)}}>
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
const SEMS=[1,2,3,4,5,6,7,8]

function Users({toast,me}){
  const [items,setItems]=useState([]),[total,setTotal]=useState(0),[q,setQ]=useState(''),[prog,setProg]=useState(''),[sem,setSem]=useState(''),[order,setOrder]=useState('role'),[progs,setProgs]=useState([])
  const [view,setView]=useState(null),[ed,setEd]=useState(null),[bulk,setBulk]=useState(null),fileRef=useRef()
  const url=offset=>`/admin/users?q=${encodeURIComponent(q)}&order=${order}&limit=50&offset=${offset}`+(prog?'&program_id='+prog:'')+(sem?'&semester='+sem:'')
  const load=()=>api(url(0)).then(r=>{setItems(r.items);setTotal(r.total)}).catch(e=>toast(e.message))
  useEffect(()=>{const t=setTimeout(load,250);return()=>clearTimeout(t)},[q,prog,sem,order])
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name})))).catch(()=>{})},[])
  const more=()=>api(url(items.length)).then(r=>{setItems([...items,...r.items]);setTotal(r.total)}).catch(e=>toast(e.message))
  const pick=async e=>{const f=e.target.files[0];e.target.value='';if(!f)return;try{const text=await f.text();setBulk({stage:'preview',text,res:await api('/admin/users/import',{method:'POST',body:{csv:text,dry_run:true}})})}catch(err){toast(err.message)}}
  const commit=async()=>{try{setBulk({...bulk,stage:'done',res:await api('/admin/users/import',{method:'POST',body:{csv:bulk.text,dry_run:false}})});load()}catch(e){toast(e.message)}}
  const cell=v=>'"'+String(v).replace(/"/g,'""')+'"',r=bulk?.res,filtered=q||prog||sem
  if(view)return <UserDetail id={view} me={me} progs={progs} toast={toast} back={()=>{setView(null);load()}}/>
  return <><Bar title="Users" sub={total+(filtered?' matches':' accounts')}/><div className="main">
    <div className="search"><Search size={18}/><input type="search" aria-label="Search users" placeholder="Search name, email, program or semester" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters">
      <select aria-label="Filter by program" value={prog} onChange={e=>setProg(e.target.value)}><option value="">All programs</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <select aria-label="Filter by semester" value={sem} onChange={e=>setSem(e.target.value)}><option value="">All semesters</option>{SEMS.map(n=><option key={n} value={n}>Semester {n}</option>)}</select>
      <select aria-label="Sort by" value={order} onChange={e=>setOrder(e.target.value)}><option value="role">Sort: role, then name</option><option value="name">Sort: name</option><option value="program">Sort: program</option><option value="semester">Sort: semester</option><option value="newest">Sort: newest first</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>New user</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>Bulk upload</button></div>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead" aria-hidden="true"><span>Name</span><span>Program</span><span>Sem</span></div>}
    {items.map(u=><button key={u.id} className="utr" onClick={()=>setView(u.id)} aria-label={'Open '+u.name}>
      <span className="nm"><span className="dot" style={{background:COL[u.id%5]}}>{(u.name||'?')[0]}</span><span className="tx"><b>{u.name}</b>{(u.role!=='student'||!u.active)&&<span className="tags">{u.role!=='student'&&<span className="pill">{u.role==='admin'?'Admin':'Faculty'}</span>}{!u.active&&<span className="pill off">Disabled</span>}</span>}</span></span>
      <span className="pg">{u.program||'—'}</span><span className="sn">{u.semester||'—'}</span></button>)}
    {!items.length&&<p className="known">{filtered?'No one matches that search.':'No users yet.'}</p>}
    {items.length<total&&<button className="btn ghost" onClick={more}>Show more</button>}
    <input ref={fileRef} type="file" accept=".csv,.txt,text/csv" hidden onChange={pick}/></div>
    {ed&&<UserSheet u={ed} me={me} progs={progs} toast={toast} close={()=>setEd(null)} done={()=>{setEd(null);load()}}/>}
    {bulk&&<Sheet close={()=>setBulk(null)}>
      {bulk.stage==='pick'&&<><h3>Bulk upload users</h3><p className="known">One row per person with the columns name, email, password, role, program and semester. Leave the password blank to generate one. Role is student or admin and defaults to student. Program must match a name on the Programs tab, and semester is a number from 1 to 8. Emails that already exist are updated, and blank program or semester cells leave the current value alone.</p>
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
    {row({admin:'Admin',faculty:'Faculty'}[u.role]||'Student','Role')}{row(u.active?'Active':'Disabled','Status')}{row(u.program||'Not set','Program')}{row(u.semester||'Not set','Semester')}{row(day(u.last_active),'Last active')}
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
    <label>Semester</label><select value={f.semester} onChange={set('semester')}><option value="">Not set</option>{SEMS.map(n=><option key={n} value={n}>{n}</option>)}</select>
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
    <div className="search"><Search size={18}/><input type="search" aria-label="Search programs" placeholder="Search program, semester or course" value={q} onChange={e=>setQ(e.target.value)}/></div>
    <div className="filters"><select aria-label="Sort by" value={order} onChange={e=>setOrder(e.target.value)}><option value="name">Sort: name</option><option value="students">Sort: most students</option><option value="newest">Sort: newest first</option></select></div>
    <div className="two"><button className="btn" onClick={()=>setEd({})}>New program</button><button className="btn ghost" onClick={()=>setBulk({stage:'pick'})}>Bulk upload</button></div>
    <div style={{height:14}}/>
    {items.length>0&&<div className="uhead p" aria-hidden="true"><span>Program</span><span>Courses</span><span>Students</span></div>}
    {items.map(x=><button key={x.id} className="utr p" onClick={()=>setView(x.id)} aria-label={'Open '+x.name}>
      <span className="nm"><span className="dot" style={{background:COL[x.id%5]}}>{(x.name||'?')[0]}</span><span className="tx"><b>{x.name}</b><small className="sub">{x.semesters} semesters, {x.topics} topics</small></span></span>
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

function ProgramDetail({id,back,onOpen,toast}){
  const [p,setP]=useState(null),[ed,setEd]=useState(false),[ask,setAsk]=useState(false),[busy,setBusy]=useState(false),[addSem,setAddSem]=useState(false)
  const load=()=>api('/admin/programs/'+id).then(setP).catch(e=>{toast(e.message);back()})
  useEffect(()=>{load()},[id])
  if(!p)return <><Bar title="Loading" back={back}/><div className="main"><div className="sk"/><div className="sk"/></div></>
  const del=async()=>{setBusy(true);try{await api('/programs/'+p.id,{method:'DELETE'});toast('Program deleted');back()}catch(e){toast(e.message);setBusy(false)}}
  const row=(v,l,k)=><div className="row" key={k}><div>{v}<small>{l}</small></div></div>
  return <><Bar title={p.name} sub={p.semesters+' semesters'} back={back}/><div className="main">
    <div className="stats">{[['semesters','Semesters'],['courses','Courses'],['topics','Topics'],['students','Students']].map(([k,l])=><div className="stat" key={k}><b>{p[k]}</b>{l}</div>)}</div>
    <h3 style={{margin:'24px 0 4px'}}>Semesters</h3>
    {p.semester_list.length?p.semester_list.map((x,i)=><div key={x.id} className="card"><button className="hit" onClick={()=>onOpen([p.id,x.id])}><span className="dot" style={{background:COL[i%5]}}>{x.number||'?'}</span><div><b>{x.name}</b><span>{(x.number?'':'No semester number set · ')+x.courses+' courses, '+x.topics+' topics'}</span></div></button></div>):<p className="known">No semesters yet.</p>}
    <button className="btn ghost" onClick={()=>setAddSem(true)}>Add semester</button>
    <h3 style={{margin:'28px 0 4px'}}>Students</h3>
    {p.student_list.length?p.student_list.map(u=>row(u.name,(u.semester?'Semester '+u.semester:'Semester not set')+(u.active?'':', disabled'),u.id)):<p className="known">No students are enrolled yet. Set a program on a user's page.</p>}
    {p.students>p.student_list.length&&<p className="known">Showing {p.student_list.length} of {p.students}. Use Users to see everyone.</p>}
    <div className="two"><button className="btn ghost" onClick={()=>setEd(true)}>Rename</button><button className="btn danger" onClick={()=>setAsk(true)}>Delete</button></div>
    <button className="btn ghost" onClick={()=>onOpen([p.id])}>Open semesters and courses</button></div>
    {ed&&<ProgramSheet p={p} toast={toast} close={()=>setEd(false)} done={()=>{setEd(false);load()}}/>}
    {addSem&&<SemesterSheet sem={{}} pid={p.id} toast={toast} close={()=>setAddSem(false)} done={()=>{setAddSem(false);load()}}/>}
    {ask&&<Sheet close={()=>setAsk(false)}><h3>Delete “{p.name}”?</h3><p className="known">This permanently deletes {p.semesters} semesters, {p.courses} courses, {p.units} units and {p.topics} topics, including their saved AI answers.{p.students>0&&` The ${p.students} enrolled students keep their accounts but lose their program.`}</p>
      <button className="btn danger" disabled={busy} onClick={del}>Delete program</button><button className="btn ghost" onClick={()=>setAsk(false)}>Keep it</button></Sheet>}</>}

function OwnerSheet({c,close,done,toast}){
  const faculty=useFaculty(true),[sel,setSel]=useState(c.owner_id||''),[busy,setBusy]=useState(false)
  const save=async()=>{if(String(sel)===String(c.owner_id||''))return close();setBusy(true);try{await api(`/courses/${c.id}/owner`,{method:'PUT',body:{user_id:sel?+sel:null}});toast('Owner updated');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>Owner of “{c.name}”</h3><p className="known">The owner adds and edits this course's units, topics and quizzes. Changing the owner keeps all content and student progress.{c.owner_problem&&c.owner_id?' '+c.owner_problem+'.':''}</p>
    <label>Owner (faculty)</label><select value={sel} onChange={e=>setSel(e.target.value)}><option value="">Not assigned</option>{c.owner_id&&!faculty.some(u=>u.id===c.owner_id)&&<option value={c.owner_id}>{c.owner} (can't edit)</option>}{faculty.map(u=><option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}</select>
    <button className="btn" disabled={busy} onClick={save}>Save</button><button className="btn ghost" onClick={close}>Cancel</button></Sheet>}

function ProgramSheet({p,close,done,toast}){
  const isNew=!p.id,[name,setName]=useState(p.name||''),[busy,setBusy]=useState(false)
  const save=async()=>{setBusy(true);try{await api(isNew?'/programs':'/programs/'+p.id,{method:isNew?'POST':'PUT',body:{name}});toast(isNew?'Program added':'Changes saved');done()}catch(e){toast(e.message)}setBusy(false)}
  return <Sheet close={close}><h3>{isNew?'New program':'Rename program'}</h3>
    <label>Name</label><input value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==='Enter'&&save()} placeholder="B.E. Mechanical Engineering" autoFocus/>
    <p className="known" style={{marginTop:10}}>Names must be unique. The users CSV import matches programs by name.</p>
    <button className="btn" disabled={busy||!name.trim()} onClick={save}>{isNew?'Add program':'Save changes'}</button></Sheet>}

function AiConfig({toast}){
  const [cfg,setCfg]=useState({}),[key,setKey]=useState(''),[model,setModel]=useState(''),[st,setSt]=useState({})
  const load=()=>{api('/admin/settings').then(c=>{setCfg(c);setModel(c.model)});api('/admin/stats').then(setSt)};useEffect(load,[])
  const run=useRun(toast,load)
  return <><Bar title="AI & email" sub={cfg.key_set?'AI is on · key '+cfg.key_hint:'AI is off · no key yet'}/><div className="main">
    <label>DeepSeek API key</label><input type="password" value={key} onChange={e=>setKey(e.target.value)} placeholder={cfg.key_set?'Leave blank to keep the current key':'sk-…'}/>
    <label>Model</label><input value={model} onChange={e=>setModel(e.target.value)} placeholder="deepseek-chat"/>
    <button className="btn" onClick={()=>run(()=>api('/admin/settings',{method:'PUT',body:{deepseek_key:key,model}}).then(()=>setKey('')),'AI settings saved')}>Save</button>
    {cfg.key_set&&<><button className="btn ghost" onClick={async()=>{try{toast((await api('/admin/ai/test',{method:'POST'})).message)}catch(e){toast(e.message)}}}>Test the key</button>
      <button className="btn ghost" onClick={()=>confirm('Turn AI off for everyone? Students will see "AI unavailable" until you save a key again.')&&run(()=>api('/admin/settings',{method:'PUT',body:{remove_key:true}}),'AI is off')}>Remove the key (turn AI off)</button></>}
    <p className="known" style={{marginTop:20}}>One key serves every student. Until a key is saved, students see “AI unavailable. Try again later.” Each topic is explained once and the answer is shared with every student. {(st.cached??0).toLocaleString()} answers are saved so far, which has saved about {(st.tokens_saved??0).toLocaleString()} tokens.</p>
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
  useEffect(()=>{api('/tree').then(t=>setProgs(t.map(p=>({id:p.id,name:p.name})))).catch(()=>{})},[])
  const qs=`?program_id=${f.p}&semester=${f.s}`
  useEffect(()=>{setRows(null);api('/reports/courses'+qs).then(setRows).catch(e=>toast(e.message))},[f.p,f.s])
  return <><div className="qopt"><select value={f.p} onChange={e=>setF({...f,p:+e.target.value})}><option value={0}>All programs</option>{progs.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select>
    <select value={f.s} onChange={e=>setF({...f,s:+e.target.value})}><option value={0}>All semesters</option>{[1,2,3,4,5,6,7,8].map(n=><option key={n} value={n}>Semester {n}</option>)}</select></div>
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
