import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen">

      {/* Hero — full viewport title page */}
      <section className="min-h-screen flex flex-col items-center justify-center px-6">
        <h1 className="text-6xl md:text-7xl font-bold tracking-tight">Q.E.D.</h1>
        <p className="text-lg md:text-xl text-gray-400 italic mt-2">
          quod erat demonstrandum
        </p>
        <p className="text-sm md:text-base text-gray-300 mt-8 max-w-lg text-center leading-relaxed">
          An autonomous research platform that runs deep, multi-day investigations
          in the fundamental sciences — so you can focus on the questions that matter
          while your agents handle the computation.
        </p>
        <div className="mt-6 text-xs text-gray-600 animate-bounce">
          scroll
        </div>
      </section>

      {/* How It Works */}
      <section className="min-h-screen flex flex-col justify-center px-6 py-20">
        <div className="max-w-3xl mx-auto w-full">
          <h2 className="text-2xl font-bold text-gray-100 mb-12 text-center">How It Works</h2>

          <div className="grid md:grid-cols-2 gap-10">

            {/* Explore */}
            <div className="border border-gray-800 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wide mb-4">
                Explore
              </h3>
              <ul className="space-y-3 text-sm text-gray-400">
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  Launch a continuous research agent that persists over days
                </li>
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  Read deep research reports generated automatically each cycle
                </li>
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  Download model scripts, libraries, and test suites your agent builds
                </li>
              </ul>
            </div>

            {/* Interact */}
            <div className="border border-gray-800 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wide mb-4">
                Interact
              </h3>
              <ul className="space-y-3 text-sm text-gray-400">
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  Ask real-time questions while your exploration runs in the background
                </li>
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  Run computations and visualize results instantly
                </li>
              </ul>
            </div>

            {/* Share */}
            <div className="border border-gray-800 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wide mb-4">
                Share
              </h3>
              <ul className="space-y-3 text-sm text-gray-400">
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  Install pre-built research packages and build on top of them
                </li>
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  Open-source your explorations for others to learn from
                </li>
              </ul>
            </div>

            {/* Safety */}
            <div className="border border-gray-800 rounded-xl p-6">
              <h3 className="text-sm font-semibold text-gray-100 uppercase tracking-wide mb-4">
                Safety
              </h3>
              <ul className="space-y-3 text-sm text-gray-400">
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  All work runs on isolated cloud VMs — no impact to your personal machine
                </li>
                <li className="flex gap-2">
                  <span className="text-gray-600 flex-shrink-0">-</span>
                  Agent permissions and tools are strictly scoped and enforced
                </li>
              </ul>
            </div>

          </div>
        </div>
      </section>

      {/* Sign up / Log in */}
      <section className="min-h-[60vh] flex flex-col items-center justify-center px-6 py-20">
        <h2 className="text-2xl font-bold text-gray-100 mb-3">Get Started</h2>
        <p className="text-sm text-gray-400 mb-8 text-center max-w-md">
          Create an account to launch your first exploration.
          All you need is a Claude account and a Wolfram Engine license (free).
        </p>
        <div className="flex gap-4">
          <Link
            href="/signup"
            className="px-6 py-2.5 bg-white text-gray-900 rounded-lg font-medium hover:bg-gray-200 transition-colors"
          >
            Sign Up
          </Link>
          <Link
            href="/login"
            className="px-6 py-2.5 border border-gray-600 rounded-lg font-medium hover:bg-gray-800 transition-colors"
          >
            Log In
          </Link>
        </div>
      </section>

    </div>
  );
}
