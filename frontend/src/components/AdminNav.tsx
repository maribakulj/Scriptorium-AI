interface AdminNavProps {
  onClick: () => void
}

export default function AdminNav({ onClick }: AdminNavProps) {
  return (
    <button
      onClick={onClick}
      className="text-stone-400 hover:text-stone-100 text-sm transition-colors"
    >
      Administration
    </button>
  )
}
