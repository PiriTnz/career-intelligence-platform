import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runAgent } from '@/api/profiles'

interface AgentDef {
  name: string
  label: string
  description: string
  params?: Record<string, unknown>
}

const AGENTS: AgentDef[] = [
  { name: 'job_collection_agent', label: 'Collect Jobs', description: 'Fetch new jobs from France Travail and Adzuna.' },
  { name: 'job_scoring_agent', label: 'Score Jobs', description: 'Score all unscored jobs against your profile.' },
  { name: 'feedback_learning_agent', label: 'Analyse Feedback', description: 'Review outcome history and surface skill gap insights.' },
  {
    name: 'opportunity_discovery_agent',
    label: 'Discover Opportunities',
    description: 'Find CIFRE, PhD, Research Engineer and MLOps roles.',
    params: { categories: ['cifre', 'phd', 'research', 'mlops'] },
  },
]

function AgentTrigger({ agent }: { agent: AgentDef }) {
  const [result, setResult] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => runAgent(agent.name, agent.params ?? {}),
    onSuccess: (data) => setResult(JSON.stringify(data, null, 2)),
    onError: (err) => setResult(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`),
  })

  return (
    <div className="border border-gray-200 rounded-xl p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-medium text-gray-900 text-sm">{agent.label}</h3>
          <p className="text-xs text-gray-500 mt-0.5">{agent.description}</p>
        </div>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="shrink-0 text-xs bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white px-3 py-1.5 rounded-lg transition-colors"
        >
          {mutation.isPending ? 'Running…' : 'Run'}
        </button>
      </div>
      {result && (
        <pre className="text-xs bg-gray-50 rounded-lg p-3 overflow-x-auto text-gray-700 max-h-32">
          {result}
        </pre>
      )}
    </div>
  )
}

export default function Settings() {
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500">Manually trigger agents and manage preferences.</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Agent Controls</h2>
        <p className="text-xs text-gray-500">
          These agents run automatically via n8n schedules. You can also trigger them manually here.
        </p>
        <div className="space-y-3">
          {AGENTS.map((agent) => <AgentTrigger key={agent.name} agent={agent} />)}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">LLM Provider</h2>
        <div className="text-sm text-gray-600 space-y-1">
          <p>Provider is configured via backend environment variables:</p>
          <ul className="list-disc list-inside text-xs text-gray-500 space-y-0.5 ml-2">
            <li><code className="bg-gray-100 px-1 rounded">OPENAI_API_KEY</code> — set to use GPT-4o-mini</li>
            <li>If not set, falls back to <strong>Ollama (Llama3)</strong> running locally</li>
          </ul>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <h2 className="font-semibold text-gray-900">Quick Links</h2>
        <div className="flex flex-col gap-2">
          <a
            href="http://localhost:5678"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-brand-600 hover:text-brand-700"
          >
            n8n Workflow Editor →
          </a>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-brand-600 hover:text-brand-700"
          >
            Backend API Docs (Swagger) →
          </a>
        </div>
      </div>
    </div>
  )
}
