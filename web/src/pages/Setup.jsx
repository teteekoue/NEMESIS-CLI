import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Setup({ onReady }) {
  const nav = useNavigate()
  const [host, setHost] = useState('192.168.1.71')
  const [port, setPort] = useState('8080')
  const [workspace, setWorkspace] = useState('./workspace')
  const [sendPrompt, setSendPrompt] = useState(true)
  const [status, setStatus] = useState('')
  const [aiResponse, setAiResponse] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setStatus('Connexion au Bridge...')
    setAiResponse('')
    try {
      const r = await fetch('/api/init', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({host, port:parseInt(port), workspace, send_prompt:sendPrompt})
      })
      const data = await r.json()
      if (data.success) {
        if (data.ai_response) {
          setStatus('Prompt envoye. Reponse de l\'IA recue.')
          setAiResponse(data.ai_response)
          setTimeout(() => { onReady(); nav('/'); }, 1500)
        } else {
          setStatus('NEMESIS pret. Redirection...')
          setTimeout(() => { onReady(); nav('/'); }, 800)
        }
      } else {
        setStatus('Erreur: ' + (data.error || 'inconnu'))
        setLoading(false)
      }
    } catch(err) {
      setStatus('Erreur reseau: ' + err.message)
      setLoading(false)
    }
  }

  const inputStyle = {width:'100%',padding:10,background:'var(--bg3)',border:'1px solid var(--border)',borderRadius:6,color:'var(--text)',marginTop:4}

  return React.createElement('div', {style:{display:'flex',justifyContent:'center',alignItems:'center',height:'100vh'}},
    React.createElement('form', {onSubmit:submit, style:{background:'var(--bg2)',border:'1px solid var(--border)',borderRadius:12,padding:40,width:420}},
      React.createElement('h1', {style:{color:'var(--accent)',textAlign:'center',marginBottom:8}}, 'NEMESIS Web UI'),
      React.createElement('p', {style:{color:'var(--text2)',textAlign:'center',marginBottom:24}}, 'Configuration du Bridge Android'),
      React.createElement('div', {style:{marginBottom:12}},
        React.createElement('label', {style:{color:'var(--text2)',fontSize:13}}, 'Adresse IP'),
        React.createElement('input', {value:host, onChange:e=>setHost(e.target.value), style:inputStyle})
      ),
      React.createElement('div', {style:{marginBottom:12}},
        React.createElement('label', {style:{color:'var(--text2)',fontSize:13}}, 'Port'),
        React.createElement('input', {value:port, onChange:e=>setPort(e.target.value), style:inputStyle})
      ),
      React.createElement('div', {style:{marginBottom:12}},
        React.createElement('label', {style:{color:'var(--text2)',fontSize:13}}, 'Workspace'),
        React.createElement('input', {value:workspace, onChange:e=>setWorkspace(e.target.value), style:inputStyle})
      ),
      React.createElement('label', {style:{display:'flex',alignItems:'center',gap:8,color:'var(--text2)',fontSize:13,marginBottom:16}},
        React.createElement('input', {type:'checkbox',checked:sendPrompt,onChange:e=>setSendPrompt(e.target.checked)}),
        'Envoyer le prompt systeme'
      ),
      React.createElement('button', {disabled:loading, style:{width:'100%',padding:12,background:loading?'var(--border)':'var(--accent)',color:'var(--bg)',border:'none',borderRadius:6,fontSize:16,fontWeight:'bold',cursor:loading?'wait':'pointer'}},
        loading ? 'Connexion...' : 'Demarrer NEMESIS'
      ),
      status && React.createElement('p', {style:{marginTop:12,fontSize:13,color:status.includes('Erreur')?'var(--danger)':'var(--accent)',textAlign:'center'}}, status),
      aiResponse && React.createElement('div', {style:{marginTop:12,padding:10,background:'var(--bg3)',borderRadius:6,fontSize:12,color:'var(--text2)',maxHeight:120,overflowY:'auto',whiteSpace:'pre-wrap',border:'1px solid var(--border)'}}, aiResponse)
    )
  )
}
