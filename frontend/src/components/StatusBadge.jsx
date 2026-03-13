export default function StatusBadge({ status }) {
  const styles = {
    pending: 'badge-pending',
    processing: 'bg-purple-100 text-purple-800 badge',
    review: 'badge-review',
    approved: 'bg-blue-100 text-blue-800 badge',
    completed: 'badge-completed',
    failed: 'badge-failed',
    rejected: 'bg-gray-100 text-gray-800 badge',
  }

  return (
    <span className={styles[status] || 'badge bg-gray-100 text-gray-600'}>
      {status}
    </span>
  )
}
