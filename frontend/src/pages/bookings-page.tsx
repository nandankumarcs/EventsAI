import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import type { SortingState } from '@tanstack/react-table'
import { ArrowUpDown, ChevronLeft, ChevronRight, Trash2, ArrowLeft } from 'lucide-react'

import { deleteBooking, listBookings, type BookingSummary } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { AppFooter } from '@/components/layout/app-footer'

export function BookingsPage() {
  const [data, setData] = useState<BookingSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [sorting, setSorting] = useState<SortingState>([])

  useEffect(() => {
    document.title = 'Bookings - Events AI'
    fetchBookings()
  }, [])

  async function fetchBookings() {
    setLoading(true)
    try {
      const resp = await listBookings()
      setData(resp.bookings)
    } catch (err) {
      console.error('Failed to fetch bookings', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm('Are you sure you want to delete this booking?')) return
    try {
      await deleteBooking(id)
      setData((prev) => prev.filter((b) => b.id !== id))
    } catch (err) {
      console.error('Failed to delete booking', err)
      alert('Failed to delete booking.')
    }
  }

  const columns: ColumnDef<BookingSummary>[] = [
    {
      accessorKey: 'event_title',
      header: ({ column }) => {
        return (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="-ml-4 h-8 data-[state=open]:bg-accent"
          >
            Event Name
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        )
      },
    },
    {
      accessorKey: 'event_type',
      header: 'Type',
      cell: ({ row }) => {
        const type = String(row.getValue('event_type') ?? '')
        return (
          <span className="capitalize px-2 py-1 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border">
            {type}
          </span>
        )
      },
    },
    {
      accessorKey: 'customer_name',
      header: 'Customer',
      cell: ({ row }) => {
        const name = String(row.getValue('customer_name') ?? '') || 'N/A'
        const email = row.original.customer_email || 'N/A'
        const contact = row.original.customer_contact_number || 'N/A'
        return (
          <div className="flex flex-col">
            <span className="font-medium">{name}</span>
            <span className="text-xs text-muted-foreground">{email}</span>
            <span className="text-xs text-muted-foreground">{contact}</span>
          </div>
        )
      },
    },
    {
      id: 'actions',
      cell: ({ row }) => {
        return (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => handleDelete(row.original.id)}
            className="text-destructive hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        )
      },
    },
  ]

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    state: {
      sorting,
    },
  })

  return (
    <div className="flex h-screen w-full flex-col bg-background">
      <header className="sticky top-0 z-10 border-b border-border/50 bg-background/95 backdrop-blur px-6 py-4">
        <div className="flex items-center gap-4 max-w-6xl mx-auto w-full">
          <Button variant="outline" size="icon" asChild>
            <Link to="/">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <h1 className="text-xl font-semibold tracking-tight">Bookings Management</h1>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-auto p-6">
        <div className="max-w-6xl mx-auto w-full space-y-4">
          <div className="rounded-md border border-border bg-card">
            <div className="overflow-x-auto relative min-h-[400px]">
              {loading ? (
                <div className="absolute inset-0 flex items-center justify-center bg-background/50 backdrop-blur-sm z-10">
                  <div className="flex items-center space-x-2 text-muted-foreground">
                    <div className="w-2 h-2 bg-primary/40 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                    <div className="w-2 h-2 bg-primary/40 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                    <div className="w-2 h-2 bg-primary/40 rounded-full animate-bounce"></div>
                  </div>
                </div>
              ) : null}
              
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 border-b border-border">
                  {table.getHeaderGroups().map((headerGroup) => (
                    <tr key={headerGroup.id}>
                      {headerGroup.headers.map((header) => (
                        <th key={header.id} className="h-12 px-4 align-middle font-medium text-muted-foreground">
                          {header.isPlaceholder
                            ? null
                            : flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody className="divide-y divide-border">
                  {table.getRowModel().rows?.length ? (
                    table.getRowModel().rows.map((row) => (
                      <tr key={row.id} className="hover:bg-muted/30 transition-colors">
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id} className="p-4 align-middle">
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                        No bookings found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <div className="flex items-center justify-end space-x-2 py-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronLeft className="h-4 w-4 mr-1" /> Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              Next <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </main>

      <AppFooter />
    </div>
  )
}
