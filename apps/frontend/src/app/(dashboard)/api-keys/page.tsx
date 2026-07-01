"use client";

import { useState } from "react";
import { useAPIKeys, useRevokeAPIKey } from "@/hooks/use-sentinel-data";
import { dashboardApi } from "@/lib/dashboard-api";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/hooks/use-sentinel-data";
import { formatDistanceToNow, format } from "date-fns";
import type { APIKeyCreated } from "@/types/dashboard";

const AVAILABLE_SCOPES = [
  "events:write",
  "events:read",
  "alerts:read",
  "alerts:write",
  "risks:read",
  "users:read",
  "api_keys:read",
];

export default function APIKeysPage() {
  const { data: keys, isLoading } = useAPIKeys();
  const revoke = useRevokeAPIKey();
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">API Keys</h1>
          <p className="mt-0.5 text-sm text-gray-400">
            Manage credentials for services and AI agents
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-sentinel-600 px-4 py-2 text-sm font-medium text-white hover:bg-sentinel-500"
        >
          + New Key
        </button>
      </div>

      {/* One-time key display */}
      {newKey && (
        <div className="rounded-xl border border-green-800 bg-green-900/20 p-5">
          <p className="mb-2 text-sm font-semibold text-green-400">
            ✓ Key created — copy it now. It will never be shown again.
          </p>
          <div className="flex items-center gap-3">
            <code className="flex-1 rounded-lg bg-gray-900 px-4 py-3 font-mono text-sm text-green-300 break-all">
              {newKey}
            </code>
            <button
              onClick={() => {
                navigator.clipboard.writeText(newKey);
              }}
              className="shrink-0 rounded-lg border border-green-800 px-3 py-2 text-xs text-green-400 hover:bg-green-900/30"
            >
              Copy
            </button>
          </div>
          <button
            onClick={() => setNewKey(null)}
            className="mt-3 text-xs text-gray-500 hover:text-gray-400"
          >
            I've saved the key — dismiss
          </button>
        </div>
      )}

      {/* Create key form */}
      {showCreate && (
        <CreateKeyForm
          onCreated={(key) => {
            setNewKey(key);
            setShowCreate(false);
          }}
          onCancel={() => setShowCreate(false)}
        />
      )}

      {/* Keys table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-xs text-gray-500">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Prefix</th>
                <th className="px-4 py-3 font-medium">Scopes</th>
                <th className="px-4 py-3 font-medium">Uses</th>
                <th className="px-4 py-3 font-medium">Last Used</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {isLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 animate-pulse rounded bg-gray-800" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : keys?.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-sm text-gray-600">
                    No API keys yet. Create one to allow services and AI agents to authenticate.
                  </td>
                </tr>
              ) : (
                keys?.map((key) => (
                  <tr key={key.id} className="hover:bg-gray-800/20">
                    <td className="px-4 py-3">
                      <p className="font-medium text-white">{key.name}</p>
                      {key.agent_name && (
                        <p className="text-xs text-gray-500">🤖 {key.agent_name}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-gray-400">
                        {key.actor_type === "AI_AGENT" ? "🤖 AI Agent" :
                         key.actor_type === "SERVICE" ? "⚙️ Service" : "👤 Human API"}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-400">
                      {key.key_prefix}…
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {key.scopes.slice(0, 2).map((s) => (
                          <span key={s} className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-gray-400">
                            {s}
                          </span>
                        ))}
                        {key.scopes.length > 2 && (
                          <span className="text-xs text-gray-600">+{key.scopes.length - 2}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 tabular text-sm text-gray-300">
                      {key.total_uses.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {key.last_used_at
                        ? formatDistanceToNow(new Date(key.last_used_at), { addSuffix: true })
                        : "Never"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          key.is_active
                            ? "bg-green-900/30 text-green-400"
                            : "bg-gray-800 text-gray-500"
                        }`}
                      >
                        {key.is_active ? "active" : "inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {key.is_active && (
                        <button
                          onClick={() => {
                            if (confirm(`Revoke key "${key.name}"? This cannot be undone.`)) {
                              revoke.mutate(key.id);
                            }
                          }}
                          className="text-xs text-red-500 hover:text-red-400"
                        >
                          Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function CreateKeyForm({
  onCreated,
  onCancel,
}: {
  onCreated: (key: string) => void;
  onCancel: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [actorType, setActorType] = useState("SERVICE");
  const [agentName, setAgentName] = useState("");
  const [agentVersion, setAgentVersion] = useState("");
  const [agentDescription, setAgentDescription] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["events:write"]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleScope(scope: string) {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  }

  async function handleCreate() {
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await dashboardApi.post<APIKeyCreated>("api-keys/create", {
        name,
        actor_type: actorType,
        scopes: selectedScopes,
        agent_name: agentName,
        agent_version: agentVersion,
        agent_description: agentDescription,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys });
      onCreated(result.key);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create key.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-white">Create API Key</h2>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">Key Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Fraud Detector Service"
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-sentinel-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">Actor Type</label>
          <select
            value={actorType}
            onChange={(e) => setActorType(e.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-sentinel-500 focus:outline-none"
          >
            <option value="SERVICE">⚙️ Service</option>
            <option value="AI_AGENT">🤖 AI Agent</option>
            <option value="HUMAN_API">👤 Human API</option>
          </select>
        </div>
      </div>

      {actorType === "AI_AGENT" && (
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">
              Agent Name <span className="text-red-500">*</span>
            </label>
            <input
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              placeholder="support-bot-v2"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-sentinel-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">
              Model / Version
            </label>
            <input
              value={agentVersion}
              onChange={(e) => setAgentVersion(e.target.value)}
              placeholder="gpt-4-turbo-2024-04"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-sentinel-500 focus:outline-none"
            />
          </div>
          <div className="col-span-2">
            <label className="mb-1 block text-xs font-medium text-gray-400">
              Description
            </label>
            <input
              value={agentDescription}
              onChange={(e) => setAgentDescription(e.target.value)}
              placeholder="Handles tier-1 customer support queries"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-600 focus:border-sentinel-500 focus:outline-none"
            />
          </div>
        </div>
      )}

      <div>
        <label className="mb-2 block text-xs font-medium text-gray-400">Scopes</label>
        <div className="flex flex-wrap gap-2">
          {AVAILABLE_SCOPES.map((scope) => (
            <button
              key={scope}
              onClick={() => toggleScope(scope)}
              className={`rounded border px-2.5 py-1 font-mono text-xs transition-colors ${
                selectedScopes.includes(scope)
                  ? "border-sentinel-600 bg-sentinel-900/40 text-sentinel-300"
                  : "border-gray-700 text-gray-500 hover:border-gray-500"
              }`}
            >
              {scope}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="rounded-lg border border-red-800 bg-red-900/20 px-3 py-2 text-xs text-red-400">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-3">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-400 hover:text-white"
        >
          Cancel
        </button>
        <button
          onClick={handleCreate}
          disabled={isSubmitting || !name || selectedScopes.length === 0}
          className="rounded-lg bg-sentinel-600 px-4 py-2 text-sm font-medium text-white hover:bg-sentinel-500 disabled:opacity-40"
        >
          {isSubmitting ? "Creating…" : "Create Key"}
        </button>
      </div>
    </div>
  );
}
