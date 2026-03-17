import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center">
      <h1 className="text-4xl font-bold tracking-tight mb-2">Q.E.D.</h1>
      <p className="text-gray-500 mb-10">
        Continuous autonomous research powered by Claude and Wolfram
      </p>
      <div className="flex gap-4">
        <Link
          href="/signup"
          className="px-6 py-2.5 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
        >
          Sign Up
        </Link>
        <Link
          href="/login"
          className="px-6 py-2.5 border border-gray-300 rounded-lg font-medium hover:bg-gray-50 transition-colors"
        >
          Log In
        </Link>
      </div>
    </div>
  );
}
