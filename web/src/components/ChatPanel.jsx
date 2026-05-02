import React, { useState, useRef, useEffect } from 'react'
import MessageBubble from './MessageBubble'
import ActionCard from './ActionCard'

export default function ChatPanel({ messages, onSend, pendingAction, onApprove, autoApprove, onToggleAuto, loading }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({behavior:'smooth'}) }, [messages, pendingAction, loading])

  const handleSend = () => {
    if (!input.trim()) return
    onSend(input)
    setInput('')
  }

  const now = () => new Date().toLocaleTimeString()

  return React.createElement(React.Fragment, null,
    React.createElement('div', {style:{flex:1,overflowY:'auto',padding:20,display:'flex',flexDirection:'column',gap:10}},
      messages.map((m,i) =>
        React.createElement(React.Fragment, {key:i},
          React.createElement('span', {style:{fontSize:9,color:'var(--text2)',alignSelf:m.type==='user'?'flex-end':'flex-start',padding:'0 4px'}}, now()),
          m.type==='action'
            ? React.createElement(ActionCard, {...m})
            : React.createElement(MessageBubble, {...m})
        )
      ),
      loading && React.createElement('div', {style:{alignSelf:'flex-start',padding:'10px 16px',background:'var(--card)',border:'1px solid var(--border)',borderRadius:12,display:'flex',alignItems:'center',gap:10}},
        React.createElement('span', {style:{width:16,height:16,border:'2px solid var(--border)',borderTop:'2px solid var(--accent)',borderRadius:'50%',animation:'spin 0.8s linear infinite'}}),
        React.createElement('span', {style:{color:'var(--text2)',fontSize:13}}, 'NEMESIS reflechit...')
      ),
      pendingAction && React.createElement('div', {
        style:{alignSelf:'flex-start',background:'var(--bg2)',border:'2px solid var(--warn)',borderRadius:8,padding:12,maxWidth:'85%'}
      },
        React.createElement('p', {style:{color:'var(--warn)',fontWeight:'bold',marginBottom:8}}, 'Action en attente : ' + pendingAction.action_type.toUpperCase()),
        React.createElement('p', {style:{color:'var(--text2)',fontSize:12,marginBottom:8}}, pendingAction.content),
        React.createElement('div', {style:{display:'flex',gap:8}},
          React.createElement('button', {onClick:()=>onApprove('y'), style:{padding:'6px 16px',background:'var(--accent)',color:'var(--bg)',border:'none',borderRadius:4,cursor:'pointer',fontWeight:'bold'}}, 'Y - Approuver'),
          React.createElement('button', {onClick:()=>onApprove('n'), style:{padding:'6px 16px',background:'var(--danger)',color:'white',border:'none',borderRadius:4,cursor:'pointer'}}, 'N - Refuser'),
          React.createElement('button', {onClick:()=>onApprove('a'), style:{padding:'6px 16px',background:'var(--info)',color:'white',border:'none',borderRadius:4,cursor:'pointer'}}, 'A - Tout approuver')
        )
      ),
      React.createElement('div', {ref:bottomRef})
    ),
    React.createElement('div', {style:{borderTop:'1px solid var(--border)',padding:10,background:'var(--bg2)'}},
      React.createElement('div', {style:{display:'flex',gap:6,marginBottom:6,alignItems:'center'}},
        React.createElement('label', {style:{display:'flex',alignItems:'center',gap:4,color:'var(--text2)',fontSize:11,cursor:'pointer'}},
          React.createElement('input', {type:'checkbox',checked:autoApprove,onChange:onToggleAuto}),
          'Auto-approuver'
        )
      ),
      React.createElement('div', {style:{display:'flex',gap:8}},
        React.createElement('textarea', {
          value:input, onChange:e=>setInput(e.target.value),
          onKeyDown:e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();handleSend()}},
          placeholder:"Message...", rows:2,
          style:{flex:1,padding:10,background:'var(--bg3)',border:'1px solid var(--border)',borderRadius:6,color:'var(--text)',resize:'none',fontFamily:'inherit'}
        }),
        React.createElement('button', {onClick:handleSend, disabled:loading, style:{width:42,height:42,background:loading?'var(--border)':'var(--accent)',color:'var(--bg)',border:'none',borderRadius:'50%',fontSize:20,cursor:loading?'wait':'pointer'}}, '>')
      )
    )
  )
}