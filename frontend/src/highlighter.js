// Highlighting text in a topic's content. The app bundles this file for Markdown and HTML topics, and the server runs the same file inside the
// sandboxed frame of an interactive topic. zgHighlighter.attach(root, {list, save, remove, changed}) marks the saved passages, offers
// "Highlight" when text is selected and "Remove highlight" when a mark is tapped. A passage is stored as its text plus the words just before
// it, and found again by searching the content's text for both, so it survives small edits elsewhere in the topic.
(function(){
  var CTX=40
  function walk(root){  // every text node under root (not inside scripts or styles), with where it starts in the joined text
    var w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:function(n){var p=n.parentNode;return p&&/^(SCRIPT|STYLE|NOSCRIPT|TEXTAREA|TEMPLATE)$/.test(p.nodeName)?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT}})
    var nodes=[],at=0,n
    while((n=w.nextNode())){nodes.push({node:n,start:at});at+=n.data.length}
    return {nodes:nodes,text:nodes.map(function(x){return x.node.data}).join('')}
  }
  function offsetOf(map,node,off){  // a selection boundary (node, offset) as a position in the joined text
    var i
    if(node.nodeType===3){for(i=0;i<map.nodes.length;i++)if(map.nodes[i].node===node)return map.nodes[i].start+off;return -1}
    var after=off<node.childNodes.length?node.childNodes[off]:null
    for(i=0;i<map.nodes.length;i++){var t=map.nodes[i].node
      if(after?(after===t||after.contains(t)||(after.compareDocumentPosition(t)&Node.DOCUMENT_POSITION_FOLLOWING)):(!node.contains(t)&&(node.compareDocumentPosition(t)&Node.DOCUMENT_POSITION_FOLLOWING)))return map.nodes[i].start}
    return map.text.length
  }
  function wrap(map,start,end,id){  // put the text between start and end in <mark> elements, one per text node it crosses
    map.nodes.forEach(function(x){
      var s=Math.max(start,x.start),e=Math.min(end,x.start+x.node.data.length)
      if(s>=e||!x.node.data.slice(s-x.start,e-x.start).trim())return
      var r=document.createRange();r.setStart(x.node,s-x.start);r.setEnd(x.node,e-x.start)
      var m=document.createElement('mark');m.className='zg-hl';m.setAttribute('data-hl',id)
      try{r.surroundContents(m)}catch{/* the passage crosses an element we cannot wrap; that part stays unmarked */}
    })
  }
  function find(map,h){var i=-1;if(h.prefix){i=map.text.indexOf(h.prefix+h.text);if(i>=0)i+=h.prefix.length}return i>=0?i:map.text.indexOf(h.text)}
  function attach(root,opts){
    var list=(opts.list||[]).slice(),pending=null,mode='',timer=null,doc=root.ownerDocument
    var btn=doc.createElement('button');btn.type='button';btn.className='zg-hl-btn';btn.style.display='none';doc.body.appendChild(btn)
    function paint(h){var map=walk(root),i=find(map,h);if(i>=0)wrap(map,i,i+h.text.length,h.id)}
    function unpaint(id){root.querySelectorAll('mark.zg-hl[data-hl="'+id+'"]').forEach(function(m){var p=m.parentNode;while(m.firstChild)p.insertBefore(m.firstChild,m);p.removeChild(m);p.normalize()})}
    function hide(){btn.style.display='none';pending=null;mode=''}
    function show(rect,label,act,kind){
      btn.textContent=label;btn.style.display='block';pending=act;mode=kind
      var top=rect.top-46;if(top<6)top=rect.bottom+8
      btn.style.top=top+'px';btn.style.left=Math.max(6,Math.min(innerWidth-btn.offsetWidth-6,rect.left+rect.width/2-btn.offsetWidth/2))+'px'
    }
    function changed(){if(opts.changed)opts.changed(list.slice())}
    function check(){
      var sel=doc.getSelection();if(!sel||sel.isCollapsed||!sel.rangeCount){if(mode==='add')hide();return}  // an empty selection leaves "Remove highlight" alone: tapping a mark makes one
      var r=sel.getRangeAt(0);if(!root.contains(r.commonAncestorContainer))return hide()
      var map=walk(root),s=offsetOf(map,r.startContainer,r.startOffset),e=offsetOf(map,r.endContainer,r.endOffset)
      if(s<0||e<=s)return hide()
      var raw=map.text.slice(s,e),text=raw.trim();if(!text||text.length>5000)return hide()
      s+=raw.length-raw.replace(/^\s+/,'').length;e=s+text.length
      var h={text:text,prefix:map.text.slice(Math.max(0,s-CTX),s)}
      show(r.getBoundingClientRect(),'Highlight',function(){
        Promise.resolve(opts.save(h)).then(function(saved){h.id=saved.id;list.push(h);wrap(walk(root),s,e,h.id);sel.removeAllRanges();changed()}).catch(function(){})
      },'add')
    }
    function onSelect(){clearTimeout(timer);timer=setTimeout(check,200)}
    function onTap(ev){
      var m=ev.target.closest&&ev.target.closest('mark.zg-hl');if(!m){if(mode==='remove')hide();return}if(!doc.getSelection().isCollapsed)return
      var id=m.getAttribute('data-hl')
      show(m.getBoundingClientRect(),'Remove highlight',function(){Promise.resolve(opts.remove(id)).then(function(){unpaint(id);list=list.filter(function(x){return String(x.id)!==String(id)});changed()}).catch(function(){})},'remove')
    }
    btn.addEventListener('mousedown',function(e){e.preventDefault()})  // keeps the selection while the button is pressed
    btn.addEventListener('click',function(){var a=pending;hide();if(a)a()})
    doc.addEventListener('selectionchange',onSelect);root.addEventListener('click',onTap);addEventListener('scroll',hide,true)
    list.forEach(paint)
    return {
      remove:function(id){unpaint(id);list=list.filter(function(x){return String(x.id)!==String(id)})},
      scrollTo:function(id){var m=root.querySelector('mark.zg-hl[data-hl="'+id+'"]');if(m)m.scrollIntoView({block:'center',behavior:'smooth'})},
      detach:function(){doc.removeEventListener('selectionchange',onSelect);root.removeEventListener('click',onTap);removeEventListener('scroll',hide,true);clearTimeout(timer);btn.remove()}
    }
  }
  window.zgHighlighter={attach:attach}
})()
