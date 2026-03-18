import { useState } from 'react'
import Home from './pages/Home.tsx'
import Reader from './pages/Reader.tsx'

type View =
  | { name: 'home' }
  | { name: 'reader'; manuscriptId: string; profileId: string }

export default function App() {
  const [view, setView] = useState<View>({ name: 'home' })

  if (view.name === 'reader') {
    return (
      <Reader
        manuscriptId={view.manuscriptId}
        profileId={view.profileId}
        onBack={() => setView({ name: 'home' })}
      />
    )
  }

  return (
    <Home
      onOpenManuscript={(manuscriptId, profileId) =>
        setView({ name: 'reader', manuscriptId, profileId })
      }
    />
  )
}
