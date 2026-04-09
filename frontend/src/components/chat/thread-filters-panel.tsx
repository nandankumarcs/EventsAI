import { Eye, Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { ThreadDetail } from '@/lib/api'

type ThreadFiltersPanelProps = {
  thread: ThreadDetail | null
}

export function ThreadFiltersPanel({ thread }: ThreadFiltersPanelProps) {
  const filterEntries = buildFilterEntries(thread?.active_filters ?? {})
  const hasFilters = filterEntries.length > 0

  return (
    <aside className="hidden xl:block">
      <div className="sticky top-4 space-y-4">
        <Card className="border-white/80 bg-white/88">
          <CardHeader className="space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.24em] text-primary">
              <Eye className="size-4" />
              Live thread filters
            </div>
            <div className="space-y-2">
              <CardTitle className="text-xl">Realtime state</CardTitle>
              <CardDescription>
                These are the filters currently saved for this thread. They refresh as the
                conversation resolves new preferences.
              </CardDescription>
            </div>
          </CardHeader>

          <CardContent className="space-y-3">
            {thread ? (
              <div className="rounded-[22px] border border-border/70 bg-background/75 p-4">
                <p className="text-sm font-semibold text-foreground">{thread.title}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {thread.status === 'booked'
                    ? 'This thread is locked after booking confirmation.'
                    : 'Watching the active filter state update turn by turn.'}
                </p>
              </div>
            ) : (
              <div className="rounded-[22px] border border-dashed border-border bg-background/60 p-4 text-sm text-muted-foreground">
                Select a thread to inspect the saved filter state in realtime.
              </div>
            )}

            {hasFilters ? (
              <div className="space-y-3">
                {filterEntries.map(({ key, label, values }) => (
                  <div
                    key={key}
                    className="rounded-[22px] border border-border/70 bg-background/70 p-4"
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      {label}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {values.map((item) => (
                        <Badge key={`${key}-${item}`} variant="default">
                          {item}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : thread ? (
              <div className="rounded-[22px] border border-dashed border-border bg-background/60 p-4 text-sm text-muted-foreground">
                No filters have been accumulated in this thread yet.
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="border-white/80 bg-white/82">
          <CardContent className="flex gap-3 p-4 text-sm text-muted-foreground">
            <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
            <p>
              Use this panel during testing to confirm that every follow-up adds, replaces,
              or clears only the intended filters.
            </p>
          </CardContent>
        </Card>
      </div>
    </aside>
  )
}

type FilterEntry = {
  key: string
  label: string
  values: string[]
}

function buildFilterEntries(filters: Record<string, string[] | string>) {
  const entries: FilterEntry[] = []
  const consumedKeys = new Set<string>()

  const eventDates = asArray(filters.event_dates)
  if (eventDates.length > 0) {
    entries.push({
      key: 'event_dates',
      label: 'Event Dates',
      values: eventDates,
    })
    consumedKeys.add('event_dates')
  }

  const dateFrom = asSingle(filters.date_from)
  const dateTo = asSingle(filters.date_to)
  if (dateFrom || dateTo) {
    entries.push({
      key: 'date_range',
      label: 'Date Range',
      values: [formatDateRange(dateFrom, dateTo)],
    })
    consumedKeys.add('date_from')
    consumedKeys.add('date_to')
  }

  const startTimeFrom = asSingle(filters.start_time_from)
  const startTimeTo = asSingle(filters.start_time_to)
  if (startTimeFrom || startTimeTo) {
    entries.push({
      key: 'time_range',
      label: 'Time Range',
      values: [formatTimeRange(startTimeFrom, startTimeTo)],
    })
    consumedKeys.add('start_time_from')
    consumedKeys.add('start_time_to')
  }

  for (const [key, value] of Object.entries(filters)) {
    if (consumedKeys.has(key)) {
      continue
    }

    const values = asArray(value)
    if (values.length === 0) {
      continue
    }

    entries.push({
      key,
      label: formatFilterKey(key),
      values,
    })
  }

  return entries
}

function formatFilterKey(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

function asArray(value: string[] | string | undefined) {
  if (Array.isArray(value)) {
    return value.filter(Boolean)
  }
  return value ? [value] : []
}

function asSingle(value: string[] | string | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? null
  }
  return value ?? null
}

function formatDateRange(dateFrom: string | null, dateTo: string | null) {
  if (dateFrom && dateTo) {
    return `${dateFrom} to ${dateTo}`
  }
  if (dateFrom) {
    return `${dateFrom} onwards`
  }
  if (dateTo) {
    return `Until ${dateTo}`
  }
  return ''
}

function formatTimeRange(start: string | null, end: string | null) {
  if (start && end) {
    return `${formatTime(start)} - ${formatTime(end)}`
  }
  if (start) {
    return `${formatTime(start)} onwards`
  }
  if (end) {
    return `Until ${formatTime(end)}`
  }
  return ''
}

function formatTime(value: string) {
  const [hourText, minuteText] = value.split(':')
  const hour = Number(hourText)
  const minute = Number(minuteText ?? '0')
  const suffix = hour >= 12 ? 'PM' : 'AM'
  const twelveHour = hour % 12 || 12
  return `${twelveHour}:${String(minute).padStart(2, '0')} ${suffix}`
}
