import { Clock3, Plus, Ticket } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
    <aside className="flex w-full max-w-sm flex-col gap-5">
      <Card className="border-white/80 bg-white/88">
        <CardHeader className="gap-4">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="inline-flex size-11 items-center justify-center rounded-2xl bg-primary/12 text-primary">
                <Ticket className="size-5" />
              </div>
              <div>
                <CardTitle>Attend</CardTitle>
                <CardDescription>
                  Stateful event discovery through chat, not filters.
                </CardDescription>
              </div>
            </div>
            <Button
              type="button"
              size="icon"
              variant="outline"
              aria-label="Create a new chat thread"
              disabled={isCreating}
              onClick={onCreateThread}
            >
              <Plus className="size-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            Each thread carries its own saved filter state, so follow-ups like
            “actually Mumbai” update the same search journey.
          </p>
          <div className="flex flex-wrap gap-2">
            <Badge variant="default">{threads.length} threads</Badge>
            <Badge variant="success">
              {threads.filter((thread) => thread.status === 'booked').length} booked
            </Badge>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        <p className="px-1 text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
          Recent threads
        </p>

        <div className="space-y-3">
          {isLoading ? (
            <Card className="border-dashed bg-white/60">
              <CardContent className="py-8 text-sm text-muted-foreground">
                Loading saved threads...
              </CardContent>
            </Card>
          ) : null}

          {!isLoading && threads.length === 0 ? (
            <Card className="border-dashed bg-white/60">
              <CardContent className="py-8 text-sm text-muted-foreground">
                Start a thread and tell Attend what you want to watch.
              </CardContent>
            </Card>
          ) : null}

          {threads.map((thread) => {
            const isActive = thread.id === selectedThreadId
            const filters = Object.entries(thread.active_filters ?? {}).slice(0, 2)

            return (
              <button
                key={thread.id}
                type="button"
                className={cn(
                  'block w-full rounded-[24px] border border-border/70 bg-white/76 p-4 text-left shadow-sm transition hover:border-primary/40 hover:bg-white',
                  isActive && 'border-primary/30 bg-white shadow-md',
                )}
                onClick={() => onSelectThread(thread.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-foreground">{thread.title}</h3>
                      {thread.status === 'booked' ? (
                        <Badge variant="success">Booked</Badge>
                      ) : null}
                    </div>
                    <p className="line-clamp-2 text-sm leading-6 text-muted-foreground">
                      {thread.last_message_preview || 'No messages yet.'}
                    </p>
                    {filters.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {filters.map(([key, value]) => (
                          <span
                            key={key}
                            className="rounded-full bg-accent/70 px-3 py-1 text-xs font-medium text-accent-foreground"
                          >
                            {Array.isArray(value) ? value.join(', ') : value}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock3 className="size-4" />
                    <span>{formatRelativeDate(thread.last_activity_at)}</span>
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>
    </aside>
  )
}

function formatRelativeDate(value: string) {
  const date = new Date(value)
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
  }).format(date)
}
