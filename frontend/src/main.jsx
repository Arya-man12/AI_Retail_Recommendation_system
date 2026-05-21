import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AreaChart,
  Bot,
  BrainCircuit,
  CircleDollarSign,
  GitBranch,
  LogIn,
  MessageSquareText,
  PackageCheck,
  Radar,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  WandSparkles
} from 'lucide-react';
import './styles.css';
import { askCopilot, clearAuthSession, fetchCustomer360, fetchDashboardData, fetchIntelligenceSnapshot, getAuthToken, loginUser } from './services/api.js';
import { fallbackDashboard } from './services/fallbackData.js';

const tabs = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'recommendations', label: 'Recommendations', icon: PackageCheck },
  { id: 'forecasting', label: 'Forecasting', icon: TrendingUp },
  { id: 'explainability', label: 'Explainability', icon: BrainCircuit },
  { id: 'customer360', label: 'Customer 360', icon: GitBranch },
  { id: 'copilot', label: 'Copilot', icon: Bot }
];

function App() {
  const [isAuthed, setIsAuthed] = useState(Boolean(getAuthToken('dashboard')));
  const [activeTab, setActiveTab] = useState('overview');
  const [data, setData] = useState(fallbackDashboard);
  const [status, setStatus] = useState('Loading live API');
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(true);
  const [isLoadingIntelligence, setIsLoadingIntelligence] = useState(true);
  const [isLoadingCustomer360, setIsLoadingCustomer360] = useState(true);
  const [hasDashboardError, setHasDashboardError] = useState(false);
  const [hasIntelligenceError, setHasIntelligenceError] = useState(false);
  const [hasCustomer360Error, setHasCustomer360Error] = useState(false);

  const [query, setQuery] = useState('Explain why Northeast revenue is rising this week.');
  const [answer, setAnswer] = useState(fallbackDashboard.copilot.sampleAnswer);
  const [intelligence, setIntelligence] = useState(null);
  const [customer360, setCustomer360] = useState(null);

  useEffect(() => {
    if (!isAuthed) return undefined;
    let mounted = true;

    setIsLoadingDashboard(true);
    setIsLoadingIntelligence(true);
    setIsLoadingCustomer360(true);
    setHasDashboardError(false);
    setHasIntelligenceError(false);
    setHasCustomer360Error(false);
    setStatus('Loading live API');

    fetchDashboardData()
      .then((payload) => {
        if (!mounted) return;
        setData(payload);
        setStatus('Connected to FastAPI');
      })
      .catch(() => {
        if (!mounted) return;
        setHasDashboardError(true);
        setStatus('Demo data fallback');
      })
      .finally(() => {
        if (!mounted) return;
        setIsLoadingDashboard(false);
      });

    fetchIntelligenceSnapshot()
      .then((payload) => {
        if (mounted) setIntelligence(payload);
      })
      .catch(() => {
        if (mounted) {
          setHasIntelligenceError(true);
          setIntelligence(null);
        }
      })
      .finally(() => {
        if (!mounted) return;
        setIsLoadingIntelligence(false);
      });

    fetchCustomer360()
      .then((payload) => {
        if (mounted) setCustomer360(payload);
      })
      .catch(() => {
        if (mounted) {
          setHasCustomer360Error(true);
          setCustomer360(null);
        }
      })
      .finally(() => {
        if (!mounted) return;
        setIsLoadingCustomer360(false);
      });

    return () => {
      mounted = false;
    };
  }, [isAuthed]);


  async function handleLogin(credentials) {
    await loginUser({ ...credentials, site: 'dashboard' });
    setIsAuthed(true);
  }

  function handleLogout() {
    clearAuthSession('dashboard');
    setIsAuthed(false);
  }

  const selectedCustomer = customer360?.profile || intelligence?.customer360?.profile || data.customers[0];
  const explanationData = intelligence?.explainability || data.explainability;
  const customerGraph = customer360?.graph || intelligence?.customer360?.graph || data.graph;
  const customerGraphSource = customer360?.source || intelligence?.customer360?.data_source || 'demo_customer_360_graph';

  async function handleCopilotSubmit(event) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setAnswer('Thinking through governed tools...');
    try {
      const response = await askCopilot(trimmed);
      setAnswer(response.answer);
    } catch {
      setAnswer(fallbackDashboard.copilot.sampleAnswer);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">
            <Radar size={24} aria-hidden="true" />
          </div>
          <div>
            <p className="eyebrow">Customer ops</p>
            <h1>Customer Intelligence</h1>
          </div>
        </div>

        <nav className="nav-list" aria-label="Dashboard views">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={activeTab === tab.id ? 'nav-item active' : 'nav-item'}
                onClick={() => setActiveTab(tab.id)}
                type="button"
                title={tab.label}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="guardrail-panel">
          <ShieldCheck size={18} aria-hidden="true" />
          <div>
            <strong>Secure workspace</strong>
            <span>Role-based access</span>
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Live workspace</p>
            <h2>{tabs.find((tab) => tab.id === activeTab)?.label}</h2>
          </div>
          <div className="topbar-actions">
            <div className="search-box">
              <Search size={16} aria-hidden="true" />
              <input aria-label="Search customers or products" placeholder="Search customers or products" />
            </div>
            <span className="connection-pill" aria-live="polite">
              {status}
            </span>

            {isAuthed && (
              <button className="icon-action" type="button" onClick={handleLogout} title="Sign out">
                <LogIn size={17} aria-hidden="true" />
              </button>
            )}
          </div>
        </header>

        {!isAuthed && <DashboardLogin onLogin={handleLogin} />}

        {isAuthed && activeTab === 'overview' && (
          <Overview data={data} isLoading={isLoadingDashboard} hasError={hasDashboardError} />
        )}
        {isAuthed && activeTab === 'recommendations' && <Recommendations recommendations={data.recommendations} />}
        {isAuthed && activeTab === 'forecasting' && <Forecasting forecast={data.forecast} />}
        {isAuthed && activeTab === 'explainability' && (
          <Explainability
            explanation={explanationData}
            isLoading={isLoadingIntelligence}
            hasError={hasIntelligenceError}
          />
        )}
        {isAuthed && activeTab === 'customer360' && (
          <Customer360
            customer={selectedCustomer}
            graph={customerGraph}
            source={customerGraphSource}
            isLoading={isLoadingCustomer360}
            hasError={hasCustomer360Error}
          />
        )}
        {isAuthed && activeTab === 'copilot' && (
          <Copilot query={query} setQuery={setQuery} answer={answer} onSubmit={handleCopilotSubmit} />
        )}

      </section>
    </main>
  );
}

