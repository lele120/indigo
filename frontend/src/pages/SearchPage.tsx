import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import apiClient from '@/api/client'
import type { SearchResult } from '@/types'
import { formatDuration } from '@/utils/format'

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [useHybrid, setUseHybrid] = useState(true)
  const [limit, setLimit] = useState(10)
  const [results, setResults] = useState<SearchResult[]>([])
  const [searchTime, setSearchTime] = useState<number | null>(null)
  const [totalResults, setTotalResults] = useState<number>(0)

  const searchMutation = useMutation({
    mutationFn: (searchQuery: string) =>
      apiClient.search({
        query: searchQuery,
        limit,
        use_hybrid: useHybrid,
      }),
    onSuccess: (data) => {
      setResults(data.results)
      setSearchTime(data.search_time_ms)
      setTotalResults(data.total)
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) {
      searchMutation.mutate(query)
    }
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Search Documents</h1>
        <p className="mt-2 text-gray-600">
          Semantic search across all your documents using hybrid vector + keyword matching
        </p>
      </div>

      {/* Search Form */}
      <form onSubmit={handleSearch} className="card mb-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Search Query
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What are vector embeddings?"
              className="input w-full text-lg"
              autoFocus
            />
          </div>

          <div className="flex items-center space-x-6">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="hybrid"
                checked={useHybrid}
                onChange={(e) => setUseHybrid(e.target.checked)}
                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              />
              <label htmlFor="hybrid" className="ml-2 text-sm text-gray-700">
                Hybrid search (Vector + BM25)
              </label>
            </div>

            <div className="flex items-center space-x-2">
              <label htmlFor="limit" className="text-sm text-gray-700">
                Results:
              </label>
              <select
                id="limit"
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="input py-1"
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={!query.trim() || searchMutation.isPending}
            className="btn btn-primary w-full"
          >
            {searchMutation.isPending ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Searching...
              </span>
            ) : (
              'Search'
            )}
          </button>
        </div>
      </form>

      {/* Search Stats */}
      {searchTime !== null && (
        <div className="mb-4 flex items-center justify-between text-sm text-gray-600">
          <span>
            Found <strong className="text-gray-900">{totalResults}</strong> results
          </span>
          <span>
            Search time: <strong className="text-gray-900">{formatDuration(searchTime)}</strong>
          </span>
        </div>
      )}

      {/* Error */}
      {searchMutation.isError && (
        <div className="card bg-red-50 border-red-200 mb-6">
          <p className="text-red-800">Search failed. Please try again.</p>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          {results.map((result, index) => (
            <div key={`${result.chunk_id}-${index}`} className="card hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <Link
                    to={`/documents/${result.document_id}`}
                    className="text-lg font-semibold text-primary-600 hover:text-primary-800"
                  >
                    {result.document_name}
                  </Link>
                  {result.page_number && (
                    <span className="ml-2 text-sm text-gray-500">
                      Page {result.page_number}
                    </span>
                  )}
                </div>
                <div className="ml-4 text-right">
                  <div className="text-xs text-gray-500 space-y-1">
                    {result.rrf_score !== undefined && (
                      <div>
                        RRF: <span className="font-medium text-gray-900">{result.rrf_score.toFixed(4)}</span>
                      </div>
                    )}
                    {result.vector_score !== undefined && (
                      <div>
                        Vector: <span className="font-medium text-gray-700">{result.vector_score.toFixed(4)}</span>
                      </div>
                    )}
                    {result.bm25_score !== undefined && result.bm25_score !== null && (
                      <div>
                        BM25: <span className="font-medium text-gray-700">{result.bm25_score.toFixed(4)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <p className="text-gray-700 leading-relaxed">{result.text_preview}</p>

              <div className="mt-3 flex items-center space-x-4 text-sm text-gray-500">
                <span>Chunk #{result.chunk_index + 1}</span>
                <span>•</span>
                <Link
                  to={`/documents/${result.document_id}`}
                  className="text-primary-600 hover:text-primary-800 font-medium"
                >
                  View document
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {searchMutation.isSuccess && results.length === 0 && (
        <div className="card text-center py-12">
          <p className="text-gray-600">No results found for "{query}"</p>
          <p className="mt-2 text-sm text-gray-500">Try different keywords or upload more documents</p>
        </div>
      )}

      {/* Initial state */}
      {!searchMutation.isSuccess && !searchMutation.isPending && (
        <div className="card text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <p className="mt-4 text-gray-600">Enter a search query to get started</p>
          <p className="mt-2 text-sm text-gray-500">
            {useHybrid
              ? 'Hybrid search combines semantic understanding with keyword matching'
              : 'Vector search uses semantic similarity to find relevant content'}
          </p>
        </div>
      )}
    </div>
  )
}
