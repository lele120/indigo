import { Link } from 'react-router-dom'
import type { Document } from '@/types'
import { formatBytes, formatDate } from '@/utils/format'

interface DocumentCardProps {
  document: Document
  onDelete?: (id: string) => void
}

export default function DocumentCard({ document, onDelete }: DocumentCardProps) {
  const statusColors = {
    pending: 'badge-pending',
    processing: 'badge-processing',
    completed: 'badge-completed',
    failed: 'badge-failed',
  }

  return (
    <div className="card hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <Link to={`/documents/${document.id}`} className="group">
            <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary-600 transition-colors truncate">
              {document.name}
            </h3>
          </Link>

          <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500">
            <span>{formatBytes(document.file_size)}</span>
            {document.page_count && <span>{document.page_count} pages</span>}
            <span>{document.chunk_count} chunks</span>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {document.tags.map((tag) => (
              <span
                key={tag.id}
                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800"
              >
                {tag.name}
              </span>
            ))}
          </div>
        </div>

        <div className="ml-4 flex flex-col items-end space-y-2">
          <span className={`badge ${statusColors[document.status]}`}>
            {document.status}
          </span>
          <span className="text-xs text-gray-500">{formatDate(document.uploaded_at)}</span>
        </div>
      </div>

      {document.error_message && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-800">{document.error_message}</p>
        </div>
      )}

      {onDelete && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <button
            onClick={() => onDelete(document.id)}
            className="text-sm text-red-600 hover:text-red-800 font-medium"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  )
}
