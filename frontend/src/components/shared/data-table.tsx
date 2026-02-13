import { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export interface DataColumn<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  className?: string
}

interface DataTableProps<T> {
  columns: DataColumn<T>[]
  data?: T[]
  loading?: boolean
  emptyState?: ReactNode
  onRowClick?: (row: T) => void
  pagination?: {
    page: number
    pageSize: number
    total?: number
    onPageChange: (page: number) => void
  }
}

export function DataTable<T>({
  columns,
  data = [],
  loading,
  emptyState,
  onRowClick,
  pagination,
}: DataTableProps<T>) {
  const totalPages = pagination?.total
    ? Math.ceil(pagination.total / pagination.pageSize)
    : undefined

  return (
    <div className="rounded-2xl border border-border/70 bg-card/95 shadow-soft overflow-hidden">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="bg-gradient-to-r from-muted/60 to-muted/30">
              {columns.map((column) => (
                <TableHead key={column.key} className={cn('text-xs font-semibold uppercase tracking-wide', column.className)}>
                  {column.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              [...Array(5)].map((_, index) => (
                <TableRow key={`skeleton-${index}`}>
                  {columns.map((column) => (
                    <TableCell key={`${column.key}-${index}`}>
                      <Skeleton className="h-4 w-full skeleton-shimmer" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
            {!loading && data.length === 0 && (
              <TableRow>
                <TableCell colSpan={columns.length} className="py-10">
                  {emptyState}
                </TableCell>
              </TableRow>
            )}
            {!loading && data.map((row, index) => (
              <TableRow
                key={index}
                className={cn(
                  'row-hover transition-colors duration-200',
                  onRowClick ? 'cursor-pointer' : undefined
                )}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((column) => (
                  <TableCell key={column.key} className={column.className}>
                    {column.render(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {pagination && totalPages !== undefined && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/70 px-4 py-3 text-sm bg-muted/20">
          <span className="text-muted-foreground">
            Sayfa {pagination.page} / {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
            >
              Önceki
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page >= totalPages}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
            >
              Sonraki
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
