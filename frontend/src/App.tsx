import { useEffect, useState } from 'react'

import { ChatWorkspace } from '@/components/chat/chat-workspace'
import { ThreadSidebar } from '@/components/chat/thread-sidebar'
import { fetchHealth, type HealthResponse } from '@/lib/api'

function App() {
  const [draft, setDraft] = useState('')
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadHealth() {
      try {
        const nextHealth = await fetchHealth()
        if (!cancelled) {
          setHealth(nextHealth)
          setHealthError(null)
        }
      } catch (error) {
        if (!cancelled) {
          setHealthError(
            error instanceof Error
              ? error.message
              : 'Unable to reach the backend health endpoint.',
          )
        }
      }
    }

    void loadHealth()

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1500px] flex-col px-4 py-4 sm:px-6 lg:px-8">
      <div className="grid flex-1 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <ThreadSidebar />
        <ChatWorkspace
          draft={draft}
          onDraftChange={setDraft}
          health={health}
          healthError={healthError}
        />
      </div>
    </div>
  )
}

export default App
