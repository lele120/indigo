import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/api/client'
import DocumentCard from '@/components/DocumentCard'

export default function DocumentsPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [tagFilter, setTagFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const pageSize = 12

  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', page, statusFilter, tagFilter, searchQuery],
    queryFn: () =>
      apiClient.listDocuments({
        page,
        page_size: pageSize,
        ...(statusFilter && { status: statusFilter }),
        ...(tagFilter && { tags: tagFilter }),
        ...(searchQuery && { search: searchQuery }),
      }),
  })

  const { data: tags } = useQuery({
    queryKey: ['tags'],
    queryFn: () => apiClient.getAllTags(),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteDocument(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this document?')) {
      deleteMutation.mutate(id)
    }
  }

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Documents</h1>
        <p className="mt-2 text-gray-600">Manage and browse your uploaded documents</p>
      </div>

      {/* Filters */}
      <div className="card mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                setPage(1)
              }}
              placeholder="Search documents..."
              className="input w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
              className="input w-full"
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tag
            </label>
            <select
              value={tagFilter}
              onChange={(e) => {
                setTagFilter(e.target.value)
                setPage(1)
              }}
              className="input w-full"
            >
              <option value="">All tags</option>
              {tags?.map((tag) => (
                <option key={tag.id} value={tag.name}>
                  {tag.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {(statusFilter || tagFilter || searchQuery) && (
          <div className="mt-4 flex items-center justify-between">
            <span className="text-sm text-gray-600">
              {data?.total || 0} documents found
            </span>
            <button
              onClick={() => {
                setStatusFilter('')
                setTagFilter('')
                setSearchQuery('')
                setPage(1)
              }}
              className="text-sm text-primary-600 hover:text-primary-800 font-medium"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>

      {/* Documents Grid */}
      {isLoading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          <p className="mt-2 text-gray-600">Loading documents...</p>
        </div>
      )}

      {error && (
        <div className="card bg-red-50 border-red-200">
          <p className="text-red-800">Failed to load documents. Please try again.</p>
        </div>
      )}

      {data && data.items.length === 0 && (
        <div className="card text-center py-12">
          <p className="text-gray-600">No documents found</p>
          {(statusFilter || tagFilter || searchQuery) && (
            <button
              onClick={() => {
                setStatusFilter('')
                setTagFilter('')
                setSearchQuery('')
                setPage(1)
              }}
              className="mt-4 btn btn-secondary"
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.items.map((doc) => (
              <DocumentCard key={doc.id} document={doc} onDelete={handleDelete} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-8 flex items-center justify-center space-x-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn btn-secondary disabled:opacity-50"
              >
                Previous
              </button>

              <div className="flex items-center space-x-1">
                {Array.from({ length: totalPages }, (_, i) => i + 1)
                  .filter((p) => {
                    // Show first, last, current, and adjacent pages
                    return (
                      p === 1 ||
                      p === totalPages ||
                      Math.abs(p - page) <= 1
                    )
                  })
                  .map((p, idx, arr) => {
                    // Add ellipsis
                    const showEllipsisBefore = idx > 0 && p - arr[idx - 1] > 1
                    return (
                      <div key={p} className="flex items-center">
                        {showEllipsisBefore && (
                          <span className="px-2 text-gray-400">...</span>
                        )}
                        <button
                          onClick={() => setPage(p)}
                          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                            p === page
                              ? 'bg-primary-600 text-white'
                              : 'bg-white text-gray-700 hover:bg-gray-100'
                          }`}
                        >
                          {p}
                        </button>
                      </div>
                    )
                  })}
              </div>

              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn btn-secondary disabled:opacity-50"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
