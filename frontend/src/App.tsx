import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ChatWorkspace } from '@/components/chat/chat-workspace'
import { ThreadFiltersPanel } from '@/components/chat/thread-filters-panel'
import { ThreadSidebar } from '@/components/chat/thread-sidebar'
import {
  deleteThread,
  fetchHealth,
  fetchThread,
  listThreads,
  sendChatMessage,
  type HealthResponse,
  type ThreadDetail,
  type ThreadMessage,
  type ThreadSummary,
} from '@/lib/api'

function App() {
  const { threadId: urlThreadId } = useParams<{ threadId?: string }>()
  const navigate = useNavigate()

  const [draft, setDraft] = useState('')
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [selectedThread, setSelectedThread] = useState<ThreadDetail | null>(null)
  const [, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [threadsLoading, setThreadsLoading] = useState(true)
  const [threadsOffset, setThreadsOffset] = useState(0)
  const [hasMoreThreads, setHasMoreThreads] = useState(false)
  const [isLoadingMoreThreads, setIsLoadingMoreThreads] = useState(false)
  const [threadLoading, setThreadLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [actionRetryLabel, setActionRetryLabel] = useState<string | null>(null)
  const actionRetryRef = useRef<null | (() => Promise<void> | void)>(null)

  // Whether we're in "pending new chat" mode — no thread yet, waiting for first message
  const isNewChat = !urlThreadId

  // ─── Bootstrap on mount ────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      setThreadsLoading(true)
      setHealthError(null)

      try {
        const [nextHealth, threadPayload] = await Promise.all([fetchHealth(), listThreads(20, 0)])
        if (cancelled) return

        setHealth(nextHealth)
        setThreads(threadPayload.threads)
        setThreadsOffset(0)
        setHasMoreThreads(threadPayload.has_more)

        if (urlThreadId) {
          // URL already has a thread — load it directly
          setThreadLoading(true)
          try {
            const payload = await fetchThread(urlThreadId)
            if (cancelled) return
            setSelectedThread(payload.thread)
          } catch (error) {
            if (cancelled) return
            setActionError(error instanceof Error ? error.message : 'Unable to load thread.')
            registerActionRetry('Retry loading thread', () => loadThread(urlThreadId))
          } finally {
            if (!cancelled) {
              setThreadLoading(false)
              setThreadsLoading(false)
            }
          }
        } else {
          // No thread in URL — stay on / to show new chat screen
          if (!cancelled) {
            setThreadsLoading(false)
          }
        }
      } catch (error) {
        if (cancelled) return
        setThreadsLoading(false)
        setHealthError(error instanceof Error ? error.message : 'Unable to reach the backend.')
      }
    }

    void bootstrap()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Run once on mount; URL-driven loading is handled by the effect below

  // ─── Load thread when URL threadId changes (e.g. back/forward nav) ─────────

  useEffect(() => {
    if (!urlThreadId) {
      // Navigated to / — clear selected thread (new chat mode)
      setSelectedThread(null)
      setActionError(null)
      clearActionRetry()
      return
    }

    // Don't re-fetch if we already have this thread loaded
    if (selectedThread?.id === urlThreadId) return

    void loadThread(urlThreadId)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlThreadId])

  // ─── Helpers ───────────────────────────────────────────────────────────────

  function clearActionRetry() {
    actionRetryRef.current = null
    setActionRetryLabel(null)
  }

  function registerActionRetry(label: string, action: () => Promise<void> | void) {
    actionRetryRef.current = action
    setActionRetryLabel(label)
  }

  async function loadThread(threadId: string, options?: { silent?: boolean }) {
    if (!options?.silent) setThreadLoading(true)
    setActionError(null)
    clearActionRetry()

    try {
      const payload = await fetchThread(threadId)
      setSelectedThread(payload.thread)
      clearActionRetry()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to load thread.')
      registerActionRetry('Retry loading thread', () => loadThread(threadId, options))
    } finally {
      setThreadLoading(false)
      setThreadsLoading(false)
    }
  }

  async function refreshThreads(preferredThreadId?: string) {
    const payload = await listThreads(20, 0)
    setThreads(payload.threads)
    setThreadsOffset(0)
    setHasMoreThreads(payload.has_more)

    // Return the preferred (or first) thread id for the caller to navigate to
    const preferred =
      payload.threads.find((t) => t.id === preferredThreadId) ??
      payload.threads.find((t) => t.id === selectedThread?.id) ??
      payload.threads[0] ??
      null

    return preferred?.id ?? null
  }

  async function loadMoreThreads() {
    if (!hasMoreThreads || isLoadingMoreThreads) return

    setIsLoadingMoreThreads(true)
    try {
      const nextOffset = threadsOffset + 20
      const payload = await listThreads(20, nextOffset)
      setThreads((prev) => {
        const currentIds = new Set(prev.map((t) => t.id))
        return [...prev, ...payload.threads.filter((t) => !currentIds.has(t.id))]
      })
      setThreadsOffset(nextOffset)
      setHasMoreThreads(payload.has_more)
    } catch {
      // fail silently
    } finally {
      setIsLoadingMoreThreads(false)
    }
  }

  async function bootstrapApp() {
    setThreadsLoading(true)
    setHealthError(null)

    try {
      const [nextHealth, threadPayload] = await Promise.all([fetchHealth(), listThreads(20, 0)])
      setHealth(nextHealth)
      setThreads(threadPayload.threads)
      setThreadsOffset(0)
      setHasMoreThreads(threadPayload.has_more)

      const firstThread = threadPayload.threads[0]
      if (firstThread) {
        navigate(`/t/${firstThread.id}`, { replace: true })
      } else {
        setSelectedThread(null)
        setThreadsLoading(false)
      }
    } catch (error) {
      setThreadsLoading(false)
      setHealthError(error instanceof Error ? error.message : 'Unable to reach the backend.')
    }
  }

  // ─── Event handlers ────────────────────────────────────────────────────────

  function handleCreateThread() {
    if (isNewChat) {
      // Already on new-chat screen — just clear the draft
      setDraft('')
      return
    }
    setDraft('')
    setActionError(null)
    clearActionRetry()
    navigate('/')
  }

  function handleSelectThread(threadId: string) {
    navigate(`/t/${threadId}`)
  }

  async function handleDeleteThread(threadId: string) {
    try {
      setThreads((prev) => prev.filter((t) => t.id !== threadId))
      
      if (threadId === urlThreadId) {
        navigate('/', { replace: true })
      }

      await deleteThread(threadId)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Unable to delete thread.')
      void refreshThreads(urlThreadId ?? undefined)
    }
  }

  async function handleSend(overrideMessage?: string) {
    const message = (overrideMessage ?? draft).trim()
    if (!message) return

    if (selectedThread?.status === 'booked') {
      clearActionRetry()
      setActionError(
        'This thread already has a confirmed booking. Start a new thread to plan another event.',
      )
      return
    }

    // Optimistic update for existing threads
    const optimisticMessage: ThreadMessage = {
      id: `opt-${Date.now()}`,
      position: (selectedThread?.messages.length ?? 0) + 1,
      role: 'user',
      content: message,
      tool_name: '',
      metadata: {},
      created_at: new Date().toISOString(),
    }
    
    const previousThread = selectedThread
    
    if (selectedThread) {
      setSelectedThread({
        ...selectedThread,
        messages: [...selectedThread.messages, optimisticMessage],
      })
    } else {
      setSelectedThread({
        id: 'temp-new-thread',
        title: 'New conversation',
        status: 'active',
        summary: '',
        last_message_preview: message,
        last_activity_at: new Date().toISOString(),
        message_count: 1,
        active_filters: {},
        latest_result_context: {},
        pending_booking: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        messages: [optimisticMessage],
      })
    }

    setSending(true)
    setDraft('')
    setActionError(null)
    clearActionRetry()

    try {
      // Pass urlThreadId (undefined for new-chat) — backend auto-creates thread when omitted
      const payload = await sendChatMessage(message, urlThreadId ?? undefined)
      const nextThreadId = payload.thread.id

      await refreshThreads(nextThreadId)
      await loadThread(nextThreadId, { silent: true })

      // Navigate to the (possibly newly created) thread URL
      if (!urlThreadId || urlThreadId !== nextThreadId) {
        navigate(`/t/${nextThreadId}`, { replace: true })
      }

      clearActionRetry()
    } catch (error) {
      setDraft(message)
      if (previousThread) {
        setSelectedThread((prev) =>
          prev
            ? { ...prev, messages: prev.messages.filter((m) => m.id !== optimisticMessage.id) }
            : prev,
        )
      } else {
        setSelectedThread(null)
      }
      setActionError(error instanceof Error ? error.message : 'Unable to send message.')
      registerActionRetry('Retry sending message', () => {
        setDraft(message)
        void handleSend()
      })
    } finally {
      setSending(false)
    }
  }

  async function handleRetryAction() {
    if (!actionRetryRef.current) return
    setActionError(null)
    await actionRetryRef.current()
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <div className="grid h-full min-h-0 flex-1 lg:grid-cols-[280px_minmax(0,1fr)] xl:grid-cols-[280px_minmax(0,1fr)_320px]">
        <ThreadSidebar
          threads={threads}
          selectedThreadId={isNewChat ? null : (urlThreadId ?? null)}
          isLoading={threadsLoading}
          isCreating={false}
          hasMore={hasMoreThreads}
          isLoadingMore={isLoadingMoreThreads}
          onLoadMore={loadMoreThreads}
          onCreateThread={handleCreateThread}
          onSelectThread={handleSelectThread}
          onDeleteThread={handleDeleteThread}
        />
        <ChatWorkspace
          thread={selectedThread}
          draft={draft}
          sending={sending}
          loadingThread={threadLoading}
          healthError={healthError}
          actionError={actionError}
          actionRetryLabel={actionRetryLabel}
          isCreatingThread={false}
          onDraftChange={setDraft}
          onSend={(msg?: string) => handleSend(msg)}
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
