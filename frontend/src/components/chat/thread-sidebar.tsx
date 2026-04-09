import { Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import type { ThreadSummary } from '@/lib/api'
import { cn } from '@/lib/utils'

type ThreadSidebarProps = {
  threads: ThreadSummary[]
  selectedThreadId: string | null
  isLoading: boolean
  isCreating: boolean
  onCreateThread: () => void
  onSelectThread: (threadId: string) => void
}

export function ThreadSidebar({
  threads,
  selectedThreadId,
  isLoading,
  isCreating,
  onCreateThread,
  onSelectThread,
}: ThreadSidebarProps) {
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
        </div>
      </div>
    </aside>
  )
}


