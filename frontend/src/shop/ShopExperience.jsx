import { useEffect, useState } from 'react';
import { LogIn, Radar, ShoppingBag, ShoppingCart, Sparkles, UserPlus } from 'lucide-react';

import { clearAuthSession, fetchShopOrders, fetchShopProducts, getAuthToken, getAuthUser, loginUser, placeShopOrder, registerUser, submitProductReview } from '../services/api.js';
import { fallbackProducts } from './shopData.js';
import './shop.css';

const shopAccess = [
  { role: 'Customer', scope: 'Browse products, place orders, view order history, and receive recommendations.' },
  { role: 'Internal roles', scope: 'Dashboard, ML, graph, copilot, streaming, feature, and ops tools stay outside the shop.' }
];

export function ShopExperience({ onOpenDashboard }) {
  const [isAuthed, setIsAuthed] = useState(Boolean(getAuthToken('shop')));
  const [products, setProducts] = useState(fallbackProducts);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [orderStatus, setOrderStatus] = useState('Browse products');
  const [emqxStatus, setEmqxStatus] = useState(null);
  const [placingProductId, setPlacingProductId] = useState(null);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);
  const [reviewProductId, setReviewProductId] = useState('');
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewText, setReviewText] = useState('');
  const [reviewStatus, setReviewStatus] = useState('Share product feedback');

  const authUser = getAuthUser('shop');
  const customerId = authUser?.customer_id || 'customer-demo-001';

  const [orders, setOrders] = useState([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);

  useEffect(() => {
    if (!isAuthed) return undefined;
    let mounted = true;

    fetchShopProducts()
      .then((payload) => {
        if (mounted) setProducts(payload.products);
      })
      .catch(() => {
        if (mounted) setOrderStatus('Demo catalog loaded');
      });

    setIsLoadingOrders(true);
    fetchShopOrders({ customerId })
      .then((payload) => {
        if (mounted) setOrders(payload.orders || []);
      })
      .catch(() => {
        if (mounted) setOrders([]);
      })
      .finally(() => {
        if (mounted) setIsLoadingOrders(false);
      });

    return () => {
      mounted = false;
    };
  }, [isAuthed, customerId]);

  async function handleLogin(credentials) {
    await loginUser({ ...credentials, site: 'shop' });
    setIsAuthed(true);
  }

  async function handleRegister(credentials) {
    await registerUser({ ...credentials, site: 'shop' });
    setIsAuthed(true);
  }

  function handleLogout() {
    clearAuthSession('shop');
    setIsAuthed(false);
    setProducts(fallbackProducts);
    setOrderStatus('Browse products');
    setOrders([]);
    setSelectedProduct(null);
    setRecommendations([]);
    setEmqxStatus(null);
  }

  async function buyProduct(product) {
    if (placingProductId === product.id) return;

    setSelectedProduct(product);
    setOrderStatus('Placing order...');
    setRecommendations([]);
    setEmqxStatus(null);
    setPlacingProductId(product.id);
    setIsLoadingRecommendations(true);

    try {
      const payload = await placeShopOrder({
        customerId,
        productId: product.id,
        quantity: 1
      });

      setOrderStatus(`Order ${payload.order.order_id} placed`);
      setRecommendations(payload.recommendations);
      setEmqxStatus(payload.emqx);
      setOrders((currentOrders) => upsertOrder(currentOrders, normalizeOrder(payload.order)));

      // Refresh order history so the customer sees the new purchase
      setIsLoadingOrders(true);
      fetchShopOrders({ customerId })
        .then((next) => setOrders(next.orders || []))
        .catch(() => {})
        .finally(() => setIsLoadingOrders(false));

    } catch {
      setOrderStatus('Order API unavailable');
    } finally {
      setPlacingProductId(null);
      setIsLoadingRecommendations(false);
    }
  }

  async function submitReview(event) {
    event.preventDefault();
    const productId = reviewProductId || selectedProduct?.id || products[0]?.id;
    if (!productId || !reviewText.trim()) return;
    setReviewStatus('Submitting review...');
    try {
      const payload = await submitProductReview({
        customerId,
        productId,
        rating: Number(reviewRating),
        text: reviewText.trim()
      });
      setReviewStatus(`Review saved: ${payload.review.sentiment.label}`);
      setReviewText('');
      setReviewProductId(productId);
    } catch (error) {
      setReviewStatus(error.message || 'Review API unavailable');
    }
  }

  return (
    <main className="shop-shell">
      <header className="shop-header">
        <div>
          <p className="eyebrow">Customer-facing demo</p>
          <h1>BrightCart</h1>
        </div>
        {onOpenDashboard && (
          <button className="surface-switch" type="button" onClick={onOpenDashboard}>
            <Radar size={17} aria-hidden="true" />
            Internal dashboard
          </button>
        )}
        {isAuthed && (
          <button className="surface-switch" type="button" onClick={handleLogout}>
            <LogIn size={17} aria-hidden="true" />
            Sign out
          </button>
        )}
      </header>

      {!isAuthed && <ShopLogin onLogin={handleLogin} onRegister={handleRegister} />}

      {isAuthed && <section className="shop-hero">
        <div>
          <p className="eyebrow">Realtime recommendations</p>
          <h2>Buy a product and get similar recommendations instantly.</h2>
        </div>
        <div className="shop-status">
          <ShoppingBag size={20} aria-hidden="true" />
          <span aria-live="polite">{orderStatus}</span>
        </div>

      </section>}

      {isAuthed && <section className="shop-grid">
        {products.map((product) => (
          <article className="shop-card" key={product.id}>
            <div className="shop-art" style={{ backgroundColor: product.accent }}>
              <ShoppingCart size={34} aria-hidden="true" />
            </div>
            <div className="shop-card-body">
              <p className="eyebrow">{product.category}</p>
              <h3>{product.name}</h3>
              <p>{product.description}</p>
              <div className="shop-buy-row">
                <strong>${product.price.toFixed(2)}</strong>
                <button
                  type="button"
                  onClick={() => buyProduct(product)}
                  disabled={placingProductId === product.id}
                  aria-disabled={placingProductId === product.id}
                >
                  {placingProductId === product.id ? 'Placing…' : 'Buy'}
                </button>

              </div>
            </div>
          </article>
        ))}
      </section>}

      {isAuthed && (
        <section className="cart-panel" aria-label="My orders">
          <div className="cart-panel-head">
            <p className="eyebrow">My orders</p>
            <strong>{isLoadingOrders ? 'Loading…' : `${orders.length} purchased`}</strong>
          </div>

          <div className="cart-list" role="list" aria-busy={isLoadingOrders}>
            {isLoadingOrders ? (
              <div className="cart-empty">Fetching order history…</div>
            ) : orders.length === 0 ? (
              <div className="cart-empty">No purchases yet. Pick a product to buy.</div>
            ) : (
              orders.slice(0, 6).map((order) => (
                <div className="cart-item" key={order.order_id} role="listitem">
                  <div
                    className="cart-item-art"
                    style={{ backgroundColor: order.product?.accent || '#0f172a' }}
                    aria-hidden="true"
                  />
                  <div className="cart-item-body">
                    <div className="cart-item-top">
                      <strong>{order.product?.name || order.product?.id || 'Unknown product'}</strong>
                      <span className="cart-item-total">${Number(order.revenue ?? 0).toFixed(2)}</span>
                    </div>
                    <div className="cart-item-meta">
                      <span>{order.quantity} × ${Number(order.price ?? 0).toFixed(2)}</span>
                      <span className="cart-item-sep">•</span>
                      <span>{order.order_id}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          {orders.length > 6 && !isLoadingOrders && (
            <div className="cart-more">Showing latest 6 orders</div>
          )}
        </section>
      )}

      {isAuthed && selectedProduct && (
        <section className="post-purchase">
          <div>
            <p className="eyebrow">Purchased</p>
            <h2>{selectedProduct.name}</h2>
          </div>
          <div className="recommendation-strip">
            {recommendations.length > 0 ? (
              recommendations.map((item) => (
                <article className="mini-reco" key={item.product}>
                  <Sparkles size={18} aria-hidden="true" />
                  <div>
                    <strong>{item.product}</strong>
                    <span>{Math.round(item.score * 100)}% match</span>
                  </div>
                </article>
              ))
            ) : isLoadingRecommendations ? (
              <p className="shop-muted">Generating similar items…</p>
            ) : (
              <p className="shop-muted">Recommendations appear after the order service responds.</p>
            )}
          </div>

          {emqxStatus && (
            <div className="stream-note">
              EMQX ecommerce event: {emqxStatus.ecommerce.published ? 'published' : emqxStatus.ecommerce.reason}
            </div>
          )}
        </section>
      )}

      {isAuthed && (
        <section className="review-panel" aria-label="Product review">
          <div>
            <p className="eyebrow">Review intelligence</p>
            <h2>Give a product review</h2>
          </div>
          <form className="review-form" onSubmit={submitReview}>
            <select value={reviewProductId || selectedProduct?.id || products[0]?.id || ''} onChange={(event) => setReviewProductId(event.target.value)} aria-label="Product">
              {products.map((product) => (
                <option key={product.id} value={product.id}>{product.name}</option>
              ))}
            </select>
            <select value={reviewRating} onChange={(event) => setReviewRating(event.target.value)} aria-label="Rating">
              {[5, 4, 3, 2, 1].map((rating) => (
                <option key={rating} value={rating}>{rating} stars</option>
              ))}
            </select>
            <textarea value={reviewText} onChange={(event) => setReviewText(event.target.value)} minLength={3} maxLength={1000} placeholder="Write your review" aria-label="Review text" />
            <button type="submit">Submit review</button>
            <span>{reviewStatus}</span>
          </form>
        </section>
      )}
    </main>
  );
}

function normalizeOrder(order) {
  return {
    ...order,
    revenue: order.revenue ?? order.total ?? 0,
    price: order.price ?? order.product?.price ?? 0
  };
}

function upsertOrder(orders, nextOrder) {
  return [
    nextOrder,
    ...orders.filter((order) => order.order_id !== nextOrder.order_id)
  ];
}

function ShopLogin({ onLogin, onRegister }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('shopper@example.com');
  const [password, setPassword] = useState('Shopper123!');
  const [status, setStatus] = useState('Use the seeded shopper account');

  async function submit(event) {
    event.preventDefault();
    setStatus(mode === 'login' ? 'Signing in...' : 'Creating customer account...');
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
    <section className="shop-login">
      <div>
        <p className="eyebrow">MongoDB RBAC</p>
        <h2>{mode === 'login' ? 'BrightCart customer access' : 'Create BrightCart account'}</h2>
        <p>Customer roles can browse products and place orders without internal analytics access.</p>
        <div className="shop-access-list" aria-label="Shop role access">
          {shopAccess.map((item) => (
            <div key={item.role}>
              <strong>{item.role}</strong>
              <span>{item.scope}</span>
            </div>
          ))}
        </div>
      </div>
      <form className="shop-login-form" onSubmit={submit}>
        <div className="shop-auth-mode" role="tablist" aria-label="Authentication mode">
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
