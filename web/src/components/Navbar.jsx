import React from 'react'

export default function Navbar({ bridgeOnline, onToggleIDE, onOpenTerminal }) {
  const btnStyle = {background:'var(--bg3)',color:'var(--text)',border:'1px solid var(--border)',padding:'4px 12px',borderRadius:6,cursor:'pointer',fontSize:12}

  return React.createElement('nav', {
    style: {height:42,background:'var(--bg2)',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',padding:'0 16px',gap:12,flexShrink:0}
  },
    React.createElement('span', {style:{fontWeight:'bold',color:'var(--accent)',fontSize:16}}, 'NEMESIS'),
    React.createElement('span', {style:{width:10,height:10,borderRadius:'50%',background:bridgeOnline?'var(--accent)':'var(--danger)',boxShadow:bridgeOnline?'0 0 8px var(--accent)':'none'}}),
    React.createElement('span', {style:{color:'var(--text2)',fontSize:13}}, bridgeOnline?'En ligne':'Deconnecte'),
    React.createElement('div', {style:{marginLeft:'auto',display:'flex',gap:8}},
      React.createElement('button', {onClick:onOpenTerminal, style:btnStyle}, 'Terminal'),
      React.createElement('button', {onClick:onToggleIDE, style:btnStyle}, 'IDE')
    )
  )
}
