import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AreaChart,
  Bot,
  BrainCircuit,
  ChevronRight,
  CircleDollarSign,
  GitBranch,
  Map,
  MessageSquareText,
  PackageCheck,
  Radar,
  Route,
  Search,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  WandSparkles
} from 'lucide-react';
import './styles.css';
import { fetchDashboardData, askCopilot } from './services/api.js';
import { fallbackDashboard } from './services/fallbackData.js';

const tabs = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'recommendations', label: 'Recommendations', icon: PackageCheck },
  { id: 'forecasting', label: 'Forecasting', icon: TrendingUp },
  { id: 'explainability', label: 'Explainability', icon: BrainCircuit },
  { id: 'customer360', label: 'Customer 360', icon: GitBranch },
  { id: 'geo', label: 'Geo Heatmap', icon: Map },
  { id: 'copilot', label: 'Copilot', icon: Bot }
];

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [data, setData] = useState(fallbackDashboard);
  const [status, setStatus] = useState('Loading live API');
  const [query, setQuery] = useState('Explain why Northeast revenue is rising this week.');
  const [answer, setAnswer] = useState(fallbackDashboard.copilot.sampleAnswer);

  useEffect(() => {
    let mounted = true;
    fetchDashboardData()
      .then((payload) => {
        if (!mounted) return;
        setData(payload);
        setStatus('Connected to FastAPI');
      })
      .catch(() => {
        if (!mounted) return;
        setStatus('Demo data fallback');
      });
    return () => {
      mounted = false;
    };
  }, []);

  const selectedCustomer = data.customers[0];

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
            <p className="eyebrow">Realtime AI</p>
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
            <strong>RBAC enabled</strong>
            <span>Marketing analyst scope</span>
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Layer 11 to Layer 10</p>
            <h2>{tabs.find((tab) => tab.id === activeTab)?.label}</h2>
          </div>
          <div className="topbar-actions">
            <div className="search-box">
              <Search size={16} aria-hidden="true" />
              <input aria-label="Search customers or products" placeholder="Search customers, products, regions" />
            </div>
            <span className="connection-pill">{status}</span>
          </div>
        </header>

        {activeTab === 'overview' && <Overview data={data} />}
        {activeTab === 'recommendations' && <Recommendations recommendations={data.recommendations} />}
        {activeTab === 'forecasting' && <Forecasting forecast={data.forecast} />}
        {activeTab === 'explainability' && <Explainability shap={data.shap} />}
        {activeTab === 'customer360' && <Customer360 customer={selectedCustomer} graph={data.graph} />}
        {activeTab === 'geo' && <GeoHeatmap regions={data.geo} />}
        {activeTab === 'copilot' && (
          <Copilot query={query} setQuery={setQuery} answer={answer} onSubmit={handleCopilotSubmit} tools={data.copilot.tools} />
        )}
      </section>
    </main>
  );
}

function Overview({ data }) {
  return (
    <div className="view-stack">
      <section className="metric-grid">
        {data.metrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <span className="metric-icon">{metric.icon === 'revenue' ? <CircleDollarSign size={18} /> : <Users size={18} />}</span>
            <p>{metric.label}</p>
            <strong>{metric.value}</strong>
            <small className={metric.delta.startsWith('+') ? 'positive' : 'warning'}>{metric.delta}</small>
          </article>
        ))}
      </section>

      <section className="analytics-layout">
        <div className="panel wide">
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
        <div className="panel">
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

function Explainability({ shap }) {
  return (
    <section className="explain-layout">
      <div className="panel">
        <PanelTitle icon={BrainCircuit} title="SHAP Feature Attribution" />
        <div className="shap-list">
          {shap.features.map((feature) => (
            <div className="shap-row" key={feature.name}>
              <span>{feature.name}</span>
              <div className="shap-track">
                <span className={feature.impact > 0 ? 'positive-bg' : 'negative-bg'} style={{ width: `${Math.abs(feature.impact) * 100}%` }} />
              </div>
              <strong>{feature.impact > 0 ? '+' : ''}{feature.impact.toFixed(2)}</strong>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <PanelTitle icon={MessageSquareText} title="Natural Language Explanation" />
        <p className="narrative">{shap.explanation}</p>
      </div>
    </section>
  );
}

function Customer360({ customer, graph }) {
  return (
    <section className="customer-layout">
      <div className="panel profile-panel">
        <PanelTitle icon={Users} title="Customer Profile" />
        <div className="avatar">{customer.initials}</div>
        <h3>{customer.name}</h3>
        <p>{customer.segment}</p>
        <dl>
          <div><dt>LTV</dt><dd>{customer.ltv}</dd></div>
          <div><dt>Churn Risk</dt><dd>{customer.churnRisk}</dd></div>
          <div><dt>Last Event</dt><dd>{customer.lastEvent}</dd></div>
        </dl>
      </div>
      <div className="panel graph-panel">
        <PanelTitle icon={GitBranch} title="Customer 360 Graph" />
        <div className="graph-canvas" aria-label="Customer graph">
          {graph.nodes.map((node) => (
            <span key={node.id} className={`graph-node ${node.kind}`} style={{ left: `${node.x}%`, top: `${node.y}%` }}>
              {node.label}
            </span>
          ))}
          {graph.edges.map((edge) => (
            <span key={edge.id} className={`graph-edge edge-${edge.id}`} />
          ))}
        </div>
      </div>
    </section>
  );
}

function GeoHeatmap({ regions }) {
  return (
    <section className="geo-layout">
      <div className="map-board">
        {regions.map((region) => (
          <button
            type="button"
            key={region.name}
            className="region-hotspot"
            style={{ left: `${region.x}%`, top: `${region.y}%`, '--heat': region.heat }}
            title={`${region.name}: ${region.revenue}`}
          >
            <span>{region.name}</span>
          </button>
        ))}
      </div>
      <div className="panel">
        <PanelTitle icon={Route} title="Regional Performance" />
        <div className="region-list">
          {regions.map((region) => (
            <div className="region-row" key={region.name}>
              <span>{region.name}</span>
              <strong>{region.revenue}</strong>
              <small>{region.trend}</small>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Copilot({ query, setQuery, answer, onSubmit, tools }) {
  return (
    <section className="copilot-layout">
      <div className="panel copilot-panel">
        <PanelTitle icon={WandSparkles} title="Controlled LLM Orchestration" />
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
      <div className="panel">
        <PanelTitle icon={ShieldCheck} title="Tools and Observability" />
        <div className="tool-list">
          {tools.map((tool) => (
            <div className="tool-row" key={tool}>
              <ChevronRight size={16} aria-hidden="true" />
              <span>{tool}</span>
            </div>
          ))}
          <div className="trace-row">
            <strong>LangSmith</strong>
            <span>Tracing enabled by backend environment</span>
          </div>
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

