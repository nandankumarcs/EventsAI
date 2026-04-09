import { useEffect, useRef } from 'react'

import {
  Bot,
  CalendarDays,
  CircleDashed,
  MapPin,
  Plus,
  SendHorizontal,
  Sparkles,
  TicketCheck,
  UserRound,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import type { HealthResponse, SearchResultItem, ThreadDetail, ThreadMessage } from '@/lib/api'

type ChatWorkspaceProps = {
  thread: ThreadDetail | null
  draft: string
  sending: boolean
  bookingListingCode: string | null
  loadingThread: boolean
  health: HealthResponse | null
  healthError: string | null
  actionError: string | null
  actionRetryLabel: string | null
  isCreatingThread: boolean
  onDraftChange: (value: string) => void
  onSend: () => void
  onBook: (listingCode: string) => void
  onCreateThread: () => void
  onRetryHealth: () => void
  onRetryAction: () => void
}

export function ChatWorkspace({
  thread,
  draft,
  sending,
  bookingListingCode,
  loadingThread,
  health,
  healthError,
  actionError,
  actionRetryLabel,
  isCreatingThread,
  onDraftChange,
  onSend,
  onBook,
  onCreateThread,
  onRetryHealth,
  onRetryAction,
}: ChatWorkspaceProps) {
  const backendOnline = health?.status === 'ok'
  const isBookedThread = thread?.status === 'booked'
  const historyRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const node = historyRef.current
    if (!node) {
      return
    }
    node.scrollTo({
      top: node.scrollHeight,
      behavior: 'smooth',
    })
  }, [thread?.id, thread?.messages.length, loadingThread, sending])

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col gap-4 overflow-hidden">
      <Card className="flex min-h-0 flex-1 flex-col border-white/80 bg-white/88">
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              <Sparkles className="size-4" />
              Event concierge
            </div>
            <CardTitle>{thread?.title ?? 'Start a new conversation'}</CardTitle>
            <CardDescription>Every message updates this thread’s active search.</CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={backendOnline ? 'success' : 'warning'}>
              {backendOnline ? 'Backend connected' : 'Backend offline'}
            </Badge>
            <Badge variant={health?.database.reachable ? 'success' : 'warning'}>
              {health?.database.reachable ? 'Database ready' : 'Database pending'}
            </Badge>
            {thread?.status === 'booked' ? <Badge variant="success">Booking saved</Badge> : null}
          </div>
        </CardHeader>

        <CardContent className="flex min-h-0 flex-1 flex-col space-y-4">
          {isBookedThread ? (
            <div className="flex flex-col gap-3 rounded-[22px] border border-emerald-500/20 bg-emerald-500/8 px-4 py-4 text-sm text-emerald-900 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <p className="font-semibold">This booking journey is complete.</p>
                <p className="text-emerald-800/80">
                  Start a fresh thread when you want to plan another movie or match.
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                disabled={isCreatingThread}
                onClick={onCreateThread}
              >
                <Plus className="size-4" />
                {isCreatingThread ? 'Opening...' : 'New thread'}
              </Button>
            </div>
          ) : null}

          <section className="flex min-h-0 flex-1 flex-col rounded-[28px] border border-border/70 bg-background/82 p-4">
            {loadingThread ? (
              <div className="flex min-h-0 flex-1 items-center justify-center text-sm text-muted-foreground">
                Loading conversation...
              </div>
            ) : null}

            {!loadingThread && !thread ? (
              <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4 text-center">
                <div className="rounded-full bg-primary/10 p-4 text-primary">
                  <CircleDashed className="size-6" />
                </div>
                <div className="space-y-2">
                  <h2 className="font-display text-2xl text-foreground">
                    Tell EventsAI what you are in the mood for
                  </h2>
                  <p className="max-w-lg text-sm leading-7 text-muted-foreground">
                    Try something like “I want to watch a cricket match this Sunday in
                    Mumbai around 7pm” and keep refining the same thread.
                  </p>
                </div>
              </div>
            ) : null}

            {!loadingThread && thread ? (
              <div ref={historyRef} className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pr-1">
                {thread.messages.map((message) => (
                  <MessageBlock
                    key={message.id}
                    message={message}
                    threadStatus={thread.status}
                    bookingListingCode={bookingListingCode}
                    onBook={onBook}
                  />
                ))}
              </div>
            ) : null}
          </section>

          {healthError ? (
            <div className="flex flex-col gap-3 rounded-[22px] border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 sm:flex-row sm:items-center sm:justify-between">
              <span>{healthError}</span>
              <Button type="button" variant="outline" size="sm" onClick={onRetryHealth}>
                Retry connection
              </Button>
            </div>
          ) : null}

          {actionError ? (
            <div className="flex flex-col gap-3 rounded-[22px] border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 sm:flex-row sm:items-center sm:justify-between">
              <span>{actionError}</span>
              {actionRetryLabel ? (
                <Button type="button" variant="outline" size="sm" onClick={onRetryAction}>
                  {actionRetryLabel}
                </Button>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="border-white/80 bg-white/88">
        <CardContent className="p-4">
          {isBookedThread ? (
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">This thread is read-only now.</p>
                <p className="text-sm text-muted-foreground">
                  Use a new thread to search with a fresh set of filters.
                </p>
              </div>
              <Button
                type="button"
                className="md:min-w-40"
                disabled={isCreatingThread}
                onClick={onCreateThread}
              >
                <Plus className="size-4" />
                {isCreatingThread ? 'Opening...' : 'Start new thread'}
              </Button>
            </div>
          ) : (
            <form
              className="flex flex-col gap-3 md:flex-row"
              onSubmit={(event) => {
                event.preventDefault()
                onSend()
              }}
            >
              <Input
                id="message-draft"
                name="message"
                value={draft}
                onChange={(event) => onDraftChange(event.target.value)}
                placeholder="Try: I want sports in Mumbai this Sunday around 7 PM"
                disabled={sending}
              />
              <Button className="md:min-w-40" type="submit" disabled={sending || !draft.trim()}>
                <SendHorizontal className="size-4" />
                {sending ? 'Sending...' : 'Send'}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  )
}

type MessageBlockProps = {
  message: ThreadMessage
  threadStatus: ThreadDetail['status']
  bookingListingCode: string | null
  onBook: (listingCode: string) => void
}

function MessageBlock({
  message,
  threadStatus,
  bookingListingCode,
  onBook,
}: MessageBlockProps) {
  const isAssistant = message.role === 'assistant'
  const resultsByDomain = message.metadata.results_by_domain ?? {}
  const allResults = Object.values(resultsByDomain).flatMap((domain) => domain.results)

  return (
    <div className={`flex ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      <div className="max-w-full space-y-3 sm:max-w-3xl">
        <div
          className={`rounded-[24px] px-4 py-3 shadow-sm ${
            isAssistant
              ? 'border border-border/70 bg-card text-card-foreground'
              : 'bg-primary text-primary-foreground'
          }`}
        >
          <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.2em] opacity-80">
            {isAssistant ? <Bot className="size-3.5" /> : <UserRound className="size-3.5" />}
            <span>{message.role}</span>
          </div>
          <p className="text-sm leading-6">{message.content}</p>

          {message.metadata.booking_reference ? (
            <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-emerald-500/12 px-3 py-1.5 text-xs font-semibold text-emerald-700">
              <TicketCheck className="size-3.5" />
              Ref {message.metadata.booking_reference}
            </div>
          ) : null}
        </div>

        {isAssistant && allResults.length > 0 ? (
          <div className="result-lane-mask max-w-full overflow-hidden">
            <div className="scrollbar-none flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-2">
              {allResults.map((result) => (
                <ResultCard
                  key={result.listing_code}
                  result={result}
                  disabled={threadStatus === 'booked'}
                  isBooking={bookingListingCode === result.listing_code}
                  onBook={onBook}
                />
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

type ResultCardProps = {
  result: SearchResultItem
  disabled: boolean
  isBooking: boolean
  onBook: (listingCode: string) => void
}

function ResultCard({ result, disabled, isBooking, onBook }: ResultCardProps) {
  const eventTypeLabel = result.sport_type ?? result.genres?.slice(0, 2).join(', ') ?? 'Event'

  return (
    <div className="snap-start w-[272px] min-w-[272px] rounded-[24px] border border-border/70 bg-white/86 p-3.5 shadow-sm sm:w-[286px] sm:min-w-[286px]">
      <div className="space-y-2.5">
        <div className="space-y-1">
          <div>
            <h3 className="text-[1.05rem] font-semibold leading-8 text-foreground">{result.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{eventTypeLabel}</p>
          </div>
        </div>

        <div className="grid gap-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <MapPin className="size-4 text-primary" />
            <span>
              {result.venue_name}, {result.city}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <CalendarDays className="size-4 text-primary" />
            <span>{formatEventDateTime(result.event_date, result.start_at)}</span>
          </div>
        </div>

        {(result.min_price ?? result.max_price) ? (
          <p className="text-sm font-medium text-foreground">
            Rs. {result.min_price ?? 0}
            {result.max_price ? ` - ${result.max_price}` : ''}
          </p>
        ) : null}

        <Button
          type="button"
          className="w-full"
          disabled={disabled || isBooking}
          onClick={() => onBook(result.listing_code)}
        >
          <TicketCheck className="size-4" />
          {disabled ? 'Booking saved' : isBooking ? 'Confirming...' : 'Confirm booking'}
        </Button>
      </div>
    </div>
  )
}

function formatEventDateTime(eventDate: string, startAt: string) {
  const startDate = new Date(startAt)
  const fallbackDate = new Date(eventDate)
  const date = Number.isNaN(startDate.getTime()) ? fallbackDate : startDate

  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}
