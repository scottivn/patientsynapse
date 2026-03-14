import { useEffect, useState } from 'react'
import { Save, RefreshCw, CheckCircle2, XCircle, ExternalLink, Shield, Cpu, Server, Building2, Zap } from 'lucide-react'
import { getAuthStatus, getStatus, loginAuth, switchEMR, connectService } from '../services/api'

const EMR_OPTIONS = [
  { value: 'ecw', label: 'eClinicalWorks', desc: 'SMART on FHIR, asymmetric JWT auth' },
  { value: 'athena', label: 'athenahealth', desc: 'SMART on FHIR, client secret auth' },
]

const LLM_OPTIONS = [
  { value: 'grok', label: 'Grok (X.AI)', desc: 'Default — fast, cost-effective' },
  { value: 'openai', label: 'OpenAI', desc: 'GPT-4o / GPT-4.1' },
  { value: 'anthropic', label: 'Anthropic', desc: 'Claude Sonnet / Opus' },
  { value: 'ollama', label: 'Ollama (Local)', desc: 'Self-hosted, fully private' },
]

export default function Settings() {
  const [auth, setAuth] = useState(null)
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [switching, setSwitching] = useState(false)
  const [connecting, setConnecting] = useState(false)

  useEffect(() => {
    Promise.all([
      getAuthStatus().catch(() => null),
      getStatus().catch(() => null),
    ]).then(([a, s]) => {
      setAuth(a)
      setStatus(s)
    }).finally(() => setLoading(false))
  }, [])

  const handleLogin = async () => {
    try {
      const data = await loginAuth()
      if (data.authorize_url) window.open(data.authorize_url, '_blank')
    } catch (err) {
      alert(err.message)
    }
  }

  const handleSwitchEMR = async (provider) => {
    if (status?.emr_provider_key === provider) return
    setSwitching(true)
    try {
      const result = await switchEMR(provider)
      // Refresh status + auth after switch
      const [a, s] = await Promise.all([
        getAuthStatus().catch(() => null),
        getStatus().catch(() => null),
      ])
      setAuth(a)
      setStatus(s)
    } catch (err) {
      alert(`Switch failed: ${err.message}`)
    } finally {
      setSwitching(false)
    }
  }

  const handleServiceConnect = async () => {
    setConnecting(true)
    try {
      await connectService()
      const [a, s] = await Promise.all([
        getAuthStatus().catch(() => null),
        getStatus().catch(() => null),
      ])
      setAuth(a)
      setStatus(s)
    } catch (err) {
      alert(`Service connect failed: ${err.message}`)
    } finally {
      setConnecting(false)
    }
  }

  if (loading) return <p className="text-gray-500 text-center py-12">Loading settings...</p>

  const connected = auth?.authenticated === true

  const emrName = status?.emr_provider || auth?.emr_provider || 'EMR'

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>

      {/* EMR Provider */}
      <div className="card">
        <div className="flex items-center gap-2 mb-5">
          <Building2 size={18} className="text-brand-500" />
          <h2 className="font-semibold text-gray-900">EMR Provider</h2>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Click a card below to switch EMR providers instantly — no server restart needed.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {EMR_OPTIONS.map((opt) => {
            const active = status?.emr_provider_key === opt.value
            return (
              <button
                key={opt.value}
                onClick={() => handleSwitchEMR(opt.value)}
                disabled={switching || active}
                className={`border rounded-lg px-4 py-3 text-left transition-all ${
                  active
                    ? 'border-brand-400 bg-brand-50 ring-2 ring-brand-200'
                    : 'border-gray-200 hover:border-brand-300 hover:bg-gray-50 cursor-pointer'
                } ${switching ? 'opacity-60' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <p className={`font-medium text-sm ${active ? 'text-brand-700' : 'text-gray-700'}`}>{opt.label}</p>
                  {active && <span className="badge-success text-xs">Active</span>}
                  {switching && !active && <RefreshCw size={14} className="animate-spin text-gray-400" />}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{opt.desc}</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* FHIR Connection */}
      <div className="card">
        <div className="flex items-center gap-2 mb-5">
          <Shield size={18} className="text-brand-500" />
          <h2 className="font-semibold text-gray-900">{emrName} FHIR Connection</h2>
        </div>

        <div className="flex items-center gap-4 mb-5">
          {connected ? (
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircle2 size={18} />
              <span className="text-sm font-medium">Connected</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-gray-400">
              <XCircle size={18} />
              <span className="text-sm font-medium">Not connected</span>
            </div>
          )}
          <button onClick={handleLogin} className="btn-primary text-sm flex items-center gap-2">
            <ExternalLink size={14} />
            {connected ? 'Reconnect' : `Connect to ${emrName}`}
          </button>
          <button onClick={handleServiceConnect} disabled={connecting} className="btn-primary text-sm flex items-center gap-2 bg-amber-600 hover:bg-amber-700">
            <Zap size={14} />
            {connecting ? 'Connecting...' : 'Service Connect (2-legged)'}
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <label className="block text-xs text-gray-500 mb-1">FHIR Base URL</label>
            <input readOnly value={auth?.fhir_base_url || '—'} className="input bg-gray-50 cursor-default" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Client ID</label>
            <input readOnly value={auth?.client_id || '—'} className="input bg-gray-50 cursor-default" />
          </div>
          {auth?.token_expires_at && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Token Expires</label>
              <input readOnly value={new Date(auth.token_expires_at * 1000).toLocaleString()} className="input bg-gray-50 cursor-default" />
            </div>
          )}
        </div>
      </div>

      {/* LLM Provider */}
      <div className="card">
        <div className="flex items-center gap-2 mb-5">
          <Cpu size={18} className="text-brand-500" />
          <h2 className="font-semibold text-gray-900">LLM Provider</h2>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          The active LLM provider is controlled via the <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">LLM_PROVIDER</code> environment variable on the server.
          Restart the server after changing it.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {LLM_OPTIONS.map((opt) => {
            const active = status?.llm_provider === opt.value
            return (
              <div
                key={opt.value}
                className={`border rounded-lg px-4 py-3 ${active ? 'border-brand-400 bg-brand-50' : 'border-gray-200'}`}
              >
                <div className="flex items-center justify-between">
                  <p className={`font-medium text-sm ${active ? 'text-brand-700' : 'text-gray-700'}`}>{opt.label}</p>
                  {active && <span className="badge-success text-xs">Active</span>}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{opt.desc}</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* System Status */}
      <div className="card">
        <div className="flex items-center gap-2 mb-5">
          <Server size={18} className="text-brand-500" />
          <h2 className="font-semibold text-gray-900">System Status</h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <StatusItem label="Server" ok={!!status} />
          <StatusItem label="FHIR" ok={connected} />
          <StatusItem label="LLM" ok={!!status?.llm_provider} />
          <StatusItem label="MCP Server" ok={status?.mcp_server === true} />
        </div>
      </div>

      {/* Environment guide */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-3">Environment Variables Reference</h2>
        <p className="text-sm text-gray-500 mb-4">
          Set these in a <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">.env</code> file at the project root. See <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">.env.example</code> for a template.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="py-2 pr-4 font-medium text-gray-700">Variable</th>
                <th className="py-2 font-medium text-gray-700">Description</th>
              </tr>
            </thead>
            <tbody className="text-gray-600">
              <EnvRow name="EMR_PROVIDER" desc="ecw | athena" />
              <EnvRow name="EMR_REDIRECT_URI" desc="OAuth2 callback URL (default: https://localhost:8443/api/auth/callback)" />
              <EnvRow name="ECW_FHIR_BASE_URL" desc="eCW FHIR R4 base URL (when using ecw)" />
              <EnvRow name="ECW_CLIENT_ID" desc="eCW SMART on FHIR client ID" />
              <EnvRow name="ATHENA_FHIR_BASE_URL" desc="Athena FHIR R4 base URL (when using athena)" />
              <EnvRow name="ATHENA_CLIENT_ID" desc="Athena OAuth2 client ID" />
              <EnvRow name="ATHENA_CLIENT_SECRET" desc="Athena OAuth2 client secret" />
              <EnvRow name="LLM_PROVIDER" desc="grok | openai | anthropic | ollama" />
              <EnvRow name="XAI_API_KEY" desc="X.AI API key (when using Grok)" />
              <EnvRow name="OPENAI_API_KEY" desc="OpenAI API key (when using OpenAI)" />
              <EnvRow name="ANTHROPIC_API_KEY" desc="Anthropic API key (when using Anthropic)" />
              <EnvRow name="OLLAMA_BASE_URL" desc="Ollama server URL (default: http://localhost:11434)" />
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StatusItem({ label, ok }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2.5 h-2.5 rounded-full ${ok ? 'bg-green-400' : 'bg-gray-300'}`} />
      <span className={ok ? 'text-gray-900' : 'text-gray-400'}>{label}</span>
    </div>
  )
}

function EnvRow({ name, desc }) {
  return (
    <tr className="border-b last:border-0">
      <td className="py-2 pr-4 font-mono text-xs text-brand-600">{name}</td>
      <td className="py-2">{desc}</td>
    </tr>
  )
}
