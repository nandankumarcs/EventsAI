export type HealthResponse = {
  status: 'ok' | 'degraded'
  service: string
  timestamp: string
  database: {
    configured: boolean
    engine: string
    reachable: boolean
    detail?: string
  }
}

export type ActiveFilters = Record<string, string[] | string>

export type SearchResultItem = {
  id: string
  listing_code: string
  title: string
  city: string
  venue_name: string
  event_date: string
  start_at: string
  min_price?: number
  max_price?: number
  languages?: string[]
  genres?: string[]
  sport_type?: string
  tournament_name?: string
  home_team?: string
  away_team?: string
}

export type ResultContextItem = {
  position: number
  domain: 'movies' | 'sports' | string
  listing_code: string
  title: string
  city: string
  venue_name: string
  event_date: string
  start_at: string
  min_price?: number | null
  max_price?: number | null
  sport_type?: string | null
  genres?: string[]
}

export type PendingBooking = {
  status: string
  listing_code: string
  selected_at?: string
  awaiting_field?: string | null
  customer_info?: {
    name?: string
    email?: string
    contact_number?: string
  }
  event_snapshot?: Partial<ResultContextItem>
}

export type SearchDomainResult = {
  count: number
  limit: number
  offset: number
  filters: ActiveFilters
  results: SearchResultItem[]
}

export type SearchResultsByDomain = Partial<
  Record<'movies' | 'sports', SearchDomainResult>
>

export type ThreadMessage = {
  id: string
  position: number
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  tool_name: string
  metadata: {
    booking_id?: string
    booking_reference?: string
    listing_code?: string
    search_domains?: string[]
    needs_clarification?: boolean
    clarification_question?: string | null
    result_listing_codes?: string[]
    results_by_domain?: SearchResultsByDomain
    active_filters?: ActiveFilters
    pending_booking?: PendingBooking
    booking_action?: string
    requested_field?: string
    selected_event?: Partial<ResultContextItem>
    booking?: BookingSummary
  }
  created_at: string
}

export type ThreadSummary = {
  id: string
  title: string
  status: 'active' | 'booked' | 'archived'
  summary: string
  last_message_preview: string
  last_activity_at: string
  message_count: number
  active_filters: ActiveFilters
  latest_result_context: {
    thread_id?: string
    captured_at?: string
    search_domains?: string[]
    results?: ResultContextItem[]
  }
  pending_booking: PendingBooking | Record<string, never>
}

export type ThreadDetail = ThreadSummary & {
  created_at: string
  updated_at: string
  messages: ThreadMessage[]
}

export type ThreadListResponse = {
  count: number
  has_more: boolean
  threads: ThreadSummary[]
}

export type ThreadDetailResponse = {
  thread: ThreadDetail
}

export type ChatTurnResponse = {
  thread: Pick<
    ThreadSummary,
    'id' | 'title' | 'status' | 'last_message_preview' | 'last_activity_at'
  >
  assistant_message: {
    id: string
    thread_id: string
    position: number
    role: string
    content: string
    metadata: ThreadMessage['metadata']
    created_at: string
  }
  active_filters: ActiveFilters
  search_domains: string[]
  results_by_domain: SearchResultsByDomain
  latest_result_context: ThreadSummary['latest_result_context']
  pending_booking: ThreadSummary['pending_booking']
  needs_clarification: boolean
  clarification_question: string | null
}

export type BookingSummary = {
  id: string
  thread_id: string | null
  booking_reference: string
  event_type: string
  status: string
  event_title: string
  customer_name: string
  customer_email: string
  customer_contact_number: string
  city: string
  venue_name: string
  starts_at: string
  confirmed_at: string
  filter_snapshot: ActiveFilters
  event_snapshot: Record<string, unknown>
}

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`

    try {
      const payload = (await response.json()) as { error?: string }
      if (payload.error) {
        detail = payload.error
      }
    } catch {
      // Keep the default error detail.
    }

    throw new Error(detail)
  }

  return (await response.json()) as T
}

export async function fetchHealth() {
  return request<HealthResponse>('/api/health/')
}

export async function listThreads(limit = 20, offset = 0) {
  const query = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  })
  return request<ThreadListResponse>(`/api/chats/threads/?${query}`)
}

export async function createThread(title?: string) {
  return request<ThreadDetailResponse>('/api/chats/threads/', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function fetchThread(threadId: string) {
  return request<ThreadDetailResponse>(`/api/chats/threads/${threadId}/`)
}

export async function sendChatMessage(message: string, threadId?: string) {
  return request<ChatTurnResponse>('/api/agents/chat/', {
    method: 'POST',
    body: JSON.stringify({
      message,
      thread_id: threadId,
    }),
  })
}

export async function confirmBooking(threadId: string, listingCode: string) {
  return request<{ booking: BookingSummary; already_confirmed?: boolean }>(
    '/api/bookings/confirm/',
    {
      method: 'POST',
      body: JSON.stringify({
        thread_id: threadId,
        listing_code: listingCode,
      }),
    },
  )
}
