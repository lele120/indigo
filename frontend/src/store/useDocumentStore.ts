import { create } from 'zustand'
import type { Document, DocumentStats } from '@/types'

interface UploadProgress {
  file: File
  uploadProgress: number
  taskId?: string
  taskProgress?: number
  documentId?: string
  status: 'uploading' | 'processing' | 'completed' | 'failed'
  error?: string
}

interface DocumentStore {
  // State
  documents: Document[]
  selectedDocument: Document | null
  stats: DocumentStats | null
  uploadQueue: UploadProgress[]
  isLoading: boolean
  error: string | null

  // Actions
  setDocuments: (documents: Document[]) => void
  setSelectedDocument: (document: Document | null) => void
  setStats: (stats: DocumentStats | null) => void
  addToUploadQueue: (file: File) => void
  updateUploadProgress: (fileId: string, progress: Partial<UploadProgress>) => void
  removeFromUploadQueue: (fileId: string) => void
  clearUploadQueue: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

const initialState = {
  documents: [],
  selectedDocument: null,
  stats: null,
  uploadQueue: [],
  isLoading: false,
  error: null,
}

export const useDocumentStore = create<DocumentStore>((set) => ({
  ...initialState,

  setDocuments: (documents) => set({ documents }),

  setSelectedDocument: (document) => set({ selectedDocument: document }),

  setStats: (stats) => set({ stats }),

  addToUploadQueue: (file) =>
    set((state) => ({
      uploadQueue: [
        ...state.uploadQueue,
        {
          file,
          uploadProgress: 0,
          status: 'uploading',
        },
      ],
    })),

  updateUploadProgress: (fileId, progress) =>
    set((state) => ({
      uploadQueue: state.uploadQueue.map((item) =>
        item.file.name === fileId ? { ...item, ...progress } : item
      ),
    })),

  removeFromUploadQueue: (fileId) =>
    set((state) => ({
      uploadQueue: state.uploadQueue.filter((item) => item.file.name !== fileId),
    })),

  clearUploadQueue: () => set({ uploadQueue: [] }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  reset: () => set(initialState),
}))
