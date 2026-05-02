import React, { useState, useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Setup from './pages/Setup'
import Chat from './pages/Chat'

export default function App() {
  const [ready, setReady] = useState(null)

  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(d => setReady(d.initialized ? true : false))
      .catch(() => setReady(false))
  }, [])

  if (ready === null) return null

  return React.createElement(Routes, null,
    React.createElement(Route, { path: "/setup", element: React.createElement(Setup, {onReady:()=>setReady(true)}) }),
    React.createElement(Route, { path: "/*", element: ready ? React.createElement(Chat) : React.createElement(Navigate, {to:"/setup"}) })
  )
}
