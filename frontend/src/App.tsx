import { useEffect, useRef, useState } from 'react'

import { ChatWorkspace } from '@/components/chat/chat-workspace'
import { ThreadFiltersPanel } from '@/components/chat/thread-filters-panel'
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
  const [actionRetryLabel, setActionRetryLabel] = useState<string | null>(null)
  const actionRetryRef = useRef<null | (() => Promise<void> | void)>(null)

  useEffect(() => {
    let cancelled = false

    async function bootstrapOnMount() {
      setThreadsLoading(true)
      setHealthError(null)

      try {
        const [nextHealth, threadPayload] = await Promise.all([fetchHealth(), listThreads()])
        if (cancelled) {
          return
        }

        setHealth(nextHealth)
        setThreads(threadPayload.threads)

        const firstThread = threadPayload.threads[0]
        if (firstThread) {
          setThreadLoading(true)
          setActionError(null)
          setSelectedThreadId(firstThread.id)

          try {
            const payload = await fetchThread(firstThread.id)
            if (cancelled) {
              return
            }
            setSelectedThread(payload.thread)
            setSelectedThreadId(payload.thread.id)
          } catch (error) {
            if (cancelled) {
              return
            }
            setActionError(error instanceof Error ? error.message : 'Unable to load thread.')
            actionRetryRef.current = async () => {
              setThreadLoading(true)
              setActionError(null)
              clearActionRetry()

              try {
                const payload = await fetchThread(firstThread.id)
                setSelectedThread(payload.thread)
                setSelectedThreadId(payload.thread.id)
              } catch (retryError) {
                setActionError(
                  retryError instanceof Error ? retryError.message : 'Unable to load thread.',
                )
                setActionRetryLabel('Retry loading thread')
              } finally {
                setThreadLoading(false)
                setThreadsLoading(false)
              }
            }
            setActionRetryLabel('Retry loading thread')
          } finally {
            if (!cancelled) {
              setThreadLoading(false)
              setThreadsLoading(false)
            }
          }
        } else {
          setSelectedThread(null)
          setSelectedThreadId(null)
          setThreadsLoading(false)
        }
      } catch (error) {
        if (cancelled) {
          return
        }
        setThreadsLoading(false)
        setHealthError(error instanceof Error ? error.message : 'Unable to reach the backend.')
      }
    }

    void bootstrapOnMount()

    return () => {
      cancelled = true
    }
  }, [])

  function clearActionRetry() {
    actionRetryRef.current = null
    setActionRetryLabel(null)
  }

  function registerActionRetry(label: string, action: () => Promise<void> | void) {
    actionRetryRef.current = action
    setActionRetryLabel(label)
  }

  async function bootstrapApp() {
    setThreadsLoading(true)
    setHealthError(null)

    try {
      const [nextHealth, threadPayload] = await Promise.all([fetchHealth(), listThreads()])

      setHealth(nextHealth)
      setThreads(threadPayload.threads)

      const firstThread = threadPayload.threads[0]
      if (firstThread) {
        setSelectedThreadId(firstThread.id)
        await loadThread(firstThread.id, { silent: false })
      } else {
        setSelectedThread(null)
        setSelectedThreadId(null)
        setThreadsLoading(false)
      }
    } catch (error) {
      setThreadsLoading(false)
      setHealthError(error instanceof Error ? error.message : 'Unable to reach the backend.')
    }
  }

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
    clearActionRetry()

    try {
      const payload = await fetchThread(threadId)
      setSelectedThread(payload.thread)
      setSelectedThreadId(payload.thread.id)
      clearActionRetry()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to load thread.')
      registerActionRetry('Retry loading thread', () => loadThread(threadId, options))
    } finally {
      setThreadLoading(false)
      setThreadsLoading(false)
    }
  }

  async function handleCreateThread() {
    setCreatingThread(true)
    setActionError(null)
    clearActionRetry()

    try {
      const payload = await createThread()
      await refreshThreads(payload.thread.id)
      setSelectedThread(payload.thread)
      setSelectedThreadId(payload.thread.id)
      setDraft('')
      clearActionRetry()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to create thread.')
      registerActionRetry('Retry creating thread', handleCreateThread)
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
    if (selectedThread?.status === 'booked') {
      clearActionRetry()
      setActionError(
        'This thread already has a confirmed booking. Start a new thread to plan another event.',
      )
      return
    }

    setSending(true)
    setActionError(null)
    clearActionRetry()

    try {
      const payload = await sendChatMessage(message, selectedThreadId ?? undefined)
      setDraft('')
      const nextThreadId = payload.thread.id
      await refreshThreads(nextThreadId)
      await loadThread(nextThreadId, { silent: true })
      clearActionRetry()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to send message.')
      registerActionRetry('Retry sending message', handleSend)
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
    clearActionRetry()

    try {
      await confirmBooking(selectedThreadId, listingCode)
      await refreshThreads(selectedThreadId)
      await loadThread(selectedThreadId, { silent: true })
      clearActionRetry()
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : 'Unable to confirm booking.',
      )
      registerActionRetry('Retry booking confirmation', () => handleBook(listingCode))
    } finally {
      setBookingListingCode(null)
    }
  }

  async function handleRetryAction() {
    if (!actionRetryRef.current) {
      return
    }

    setActionError(null)
    await actionRetryRef.current()
  }

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <div className="grid h-full min-h-0 flex-1 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_300px]">
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
          actionRetryLabel={actionRetryLabel}
          isCreatingThread={creatingThread}
          onDraftChange={setDraft}
          onSend={handleSend}
          onBook={handleBook}
          onCreateThread={handleCreateThread}
          onRetryHealth={bootstrapApp}
          onRetryAction={handleRetryAction}
        />
        <ThreadFiltersPanel thread={selectedThread} />
      </div>
    </div>
  )
}

export default App
