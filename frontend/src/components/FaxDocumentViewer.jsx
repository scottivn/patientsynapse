import { useEffect, useState, useCallback } from 'react'
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize2, Eye, EyeOff } from 'lucide-react'
import { getFaxFileInfo, getFaxFileUrl, getFaxPageUrl } from '../services/api'

const ZOOM_LEVELS = [50, 75, 100, 125, 150, 200]

export default function FaxDocumentViewer({ filename, collapsed, onToggle }) {
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [currentPage, setCurrentPage] = useState(0)
  const [zoomIdx, setZoomIdx] = useState(2) // 100%

  useEffect(() => {
    if (!filename) return
    setLoading(true)
    setError(null)
    getFaxFileInfo(filename)
      .then((data) => {
        setInfo(data)
        setCurrentPage(0)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [filename])

  const zoom = ZOOM_LEVELS[zoomIdx]
  const zoomIn = useCallback(() => setZoomIdx((i) => Math.min(i + 1, ZOOM_LEVELS.length - 1)), [])
  const zoomOut = useCallback(() => setZoomIdx((i) => Math.max(i - 1, 0)), [])
  const fitWidth = useCallback(() => setZoomIdx(2), [])

  if (!filename) return null

  const ext = filename.split('.').pop()?.toLowerCase() || ''
  const isPdf = ext === 'pdf'
  const isImage = ['png', 'jpg', 'jpeg'].includes(ext)
  const isTiff = ['tiff', 'tif'].includes(ext)
  const needsPageRender = isPdf || isTiff

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between bg-gray-100 border-b border-gray-200 px-3 py-2 rounded-t-xl">
        <div className="flex items-center gap-2">
          <button
            onClick={onToggle}
            className="p-1.5 hover:bg-gray-200 rounded text-gray-600"
            title={collapsed ? 'Show document' : 'Hide document'}
          >
            {collapsed ? <Eye size={16} /> : <EyeOff size={16} />}
          </button>
          <span className="text-xs font-medium text-gray-700 truncate max-w-[200px]">{filename}</span>
        </div>
        {!collapsed && info && (
          <div className="flex items-center gap-1.5">
            {info.pages > 1 && (
              <>
                <button
                  onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
                  disabled={currentPage === 0}
                  className="p-1 hover:bg-gray-200 rounded disabled:opacity-30"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="text-xs text-gray-600 min-w-[60px] text-center">
                  {currentPage + 1} / {info.pages}
                </span>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(info.pages - 1, p + 1))}
                  disabled={currentPage >= info.pages - 1}
                  className="p-1 hover:bg-gray-200 rounded disabled:opacity-30"
                >
                  <ChevronRight size={16} />
                </button>
                <span className="w-px h-4 bg-gray-300 mx-1" />
              </>
            )}
            <button onClick={zoomOut} disabled={zoomIdx === 0} className="p-1 hover:bg-gray-200 rounded disabled:opacity-30">
              <ZoomOut size={14} />
            </button>
            <span className="text-xs text-gray-600 min-w-[36px] text-center">{zoom}%</span>
            <button onClick={zoomIn} disabled={zoomIdx === ZOOM_LEVELS.length - 1} className="p-1 hover:bg-gray-200 rounded disabled:opacity-30">
              <ZoomIn size={14} />
            </button>
            <button onClick={fitWidth} className="p-1 hover:bg-gray-200 rounded" title="Fit width">
              <Maximize2 size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Content */}
      {!collapsed && (
        <div className="flex-1 overflow-auto bg-gray-200 rounded-b-xl">
          {loading && (
            <div className="flex items-center justify-center h-64">
              <p className="text-sm text-gray-500">Loading document...</p>
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center h-64">
              <p className="text-sm text-red-500">Failed to load: {error}</p>
            </div>
          )}
          {!loading && !error && info && (
            <div className="flex justify-center p-4">
              {needsPageRender ? (
                <img
                  key={`${filename}-${currentPage}`}
                  src={getFaxPageUrl(filename, currentPage)}
                  alt={`Page ${currentPage + 1}`}
                  style={{ width: `${zoom}%`, maxWidth: 'none' }}
                  className="shadow-lg bg-white"
                />
              ) : isImage ? (
                <img
                  src={getFaxFileUrl(filename)}
                  alt={filename}
                  style={{ width: `${zoom}%`, maxWidth: 'none' }}
                  className="shadow-lg bg-white"
                />
              ) : (
                <div className="flex items-center justify-center h-64">
                  <p className="text-sm text-gray-500">Preview not available for this file type</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
