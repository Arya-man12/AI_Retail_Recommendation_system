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
  UserPlus,
  Users,
  WandSparkles
} from 'lucide-react';
import './styles.css';
import {
  askCopilot,
  clearAuthSession,
  fetchCustomer360,
  fetchDashboardData,
  fetchFeatureAttribution,
  fetchRegisteredCustomers,
  fetchIntelligenceSnapshot,
  fetchProductRecommendations,
  forecastRevenue,
  getAuthToken,
  loginUser,
  registerUser
} from './services/api.js';

const tabs = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'recommendations', label: 'Recommendations', icon: PackageCheck },
  { id: 'forecasting', label: 'Forecasting', icon: TrendingUp },
  { id: 'retail-ai', label: 'Retail AI', icon: WandSparkles },
  { id: 'explainability', label: 'Explainability', icon: BrainCircuit },
  { id: 'customer360', label: 'Customer 360', icon: GitBranch },
  { id: 'copilot', label: 'Copilot', icon: Bot }
];

const dashboardAccess = [
  { role: 'Viewer', scope: 'Dashboard metrics and intelligence snapshots only.' },
  { role: 'Marketing analyst', scope: 'Viewer access plus ecommerce reads, ML reads, features, graph, streaming, and copilot.' },
  { role: 'Admin', scope: 'Full internal access, write tools for ecommerce, ML, features, graph, plus ops and user seeding.' }
];

const emptyDashboard = {
  metrics: [],
  revenueSeries: [],
  signals: [],
  explainability: null
};

