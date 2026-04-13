import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Trash2, Check, X, Ticket } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { ThreadSummary } from '@/lib/api'
import { cn } from '@/lib/utils'

type ThreadSidebarProps = {
  threads: ThreadSummary[]
  selectedThreadId: string | null
  isLoading: boolean
  isCreating: boolean
  hasMore: boolean
  isLoadingMore: boolean
  onLoadMore: () => void
  onCreateThread: () => void
  onSelectThread: (threadId: string) => void
  onDeleteThread: (threadId: string) => void
}

export function ThreadSidebar({
  threads,
  selectedThreadId,
  isLoading,
  isCreating,
  hasMore,
  isLoadingMore,
  onLoadMore,
  onCreateThread,
  onSelectThread,
  onDeleteThread,
}: ThreadSidebarProps) {
  const sentinelRef = useRef<HTMLDivElement>(null)
  const [threadToDelete, setThreadToDelete] = useState<string | null>(null)

  useEffect(() => {
    if (!sentinelRef.current || !hasMore || isLoadingMore) {
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0] && entries[0].isIntersecting) {
          onLoadMore()
        }
      },
      {
        root: null, // relative to viewport (or closest scrollable ancestor depending on markup)
        rootMargin: '100px', // load a bit intuitively before reaching the absolute edge
        threshold: 0.1,
      }
    )

    observer.observe(sentinelRef.current)

    return () => {
      observer.disconnect()
    }
  }, [hasMore, isLoadingMore, onLoadMore])

  return (
    <aside className="flex h-full min-h-0 w-full flex-col bg-muted/30 border-r border-border/50 overflow-hidden">
      <div className="p-3 space-y-2 border-b border-border/40">
        <Button
          type="button"
          variant="outline"
          className="w-full justify-start gap-2 bg-background shadow-xs hover:bg-accent"
          disabled={isCreating}
          onClick={onCreateThread}
        >
          <Plus className="size-4" />
          {isCreating ? 'Opening...' : 'New chat'}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="w-full justify-start gap-2 text-muted-foreground hover:bg-accent hover:text-foreground"
          asChild
        >
          <Link to="/bookings">
            <Ticket className="size-4" />
            Bookings
          </Link>
        </Button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="px-3 py-2 text-xs font-semibold text-muted-foreground">
          Recents
        </div>

        <div className="min-h-0 flex-1 space-y-[2px] overflow-y-auto px-2 pb-4">
          {isLoading ? (
            <div className="space-y-[2px] px-1 pt-1">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex flex-col gap-1.5 rounded-lg px-3 py-2.5">
                  <Skeleton className="h-3 w-[85%] rounded-full" style={{ width: `${60 + (i * 13) % 35}%` }} />
                  <Skeleton className="h-2.5 w-[50%] rounded-full opacity-60" />
                </div>
              ))}
            </div>
          ) : null}

          {!isLoading && threads.length === 0 ? (
            <div className="p-3 text-sm text-muted-foreground">No recent chats.</div>
          ) : null}

          {threads.map((thread) => {
            const isActive = thread.id === selectedThreadId
            const isConfirming = threadToDelete === thread.id

            if (isConfirming) {
              return (
                <div
                  key={thread.id}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm bg-destructive/15 text-destructive font-medium transition"
                >
                  <span className="flex-1 truncate text-left">Sure?</span>
                  <div className="ml-2 flex items-center gap-1">
                    <button
                      type="button"
                      className="flex items-center justify-center rounded p-1 hover:bg-destructive/25 focus:outline-none"
                      onClick={(e) => {
                        e.stopPropagation()
                        setThreadToDelete(null)
                        onDeleteThread(thread.id)
                      }}
                      title="Confirm delete"
                    >
                      <Check className="size-[14px]" />
                    </button>
                    <button
                      type="button"
                      className="flex items-center justify-center rounded p-1 hover:bg-destructive/25 focus:outline-none"
                      onClick={(e) => {
                        e.stopPropagation()
                        setThreadToDelete(null)
                      }}
                      title="Cancel"
                    >
                      <X className="size-[14px]" />
                    </button>
                  </div>
                </div>
              )
            }

            return (
              <button
                key={thread.id}
                type="button"
                title={thread.title}
                onClick={() => onSelectThread(thread.id)}
                className={cn(
                  'group flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm transition focus:outline-none',
                  isActive
                    ? 'bg-accent/80 font-medium text-accent-foreground'
                    : 'text-muted-foreground hover:bg-accent/40 hover:text-foreground',
                )}
              >
                <span className="flex-1 text-left truncate">
                  {thread.title}
                </span>
                <div
                  role="button"
                  tabIndex={0}
                  className="ml-2 flex items-center justify-center rounded p-1 opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 focus:opacity-100 focus:outline-none"
                  onClick={(e) => {
                    e.stopPropagation()
                    setThreadToDelete(thread.id)
                  }}
                  title="Delete chat"
                >
                  <Trash2 className="size-[14px]" />
                </div>
              </button>
            )
          })}

          {hasMore ? (
            <div
              ref={sentinelRef}
              className="py-4 text-center text-xs font-semibold text-muted-foreground"
            >
              {isLoadingMore ? 'Loading more...' : ''}
            </div>
          ) : threads.length > 0 ? (
            <div className="py-4 text-center text-[10px] uppercase tracking-wider text-muted-foreground opacity-50">
              End of history
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  )
}


