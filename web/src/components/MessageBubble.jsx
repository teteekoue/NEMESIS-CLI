import React from 'react'

export default function MessageBubble({ type, text }) {
  if (!text) return null
  const isUser = type === 'user'
  return React.createElement('div', {
    style: {
      alignSelf: isUser?'flex-end':'flex-start',
      maxWidth:'80%',padding:'10px 14px',borderRadius:12,
      background: isUser?'var(--accent)':'var(--card)',
      color: isUser?'var(--bg)':'var(--text)',
      border: isUser?'none':'1px solid var(--border)',
      borderBottomRightRadius: isUser?4:12,
      borderBottomLeftRadius: isUser?12:4,
      fontSize:14,lineHeight:1.5,whiteSpace:'pre-wrap'
    }
  }, text)
}
