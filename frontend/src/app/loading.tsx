export default function Loading() {
  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center gap-4">
      <div className="inline-flex items-center gap-2">
        <div className="w-8 h-8 bg-blue-700 rounded-lg flex items-center justify-center">
          <span className="text-white font-bold text-sm">G</span>
        </div>
        <span className="font-bold text-gray-900 text-lg">GSTSense</span>
      </div>
      <div className="w-8 h-8 border-[3px] border-blue-200 border-t-blue-700 rounded-full animate-spin" />
      <p className="text-sm text-gray-400">Loading…</p>
    </div>
  );
}
