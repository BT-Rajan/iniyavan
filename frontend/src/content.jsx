// How a topic's content and the AI's answers are shown: Markdown with tables and maths (KaTeX, chemistry with mhchem), or the cleaned HTML of an
// uploaded file. Shared by the web app and the reader page the Android app shows (reader.jsx), so both render the same text the same way.
import Markdown,{defaultUrlTransform} from 'react-markdown'
import {at,atHtml} from './base.js'
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
const url=u=>defaultUrlTransform(at(u))  // saved pictures (/api/uploads/...) under the site's folder
export const Md=({children})=><Markdown remarkPlugins={[remarkGfm,remarkMath]} rehypePlugins={[rehypeKatex]} urlTransform={url}>{fixTables(children)}</Markdown>
// a topic's content: Markdown, or HTML from an uploaded file (the server cleans it on every save and every read, so it carries no scripts or styles)
export const Body=({text,format})=>format==='html'?<div className="htmlc" dangerouslySetInnerHTML={{__html:atHtml(text||'')}}/>:<Md>{text}</Md>
