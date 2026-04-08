import { useEffect, useState } from 'react'

import { ChatWorkspace } from '@/components/chat/chat-workspace'
import { ThreadSidebar } from '@/components/chat/thread-sidebar'
import {
  confirmBooking,
  createThread,
  fetchHealth,
  fetchThread,
  listThreads,
  sendChatMessage,
  type HealthResponse,
  type ThreadDetail,
  type ThreadSummary,
} from '@/lib/api'

function App() {
  const [draft, setDraft] = useState('')
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [selectedThread, setSelectedThread] = useState<ThreadDetail | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [threadsLoading, setThreadsLoading] = useState(true)
  const [threadLoading, setThreadLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [creatingThread, setCreatingThread] = useState(false)
  const [bookingListingCode, setBookingListingCode] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      try {
        const [nextHealth, threadPayload] = await Promise.all([
          fetchHealth(),
          listThreads(),
        ])

        if (cancelled) {
          return
        }

        setHealth(nextHealth)
        setHealthError(null)
        setThreads(threadPayload.threads)

        const firstThread = threadPayload.threads[0]
        if (firstThread) {
          setSelectedThreadId(firstThread.id)
          void loadThread(firstThread.id, { silent: false })
        } else {
          setThreadsLoading(false)
        }
      } catch (error) {
        if (cancelled) {
          return
        }
        setThreadsLoading(false)
        setHealthError(
          error instanceof Error
            ? error.message
            : 'Unable to reach the backend.',
        )
      }
    }

    void bootstrap()

    return () => {
      cancelled = true
    }
  }, [])

  async function refreshThreads(preferredThreadId?: string) {
    const payload = await listThreads()
    setThreads(payload.threads)

    const preferred =
      payload.threads.find((thread) => thread.id === preferredThreadId) ??
      payload.threads.find((thread) => thread.id === selectedThreadId) ??
      payload.threads[0] ??
      null

    if (!preferred) {
      setSelectedThreadId(null)
      setSelectedThread(null)
      return null
    }

    setSelectedThreadId(preferred.id)
    return preferred.id
  }

  async function loadThread(threadId: string, options?: { silent?: boolean }) {
    if (!options?.silent) {
      setThreadLoading(true)
    }
    setActionError(null)

    try {
      const payload = await fetchThread(threadId)
      setSelectedThread(payload.thread)
      setSelectedThreadId(payload.thread.id)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to load thread.')
    } finally {
      setThreadLoading(false)
      setThreadsLoading(false)
    }
  }

  async function handleCreateThread() {
    setCreatingThread(true)
    setActionError(null)

    try {
      const payload = await createThread()
      await refreshThreads(payload.thread.id)
      setSelectedThread(payload.thread)
      setSelectedThreadId(payload.thread.id)
      setDraft('')
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to create thread.')
    } finally {
      setCreatingThread(false)
    }
  }

  async function handleSelectThread(threadId: string) {
    setSelectedThreadId(threadId)
    await loadThread(threadId)
  }

  async function handleSend() {
    const message = draft.trim()
    if (!message) {
      return
    }

    setSending(true)
    setActionError(null)

    try {
      const payload = await sendChatMessage(message, selectedThreadId ?? undefined)
      setDraft('')
      const nextThreadId = payload.thread.id
      await refreshThreads(nextThreadId)
      await loadThread(nextThreadId, { silent: true })
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to send message.')
    } finally {
      setSending(false)
    }
  }

  async function handleBook(listingCode: string) {
    if (!selectedThreadId) {
      return
    }

    setBookingListingCode(listingCode)
    setActionError(null)

    try {
      await confirmBooking(selectedThreadId, listingCode)
      await refreshThreads(selectedThreadId)
      await loadThread(selectedThreadId, { silent: true })
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : 'Unable to confirm booking.',
      )
    } finally {
      setBookingListingCode(null)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1500px] flex-col px-4 py-4 sm:px-6 lg:px-8">
      <div className="grid flex-1 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <ThreadSidebar
          threads={threads}
          selectedThreadId={selectedThreadId}
          isLoading={threadsLoading}
          isCreating={creatingThread}
          onCreateThread={handleCreateThread}
          onSelectThread={handleSelectThread}
        />
        <ChatWorkspace
          thread={selectedThread}
          draft={draft}
          sending={sending}
          bookingListingCode={bookingListingCode}
          loadingThread={threadLoading}
          health={health}
          healthError={healthError}
          actionError={actionError}
          onDraftChange={setDraft}
          onSend={handleSend}
          onBook={handleBook}
        />
      </div>
    </div>
  )
}

export default App
