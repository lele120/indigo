// Document types
export interface Tag {
  id: number
  name: string
  created_at: string
}

export interface Document {
  id: string
  name: string
  file_hash: string
  file_size: number
  mime_type: string
  page_count: number | null
  chunk_count: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message: string | null
  uploaded_at: string
  updated_at: string
  tags: Tag[]
}

export interface UploadTask {
  id: string
  document_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface Chunk {
  id: string
  document_id: string
  chunk_index: number
  chunk_type: 'text' | 'table' | 'image'
  page_number: number | null
  text: string
  text_preview: string
  created_at: string
}

// API Response types
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface UploadResponse {
  document_id: string
  task_id: string
  message: string
}

export interface SearchResult {
  chunk_id: string
  document_id: string
  document_name: string
  chunk_index: number
  page_number: number | null
  text_preview: string
  rrf_score?: number
  vector_score?: number
  bm25_score?: number
}

export interface SearchResponse {
  query: string
  total: number
  results: SearchResult[]
  search_time_ms: number
  use_hybrid: boolean
}

// Request types
export interface SearchRequest {
  query: string
  limit?: number
  document_ids?: string[]
  use_hybrid?: boolean
  vector_weight?: number
  bm25_weight?: number
  use_cache?: boolean
}

export interface UpdateDocumentRequest {
  name?: string
  tags?: string[]
}

// Statistics
export interface DocumentStats {
  total: number
  pending: number
  processing: number
  completed: number
  failed: number
  tags: string[]
}
