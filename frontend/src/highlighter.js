// Highlighting text in a topic's content. The app bundles this file for Markdown and HTML topics, and the server runs the same file inside the
// sandboxed frame of an interactive topic. zgHighlighter.attach(root, {list, save, remove, update, note, explain, changed}) marks the saved passages,
// offers colour swatches when text is selected, and colours, Explain, Note and Remove when a highlight is tapped. A passage is stored as its text plus
// the words just before it, and found again by searching the content's text for both, so it survives small edits elsewhere in the topic.
(function(){
  var CTX=40
  var COLORS={coral:'rgba(255,146,146,.5)',yellow:'rgba(255,214,10,.45)',green:'rgba(80,200,120,.4)',blue:'rgba(90,160,255,.38)'}
  var CSS='mark.zg-hl{color:inherit;border-radius:2px;cursor:pointer;padding:0;background:'+COLORS.coral+'}'+
    Object.keys(COLORS).map(function(c){return 'mark.zg-hl[data-c="'+c+'"]{background:'+COLORS[c]+'}'}).join('')+
    '.zg-hl-bar{position:fixed;z-index:2147483647;display:flex;align-items:center;gap:6px;padding:6px 8px;border-radius:12px;background:#2a1238;color:#fff;'+
    'box-shadow:0 8px 24px rgba(0,0,0,.3);font:600 13px system-ui,-apple-system,sans-serif}'+
    '.zg-hl-bar button{border:0;cursor:pointer;font:inherit;margin:0}.zg-hl-bar .zg-l{padding:0 2px 0 4px;opacity:.85}'+
    '.zg-hl-sw{width:24px;height:24px;border-radius:50%;padding:0;box-shadow:inset 0 0 0 2px rgba(255,255,255,.7)}.zg-hl-sw.on{box-shadow:0 0 0 2px #fff}'+
    '.zg-hl-tx{background:transparent;color:#fff;padding:5px 8px;border-radius:6px}.zg-hl-tx:hover{background:rgba(255,255,255,.15)}'
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
  function wrap(map,start,end,id,color){  // put the text between start and end in <mark> elements, one per text node it crosses
    map.nodes.forEach(function(x){
      var s=Math.max(start,x.start),e=Math.min(end,x.start+x.node.data.length)
      if(s>=e||!x.node.data.slice(s-x.start,e-x.start).trim())return
      var r=document.createRange();r.setStart(x.node,s-x.start);r.setEnd(x.node,e-x.start)
      var m=document.createElement('mark');m.className='zg-hl';m.setAttribute('data-hl',id);m.setAttribute('data-c',color||'coral')
      try{r.surroundContents(m)}catch{/* the passage crosses an element we cannot wrap; that part stays unmarked */}
    })
  }
  function find(map,h){var i=-1;if(h.prefix){i=map.text.indexOf(h.prefix+h.text);if(i>=0)i+=h.prefix.length}return i>=0?i:map.text.indexOf(h.text)}
  function attach(root,opts){
    var list=(opts.list||[]).slice(),mode='',timer=null,doc=root.ownerDocument
    if(!doc.getElementById('zg-hl-style')){var st=doc.createElement('style');st.id='zg-hl-style';st.textContent=CSS;(doc.head||doc.body).appendChild(st)}
    var bar=doc.createElement('div');bar.className='zg-hl-bar';bar.style.display='none';bar.setAttribute('role','toolbar');bar.setAttribute('aria-label','Highlight');doc.body.appendChild(bar)
    bar.addEventListener('mousedown',function(e){e.preventDefault()})  // keeps the selection while a button is pressed
    function marks(id){return root.querySelectorAll('mark.zg-hl[data-hl="'+id+'"]')}
    function paint(h){var map=walk(root),i=find(map,h);if(i>=0)wrap(map,i,i+h.text.length,h.id,h.color)}
    function unpaint(id){marks(id).forEach(function(m){var p=m.parentNode;while(m.firstChild)p.insertBefore(m.firstChild,m);p.removeChild(m);p.normalize()})}
    function recolor(id,c){marks(id).forEach(function(m){m.setAttribute('data-c',c)});list.forEach(function(x){if(String(x.id)===String(id))x.color=c})}
    function hide(){bar.style.display='none';mode=''}
    function changed(){if(opts.changed)opts.changed(list.slice())}
    function button(cls,label,title,act){var b=doc.createElement('button');b.type='button';b.className=cls;b.textContent=label;if(title){b.title=title;b.setAttribute('aria-label',title)}b.addEventListener('click',function(){hide();act()});return b}
    function swatches(current,verb,pick){return Object.keys(COLORS).map(function(c){var b=button('zg-hl-sw'+(c===current?' on':''),'',verb+' '+c,function(){pick(c)});b.style.background=COLORS[c].replace(/,[.\d]+\)$/,',1)');return b})}
    function show(rect,kind,items){
      mode=kind;bar.innerHTML='';items.forEach(function(x){bar.appendChild(x)});bar.style.display='flex'
      var top=rect.top-50;if(top<6)top=rect.bottom+8
      bar.style.top=top+'px';bar.style.left=Math.max(6,Math.min(innerWidth-bar.offsetWidth-6,rect.left+rect.width/2-bar.offsetWidth/2))+'px'
    }
    function check(){
      var sel=doc.getSelection();if(!sel||sel.isCollapsed||!sel.rangeCount){if(mode==='add')hide();return}  // an empty selection leaves a tapped highlight's tools alone
      var r=sel.getRangeAt(0);if(!root.contains(r.commonAncestorContainer))return hide()
      var map=walk(root),s=offsetOf(map,r.startContainer,r.startOffset),e=offsetOf(map,r.endContainer,r.endOffset)
      if(s<0||e<=s)return hide()
      var raw=map.text.slice(s,e),text=raw.trim();if(!text||text.length>5000)return hide()
      s+=raw.length-raw.replace(/^\s+/,'').length;e=s+text.length
      var prefix=map.text.slice(Math.max(0,s-CTX),s),label=doc.createElement('span');label.className='zg-l';label.textContent='Highlight'
      show(r.getBoundingClientRect(),'add',[label].concat(swatches('','Highlight in',function(c){
        var h={text:text,prefix:prefix,color:c}
        Promise.resolve(opts.save(h)).then(function(saved){h.id=saved.id;list.push(h);wrap(walk(root),s,e,h.id,c);sel.removeAllRanges();changed()}).catch(function(){})
      })).concat(opts.doubt&&text.length<=300?[button('zg-hl-tx',opts.doubtLabel||'Not clear?','Ask about this phrase',function(){opts.doubt(text)})]:[]))
    }
    function onSelect(){clearTimeout(timer);timer=setTimeout(check,200)}
    function onTap(ev){
      var m=ev.target.closest&&ev.target.closest('mark.zg-hl');if(!m){if(mode==='edit')hide();return}if(!doc.getSelection().isCollapsed)return
      var id=m.getAttribute('data-hl')
      show(m.getBoundingClientRect(),'edit',swatches(m.getAttribute('data-c')||'coral','Make it',function(c){Promise.resolve(opts.update&&opts.update(id,{color:c})).then(function(){recolor(id,c);changed()}).catch(function(){})})
        .concat(opts.explain?[button('zg-hl-tx','Explain','Explain this passage',function(){opts.explain(id)})]:[])
        .concat(opts.note?[button('zg-hl-tx','Note','Add a note to this highlight',function(){opts.note(id)})]:[])
        .concat([button('zg-hl-tx','Remove','Remove this highlight',function(){Promise.resolve(opts.remove(id)).then(function(){unpaint(id);list=list.filter(function(x){return String(x.id)!==String(id)});changed()}).catch(function(){})})]))
    }
    doc.addEventListener('selectionchange',onSelect);root.addEventListener('click',onTap);addEventListener('scroll',hide,true)
    list.forEach(paint)
    return {
      remove:function(id){unpaint(id);list=list.filter(function(x){return String(x.id)!==String(id)})},
      setColor:recolor,
      scrollTo:function(id){var m=marks(id)[0];if(m)m.scrollIntoView({block:'center',behavior:'smooth'})},
      detach:function(){doc.removeEventListener('selectionchange',onSelect);root.removeEventListener('click',onTap);removeEventListener('scroll',hide,true);clearTimeout(timer);bar.remove()}
    }
  }
  window.zgHighlighter={attach:attach,colors:COLORS}
})()
