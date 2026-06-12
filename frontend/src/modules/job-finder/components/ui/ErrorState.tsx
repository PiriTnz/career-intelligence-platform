import { AlertCircle } from 'lucide-react'

interface Props {
  title?: string
  message?: string
  onRetry?: () => void
}

export default function ErrorState({
  title = 'Something went wrong',
  message = 'Failed to load data. Please try again.',
  onRetry,
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center animate-fade-in">
      <div className="w-14 h-14 rounded-2xl bg-rose-50 border border-rose-100 flex items-center justify-center mb-4">
        <AlertCircle size={24} className="text-rose-400" />
      </div>
      <h3 className="text-base font-semibold text-slate-800 mb-1.5">{title}</h3>
      <p className="text-sm text-slate-500 max-w-xs">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-5 px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm font-medium rounded-xl transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  )
}
