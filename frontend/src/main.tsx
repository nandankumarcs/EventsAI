import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { BookingsPage } from './pages/bookings-page.tsx'
import { LoginPage } from './pages/login-page.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename="/ai-agents/ticket-booking-agent">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/t/:threadId" element={<App />} />
        <Route path="/bookings" element={<BookingsPage />} />
        <Route path="/" element={<App />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
