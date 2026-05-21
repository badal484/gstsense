import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4">
      <div className="text-center space-y-4 max-w-md">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-8 h-8 bg-blue-700 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">G</span>
          </div>
          <span className="font-bold text-gray-900 text-lg">GSTSense</span>
        </div>

        <p className="text-8xl font-extrabold text-blue-700">404</p>
        <h1 className="text-2xl font-bold text-gray-900">Page not found</h1>
        <p className="text-gray-500 text-sm">
          The page you are looking for does not exist or has been moved.
        </p>
        <p className="text-gray-400 text-xs">You may need to login first.</p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
          <Link
            href="/dashboard"
            className="bg-blue-700 text-white font-semibold px-6 py-2.5 rounded-xl text-sm hover:bg-blue-800 transition-colors"
          >
            Go to Dashboard
          </Link>
          <Link
            href="/"
            className="border border-gray-200 text-gray-700 font-semibold px-6 py-2.5 rounded-xl text-sm hover:bg-gray-50 transition-colors"
          >
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
}
