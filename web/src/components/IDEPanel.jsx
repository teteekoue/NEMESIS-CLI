import React, { useState, useEffect, useRef } from 'react'

export default function IDEPanel({ onClose }) {
  const [tree, setTree] = useState([])
  const [currentPath, setCurrentPath] = useState('')
  const [content, setContent] = useState('')
  const [status, setStatus] = useState('')
  const editorRef = useRef(null)
  const lineRef = useRef(null)

  useEffect(() => { navigateDir('') }, [])

  const navigateDir = (dir) => {
    setCurrentPath(dir)
    setContent('')
    fetch('/api/workspace/read?path='+encodeURIComponent(dir||''))
      .then(r => r.json())
      .then(d => {
        if (d.success && d.is_dir) setTree(d.files||[])
        if (d.success && !d.is_dir) setContent(d.content||'')
      })
      .catch(() => {})
  }

  const loadFile = (path) => {
    setCurrentPath(path)
    fetch('/api/workspace/read?path='+encodeURIComponent(path))
      .then(r => r.json())
      .then(d => {
        if (d.success && !d.is_dir) setContent(d.content||'')
        if (d.success && d.is_dir) navigateDir(path)
      })
      .catch(() => {})
  }

  const save = () => {
    if (!currentPath) return
    fetch('/api/workspace/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:currentPath,content})})
      .then(r=>r.json()).then(d=>{
        setStatus(d.success?'Sauvegarde OK':'Erreur: '+d.error)
        setTimeout(()=>setStatus(''),2000)
      })
  }

  const goUp = () => {
    if (!currentPath || !currentPath.includes('/')) { navigateDir(''); return }
    const parts = currentPath.split('/')
    parts.pop()
    navigateDir(parts.join('/'))
  }

  const lineCount = (content||'').split('\n').length
  const lineNumbers = Array.from({length:Math.max(lineCount,1)}, (_,i) => i+1).join('\n')

  const handleScroll = () => {
    if (lineRef.current && editorRef.current) {
      lineRef.current.scrollTop = editorRef.current.scrollTop
    }
  }

  return React.createElement('div', {
    style: {position:'fixed',top:42,right:0,bottom:0,width:'45%',background:'var(--bg2)',borderLeft:'2px solid var(--accent)',display:'flex',flexDirection:'column',zIndex:100}
  },
    React.createElement('div', {style:{display:'flex',alignItems:'center',gap:8,padding:'6px 12px',background:'var(--bg3)',borderBottom:'1px solid var(--border)'}},
      React.createElement('span', {style:{color:'var(--accent)',fontWeight:'bold',fontSize:13}}, 'IDE'),
      React.createElement('button', {onClick:goUp, style:{background:'var(--bg)',border:'1px solid var(--border)',color:'var(--text)',borderRadius:4,padding:'2px 8px',cursor:'pointer',fontSize:12}}, '↑'),
      React.createElement('span', {style:{color:'var(--text2)',fontSize:11,flex:1}}, currentPath||'workspace/'),
      React.createElement('button', {onClick:save, style:{padding:'4px 10px',background:'var(--accent)',color:'var(--bg)',border:'none',borderRadius:4,cursor:'pointer',fontSize:12}}, 'Sauver'),
      React.createElement('button', {onClick:onClose, style:{background:'none',border:'none',color:'var(--danger)',cursor:'pointer',fontSize:16}}, 'X')
    ),
    React.createElement('div', {style:{flex:1,display:'flex',overflow:'hidden'}},
      React.createElement('div', {style:{width:'30%',overflowY:'auto',padding:8,background:'var(--bg)',borderRight:'1px solid var(--border)'}},
        tree.map(f =>
          React.createElement('div', {key:f.path, onClick:()=>f.is_dir?navigateDir(f.path):loadFile(f.path),
            style:{padding:'4px 6px',cursor:'pointer',color:f.is_dir?'var(--info)':'var(--text)',fontSize:12,fontFamily:'monospace',borderRadius:4,background:currentPath===f.path?'var(--bg3)':'transparent'}},
            (f.is_dir?'📁 ':'📄 ') + f.name
          )
        )
      ),
      React.createElement('div', {style:{display:'flex',flex:1,overflow:'hidden'}},
        React.createElement('pre', {ref:lineRef, style:{width:40,padding:'12px 4px',background:'#111',color:'var(--text2)',fontFamily:'monospace',fontSize:13,textAlign:'right',margin:0,overflow:'hidden',userSelect:'none'}},
          lineNumbers
        ),
        React.createElement('textarea', {ref:editorRef, value:content, onChange:e=>setContent(e.target.value), onScroll:handleScroll,
style:{flex:1,padding:12,background:'#000',border:'none',color:'var(--accent)',fontFamily:'monospace',fontSize:13,resize:'none',outline:'none',tabSize:4,lineHeight:'1.5',overflowX:'auto',overflowY:'auto',whiteSpace:'pre'}
        })
      )
    ),
    status && React.createElement('div', {style:{padding:'3px 12px',background:'var(--bg3)',fontSize:11,color:status.includes('Erreur')?'var(--danger)':'var(--accent)'}}, status)
  )
}