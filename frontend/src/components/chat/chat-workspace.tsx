import { useEffect, useMemo, useRef, useState } from 'react'

import {
  ArrowDown,
  Bot,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  MapPin,
  Plus,
  SendHorizontal,
  Sparkles,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type {
  PendingBooking,
  SearchResultItem,
  ThreadDetail,
  ThreadMessage,
} from '@/lib/api'
import { getRandomPrompts } from '@/lib/prompts'
import { Skeleton } from '@/components/ui/skeleton'

type ChatWorkspaceProps = {
  thread: ThreadDetail | null
  draft: string
  sending: boolean
  loadingThread: boolean
  healthError: string | null
  actionError: string | null
  actionRetryLabel: string | null
  isCreatingThread: boolean
  onDraftChange: (value: string) => void
  onSend: (message?: string) => void
  onCreateThread: () => void
  onRetryHealth: () => void
  onRetryAction: () => void
}

export function ChatWorkspace({
  thread,
  draft,
  sending,
  loadingThread,
  healthError,
  actionError,
  actionRetryLabel,
  isCreatingThread,
  onDraftChange,
  onSend,
  onCreateThread,
  onRetryHealth,
  onRetryAction,
}: ChatWorkspaceProps) {
  const isBookedThread = thread?.status === 'booked'
  const pendingBooking = isPendingBooking(thread?.pending_booking) ? thread.pending_booking : null
  const awaitingFieldLabel = formatAwaitingFieldLabel(pendingBooking?.awaiting_field)
  const historyRef = useRef<HTMLDivElement | null>(null)
  const [isAtBottom, setIsAtBottom] = useState(true)

  // Randomly fetch 4 prompts on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const suggestedPrompts = useMemo(() => getRandomPrompts(4), [thread?.id])

  // Track whether the user has scrolled away from the bottom
  function handleScroll() {
    const node = historyRef.current
    if (!node) return
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight
    setIsAtBottom(distanceFromBottom < 80)
  }

  function scrollToBottom(behavior: ScrollBehavior = 'smooth') {
    const node = historyRef.current
    if (!node) return
    node.scrollTo({ top: node.scrollHeight, behavior })
    setIsAtBottom(true)
  }

  // Auto-scroll when new messages arrive — only if user is already at the bottom
  useEffect(() => {
    if (isAtBottom) {
      scrollToBottom('smooth')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread?.messages.length, sending])

  // Always scroll to bottom when switching threads
  useEffect(() => {
    scrollToBottom('instant')
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread?.id, loadingThread])

  return (
    <main className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-background">
      {/* Top Navigation */}
      <header className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 border-b border-border/70 bg-background/95 backdrop-blur">
        <div className="flex items-center gap-2 font-semibold">
          <Sparkles className="size-4 text-primary" />
          <span>{thread?.title ?? 'New conversation'}</span>
        </div>
        <div className="flex items-center gap-2">
          {thread?.status === 'booked' ? <Badge variant="success">Booking saved</Badge> : null}
        </div>
      </header>

      {/* Main scrolling area — wrapper is relative so the FAB can be absolutely positioned */}
      <div className="relative flex min-h-0 flex-1 flex-col">
        <div
          className="flex min-h-0 flex-1 flex-col overflow-y-auto"
          ref={historyRef}
          onScroll={handleScroll}
        >
        <div className="mx-auto w-full max-w-4xl px-4 py-6 md:py-10 space-y-6">
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

          {!isBookedThread && pendingBooking?.event_snapshot ? (
            <div className="space-y-3 rounded-[22px] border border-amber-500/25 bg-amber-500/8 px-4 py-4">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-foreground">Pending booking confirmation</p>
                <p className="text-sm text-muted-foreground">
                  {awaitingFieldLabel
                    ? `Reply with your ${awaitingFieldLabel} to continue this booking.`
                    : 'Reply with `yes` to confirm this event or `no` to clear it.'}
                </p>
              </div>
              <div className="max-w-[286px]">
                <ResultCard result={normalizePendingBookingResult(pendingBooking)} />
              </div>
            </div>
          ) : null}

          {loadingThread ? (
            <div className="flex flex-col gap-8 pb-4">
              {/* AI message skeleton */}
              <div className="flex w-full justify-start">
                <div className="w-full max-w-full space-y-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Skeleton className="size-4 rounded-full" />
                    <Skeleton className="h-3 w-20 rounded-full" />
                  </div>
                  <Skeleton className="h-4 w-[90%] rounded-full" />
                  <Skeleton className="h-4 w-[75%] rounded-full" />
                  <Skeleton className="h-4 w-[55%] rounded-full" />
                </div>
              </div>

              {/* User message skeleton */}
              <div className="flex w-full justify-end">
                <div className="max-w-sm space-y-2">
                  <Skeleton className="h-10 w-52 rounded-3xl" />
                </div>
              </div>

              {/* AI message skeleton */}
              <div className="flex w-full justify-start">
                <div className="w-full max-w-full space-y-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Skeleton className="size-4 rounded-full" />
                    <Skeleton className="h-3 w-20 rounded-full" />
                  </div>
                  <Skeleton className="h-4 w-[85%] rounded-full" />
                  <Skeleton className="h-4 w-[65%] rounded-full" />
                  <Skeleton className="h-4 w-[45%] rounded-full" />
                  <Skeleton className="h-4 w-[70%] rounded-full" />
                </div>
              </div>

              {/* User message skeleton */}
              <div className="flex w-full justify-end">
                <div className="max-w-sm space-y-2">
                  <Skeleton className="h-10 w-72 rounded-3xl" />
                </div>
              </div>
            </div>
          ) : null}

          {!loadingThread && (!thread || thread.messages.length === 0) && !sending ? (
            <div className="flex flex-col items-center justify-center gap-8 pt-16 pb-8 min-h-[50vh] text-center max-w-2xl mx-auto w-full">
              <div className="space-y-2">
                <h1 className="text-[28px] font-medium tracking-tight text-foreground/80">
                  {getGreeting()}
                </h1>
                <p className="text-xl text-muted-foreground/80">
                  What event are we planning today?
                </p>
              </div>

              <div className="grid w-full grid-cols-1 sm:grid-cols-2 gap-3 text-left">
                {suggestedPrompts.map((prompt: { icon: any; text: string }, idx: number) => {
                  const Icon = prompt.icon
                  return (
                    <button
                      key={idx}
                      type="button"
                      className="group flex flex-col justify-between gap-3 rounded-2xl border border-border/60 bg-muted/40 p-4 transition-all hover:border-primary/30 hover:bg-muted hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 active:scale-[0.98]"
                      onClick={() => onSend(prompt.text)}
                    >
                      <Icon className="size-5 text-muted-foreground group-hover:text-primary transition-colors" />
                      <span className="text-[14px] text-foreground/90 font-medium">
                        {prompt.text}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : null}

          {!loadingThread && thread ? (
            <div className="flex flex-col gap-8 pb-4">
              {thread.messages.map((message) => (
                <MessageBlock
                  key={message.id}
                  message={message}
                  threadStatus={thread.status}
                />
              ))}
            </div>
          ) : null}

          {!loadingThread && sending ? (
            <div className="flex flex-col gap-8 pb-4 mt-8">
              <div className="flex w-full justify-start">
                <div className="max-w-full space-y-3 w-full">
                  <div className="bg-transparent text-foreground">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      <Bot className="size-4" />
                      <span>Events AI</span>
                    </div>
                    <div className="flex space-x-1.5 mt-2 h-6 items-center">
                      <div className="w-2 h-2 bg-primary/40 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                      <div className="w-2 h-2 bg-primary/40 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                      <div className="w-2 h-2 bg-primary/40 rounded-full animate-bounce"></div>
                    </div>
                  </div>
                  {/* Skeleton cards while waiting for results */}
                  <div className="flex gap-3 overflow-hidden px-1 pb-2 pt-1">
                    <ResultCardSkeleton />
                    <ResultCardSkeleton />
                    <ResultCardSkeleton />
                  </div>
                </div>
              </div>
            </div>
          ) : null}

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
        </div>
      </div>

        {/* Scroll-to-bottom floating button — sits above the input bar */}
        {!isAtBottom && (
          <button
            type="button"
            onClick={() => scrollToBottom('smooth')}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1.5 rounded-full border border-border/60 bg-background/90 px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-md backdrop-blur transition-all hover:bg-accent hover:text-foreground z-10"
          >
            <ArrowDown className="size-3.5" />
            Scroll to bottom
          </button>
        )}
      </div>

      {/* Input area */}
      <div className="mt-auto bg-background px-4 pb-6 pt-2">
        <div className="mx-auto w-full max-w-4xl">
          {isBookedThread ? (
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between px-2">
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
              className="relative flex items-center w-full rounded-[32px] border border-border/50 bg-muted/30 px-3 py-2 shadow-sm focus-within:ring-1 focus-within:border-border hover:border-border transition-all duration-300"
              onSubmit={(event) => {
                event.preventDefault()
                if (draft.trim() && !sending) onSend()
              }}
            >
              <Input
                id="message-draft"
                name="message"
                value={draft}
                onChange={(event) => onDraftChange(event.target.value)}
                placeholder="Message EventsAI..."
                disabled={sending}
                className="flex-1 border-0 bg-transparent px-3 py-2 text-[15px] shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/70"
              />
              <Button 
                className="shrink-0 rounded-full h-9 w-9 p-0 ml-2 transition-transform duration-300 hover:scale-105 active:scale-95" 
                type="submit" 
                size="icon"
                disabled={sending || !draft.trim()}
              >
                <SendHorizontal className="size-[18px]" />
                <span className="sr-only">Send</span>
              </Button>
            </form>
          )}
        </div>
      </div>
    </main>
  )
}

type MessageBlockProps = {
  message: ThreadMessage
  threadStatus: ThreadDetail['status']
}

function MessageBlock({ message, threadStatus }: MessageBlockProps) {
  const isAssistant = message.role === 'assistant'
  const resultsByDomain = message.metadata.results_by_domain ?? {}
  const allResults = Object.values(resultsByDomain).flatMap((domain) => domain.results)
  const selectedBookingResult = getSelectedBookingResult(message)
  const formattedTime = message.created_at
    ? new Date(message.created_at).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null

  return (
    <div className={`group flex w-full ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-full space-y-3 ${isAssistant ? 'w-full' : 'sm:max-w-3xl'}`}>
        <div
          className={`${
            isAssistant
              ? 'bg-transparent text-foreground'
              : 'rounded-3xl bg-muted/60 px-5 py-3.5 text-foreground shadow-none'
          }`}
        >
          <div className={`mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground ${isAssistant ? '' : 'hidden'}`}>
            <Bot className="size-4" />
            <span>Events AI</span>
          </div>
          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{message.content}</p>

          {message.metadata.booking_reference ? (
            <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-800">
              <span>✓</span>
              Ref {message.metadata.booking_reference}
            </div>
          ) : null}
        </div>

        {/* Timestamp — visible on hover */}
        {formattedTime && (
          <div className={`text-[11px] text-muted-foreground/60 opacity-0 transition-opacity duration-150 group-hover:opacity-100 px-1 ${isAssistant ? 'text-left' : 'text-right'}`}>
            {formattedTime}
          </div>
        )}

        {isAssistant && allResults.length > 0 ? (
          <ResultCarousel results={allResults} threadStatus={threadStatus} />
        ) : null}

        {isAssistant && selectedBookingResult ? (
          <div className="max-w-[286px]">
            <ResultCard result={selectedBookingResult} />
          </div>
        ) : null}
      </div>
    </div>
  )
}

function ResultCarousel({
  results,
  threadStatus,
}: {
  results: SearchResultItem[]
  threadStatus?: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)

  const checkScroll = () => {
    if (containerRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = containerRef.current
      setCanScrollLeft(scrollLeft > 5)
      setCanScrollRight(Math.ceil(scrollLeft + clientWidth + 5) < scrollWidth)
    }
  }

  useEffect(() => {
    checkScroll()
    window.addEventListener('resize', checkScroll)
    return () => window.removeEventListener('resize', checkScroll)
  }, [results])

  const scrollLeft = () => {
    containerRef.current?.scrollBy({ left: -320, behavior: 'smooth' })
  }

  const scrollRight = () => {
    containerRef.current?.scrollBy({ left: 320, behavior: 'smooth' })
  }

  return (
    <div className="group relative max-w-full">
      {canScrollLeft && (
        <button
          onClick={scrollLeft}
          className="absolute -left-3 top-1/2 z-10 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-border/80 bg-background text-foreground shadow-md transition-all hover:scale-110 hover:shadow-lg active:scale-95 focus:outline-none"
        >
          <ChevronLeft className="h-[18px] w-[18px]" />
        </button>
      )}

      <div
        ref={containerRef}
        onScroll={checkScroll}
        className="scrollbar-none flex snap-x snap-mandatory gap-3 overflow-x-auto px-1 pb-2"
      >
        {results.map((result) => (
          <ResultCard
            key={result.listing_code}
            result={result}
            booked={threadStatus === 'booked'}
          />
        ))}
      </div>

      {canScrollRight && (
        <button
          onClick={scrollRight}
          className="absolute -right-3 top-1/2 z-10 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-border/80 bg-background text-foreground shadow-md transition-all hover:scale-110 hover:shadow-lg active:scale-95 focus:outline-none"
        >
          <ChevronRight className="h-[18px] w-[18px]" />
        </button>
      )}
    </div>
  )
}


type ResultCardProps = {
  result: SearchResultItem
  booked?: boolean
}

function ResultCard({ result, booked }: ResultCardProps) {
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

        {booked ? (
          <p className="text-xs font-medium text-emerald-700">✓ Booking saved</p>
        ) : null}
      </div>
    </div>
  )
}

function ResultCardSkeleton() {
  return (
    <div className="snap-start w-[272px] min-w-[272px] rounded-[24px] border border-border/70 bg-white/86 p-3.5 shadow-sm sm:w-[286px] sm:min-w-[286px]">
      <div className="space-y-2.5">
        {/* Title block */}
        <div className="space-y-1.5">
          <Skeleton className="h-5 w-[90%] rounded-full" />
          <Skeleton className="h-5 w-[65%] rounded-full" />
          <Skeleton className="h-3.5 w-[40%] rounded-full mt-1 opacity-60" />
        </div>
        {/* Location + date rows */}
        <div className="grid gap-2">
          <div className="flex items-center gap-2">
            <Skeleton className="size-4 rounded-full shrink-0" />
            <Skeleton className="h-3 w-[70%] rounded-full" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="size-4 rounded-full shrink-0" />
            <Skeleton className="h-3 w-[50%] rounded-full" />
          </div>
        </div>
        {/* Price */}
        <Skeleton className="h-3.5 w-[35%] rounded-full" />
      </div>
    </div>
  )
}

function isPendingBooking(value: ThreadDetail['pending_booking'] | null | undefined): value is PendingBooking {
  return Boolean(value && typeof value === 'object' && 'listing_code' in value && value.listing_code)
}

function normalizePendingBookingResult(pendingBooking: PendingBooking): SearchResultItem {
  const snapshot = pendingBooking.event_snapshot ?? {}
  return {
    id: pendingBooking.listing_code,
    listing_code: pendingBooking.listing_code,
    title: snapshot.title ?? 'Selected event',
    city: snapshot.city ?? '',
    venue_name: snapshot.venue_name ?? '',
    event_date: snapshot.event_date ?? '',
    start_at: snapshot.start_at ?? snapshot.event_date ?? '',
    min_price: snapshot.min_price ?? undefined,
    max_price: snapshot.max_price ?? undefined,
    genres: snapshot.genres,
    sport_type: snapshot.sport_type ?? undefined,
  }
}

function getSelectedBookingResult(message: ThreadMessage): SearchResultItem | null {
  if (!['selection_pending', 'awaiting_user_info'].includes(message.metadata.booking_action ?? '')) {
    return null
  }

  const snapshot =
    message.metadata.selected_event ??
    message.metadata.pending_booking?.event_snapshot ??
    null

  if (!snapshot?.listing_code) {
    return null
  }

  return {
    id: snapshot.listing_code,
    listing_code: snapshot.listing_code,
    title: snapshot.title ?? 'Selected event',
    city: snapshot.city ?? '',
    venue_name: snapshot.venue_name ?? '',
    event_date: snapshot.event_date ?? '',
    start_at: snapshot.start_at ?? snapshot.event_date ?? '',
    min_price: snapshot.min_price ?? undefined,
    max_price: snapshot.max_price ?? undefined,
    genres: snapshot.genres,
    sport_type: snapshot.sport_type ?? undefined,
  }
}

function formatAwaitingFieldLabel(fieldName: string | null | undefined) {
  if (!fieldName) {
    return null
  }
  if (fieldName === 'contact_number') {
    return 'contact number'
  }
  return fieldName
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

function getGreeting() {
  const currentHour = new Date().getHours()
  if (currentHour < 12) return 'Good morning'
  if (currentHour < 18) return 'Good afternoon'
  return 'Good evening'
}
