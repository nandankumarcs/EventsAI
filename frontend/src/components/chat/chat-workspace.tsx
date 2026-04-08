import { Bot, DatabaseZap, SendHorizontal, UserRound } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import type { HealthResponse } from '@/lib/api'

type ChatWorkspaceProps = {
  draft: string
  onDraftChange: (value: string) => void
  health: HealthResponse | null
  healthError: string | null
}

const sampleMessages = [
  {
    role: 'assistant',
    content:
      'Tell me what you want to watch or attend, and I will keep refining the results as your filters evolve.',
  },
  {
    role: 'user',
    content: 'I want to watch a cricket match this Sunday in Delhi around 7 PM.',
  },
  {
    role: 'assistant',
    content:
      'Nice. In later phases I will resolve event type, date, location, and time into deterministic filters before fetching exact results from PostgreSQL.',
  },
]

export function ChatWorkspace({
  draft,
  onDraftChange,
  health,
  healthError,
}: ChatWorkspaceProps) {
  const backendOnline = health?.status === 'ok'

  return (
    <main className="flex min-h-[720px] flex-1 flex-col gap-5">
      <Card className="border-white/70 bg-white/85">
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Conversational booking workspace</CardTitle>
            <CardDescription>
              The main interface is already centered around chat, with the backend health
              check confirming our local integration path.
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={backendOnline ? 'success' : 'warning'}>
              {backendOnline ? 'Backend connected' : 'Backend needs attention'}
            </Badge>
            <Badge>
              {health?.database.reachable ? 'Database reachable' : 'Database not verified yet'}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <section className="space-y-4 rounded-[26px] border border-border/70 bg-background/85 p-4">
            {sampleMessages.map((message) => (
              <div
                key={`${message.role}-${message.content.slice(0, 24)}`}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-2xl rounded-[24px] px-4 py-3 shadow-sm ${
                    message.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'border border-border/70 bg-card text-card-foreground'
                  }`}
                >
                  <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.2em] opacity-80">
                    {message.role === 'assistant' ? (
                      <Bot className="size-3.5" />
                    ) : (
                      <UserRound className="size-3.5" />
                    )}
                    <span>{message.role}</span>
                  </div>
                  <p className="text-sm leading-7">{message.content}</p>
                </div>
              </div>
            ))}
          </section>

          <section className="space-y-4">
            <div className="rounded-[26px] border border-border/70 bg-background/85 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                <DatabaseZap className="size-4 text-primary" />
                System status
              </div>
              <dl className="space-y-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-foreground">Service</dt>
                  <dd className="font-medium text-foreground">
                    {health?.service ?? 'attend-backend'}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-foreground">Health</dt>
                  <dd className="font-medium text-foreground">{health?.status ?? 'pending'}</dd>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-foreground">Database</dt>
                  <dd className="font-medium text-foreground">
                    {health?.database.reachable ? 'reachable' : 'checking'}
                  </dd>
                </div>
              </dl>
              {healthError ? (
                <p className="mt-4 rounded-2xl bg-amber-500/10 px-3 py-2 text-sm text-amber-700">
                  {healthError}
                </p>
              ) : null}
            </div>

            <div className="rounded-[26px] border border-dashed border-border bg-background/70 p-4 text-sm leading-6 text-muted-foreground">
              A right-side “active filters” panel will be added in a later phase. The layout is
              already shaped so we can slot it in cleanly.
            </div>
          </section>
        </CardContent>
      </Card>

      <Card className="border-white/70 bg-white/85">
        <CardContent className="p-4">
          <form
            className="flex flex-col gap-3 md:flex-row"
            onSubmit={(event) => event.preventDefault()}
          >
            <Input
              id="message-draft"
              name="message"
              value={draft}
              onChange={(event) => onDraftChange(event.target.value)}
              placeholder="Try: I want sports in Delhi this Sunday around 7 PM"
            />
            <Button className="md:min-w-40" type="submit">
              <SendHorizontal className="size-4" />
              Send
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
