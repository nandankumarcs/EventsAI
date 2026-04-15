import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AppFooter } from '@/components/layout/app-footer'
import { login } from '@/lib/api'

export function LoginPage() {
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const navigate = useNavigate()
  const location = useLocation()

  const next = new URLSearchParams(location.search).get('next') || '/'

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      await login(password)
      navigate(next, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#f3f4f6]">
      {/* Main Content Area */}
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-[440px] rounded-xl bg-white p-12 shadow-[0_4px_20px_-4px_rgba(0,0,0,0.1)]">
          <h1 className="mb-8 text-center text-3xl font-bold text-[#4f46e5]">Login</h1>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700" htmlFor="password">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                autoComplete="current-password"
                onChange={(e) => setPassword(e.target.value)}
                placeholder=""
                disabled={submitting}
                className="h-11 rounded-sm border-gray-200 bg-white px-3 focus-visible:ring-[#4f46e5]/20"
                autoFocus
              />
            </div>

            {error ? (
              <div className="rounded-md border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600">
                {error}
              </div>
            ) : null}

            <Button
              type="submit"
              className="h-11 w-full rounded-md bg-[#4f46e5] text-base font-semibold text-white shadow-none hover:bg-[#4338ca]"
              disabled={submitting || !password.trim()}
            >
              {submitting ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
        </div>
      </div>

      <AppFooter />
    </div>
  )
}

