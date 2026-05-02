import React from 'react'

export default function ActionCard({ actionType, status, output }) {
  const statusColor = status==='ok'?'var(--accent)':status==='fail'?'var(--danger)':'var(--warn)'
  const statusText = status==='running'?'En cours...':status==='ok'?'OK':'ECHEC'

  return React.createElement('div', {
    style: {
      alignSelf:'flex-start',maxWidth:'85%',padding:'8px 14px',borderRadius:8,
      background:'var(--bg2)',border:'1px solid var(--border)',
      borderLeft:'3px solid '+statusColor,
      display:'flex',alignItems:'center',gap:10,fontSize:13
    }
  },
    React.createElement('span', null, '⚡'),
    React.createElement('span', {style:{color:'var(--info)',fontWeight:'bold',fontFamily:'monospace'}}, (actionType||'').toUpperCase()),
    React.createElement('span', {style:{color:statusColor}}, statusText),
    output && React.createElement('span', {style:{color:'var(--text2)',fontSize:11,maxHeight:40,overflow:'hidden'}}, output.substring(0,100))
  )
}
