// The reader page inside the Android app: a topic's content (or a long AI answer) rendered by the web's own components, with the web's highlighter.
// The app hands it the text and its colours (window.zgReader.show), and everything the reader does goes back to the app as a message
// (window.ZigoraBridge.post): saving, recolouring or removing a highlight, a note, Explain, "Not clear?", links and the page's height.
// It never calls the server itself and holds no sign-in: the app does that.
import {useState,useEffect,useRef} from 'react'
import {createRoot} from 'react-dom/client'
import {Body} from './content.jsx'
import './styles.css'
import './highlighter.js'

const post=m=>{try{window.ZigoraBridge?.post(JSON.stringify(m))}catch{/* outside the app: nothing to tell */}}
let n=0;const waiting={}
const ask=m=>new Promise((ok,no)=>{const k=++n;waiting[k]=[ok,no];post({...m,k})})
let setOpts=null,hl=null
window.zgReader={
  show:o=>setOpts?.(o),
  reply:(k,d)=>{const w=waiting[k];if(!w)return;delete waiting[k];(d&&d.error?w[1]:w[0])(d||{})},
  scrollTo:id=>hl?.scrollTo(id),unpaint:id=>hl?.remove(id)}

function Reader(){
  const [o,setO]=useState(null),box=useRef(null);setOpts=setO
  useEffect(()=>{post({type:'ready'})},[])
  useEffect(()=>{if(!o)return;const r=document.documentElement,c=o.colors||{}
    r.lang=o.lang||'en';r.dir=o.dir||'ltr'
    for(const [k,v] of Object.entries(c))r.style.setProperty('--'+k,v)
    r.style.fontSize=(o.fontScale||1)*100+'%'},[o])
  useEffect(()=>{if(!o||!box.current)return
    box.current.querySelectorAll('img[src^="/api/"]').forEach(i=>{i.src=(o.base||'')+i.getAttribute('src')})  // uploads live on the college's server
    if(!o.highlights||!window.zgHighlighter)return
    hl=window.zgHighlighter.attach(box.current,{list:o.list||[],
      save:x=>ask({type:'save',text:x.text,prefix:x.prefix,color:x.color}),remove:id=>ask({type:'remove',id}),update:(id,c)=>ask({type:'update',id,color:c.color}),
      note:id=>post({type:'note',id}),doubt:p=>post({type:'doubt',phrase:p}),doubtLabel:o.doubtLabel,...(o.explain?{explain:id=>post({type:'explain',id})}:{}),
      changed:l=>post({type:'changed',count:l.length})})
    return()=>{hl?.detach();hl=null}},[o])
  useEffect(()=>{const root=document.getElementById('root'),send=()=>post({type:'height',h:Math.ceil(root.getBoundingClientRect().height)})  // the content's own height, so the card shrinks too
    const ro=new ResizeObserver(send);ro.observe(root);send();return()=>ro.disconnect()},[o])
  useEffect(()=>{const click=e=>{const a=e.target.closest?.('a[href]');if(!a)return;e.preventDefault();post({type:'link',href:a.href})}
    addEventListener('click',click);return()=>removeEventListener('click',click)},[])
  if(!o)return null
  return <div className="prose zgr" ref={box}><Body text={o.text} format={o.format}/></div>}

createRoot(document.getElementById('root')).render(<Reader/>)
