import { useState } from 'react'
import Admin from './pages/Admin.tsx'
import Editor from './pages/Editor.tsx'
import Home from './pages/Home.tsx'
import Reader from './pages/Reader.tsx'

type View =
  | { name: 'home' }
  | { name: 'reader'; manuscriptId: string; profileId: string }
  | { name: 'admin' }
  | { name: 'editor'; pageId: string }

export default function App() {
  const [view, setView] = useState<View>({ name: 'home' })

  if (view.name === 'reader') {
    return (
      <Reader
        manuscriptId={view.manuscriptId}
        profileId={view.profileId}
        onBack={() => setView({ name: 'home' })}
        onEdit={(pageId) => setView({ name: 'editor', pageId })}
      />
    )
  }

  if (view.name === 'admin') {
    return <Admin onHome={() => setView({ name: 'home' })} />
  }

  if (view.name === 'editor') {
    return (
      <Editor
        pageId={view.pageId}
        onBack={() => setView({ name: 'home' })}
      />
    )
  }

  return (
    <Home
      onOpenManuscript={(manuscriptId, profileId) =>
        setView({ name: 'reader', manuscriptId, profileId })
      }
      onAdmin={() => setView({ name: 'admin' })}
    />
  )
}
