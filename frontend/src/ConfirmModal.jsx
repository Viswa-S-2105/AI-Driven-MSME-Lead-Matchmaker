export default function ConfirmModal({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  confirmText = 'Confirm',
  showCancel = true,
}) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl shadow-black/50">
        <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-slate-300">{message}</p>

        <div className="mt-6 flex items-center justify-end gap-2">
          {showCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg border border-slate-600 bg-slate-800/40 px-4 py-2 text-sm font-medium text-slate-300 transition hover:border-slate-500 hover:bg-slate-800"
            >
              Cancel
            </button>
          )}
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-sm shadow-orange-900/30 transition hover:bg-orange-400"
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
