import { Eye } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import type { ThreadDetail } from '@/lib/api'

type ThreadFiltersPanelProps = {
  thread: ThreadDetail | null
}

export function ThreadFiltersPanel({ thread }: ThreadFiltersPanelProps) {
  const filterEntries = buildFilterEntries(thread?.active_filters ?? {})
  const hasFilters = filterEntries.length > 0

  return (
    <aside className="hidden h-full min-h-0 w-80 shrink-0 border-l border-border/70 bg-background/50 xl:block">
      <div className="flex h-full flex-col">
        <div className="sticky top-0 z-10 border-b border-border/70 bg-background/95 p-6 pr-8 backdrop-blur">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            <Eye className="size-4" />
            Live filters
          </div>
          <div>
            <h2 className="text-lg font-semibold">Realtime state</h2>
            <p className="text-sm text-muted-foreground">Saved filters for the active thread.</p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 pr-8 space-y-4">
          {thread ? (
            <div className="rounded-[16px] border border-border/70 bg-background p-4">
              <p className="text-sm font-semibold text-foreground">{thread.title}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {thread.status === 'booked' ? 'Booking saved' : 'Active search state'}
              </p>
            </div>
          ) : (
            <div className="rounded-[16px] border border-dashed border-border p-4 text-sm text-muted-foreground">
              Select a thread to inspect the saved filter state in realtime.
            </div>
          )}

          {thread?.customer_info && Object.values(thread.customer_info).some(Boolean) ? (
            <div className="rounded-[16px] border border-border/70 bg-background p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-2.5">
                User Details
              </p>
              <div className="space-y-1.5 text-sm">
                {thread.customer_info.name && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-12">Name:</span>
                    <span className="font-medium truncate">{thread.customer_info.name}</span>
                  </div>
                )}
                {thread.customer_info.email && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-12">Email:</span>
                    <span className="font-medium truncate">{thread.customer_info.email}</span>
                  </div>
                )}
                {thread.customer_info.contact_number && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-12">Phone:</span>
                    <span className="font-medium truncate">{thread.customer_info.contact_number}</span>
                  </div>
                )}
              </div>
            </div>
          ) : null}

          {hasFilters ? (
            <div className="space-y-2">
              {filterEntries.map(({ key, label, values }) => (
                <div
                  key={key}
                  className="rounded-[16px] border border-border/70 bg-background p-3.5"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    {label}
                  </p>
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    {values.map((item) => (
                      <Badge key={`${key}-${item}`} variant="default" className="font-medium bg-muted/60 text-foreground">
                        {item}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : thread ? (
            <div className="rounded-[16px] border border-dashed border-border p-4 text-sm text-muted-foreground">
              No filters have been accumulated in this thread yet.
            </div>
          ) : null}
        </div>
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
