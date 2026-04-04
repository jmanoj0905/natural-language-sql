import { SignInButton, SignUpButton } from '@clerk/react'

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Top bar */}
      <header className="w-full px-6 h-16 flex items-center border-b-2 border-border bg-white">
        <span className="text-2xl font-black text-foreground uppercase font-heading tracking-tight">NLSQL</span>
      </header>

      {/* Main */}
      <div className="flex-1 flex items-center justify-center hatch-pattern px-4">
        <div className="w-full max-w-md space-y-6">

          {/* Card */}
          <div className="bg-white brutalist-border soft-shadow-lg rounded-2xl overflow-hidden">

            {/* Card header */}
            <div className="bg-[#E9D5FF] border-b-2 border-border px-8 pt-8 pb-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 bg-[#1a1c1d] rounded-full flex items-center justify-center">
                  <span className="material-symbols-outlined text-white text-sm">database</span>
                </div>
                <span className="font-mono text-xs uppercase tracking-widest text-foreground/60">v1.0 · Cloud</span>
              </div>
              <h1 className="text-4xl font-black uppercase font-heading tracking-tight leading-none">
                Natural<br />Language<br />SQL
              </h1>
              <p className="mt-3 text-sm font-body text-foreground/70 leading-relaxed">
                Query any database in plain English. Powered by local AI.
              </p>
            </div>

            {/* Card body */}
            <div className="px-8 py-6 space-y-4">

              {/* Feature list */}
              <ul className="space-y-2 pb-2">
                {[
                  ['smart_toy', 'AI-powered SQL generation'],
                  ['hub', 'Connect local databases via tunnel'],
                  ['table_chart', 'PostgreSQL & MySQL support'],
                  ['lock', 'Encrypted credential storage'],
                ].map(([icon, label]) => (
                  <li key={icon} className="flex items-center gap-3 text-sm font-body text-foreground/70">
                    <span className="material-symbols-outlined text-base text-[#7d4e58]">{icon}</span>
                    {label}
                  </li>
                ))}
              </ul>

              {/* CTA buttons */}
              <SignInButton mode="modal">
                <button className="w-full px-6 py-3 bg-[#1a1c1d] text-white font-heading font-bold text-sm rounded-base hover:bg-[#333] transition-colors cursor-pointer brutalist-border soft-shadow active-press">
                  Sign In
                </button>
              </SignInButton>

              <SignUpButton mode="modal">
                <button className="w-full px-6 py-3 bg-white text-foreground font-heading font-bold text-sm rounded-base hover:bg-[#f1f5f9] transition-colors cursor-pointer brutalist-border active-press">
                  Create Account
                </button>
              </SignUpButton>
            </div>
          </div>

          <p className="text-center font-mono text-[10px] uppercase text-foreground/40 tracking-widest">
            &copy; {new Date().getFullYear()} NLSQL &mdash; All data stays in your infrastructure
          </p>
        </div>
      </div>
    </div>
  )
}
