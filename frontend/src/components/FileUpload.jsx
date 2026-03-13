import { useCallback, useState } from 'react'
import { Upload, FileText, X } from 'lucide-react'

export default function FileUpload({ onUpload, accept = '.pdf,.png,.jpg,.jpeg,.tiff' }) {
  const [dragOver, setDragOver] = useState(false)
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }, [])

  const handleSelect = (e) => {
    const selected = e.target.files[0]
    if (selected) setFile(selected)
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      await onUpload(file)
      setFile(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
          dragOver ? 'border-brand-400 bg-brand-50' : 'border-gray-300 hover:border-gray-400'
        }`}
      >
        <input
          type="file"
          accept={accept}
          onChange={handleSelect}
          className="hidden"
          id="fax-upload"
        />
        <label htmlFor="fax-upload" className="cursor-pointer">
          <Upload className="mx-auto mb-3 text-gray-400" size={32} />
          <p className="text-sm font-medium text-gray-700">
            Drop a referral fax here or <span className="text-brand-500">browse</span>
          </p>
          <p className="text-xs text-gray-500 mt-1">PDF, PNG, JPG, TIFF</p>
        </label>
      </div>

      {file && (
        <div className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-3">
          <div className="flex items-center gap-3">
            <FileText size={18} className="text-gray-400" />
            <div>
              <p className="text-sm font-medium text-gray-700">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(0)} KB</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleUpload} disabled={uploading} className="btn-primary text-sm">
              {uploading ? 'Processing...' : 'Upload & Process'}
            </button>
            <button onClick={() => setFile(null)} className="p-1 hover:bg-gray-200 rounded">
              <X size={16} className="text-gray-500" />
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-2">{error}</p>
      )}
    </div>
  )
}
