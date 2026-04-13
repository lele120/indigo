import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/api/client'

export default function Navbar() {
  const location = useLocation()

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: () => apiClient.getStats(),
    refetchInterval: 30000, // Refresh every 30s
  })

  const navLinks = [
    { path: '/upload', label: 'Upload' },
    { path: '/documents', label: 'Documents' },
    { path: '/search', label: 'Search' },
  ]

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <Link to="/" className="text-2xl font-bold text-primary-600">
                Indigo
              </Link>
              <span className="ml-2 text-sm text-gray-500">Document Intelligence</span>
            </div>
            <div className="hidden sm:ml-8 sm:flex sm:space-x-8">
              {navLinks.map(({ path, label }) => (
                <Link
                  key={path}
                  to={path}
                  className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium transition-colors ${
                    location.pathname === path
                      ? 'border-primary-500 text-gray-900'
                      : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                  }`}
                >
                  {label}
                </Link>
              ))}
            </div>
          </div>

          {stats && (
            <div className="flex items-center space-x-4 text-sm">
              <div className="flex items-center space-x-2">
                <span className="text-gray-500">Total:</span>
                <span className="font-semibold text-gray-900">{stats.total}</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="badge badge-processing">{stats.processing} processing</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
