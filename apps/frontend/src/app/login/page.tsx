"use client";

import Link from "next/link";
import { Brand } from "@/components/brand";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Invalid credentials. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="login-page workspace flex min-h-full items-center justify-center px-6">
      <div className="login-card w-full max-w-sm">
        <div className="mb-10">
          <Brand />
        </div>
        <h1 className="mb-1 text-2xl font-bold text-white">Welcome back.</h1>
        <p className="mb-8 text-sm text-gray-400">
          A clearer view starts here. Sign in to your workspace.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="email"
              className="mb-1.5 block text-sm font-medium text-gray-300"
            >
              Email address
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:border-sentinel-500 focus:outline-none focus:ring-1 focus:ring-sentinel-500"
              placeholder="you@company.com"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-1.5 block text-sm font-medium text-gray-300"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:border-sentinel-500 focus:outline-none focus:ring-1 focus:ring-sentinel-500"
              placeholder="••••••••••••"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-800 bg-red-900/20 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full rounded-lg bg-sentinel-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-sentinel-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <Link href="/" className="login-back">
          ← Back to Sentinel 2
        </Link>

        <p className="mt-6 text-center text-xs text-gray-600">
          Access is controlled by your administrator.
          <br />
          Contact your Sentinel admin if you need an account.
        </p>
      </div>
    </div>
  );
}
