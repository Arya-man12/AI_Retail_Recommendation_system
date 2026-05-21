import { useEffect, useState } from 'react';
import { LogIn, Radar, ShoppingBag, ShoppingCart, Sparkles } from 'lucide-react';

import { clearAuthSession, fetchShopOrders, fetchShopProducts, getAuthToken, loginUser, placeShopOrder } from '../services/api.js';
import { fallbackProducts } from './shopData.js';
import './shop.css';

export function ShopExperience({ onOpenDashboard }) {
  const [isAuthed, setIsAuthed] = useState(Boolean(getAuthToken('shop')));
  const [products, setProducts] = useState(fallbackProducts);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [orderStatus, setOrderStatus] = useState('Browse products');
  const [emqxStatus, setEmqxStatus] = useState(null);
  const [placingProductId, setPlacingProductId] = useState(null);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);

  const customerId = 'customer-demo-001';

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
  }, [isAuthed]);

  async function handleLogin(credentials) {
    await loginUser({ ...credentials, site: 'shop' });
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

      {!isAuthed && <ShopLogin onLogin={handleLogin} />}

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

function ShopLogin({ onLogin }) {
  const [email, setEmail] = useState('shopper@example.com');
  const [password, setPassword] = useState('Shopper123!');
  const [status, setStatus] = useState('Use the seeded shopper account');

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
    <section className="shop-login">
      <div>
        <p className="eyebrow">MongoDB RBAC</p>
        <h2>BrightCart customer access</h2>
        <p>Customer roles can browse products and place orders without internal analytics access.</p>
      </div>
      <form className="shop-login-form" onSubmit={submit}>
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
