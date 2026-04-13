import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useDocumentStore } from '@/store/useDocumentStore'
import apiClient from '@/api/client'
import ProgressBar from '@/components/ProgressBar'

export default function UploadPage() {
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [newTag, setNewTag] = useState('')
  const { uploadQueue, addToUploadQueue, updateUploadProgress, removeFromUploadQueue } =
    useDocumentStore()

  const { data: allTags } = useQuery({
    queryKey: ['tags'],
    queryFn: () => apiClient.getAllTags(),
  })

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      // Upload file
      const response = await apiClient.uploadDocument(file, selectedTags, (progress) => {
        updateUploadProgress(file.name, { uploadProgress: progress })
      })

      updateUploadProgress(file.name, {
        taskId: response.task_id,
        documentId: response.document_id,
        uploadProgress: 100,
        taskProgress: 0,
      })

      // Poll task status
      const pollInterval = setInterval(async () => {
        try {
          const task = await apiClient.getTask(response.task_id)
          updateUploadProgress(file.name, {
            taskProgress: task.progress,
            status: task.status === 'completed' ? 'completed' : 'processing',
          })

          if (task.status === 'completed' || task.status === 'failed') {
            clearInterval(pollInterval)
            if (task.status === 'failed') {
              updateUploadProgress(file.name, {
                status: 'failed',
                error: task.error_message || 'Processing failed',
              })
            }
            setTimeout(() => removeFromUploadQueue(file.name), 3000)
          }
        } catch (error) {
          clearInterval(pollInterval)
          updateUploadProgress(file.name, {
            status: 'failed',
            error: 'Failed to get task status',
          })
        }
      }, 2000)

      return response
    },
  })

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      acceptedFiles.forEach((file) => {
        addToUploadQueue(file)
        uploadMutation.mutate(file)
      })
    },
    [selectedTags]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  })

  const handleAddTag = () => {
    if (newTag && !selectedTags.includes(newTag)) {
      setSelectedTags([...selectedTags, newTag])
      setNewTag('')
    }
  }

  const handleRemoveTag = (tag: string) => {
    setSelectedTags(selectedTags.filter((t) => t !== tag))
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Upload Documents</h1>
        <p className="mt-2 text-gray-600">
          Upload PDF documents to process and index them for semantic search
        </p>
      </div>

      {/* Tags Selection */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Tags (Optional)</h2>
        <div className="flex flex-wrap gap-2 mb-4">
          {selectedTags.map((tag) => (
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
          <div className="mt-4">
            <p className="text-sm text-gray-600 mb-2">Existing tags:</p>
            <div className="flex flex-wrap gap-2">
              {allTags.map((tag) => (
                <button
                  key={tag.id}
                  onClick={() => !selectedTags.includes(tag.name) && setSelectedTags([...selectedTags, tag.name])}
                  className={`text-sm px-2 py-1 rounded ${
                    selectedTags.includes(tag.name)
                      ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                  disabled={selectedTags.includes(tag.name)}
                >
                  {tag.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`card border-2 border-dashed cursor-pointer transition-colors ${
          isDragActive
            ? 'border-primary-500 bg-primary-50'
            : 'border-gray-300 hover:border-primary-400'
        }`}
      >
        <input {...getInputProps()} />
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p className="mt-4 text-lg text-gray-600">
            {isDragActive ? 'Drop files here' : 'Drag & drop PDF files here'}
          </p>
          <p className="mt-2 text-sm text-gray-500">or click to select files</p>
        </div>
      </div>

      {/* Upload Queue */}
      {uploadQueue.length > 0 && (
        <div className="mt-8 card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Progress</h2>
          <div className="space-y-4">
            {uploadQueue.map((upload) => (
              <div key={upload.file.name} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-900 truncate flex-1">
                    {upload.file.name}
                  </span>
                  <span
                    className={`badge ${
                      upload.status === 'completed'
                        ? 'badge-completed'
                        : upload.status === 'failed'
                        ? 'badge-failed'
                        : upload.status === 'processing'
                        ? 'badge-processing'
                        : 'badge-pending'
                    }`}
                  >
                    {upload.status}
                  </span>
                </div>

                {upload.status === 'uploading' && (
                  <ProgressBar progress={upload.uploadProgress} label="Uploading" />
                )}

                {upload.status === 'processing' && upload.taskProgress !== undefined && (
                  <ProgressBar progress={upload.taskProgress} label="Processing" />
                )}

                {upload.error && (
                  <p className="mt-2 text-sm text-red-600">{upload.error}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
