import React, { useState, useEffect, useRef, useCallback } from 'react'
import Navbar from '../components/Navbar'
import ChatPanel from '../components/ChatPanel'
import LogsPanel from '../components/LogsPanel'
import IDEPanel from '../components/IDEPanel'

export default function Chat() {
  const [logs, setLogs] = useState({})
  const [messages, setMessages] = useState([])
  const [showIDE, setShowIDE] = useState(false)
  const [bridgeOnline, setBridgeOnline] = useState(false)
  const [pendingAction, setPendingAction] = useState(null)
  const [autoApprove, setAutoApprove] = useState(false)
  const [loading, setLoading] = useState(false)

  const addMessage = useCallback((msg) => setMessages(prev => [...prev, msg]), [])

  useEffect(() => {
    const ws = new WebSocket('ws://'+window.location.host+'/api/ws')
    ws.onopen = () => setBridgeOnline(true)
    ws.onclose = () => setBridgeOnline(false)
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data)
      if (d.type === 'ai_text') { addMessage({ type:'ai', text:d.content }); setLoading(false) }
      if (d.type === 'ai_done') setLoading(false)
      if (d.type === 'auto_approve_enabled') setAutoApprove(true)
      if (d.type === 'log_block_create') {
        setLogs(prev => ({...prev, [d.block_id]:{type:d.block_type, label:d.label, lines:[], pid:null, done:false}}))
      }
      if (d.type === 'log_block_update') {
        setLogs(prev => { const n={...prev}; if (n[d.block_id]) n[d.block_id]={...n[d.block_id], pid:d.pid}; return n })
      }
      if (d.type === 'log_line') {
        setLogs(prev => {
          const n = {...prev}
          if (!n[d.block_id]) n[d.block_id] = {type:'sync', label:'Terminal', lines:[], pid:null, done:false}
          n[d.block_id] = {...n[d.block_id], lines:[...n[d.block_id].lines, {text:d.line, style:d.style||''}]}
          return n
        })
      }
      if (d.type === 'log_block_done') {
        setLogs(prev => { const n={...prev}; if (n[d.block_id]) n[d.block_id]={...n[d.block_id], done:true}; return n })
      }
      if (d.type === 'action_start') addMessage({ type:'action', actionType:d.action_type, status:'running' })
      if (d.type === 'action_pending') setPendingAction(d)
      if (d.type === 'action_result') setMessages(prev => {
        const next = [...prev]
        for (let i=next.length-1; i>=0; i--) {
          if (next[i].type==='action' && next[i].status==='running') {
            next[i] = {...next[i], status:d.success?'ok':'fail', output:d.output}
            break
          }
        }
        return next
      })
    }
    return () => ws.close()
  }, [])

  const sendMessage = async (text) => {
    addMessage({ type:'user', text })
    setLoading(true)
    fetch('/api/ask', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:text, auto_approve:autoApprove}) })
  }

  const approve = (choice) => {
    setPendingAction(null)
    if (choice === 'a') setAutoApprove(true)
    fetch('/api/approve', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({choice}) })
  }

  const removeLog = (id) => setLogs(prev => { const n={...prev}; delete n[id]; return n })

  const openTerminal = () => {
    const tid = 'manual-' + Date.now()
    setLogs(prev => ({...prev, [tid]:{type:'manual', label:'Terminal Manuel', lines:[], pid:null, interactive:true}}))
  }

  return React.createElement('div', {style:{display:'flex',flexDirection:'column',height:'100vh'}},
    React.createElement(Navbar, {bridgeOnline, onToggleIDE:()=>setShowIDE(!showIDE), onOpenTerminal:openTerminal}),
    React.createElement('div', {style:{flex:1,display:'flex',overflow:'hidden'}},
      React.createElement('div', {style:{flex:3,display:'flex',flexDirection:'column'}},
        React.createElement(ChatPanel, {messages, onSend:sendMessage, pendingAction, onApprove:approve, autoApprove, onToggleAuto:()=>setAutoApprove(!autoApprove), loading})
      ),
      React.createElement(LogsPanel, {logs, onRemove:removeLog, onOpenTerminal:openTerminal})
    ),
    showIDE && React.createElement(IDEPanel, {onClose:()=>setShowIDE(false)})
  )
}
