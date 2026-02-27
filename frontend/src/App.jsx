import { useMemo, useState } from 'react'

const API_URL = 'http://localhost:8002/analyze'

const badgeStyle = (flagged) => ({
  padding: '4px 10px',
  borderRadius: '999px',
  fontSize: '12px',
  fontWeight: 600,
  background: flagged ? '#fee2e2' : '#dcfce7',
  color: flagged ? '#991b1b' : '#166534',
})

function SectionTitle({ children }) {
  return <h2 style={{ marginTop: 28, marginBottom: 10 }}>{children}</h2>
}

function App() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runAnalysis = async () => {
    setLoading(true)
    setError(null)
    setReport(null)

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode: 'tier1', use_web_retrieval: true }),
      })

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`)
      }

      const data = await response.json()
      setReport(data.report)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const hasReport = useMemo(() => report && typeof report === 'object', [report])

  return (
    <div style={{ maxWidth: '1100px', margin: '32px auto', padding: '0 20px', fontFamily: 'ui-sans-serif, system-ui, sans-serif' }}>
      <h1 style={{ marginBottom: 6 }}>BS Detector</h1>
      <p style={{ marginTop: 0, color: '#334155' }}>Tier 1 multi-agent legal verification pipeline</p>

      <button
        onClick={runAnalysis}
        disabled={loading}
        style={{
          marginTop: 6,
          padding: '10px 20px',
          border: 'none',
          borderRadius: '8px',
          background: loading ? '#94a3b8' : '#0f172a',
          color: '#fff',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontWeight: 600,
        }}
      >
        {loading ? 'Analyzing...' : 'Run Analysis'}
      </button>

      {error && (
        <div style={{ marginTop: '20px', color: '#991b1b', background: '#fee2e2', padding: 12, borderRadius: 8 }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {hasReport && (
        <>
          <SectionTitle>Run Summary</SectionTitle>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
            <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#334155' }}>Status</div>
              <div style={{ fontWeight: 700 }}>{report.status}</div>
            </div>
            <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#334155' }}>Citations</div>
              <div style={{ fontWeight: 700 }}>{report.summary?.citations_extracted ?? 0}</div>
            </div>
            <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#334155' }}>Quotes</div>
              <div style={{ fontWeight: 700 }}>{report.summary?.quotes_checked ?? 0}</div>
            </div>
            <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: '#334155' }}>Flags</div>
              <div style={{ fontWeight: 700 }}>{report.summary?.flags_total ?? 0}</div>
            </div>
          </div>

          <SectionTitle>Citation Findings</SectionTitle>
          <div style={{ display: 'grid', gap: 12 }}>
            {(report.citation_findings ?? []).map((item) => (
              <div key={item.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ fontWeight: 700 }}>{item.raw_citation}</div>
                  <span style={badgeStyle(item.flagged)}>{item.flagged ? 'Flagged' : 'Clear'}</span>
                </div>
                <div style={{ marginTop: 8, color: '#334155' }}><strong>Label:</strong> {item.support_label}</div>
                <div style={{ marginTop: 4, color: '#334155' }}><strong>Confidence:</strong> {item.confidence}</div>
                <div style={{ marginTop: 4, color: '#334155' }}><strong>Reason:</strong> {item.reason}</div>
                {item.source_url && (
                  <div style={{ marginTop: 4 }}>
                    <a href={item.source_url} target="_blank" rel="noreferrer">Source</a>
                  </div>
                )}
              </div>
            ))}
          </div>

          <SectionTitle>Quote Findings</SectionTitle>
          <div style={{ display: 'grid', gap: 12 }}>
            {(report.quote_findings ?? []).map((item) => (
              <div key={item.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                  <div style={{ fontWeight: 700 }}>"{item.quote_text}"</div>
                  <span style={badgeStyle(item.flagged)}>{item.flagged ? 'Flagged' : 'Clear'}</span>
                </div>
                <div style={{ marginTop: 8, color: '#334155' }}><strong>Label:</strong> {item.quote_label}</div>
                <div style={{ marginTop: 4, color: '#334155' }}><strong>Confidence:</strong> {item.confidence}</div>
                <div style={{ marginTop: 4, color: '#334155' }}><strong>Reason:</strong> {item.reason}</div>
              </div>
            ))}
          </div>

          {(report.errors ?? []).length > 0 && (
            <>
              <SectionTitle>Pipeline Errors</SectionTitle>
              <div style={{ background: '#fff7ed', border: '1px solid #fdba74', borderRadius: 10, padding: 14 }}>
                {(report.errors ?? []).map((err, idx) => (
                  <div key={`${err.step}_${idx}`} style={{ marginBottom: 10 }}>
                    <strong>{err.step}:</strong> {err.message}
                    {err.detail && <div style={{ color: '#7c2d12' }}>{err.detail}</div>}
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {!hasReport && !loading && !error && (
        <p style={{ marginTop: '20px', color: '#64748b' }}>
          Click "Run Analysis" to produce a structured verification report.
        </p>
      )}
    </div>
  )
}

export default App
