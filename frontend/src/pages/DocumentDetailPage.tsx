import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/api/client'
import { formatBytes, formatDate } from '@/utils/format'

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editTags, setEditTags] = useState<string[]>([])
  const [newTag, setNewTag] = useState('')

  const { data: document, isLoading, error } = useQuery({
    queryKey: ['document', id],
    queryFn: () => apiClient.getDocument(id!),
    enabled: !!id,
  })

  const { data: allTags } = useQuery({
    queryKey: ['tags'],
    queryFn: () => apiClient.getAllTags(),
  })

  const updateMutation = useMutation({
    mutationFn: () =>
      apiClient.updateDocument(id!, {
        name: editName,
        tags: editTags,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      setIsEditing(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => apiClient.deleteDocument(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      navigate('/documents')
    },
  })

  const handleEdit = () => {
    if (document) {
      setEditName(document.name)
      setEditTags(document.tags.map((t) => t.name))
      setIsEditing(true)
    }
  }

  const handleSave = () => {
    updateMutation.mutate()
  }

  const handleDelete = () => {
    if (window.confirm('Are you sure you want to delete this document?')) {
      deleteMutation.mutate()
    }
  }

  const handleAddTag = () => {
    if (newTag && !editTags.includes(newTag)) {
      setEditTags([...editTags, newTag])
      setNewTag('')
    }
  }

  const handleRemoveTag = (tag: string) => {
    setEditTags(editTags.filter((t) => t !== tag))
  }

  if (isLoading) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        <p className="mt-2 text-gray-600">Loading document...</p>
      </div>
    )
  }

  if (error || !document) {
    return (
      <div className="card bg-red-50 border-red-200">
        <p className="text-red-800">Failed to load document. Please try again.</p>
        <Link to="/documents" className="mt-4 inline-block text-primary-600 hover:text-primary-800">
          ← Back to documents
        </Link>
      </div>
    )
  }

  const statusColors = {
    pending: 'badge-pending',
    processing: 'badge-processing',
    completed: 'badge-completed',
    failed: 'badge-failed',
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <Link to="/documents" className="text-primary-600 hover:text-primary-800 font-medium">
          ← Back to documents
        </Link>
      </div>

      <div className="card">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex-1">
            {isEditing ? (
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="input text-2xl font-bold w-full"
              />
            ) : (
              <h1 className="text-3xl font-bold text-gray-900">{document.name}</h1>
            )}
          </div>
          <span className={`badge ml-4 ${statusColors[document.status]}`}>
            {document.status}
          </span>
        </div>

        {/* Metadata */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">File Size</p>
            <p className="mt-1 text-lg font-semibold text-gray-900">
              {formatBytes(document.file_size)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Pages</p>
            <p className="mt-1 text-lg font-semibold text-gray-900">
              {document.page_count || 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Chunks</p>
            <p className="mt-1 text-lg font-semibold text-gray-900">{document.chunk_count}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-wider">Uploaded</p>
            <p className="mt-1 text-lg font-semibold text-gray-900">
              {formatDate(document.uploaded_at)}
            </p>
          </div>
        </div>

        {/* Tags */}
        <div className="mb-6">
          <h2 className="text-sm font-medium text-gray-700 mb-2">Tags</h2>
          {isEditing ? (
            <div>
              <div className="flex flex-wrap gap-2 mb-3">
                {editTags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-primary-100 text-primary-800"
                  >
                    {tag}
                    <button
                      onClick={() => handleRemoveTag(tag)}
                      className="ml-2 hover:text-primary-900"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleAddTag()}
                  placeholder="Add a tag..."
                  className="input flex-1"
                />
                <button onClick={handleAddTag} className="btn btn-secondary">
                  Add
                </button>
              </div>
              {allTags && allTags.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs text-gray-500 mb-2">Suggested:</p>
                  <div className="flex flex-wrap gap-2">
                    {allTags
                      .filter((tag) => !editTags.includes(tag.name))
                      .map((tag) => (
                        <button
                          key={tag.id}
                          onClick={() => setEditTags([...editTags, tag.name])}
                          className="text-sm px-2 py-1 rounded bg-gray-100 text-gray-700 hover:bg-gray-200"
                        >
                          {tag.name}
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {document.tags.length > 0 ? (
                document.tags.map((tag) => (
                  <span
                    key={tag.id}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800"
                  >
                    {tag.name}
                  </span>
                ))
              ) : (
                <span className="text-gray-500 text-sm">No tags</span>
              )}
            </div>
          )}
        </div>

        {/* Error Message */}
        {document.error_message && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <h3 className="text-sm font-medium text-red-800 mb-1">Processing Error</h3>
            <p className="text-sm text-red-700">{document.error_message}</p>
          </div>
        )}

        {/* Additional Info */}
        <div className="mb-6 p-4 border border-gray-200 rounded-lg">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Document Information</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Document ID</dt>
              <dd className="font-mono text-gray-900 text-xs">{document.id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">File Hash (SHA256)</dt>
              <dd className="font-mono text-gray-900 text-xs truncate max-w-xs">
                {document.file_hash}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">MIME Type</dt>
              <dd className="text-gray-900">{document.mime_type}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Last Updated</dt>
              <dd className="text-gray-900">{formatDate(document.updated_at)}</dd>
            </div>
          </dl>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-6 border-t border-gray-200">
          {isEditing ? (
            <div className="flex space-x-3">
              <button
                onClick={handleSave}
                disabled={updateMutation.isPending}
                className="btn btn-primary"
              >
                {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
              </button>
              <button
                onClick={() => setIsEditing(false)}
                disabled={updateMutation.isPending}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button onClick={handleEdit} className="btn btn-secondary">
              Edit Document
            </button>
          )}

          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="btn btn-danger"
          >
            {deleteMutation.isPending ? 'Deleting...' : 'Delete Document'}
          </button>
        </div>
      </div>
    </div>
  )
}
