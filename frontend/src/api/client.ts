import axios, { AxiosInstance, AxiosProgressEvent } from 'axios'
import type {
  Document,
  PaginatedResponse,
  UploadResponse,
  UploadTask,
  SearchRequest,
  SearchResponse,
  UpdateDocumentRequest,
  Tag,
  DocumentStats,
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    })
  }

  // Documents
  async listDocuments(params: {
    page?: number
    page_size?: number
    status?: string
    tags?: string
    search?: string
  } = {}): Promise<PaginatedResponse<Document>> {
    const { data } = await this.client.get('/documents', { params })
    return data
  }

  async getDocument(id: string): Promise<Document> {
    const { data } = await this.client.get(`/documents/${id}`)
    return data
  }

  async uploadDocument(
    file: File,
    tags: string[] = [],
    onProgress?: (progress: number) => void
  ): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (tags.length > 0) {
      formData.append('tags', tags.join(','))
    }

    const { data } = await this.client.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (progressEvent.total && onProgress) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      },
    })
    return data
  }

  async updateDocument(id: string, data: UpdateDocumentRequest): Promise<Document> {
    const { data: response } = await this.client.patch(`/documents/${id}`, data)
    return response
  }

  async deleteDocument(id: string): Promise<void> {
    await this.client.delete(`/documents/${id}`)
  }

  // Upload Tasks
  async getTask(taskId: string): Promise<UploadTask> {
    const { data } = await this.client.get(`/documents/tasks/${taskId}/status`)
    return data
  }

  // Tags
  async getAllTags(): Promise<Tag[]> {
    const { data } = await this.client.get('/documents/tags/all')
    return data
  }

  // Search
  async search(request: SearchRequest): Promise<SearchResponse> {
    const { data } = await this.client.post('/search', request)
    return data
  }

  async searchByTag(tag: string, page = 1, pageSize = 10): Promise<PaginatedResponse<Document>> {
    return this.listDocuments({ tags: tag, page, page_size: pageSize })
  }

  // Stats
  async getStats(): Promise<DocumentStats> {
    const { data } = await this.client.get('/documents/stats')
    return data
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    const { data } = await this.client.get('/health')
    return data
  }
}

export const apiClient = new ApiClient()
export default apiClient
