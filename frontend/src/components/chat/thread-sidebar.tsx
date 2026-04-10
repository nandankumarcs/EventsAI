import { useEffect, useRef } from 'react'
import { Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
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
}: ThreadSidebarProps) {
  const sentinelRef = useRef<HTMLDivElement>(null)

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
      <div className="p-3">
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
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="px-3 py-2 text-xs font-semibold text-muted-foreground">
          Recents
        </div>

        <div className="min-h-0 flex-1 space-y-[2px] overflow-y-auto px-2 pb-4">
          {isLoading ? (
            <div className="p-3 text-sm text-muted-foreground">Loading...</div>
          ) : null}

          {!isLoading && threads.length === 0 ? (
            <div className="p-3 text-sm text-muted-foreground">No recent chats.</div>
          ) : null}

          {threads.map((thread) => {
            const isActive = thread.id === selectedThreadId
            return (
              <button
                key={thread.id}
                type="button"
                className={cn(
                  'block w-full rounded-lg px-3 py-2.5 text-left text-sm transition',
                  isActive
                    ? 'bg-accent/80 font-medium text-accent-foreground'
                    : 'text-muted-foreground hover:bg-accent/40 hover:text-foreground',
                )}
                onClick={() => onSelectThread(thread.id)}
              >
                <div className="truncate">{thread.title}</div>
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


