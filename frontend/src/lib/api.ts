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

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ??
  'http://127.0.0.1:8000'

export async function fetchHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health/`)

  if (!response.ok) {
    throw new Error(`Health request failed with status ${response.status}`)
  }

  return (await response.json()) as HealthResponse
}

