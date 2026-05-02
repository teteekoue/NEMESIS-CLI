import React, { useRef, useEffect, useState } from 'react'

export default function LogBlock({ id, type, label, lines, interactive, pid, onRemove }) {
  const [localLines, setLocalLines] = useState(lines||[])
  const [input, setInput] = useState('')
  const wsRef = useRef(null)
  const contentRef = useRef(null)

  useEffect(() => {
    if (interactive) {
      const ws = new WebSocket('ws://'+window.location.host+'/api/terminal/ws')
      wsRef.current = ws
      ws.onmessage = (e) => {
        const d = JSON.parse(e.data)
        if (d.type === 'output') {
          setLocalLines(prev => [...prev, {text:d.data, style:''}])
        }
      }
      return () => ws.close()
    }
  }, [interactive])

  useEffect(() => {
    if (contentRef.current) contentRef.current.scrollTop = contentRef.current.scrollHeight
  }, [localLines])

  const sendCmd = () => {
    if (!input.trim() || !wsRef.current) return
    setLocalLines(prev => [...prev, {text:'$ '+input+'\n', style:'info'}])
    wsRef.current.send(JSON.stringify({type:'input', data:input+'\n'}))
    setInput('')
  }

  const handleRemove = () => {
    if (pid && type==='async') {
      fetch('/api/kill_process',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pid:pid})})
    }
    onRemove(id)
  }

  const allText = localLines.map(l => l.text).join('')

  return React.createElement('div', {
    style: {background:'#000',border:'1px solid var(--border)',borderRadius:6,overflow:'hidden',display:'flex',flexDirection:'column',minHeight:30,maxHeight:interactive?350:200}
  },
    React.createElement('div', {style:{display:'flex',justifyContent:'space-between',padding:'2px 8px',background:'var(--bg3)',fontSize:11,fontFamily:'monospace'}},
      React.createElement('span', {style:{color:type==='sync'?'var(--info)':type==='async'?'var(--warn)':'var(--accent)'}}, (label||type) + (pid?' [PID '+pid+']':'')),
      React.createElement('button', {onClick:handleRemove, style:{background:'none',border:'none',color:'var(--text2)',cursor:'pointer'}}, 'X')
    ),
    React.createElement('pre', {ref:contentRef, style:{flex:1,overflowY:'auto',padding:'4px 8px',fontFamily:'monospace',fontSize:11,color:'var(--accent)',whiteSpace:'pre-wrap',margin:0}},
      allText
    ),
    interactive && React.createElement('div', {style:{display:'flex',borderTop:'1px solid var(--border)'}},
      React.createElement('input', {value:input, onChange:e=>setInput(e.target.value), onKeyDown:e=>{if(e.key==='Enter')sendCmd()},
        placeholder:'$ ...', style:{flex:1,background:'#000',border:'none',color:'var(--accent)',padding:'4px 8px',fontFamily:'monospace',fontSize:12,outline:'none'}
      })
    )
  )
}