function App() {
  const [isAuthed, setIsAuthed] = useState(Boolean(getAuthToken('dashboard')));
  const [activeTab, setActiveTab] = useState('overview');
  const [customerOptions, setCustomerOptions] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [data, setData] = useState(emptyDashboard);
  const [status, setStatus] = useState('Loading live API');
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(true);
  const [isLoadingIntelligence, setIsLoadingIntelligence] = useState(true);
  const [isLoadingCustomer360, setIsLoadingCustomer360] = useState(true);
  const [hasDashboardError, setHasDashboardError] = useState(false);
  const [hasIntelligenceError, setHasIntelligenceError] = useState(false);
  const [hasCustomer360Error, setHasCustomer360Error] = useState(false);
  const [hasRecommendationError, setHasRecommendationError] = useState(false);
  const [hasForecastError, setHasForecastError] = useState(false);
  const [hasExplanationError, setHasExplanationError] = useState(false);
  const [isLoadingML, setIsLoadingML] = useState(true);
  const [isLoadingExplanation, setIsLoadingExplanation] = useState(true);

  const [query, setQuery] = useState('Explain why this customer received these product recommendations.');
  const [answer, setAnswer] = useState('Ask a question to run the governed copilot.');
  const [intelligence, setIntelligence] = useState(null);
  const [customer360, setCustomer360] = useState(null);
  const [mlForecast, setMlForecast] = useState(null);
  const [mlRecommendations, setMlRecommendations] = useState(null);
  const [featureAttribution, setFeatureAttribution] = useState(null);

  const selectedCustomerOption = customerOptions.find((customer) => customer.id === selectedCustomerId) || null;

  useEffect(() => {
    if (!isAuthed) return undefined;
    let mounted = true;
    fetchRegisteredCustomers()
      .then((payload) => {
        if (!mounted) return;
        const customers = payload.customers || [];
        setCustomerOptions(customers);
        setSelectedCustomerId((current) => current || customers[0]?.id || '');
      })
      .catch(() => {
        if (!mounted) return;
        setCustomerOptions([]);
        setSelectedCustomerId('');
      });
    return () => {
      mounted = false;
    };
  }, [isAuthed]);

  useEffect(() => {
    if (!isAuthed) return undefined;
    let mounted = true;

    setIsLoadingDashboard(true);
    setIsLoadingIntelligence(true);
    setIsLoadingCustomer360(true);
    setIsLoadingML(true);
    setIsLoadingExplanation(true);
    setHasDashboardError(false);
    setHasIntelligenceError(false);
    setHasCustomer360Error(false);
    setHasRecommendationError(false);
    setHasForecastError(false);
    setHasExplanationError(false);
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
        setData(emptyDashboard);
        setStatus('Dashboard API error');
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

    if (selectedCustomerOption) {
      fetchCustomer360(selectedCustomerId)
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

      const revenueHistory = selectedCustomerOption.revenueHistory?.length >= 3
        ? selectedCustomerOption.revenueHistory
        : null;

      const forecastRequest = revenueHistory
        ? forecastRevenue(revenueHistory)
        : Promise.reject(new Error('This customer needs at least three orders before forecasting.'));

      Promise.allSettled([
        forecastRequest,
        fetchProductRecommendations({
          customerId: selectedCustomerOption.id,
          segment: selectedCustomerOption.segment,
          recentCategories: selectedCustomerOption.recentCategories
        })
      ])
        .then(([forecastResult, recommendationResult]) => {
          if (!mounted) return;
          if (forecastResult.status === 'fulfilled') {
            setMlForecast(toForecastSeries(revenueHistory, forecastResult.value));
            setHasForecastError(false);
          } else {
            setMlForecast(null);
            setHasForecastError(true);
          }

          if (recommendationResult.status === 'fulfilled') {
            setMlRecommendations(toRecommendationCards(recommendationResult.value, selectedCustomerOption));
            setHasRecommendationError(false);
          } else {
            setMlRecommendations(null);
            setHasRecommendationError(true);
          }
        })
        .finally(() => {
          if (!mounted) return;
          setIsLoadingML(false);
        });

      fetchFeatureAttribution({
        customerId: selectedCustomerOption.id,
        segment: selectedCustomerOption.segment,
        recentCategories: selectedCustomerOption.recentCategories
      })
        .then((payload) => {
          if (!mounted) return;
          setFeatureAttribution(payload);
          setHasExplanationError(false);
        })
        .catch(() => {
          if (!mounted) return;
          setFeatureAttribution(null);
          setHasExplanationError(true);
        })
        .finally(() => {
          if (!mounted) return;
          setIsLoadingExplanation(false);
        });
    } else {
      setCustomer360(null);
      setMlForecast(null);
      setMlRecommendations(null);
      setFeatureAttribution(null);
      setIsLoadingCustomer360(false);
      setIsLoadingML(false);
      setIsLoadingExplanation(false);
    }

    return () => {
      mounted = false;
    };
  }, [isAuthed, selectedCustomerId, selectedCustomerOption]);


  async function handleLogin(credentials) {
    await loginUser({ ...credentials, site: 'dashboard' });
    setIsAuthed(true);
  }

  async function handleRegister(credentials) {
    await registerUser({ ...credentials, site: 'dashboard' });
    setIsAuthed(true);
  }

  function handleLogout() {
    clearAuthSession('dashboard');
    setIsAuthed(false);
  }

  const selectedCustomer = customer360?.profile || null;
  const explanationData = featureAttribution;
  const customerGraph = customer360?.graph || { nodes: [], edges: [] };
  const customerGraphSource = customer360?.source || intelligence?.customer360?.data_source || 'demo_customer_360_graph';
  const recommendationCards = mlRecommendations || [];
  const forecastSeries = mlForecast?.series || [];

  async function handleCopilotSubmit(event) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setAnswer('Thinking through governed tools...');
    try {
      const response = await askCopilot(trimmed);
      setAnswer(response.answer);
    } catch (error) {
      setAnswer(error.message || 'Copilot API unavailable.');
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

        {!isAuthed && <DashboardLogin onLogin={handleLogin} onRegister={handleRegister} />}

        {isAuthed && activeTab === 'overview' && (
          <Overview data={data} isLoading={isLoadingDashboard} hasError={hasDashboardError} />
        )}
        {isAuthed && activeTab === 'recommendations' && (
          <Recommendations
            recommendations={recommendationCards}
            customerOptions={customerOptions}
            selectedCustomerId={selectedCustomerId}
            onCustomerChange={setSelectedCustomerId}
            isLoading={isLoadingML}
            hasError={hasRecommendationError}
          />
        )}
        {isAuthed && activeTab === 'forecasting' && (
          <Forecasting
            forecast={forecastSeries}
            model={mlForecast?.model}
            customerOptions={customerOptions}
            selectedCustomerId={selectedCustomerId}
            onCustomerChange={setSelectedCustomerId}
            isLoading={isLoadingML}
            hasError={hasForecastError}
          />
        )}
        {isAuthed && activeTab === 'retail-ai' && (
          <RetailAI intelligence={intelligence} isLoading={isLoadingIntelligence} hasError={hasIntelligenceError} />
        )}
        {isAuthed && activeTab === 'explainability' && (
          <Explainability
            explanation={explanationData}
            isLoading={isLoadingExplanation}
            hasError={hasExplanationError}
          />
        )}
        {isAuthed && activeTab === 'customer360' && (
          <Customer360
            customer={selectedCustomer}
            graph={customerGraph}
            source={customerGraphSource}
            customerOptions={customerOptions}
            selectedCustomerId={selectedCustomerId}
            onCustomerChange={setSelectedCustomerId}
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

function toForecastSeries(history, payload) {
  const labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const prediction = payload?.prediction ?? history[history.length - 1];
  return {
    model: payload?.model,
    series: [
      ...history.map((value, index) => ({
        day: labels[index] || `T-${history.length - index}`,
        actual: value,
        predicted: value
      })),
      {
        day: 'Next',
        actual: 0,
        predicted: prediction
      }
    ]
  };
}

function toRecommendationCards(payload, customer) {
  return (payload?.recommendations || []).map((item, index) => ({
    product: item.product,
    score: Math.round(item.score * 100),
    segment: customer.segment,
    reason: recommendationReason(item.product, customer.recentCategories, payload?.source),
    gradient: productGradient(item.product, index)
  }));
}

function recommendationReason(product, categories, source) {
  const categoryText = categories?.length ? categories.join(', ') : 'purchase';
  if (source === 'transparent_rules') {
    return `${product} was selected by transparent scoring over this customer's ${categoryText} profile.`;
  }
  return `${product} matches recent ${categoryText} behavior for this customer profile.`;
}

function productGradient(product, index) {
  const gradients = {
    'Smart Hydration Bundle': 'linear-gradient(135deg, #0f766e, #22c55e)',
    'Air Quality Monitor Pro': 'linear-gradient(135deg, #2563eb, #06b6d4)',
    'Compact Power Kit': 'linear-gradient(135deg, #b45309, #f59e0b)',
    'Sleep Recovery Sensor': 'linear-gradient(135deg, #7c3aed, #db2777)'
  };
  return gradients[product] || ['linear-gradient(135deg, #334155, #0f766e)', 'linear-gradient(135deg, #1d4ed8, #0891b2)', 'linear-gradient(135deg, #be123c, #c2410c)'][index % 3];
}

function DashboardLogin({ onLogin, onRegister }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('analyst@example.com');
  const [password, setPassword] = useState('Analyst123!');
  const [status, setStatus] = useState('Use the seeded analyst account');

  async function submit(event) {
    event.preventDefault();
    setStatus(mode === 'login' ? 'Signing in...' : 'Creating viewer account...');
    try {
      if (mode === 'login') {
        await onLogin({ email, password });
        setStatus('Signed in');
      } else {
        await onRegister({ email, password });
        setStatus('Account created');
      }
    } catch (error) {
      setStatus(error.message || (mode === 'login' ? 'Sign in failed' : 'Registration failed'));
    }
  }

  return (
    <section className="auth-panel">
      <div>
        <p className="eyebrow">MongoDB RBAC</p>
        <h3>{mode === 'login' ? 'Internal dashboard access' : 'Create dashboard account'}</h3>
        <p>
          {mode === 'login'
            ? 'Sign in with a dashboard role before loading analytics, ML, customer graph, and copilot insights.'
            : 'New dashboard accounts start as viewers with read-only dashboard and intelligence access.'}
        </p>
        <div className="access-list" aria-label="Dashboard role access">
          {dashboardAccess.map((item) => (
            <div key={item.role}>
              <strong>{item.role}</strong>
              <span>{item.scope}</span>
            </div>
          ))}
        </div>
      </div>
      <form className="auth-form" onSubmit={submit}>
        <div className="auth-mode" role="tablist" aria-label="Authentication mode">
          <button className={mode === 'login' ? 'active' : ''} type="button" onClick={() => setMode('login')}>
            <LogIn size={16} aria-hidden="true" />
            Sign in
          </button>
          <button className={mode === 'register' ? 'active' : ''} type="button" onClick={() => setMode('register')}>
            <UserPlus size={16} aria-hidden="true" />
            Register
          </button>
        </div>
        <input aria-label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        <input aria-label="Password" type="password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} />
        <button type="submit">
          {mode === 'login' ? <LogIn size={18} aria-hidden="true" /> : <UserPlus size={18} aria-hidden="true" />}
          {mode === 'login' ? 'Sign in' : 'Create account'}
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
        <div className={`status-banner ${hasError ? 'error' : ''}`} role="status" aria-live="polite">
          <strong>{hasError ? 'Dashboard error' : 'Loading'}</strong>
          <span>
            {hasError ? 'Internal API unavailable. No fallback data is being shown.' : 'Fetching live dashboard metrics...'}
          </span>
        </div>
      )}

      {hasError && !isLoading && <EmptyPanel title="Dashboard data unavailable" detail="Fix the API or MongoDB connection, then reload this view." />}

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


function Recommendations({ recommendations, customerOptions, selectedCustomerId, onCustomerChange, isLoading, hasError }) {
  if (!customerOptions.length) {
    return <EmptyPanel title="No registered customers" detail="Register a customer in the shop before running recommendations." />;
  }
  return (
    <div className="view-stack">
      {(isLoading || hasError) && (
        <div className={`status-banner ${hasError ? 'error' : ''}`} role="status" aria-live="polite">
          <strong>{hasError ? 'Recommendation error' : 'Loading'}</strong>
          <span>{hasError ? 'ML recommendation API unavailable.' : 'Running product affinity model...'}</span>
        </div>
      )}
      <div className="panel controls-panel">
        <label className="customer-picker compact">
          <span>Customer</span>
          <select value={selectedCustomerId} onChange={(event) => onCustomerChange(event.target.value)}>
            {customerOptions.map((option) => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>
      {hasError && !isLoading && (
        <EmptyPanel title="Recommendations unavailable" detail="The dashboard did not receive a recommendation response from the ML API." />
      )}
      {!hasError && !isLoading && recommendations.length === 0 && (
        <EmptyPanel title="No recommendations yet" detail="Place an order in the shop, then return here to see recommendation output for that customer." />
      )}
      <section className="recommendation-grid" aria-busy={isLoading}>
        {!hasError && recommendations.map((item) => (
          <article className={`product-card ${isLoading ? 'is-skeleton' : ''}`} key={item.product}>
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
    </div>
  );
}

function Forecasting({ forecast, model, customerOptions, selectedCustomerId, onCustomerChange, isLoading, hasError }) {
  if (!customerOptions.length) {
    return <EmptyPanel title="No registered customers" detail="Register a customer in the shop before running a forecast." />;
  }
  if (hasError && !isLoading) {
    return <EmptyPanel title="Forecast unavailable" detail="This customer needs enough order history, or the ML forecast API is unavailable." />;
  }
  if (!forecast.length && !isLoading) {
    return <EmptyPanel title="No forecast data" detail="This customer needs at least three orders before forecasting." />;
  }
  const max = Math.max(...forecast.map((point) => point.predicted));
  return (
    <div className="view-stack">
      {(isLoading || hasError) && (
        <div className={`status-banner ${hasError ? 'error' : ''}`} role="status" aria-live="polite">
          <strong>{hasError ? 'Forecast error' : 'Loading'}</strong>
          <span>{hasError ? 'ML forecast API unavailable.' : 'Running revenue forecast model...'}</span>
        </div>
      )}
      <section className={`panel full-height ${isLoading ? 'is-skeleton' : ''}`}>
        <div className="forecast-head">
          <PanelTitle icon={TrendingUp} title="Revenue Forecast" />
          <label className="customer-picker compact">
            <span>Customer</span>
            <select value={selectedCustomerId} onChange={(event) => onCustomerChange(event.target.value)}>
              {customerOptions.map((option) => (
                <option key={option.id} value={option.id}>{option.label}</option>
              ))}
            </select>
          </label>
        </div>
        {model && <span className="source-pill live">{model}</span>}
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
    </div>
  );
}

function RetailAI({ intelligence, isLoading, hasError }) {
  const churn = intelligence?.churn?.churn;
  const behavior = intelligence?.churn?.behavior;
  const basketPairs = intelligence?.basket_analysis?.pairs || [];
  const demand = intelligence?.demand_forecast?.forecasts || [];
  const reviews = intelligence?.review_intelligence;

  return (
    <section className="retail-ai-grid">
      {(isLoading || hasError) && (
        <div className={`status-banner ${hasError ? 'error' : ''}`} role="status" aria-live="polite">
          <strong>{hasError ? 'Retail AI error' : 'Loading'}</strong>
          <span>{hasError ? 'Internal intelligence API unavailable.' : 'Fetching retail ML outputs...'}</span>
        </div>
      )}

      <div className={`panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={ShieldCheck} title="Churn Risk" />
        <div className="retail-kpi">
          <strong>{churn ? `${churn.percent}%` : 'N/A'}</strong>
          <span>{churn ? `${churn.risk_band} risk` : 'No churn output yet'}</span>
        </div>
        <p className="narrative">{churn?.recommended_action || 'Connect transaction features to score churn.'}</p>
      </div>

      <div className={`panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={Users} title="Behavior" />
        <div className="compact-list">
          <span>Orders: <strong>{behavior?.orders ?? 0}</strong></span>
          <span>Views: <strong>{behavior?.browse_events ?? 0}</strong></span>
          <span>Segment: <strong>{behavior?.behavior_segment || 'N/A'}</strong></span>
        </div>
      </div>

      <div className={`panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={PackageCheck} title="Basket Analysis" />
        <div className="compact-list">
          {basketPairs.length ? basketPairs.slice(0, 4).map((pair) => (
            <span key={pair.product_ids.join('-')}>
              {pair.products.join(' + ')} <strong>{pair.lift}x lift</strong>
            </span>
          )) : <span>No product pairs yet</span>}
        </div>
      </div>

      <div className={`panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={TrendingUp} title="Product Demand" />
        <div className="compact-list">
          {demand.length ? demand.slice(0, 4).map((item) => (
            <span key={item.product_id}>
              {item.product} <strong>{item.daily_average_units} avg/day</strong>
            </span>
          )) : <span>No demand history yet</span>}
        </div>
      </div>

      <div className={`panel wide ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={MessageSquareText} title="Review Intelligence" />
        <div className="compact-list horizontal">
          <span>Reviews: <strong>{reviews?.review_count ?? 0}</strong></span>
          <span>Positive: <strong>{Math.round((reviews?.sentiment_mix?.positive || 0) * 100)}%</strong></span>
          <span>Neutral: <strong>{Math.round((reviews?.sentiment_mix?.neutral || 0) * 100)}%</strong></span>
          <span>Negative: <strong>{Math.round((reviews?.sentiment_mix?.negative || 0) * 100)}%</strong></span>
        </div>
      </div>
    </section>
  );
}

function Explainability({ explanation, isLoading, hasError }) {
  if ((hasError || !explanation) && !isLoading) {
    return <EmptyPanel title="Explainability unavailable" detail="The intelligence API could not compute attribution from the selected customer and recommendation inputs." />;
  }
  const features = explanation?.features || [];
  return (
    <section className="explain-layout">
      {(isLoading || hasError) && (
        <div className={`status-banner ${hasError ? 'error' : ''}`} role="status" aria-live="polite">
          <strong>{hasError ? 'Explainability error' : 'Loading'}</strong>
          <span>
            {hasError ? 'Internal intelligence API unavailable.' : 'Fetching feature attribution...'}
          </span>
        </div>
      )}

      <div className={`panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={BrainCircuit} title="Feature Attribution" />
        {explanation?.recommended_product && (
          <div className="compact-list horizontal">
            <span>Product: <strong>{explanation.recommended_product}</strong></span>
            <span>Score: <strong>{Math.round(explanation.recommendation_score * 100)}%</strong></span>
            <span>Source: <strong>{explanation.recommendation_source}</strong></span>
          </div>
        )}
        <div className="attribution-list" aria-busy={isLoading}>
          {features.map((feature) => (
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
        <p className="narrative">{explanation?.explanation || 'Computing attribution from recommendation evidence...'}</p>
      </div>
    </section>
  );
}


function Customer360({ customer, graph, source, customerOptions, selectedCustomerId, onCustomerChange, isLoading, hasError }) {
  if (!customerOptions.length) {
    return <EmptyPanel title="No registered customers" detail="Register a customer in the shop before viewing Customer 360." />;
  }
  if (hasError && !isLoading) {
    return <EmptyPanel title="Customer graph unavailable" detail="The graph API did not return customer data." />;
  }
  if (!customer || !graph.nodes.length) {
    return <EmptyPanel title="No customer graph yet" detail="This customer has no purchases, browse events, or graph edges to visualize." />;
  }
  const relationshipEdges = graph.edges.filter((edge) => edge.source_position && edge.target_position);
  return (
    <section className="customer-layout">
      {(isLoading || hasError) && (
        <div className={`status-banner ${hasError ? 'error' : ''}`} role="status" aria-live="polite">
          <strong>{hasError ? 'Graph error' : 'Loading'}</strong>
          <span>
            {hasError ? 'Internal customer graph API unavailable.' : 'Fetching customer graph & profile...'}
          </span>
        </div>
      )}

      <div className={`panel profile-panel ${isLoading ? 'is-skeleton' : ''}`}>
        <PanelTitle icon={Users} title="Customer Profile" />
        <label className="customer-picker">
          <span>Customer</span>
          <select value={selectedCustomerId} onChange={(event) => onCustomerChange(event.target.value)}>
            {customerOptions.map((option) => (
              <option key={option.id} value={option.id}>{option.label}</option>
            ))}
          </select>
        </label>
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
        <span className={source === 'mongodb_graph' ? 'source-pill live' : 'source-pill'}>
          {source === 'mongodb_graph' ? 'MongoDB graph' : 'Graph source unavailable'}
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

function EmptyPanel({ title, detail }) {
  return (
    <section className="panel empty-panel">
      <strong>{title}</strong>
      <p>{detail}</p>
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
