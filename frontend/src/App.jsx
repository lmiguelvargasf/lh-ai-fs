import { useMemo, useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8002/analyze'
const LOADING_STEPS = [
  'Extracting citations and direct quotes',
  'Checking cross-document factual consistency',
  'Calibrating confidence and drafting memo',
]

function SectionTitle({ title, count }) {
  return (
    <div className="section-header">
      <h2>{title}</h2>
      <span className="count-pill">{count}</span>
    </div>
  )
}

function StatusPill({ flagged }) {
  return <span className={`status-pill ${flagged ? 'is-flagged' : 'is-clear'}`}>{flagged ? 'Flagged' : 'Clear'}</span>
}

function KeyValue({ label, value }) {
  return (
    <div className="kv-item">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function formatConfidence(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'n/a'
  }
  return value.toFixed(2)
}

function LoadingPanel() {
  return (
    <section className="panel loading-panel section-appear" aria-live="polite" aria-busy="true">
      <div className="loading-head">
        <div>
          <h2>Analyzing Case File</h2>
          <p>Running multi-agent verification across authorities, quotes, and evidence records.</p>
        </div>
        <div className="signal-orb" aria-hidden>
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className="loading-track" aria-hidden>
        <div className="loading-beam" />
      </div>
      <ul className="loading-steps">
        {LOADING_STEPS.map((step, index) => (
          <li key={step} style={{ '--step-delay': `${index * 220}ms` }}>
            <span className="step-dot" aria-hidden />
            <span>{step}</span>
          </li>
        ))}
      </ul>
    </section>
  )
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
        body: JSON.stringify({ use_web_retrieval: true }),
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

  const hasReport = useMemo(() => Boolean(report && typeof report === 'object'), [report])

  const summaryItems = useMemo(() => {
    if (!report) {
      return []
    }
    const summary = report.summary ?? {}
    return [
      { label: 'Status', value: report.status ?? 'n/a' },
      { label: 'Citations', value: summary.citations_extracted ?? 0 },
      { label: 'Quotes', value: summary.quotes_checked ?? 0 },
      { label: 'Flags', value: summary.flags_total ?? 0 },
      { label: 'Fact Claims', value: summary.fact_claims_checked ?? 0 },
      { label: 'Cross-Doc Flags', value: summary.cross_doc_flags_total ?? 0 },
    ]
  }, [report])

  return (
    <div className="page-shell">
      <div className="page-bg" aria-hidden />
      <main className="layout">
        <header className="hero section-appear">
          <div className="hero-kicker">Multi-Agent Verification</div>
          <h1>BS Detector</h1>
          <p className="hero-copy">
            Structured legal-brief verification with calibrated confidence, cross-document checks, and judge-ready synthesis.
          </p>
          <div className="hero-actions">
            <button className="run-button" onClick={runAnalysis} disabled={loading}>
              {loading ? 'Analyzing Record...' : 'Run Analysis'}
            </button>
          </div>
        </header>

        {error && (
          <section className="panel error-panel section-appear">
            <h3>Pipeline Error</h3>
            <p>{error}</p>
          </section>
        )}

        {loading && <LoadingPanel />}

        {hasReport && (
          <>
            <section className="panel memo-panel section-appear">
              <div className="memo-head">
                <h2>Judicial Memo</h2>
                <span className="mode-chip">{report.judicial_memo?.generation_mode ?? 'n/a'}</span>
              </div>
              <p className="memo-text">{report.judicial_memo?.text || 'No memo available.'}</p>
              {report.judicial_memo?.uncertainty_note && (
                <p className="memo-note">
                  <strong>Uncertainty:</strong> {report.judicial_memo.uncertainty_note}
                </p>
              )}
              {(report.judicial_memo?.supporting_finding_ids ?? []).length > 0 && (
                <p className="memo-support">
                  <strong>Supporting Findings:</strong> {report.judicial_memo.supporting_finding_ids.join(', ')}
                </p>
              )}
            </section>

            <section className="metrics-grid section-appear">
              {summaryItems.map((item) => (
                <article key={item.label} className="metric-card">
                  <p>{item.label}</p>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </section>

            <section className="section-appear">
              <SectionTitle title="Citation Findings" count={(report.citation_findings ?? []).length} />
              <div className="findings-grid">
                {(report.citation_findings ?? []).map((item, index) => (
                  <article
                    key={item.id}
                    className={`finding-card ${item.flagged ? 'flagged' : 'clean'}`}
                    style={{ '--stagger': index }}
                  >
                    <div className="finding-head">
                      <h3>{item.raw_citation}</h3>
                      <StatusPill flagged={item.flagged} />
                    </div>
                    <p className="finding-reason">{item.reason}</p>
                    <dl className="kv-grid">
                      <KeyValue label="Label" value={item.support_label ?? 'n/a'} />
                      <KeyValue label="Confidence" value={formatConfidence(item.confidence)} />
                      <KeyValue label="Raw Confidence" value={formatConfidence(item.raw_confidence)} />
                      <KeyValue label="Confidence Reason" value={item.confidence_reason ?? 'n/a'} />
                    </dl>
                    {item.source_url && (
                      <a className="inline-link" href={item.source_url} target="_blank" rel="noreferrer">
                        View Source
                      </a>
                    )}
                  </article>
                ))}
              </div>
            </section>

            <section className="section-appear">
              <SectionTitle title="Quote Findings" count={(report.quote_findings ?? []).length} />
              <div className="findings-grid">
                {(report.quote_findings ?? []).map((item, index) => (
                  <article
                    key={item.id}
                    className={`finding-card ${item.flagged ? 'flagged' : 'clean'}`}
                    style={{ '--stagger': index }}
                  >
                    <div className="finding-head">
                      <h3>&quot;{item.quote_text}&quot;</h3>
                      <StatusPill flagged={item.flagged} />
                    </div>
                    <p className="finding-reason">{item.reason}</p>
                    <dl className="kv-grid">
                      <KeyValue label="Label" value={item.quote_label ?? 'n/a'} />
                      <KeyValue label="Confidence" value={formatConfidence(item.confidence)} />
                      <KeyValue label="Raw Confidence" value={formatConfidence(item.raw_confidence)} />
                      <KeyValue label="Confidence Reason" value={item.confidence_reason ?? 'n/a'} />
                    </dl>
                  </article>
                ))}
              </div>
            </section>

            <section className="section-appear">
              <SectionTitle title="Cross-Document Findings" count={(report.cross_document_findings ?? []).length} />
              <div className="findings-grid">
                {(report.cross_document_findings ?? []).map((item, index) => (
                  <article
                    key={item.id}
                    className={`finding-card ${item.flagged ? 'flagged' : 'clean'}`}
                    style={{ '--stagger': index }}
                  >
                    <div className="finding-head">
                      <h3>{item.claim_text}</h3>
                      <StatusPill flagged={item.flagged} />
                    </div>
                    <p className="finding-reason">{item.reason}</p>
                    <dl className="kv-grid">
                      <KeyValue label="Label" value={item.label ?? 'n/a'} />
                      <KeyValue label="Confidence" value={formatConfidence(item.confidence)} />
                      <KeyValue label="Raw Confidence" value={formatConfidence(item.raw_confidence)} />
                      <KeyValue label="Confidence Reason" value={item.confidence_reason ?? 'n/a'} />
                    </dl>
                  </article>
                ))}
              </div>
            </section>

            {(report.errors ?? []).length > 0 && (
              <section className="panel warning-panel section-appear">
                <SectionTitle title="Pipeline Errors" count={(report.errors ?? []).length} />
                <div className="error-list">
                  {(report.errors ?? []).map((item) => (
                    <article key={`${item.step}_${item.message}_${item.detail ?? ''}`}>
                      <h4>{item.step}</h4>
                      <p>{item.message}</p>
                      {item.detail && <small>{item.detail}</small>}
                    </article>
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        {!hasReport && !loading && !error && (
          <section className="panel empty-panel section-appear">
            <p>Run analysis to generate a structured verification report.</p>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
