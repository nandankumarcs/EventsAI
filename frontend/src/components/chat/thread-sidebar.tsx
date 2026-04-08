import { Clock3, Sparkles } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type Thread = {
  id: string
  title: string
  preview: string
  active?: boolean
}

const demoThreads: Thread[] = [
  {
    id: 'weekend-sports',
    title: 'Weekend sports',
    preview: 'Looking for cricket in Delhi around 7 PM.',
    active: true,
  },
  {
    id: 'movie-night',
    title: 'Movie night',
    preview: 'Hindi thriller options for Sunday evening.',
  },
  {
    id: 'family-plan',
    title: 'Family plan',
    preview: 'Kid-friendly experiences in Gurgaon.',
  },
]

export function ThreadSidebar() {
  return (
    <aside className="flex w-full max-w-sm flex-col gap-5">
      <Card className="border-white/70 bg-white/85">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-primary/12 text-primary">
              <Sparkles className="size-5" />
            </div>
            <div>
              <CardTitle>Attend</CardTitle>
              <CardDescription>
                Chat-first event discovery with stateful filters.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            Phase 1 gives us the shell: sidebar threads, main chat workspace, and a live
            backend connection check.
          </p>
          <p>
            Future phases will wire persisted conversations, filters, and agent-driven event
            retrieval.
          </p>
        </CardContent>
      </Card>

      <div className="space-y-3">
        <p className="px-1 text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
          Recent threads
        </p>
        {demoThreads.map((thread) => (
          <article
            key={thread.id}
            className={cn(
              'rounded-[24px] border border-border/70 bg-white/75 p-4 shadow-sm backdrop-blur transition hover:border-primary/40 hover:bg-white',
              thread.active && 'border-primary/30 bg-white shadow-md',
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-foreground">{thread.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {thread.preview}
                </p>
              </div>
              <Clock3 className="mt-1 size-4 shrink-0 text-muted-foreground" />
            </div>
          </article>
        ))}
      </div>
    </aside>
  )
}