function DashboardLogin({ onLogin }) {
  const [email, setEmail] = useState('analyst@example.com');
  const [password, setPassword] = useState('Analyst123!');
  const [status, setStatus] = useState('Use the seeded analyst account');

  async function submit(event) {
    event.preventDefault();
    setStatus('Signing in...');
    try {
      await onLogin({ email, password });
      setStatus('Signed in');
    } catch {
      setStatus('Sign in failed');
    }
  }

  return (
    <section className="auth-panel">
      <div>
        <p className="eyebrow">MongoDB RBAC</p>
        <h3>Internal dashboard access</h3>
        <p>Sign in with a dashboard role before loading analytics, ML, customer graph, and copilot insights.</p>
      </div>
      <form className="auth-form" onSubmit={submit}>
        <input aria-label="Email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <input aria-label="Password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        <button type="submit">
          <LogIn size={18} aria-hidden="true" />
          Sign in
        </button>
        <span>{status}</span>
      </form>
    </section>
  );
}

function Overview({ data, isLoading, hasError }) {
  return (
    <div className="view-stack">
      {(isLoading || hasError) && (
        <div className="status-banner" role="status" aria-live="polite">
          <strong>{hasError ? 'Demo data' : 'Loading'}</strong>
          <span>
            {hasError ? 'Internal API unavailable — showing demo analytics.' : 'Fetching live dashboard metrics...'}
          </span>
        </div>
      )}

      <section className="metric-grid" aria-busy={isLoading}>
        {data.metrics.map((metric) => (
          <article className={`metric-card ${isLoading ? 'is-skeleton' : ''}`} key={metric.label}>
            <span className="metric-icon">{metric.icon === 'revenue' ? <CircleDollarSign size={18} /> : <Users size={18} />}</span>
            <p>{metric.label}</p>
            <strong>{metric.value}</strong>
            <small className={metric.delta.startsWith('+') ? 'positive' : 'warning'}>{metric.delta}</small>
          </article>
        ))}
      </section>

      <section className="analytics-layout">
        <div className={`panel wide ${isLoading ? 'is-skeleton' : ''}`}>
          <PanelTitle icon={AreaChart} title="Streaming Sales Analytics" />
          <div className="bar-chart" aria-label="Hourly revenue chart">
            {data.revenueSeries.map((item) => (
              <div className="bar-slot" key={item.hour}>
                <span style={{ height: `${item.value}%` }} />
                <small>{item.hour}</small>
              </div>
            ))}
          </div>
        </div>
        <div className={`panel ${isLoading ? 'is-skeleton' : ''}`}>
          <PanelTitle icon={Sparkles} title="Live Signals" />
          <div className="signal-list">
            {data.signals.map((signal) => (
              <div className="signal-row" key={signal.title}>
                <span className={`signal-dot ${signal.intent}`} />
                <div>
                  <strong>{signal.title}</strong>
                  <p>{signal.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}


function Recommendations({ recommendations }) {
  return (
    <section className="recommendation-grid">
      {recommendations.map((item) => (
        <article className="product-card" key={item.product}>
          <div className="product-art" style={{ background: item.gradient }}>
            <PackageCheck size={30} aria-hidden="true" />
          </div>
          <div className="product-body">
            <p className="eyebrow">{item.segment}</p>
            <h3>{item.product}</h3>
            <p>{item.reason}</p>
            <div className="score-row">
              <span>Affinity</span>
              <strong>{item.score}%</strong>
            </div>
            <div className="progress-track">
              <span style={{ width: `${item.score}%` }} />
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}

function Forecasting({ forecast }) {
  const max = Math.max(...forecast.map((point) => point.predicted));
  return (
    <section className="panel full-height">
      <PanelTitle icon={TrendingUp} title="Demand Forecast" />
      <div className="line-chart">
        {forecast.map((point, index) => (
          <div className="line-point" key={point.day}>
            <span className="forecast-stem" style={{ height: `${(point.predicted / max) * 78}%` }} />
            <span className="actual-stem" style={{ height: `${(point.actual / max) * 78}%` }} />
            <small>{point.day}</small>
            <strong>{point.predicted}k</strong>
            {index === forecast.length - 1 && <em>next</em>}
          </div>
        ))}
      </div>
    </section>
  );
}

function Explainability({ explanation, isLoading, hasError }) {
  return (
    <section className="explain-layout">
      {(isLoading || hasError) && (
        <div className="status-banner" role="status" aria-live="polite">
          <strong>{hasError ? 'Demo explainability' : 'Loading'}</strong>
          <span>
            {hasError ? 'Internal intelligence API unavailable — showing demo explanations.' : 'Fetching feature attribution...'}
          </span>
        </div>
      )}

      <div className={`panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={BrainCircuit} title="Feature Attribution" />
        <div className="attribution-list" aria-busy={isLoading}>
          {explanation.features.map((feature) => (
            <div className="attribution-row" key={feature.name}>
              <span>{feature.name}</span>
              <div className="attribution-track">
                <span
                  className={feature.impact > 0 ? 'positive-bg' : 'negative-bg'}
                  style={{ width: `${Math.abs(feature.impact) * 100}%` }}
                />
              </div>
              <strong>
                {feature.impact > 0 ? '+' : ''}
                {feature.impact.toFixed(2)}
              </strong>
            </div>
          ))}
        </div>
      </div>
      <div className={`panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={MessageSquareText} title="Natural Language Explanation" />
        <p className="narrative">{explanation.explanation}</p>
      </div>
    </section>
  );
}


function Customer360({ customer, graph, source, isLoading, hasError }) {
  const relationshipEdges = graph.edges.filter((edge) => edge.source_position && edge.target_position);
  return (
    <section className="customer-layout">
      {(isLoading || hasError) && (
        <div className="status-banner" role="status" aria-live="polite">
          <strong>{hasError ? 'Demo graph' : 'Loading'}</strong>
          <span>
            {hasError ? 'Internal customer graph API unavailable — showing demo graph.' : 'Fetching customer graph & profile...'}
          </span>
        </div>
      )}

      <div className={`panel profile-panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={Users} title="Customer Profile" />
        <div className="avatar">{customer.initials}</div>
        <h3>{customer.name}</h3>
        <p>{customer.segment}</p>
        <dl>
          <div>
            <dt>LTV</dt>
            <dd>{customer.ltv}</dd>
          </div>
          <div>
            <dt>Churn Risk</dt>
            <dd>{customer.churnRisk}</dd>
          </div>
          <div>
            <dt>Last Event</dt>
            <dd>{customer.lastEvent}</dd>
          </div>
        </dl>
        <span className={source === 'neo4j' ? 'source-pill live' : 'source-pill'}>
          {source === 'neo4j' ? 'Neo4j connected' : 'Graph fallback'}
        </span>
      </div>
      <div className={`panel graph-panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={GitBranch} title="Customer 360 Graph" />
        <div className="graph-canvas" aria-label="Customer graph" aria-busy={isLoading}>
          <svg className="graph-lines" aria-hidden="true" viewBox="0 0 100 100" preserveAspectRatio="none">
            {relationshipEdges.map((edge) => (
              <line
                key={edge.id}
                x1={edge.source_position.x}
                y1={edge.source_position.y}
                x2={edge.target_position.x}
                y2={edge.target_position.y}
              />
            ))}
          </svg>
          {graph.nodes.map((node) => (
            <span
              key={node.id}
              className={`graph-node ${node.kind}`}
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
            >
              {node.label}
            </span>
          ))}
        </div>
        <div className="relationship-list">
          {graph.edges.slice(0, 6).map((edge) => (
            <span key={edge.id}>{edge.type || 'RELATED'}</span>
          ))}
        </div>
      </div>
    </section>
  );
}


function Copilot({ query, setQuery, answer, onSubmit }) {
  return (
    <section className="copilot-layout single">
      <div className="panel copilot-panel">
        <PanelTitle icon={WandSparkles} title="Insight Copilot" />
        <form onSubmit={onSubmit} className="copilot-form">
          <textarea value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Ask copilot" />
          <button type="submit">
            <Bot size={18} aria-hidden="true" />
            Ask
          </button>
        </form>
        <div className="answer-box">
          <p>{answer}</p>
        </div>
      </div>
    </section>
  );
}

function PanelTitle({ icon: Icon, title }) {
  return (
    <div className="panel-title">
      <Icon size={18} aria-hidden="true" />
      <h3>{title}</h3>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
