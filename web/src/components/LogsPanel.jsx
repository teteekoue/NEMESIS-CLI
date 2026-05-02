import React from 'react'
import LogBlock from './LogBlock'

export default function LogsPanel({ logs, onRemove, onOpenTerminal }) {
  const entries = Object.entries(logs)

  return React.createElement('div', {
    style: {flex:1,minWidth:280,maxWidth:400,background:'var(--bg2)',borderLeft:'1px solid var(--border)',display:'flex',flexDirection:'column'}
  },
    React.createElement('div', {style:{padding:'8px 12px',background:'var(--bg3)',borderBottom:'1px solid var(--border)',display:'flex',justifyContent:'space-between',alignItems:'center'}},
      React.createElement('span', {style:{fontSize:13,fontWeight:'bold',color:'var(--accent)'}}, 'Terminaux'),
      React.createElement('button', {onClick:onOpenTerminal, style:{background:'var(--accent)',color:'var(--bg)',border:'none',padding:'3px 10px',borderRadius:4,cursor:'pointer',fontSize:11,fontWeight:'bold'}}, '+ Terminal')
    ),
    React.createElement('div', {style:{flex:1,overflowY:'auto',padding:8,display:'flex',flexDirection:'column',gap:6}},
      entries.length===0 && React.createElement('p', {style:{color:'var(--text2)',textAlign:'center',padding:20,fontSize:13}}, 'Aucun terminal. Lancez une commande ou ouvrez un terminal manuel.'),
      entries.map(([id,log]) => React.createElement(LogBlock, {key:id, id, ...log, onRemove}))
    )
  )
}
