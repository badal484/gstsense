export default function CALoading() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
      <div className="w-8 h-8 border-4 border-blue-700 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-gray-500">Loading CA dashboard...</p>
    </div>
  )
}
