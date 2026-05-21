import { useEffect, useState } from 'react';
import { LogIn, Radar, ShoppingBag, ShoppingCart, Sparkles } from 'lucide-react';

import { clearAuthSession, fetchShopProducts, getAuthToken, loginUser, placeShopOrder } from '../services/api.js';
import { fallbackProducts } from './shopData.js';
import './shop.css';

export function ShopExperience({ onOpenDashboard }) {
  const [isAuthed, setIsAuthed] = useState(Boolean(getAuthToken('shop')));
  const [products, setProducts] = useState(fallbackProducts);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [orderStatus, setOrderStatus] = useState('Browse products');
  const [emqxStatus, setEmqxStatus] = useState(null);
  const [isPlacingOrder, setIsPlacingOrder] = useState(false);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);


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
  }

  async function buyProduct(product) {
    if (isPlacingOrder) return;

    setSelectedProduct(product);
    setOrderStatus('Placing order...');
    setRecommendations([]);
    setEmqxStatus(null);
    setIsPlacingOrder(true);
    setIsLoadingRecommendations(true);

    try {
      const payload = await placeShopOrder({
        customerId: 'customer-demo-001',
        productId: product.id,
        quantity: 1
      });

      setOrderStatus(`Order ${payload.order.order_id} placed`);
      setRecommendations(payload.recommendations);
      setEmqxStatus(payload.emqx);
    } catch {
      setOrderStatus('Order API unavailable');
    } finally {
      setIsPlacingOrder(false);
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
                  disabled={isPlacingOrder}
                  aria-disabled={isPlacingOrder}
                >
                  {isPlacingOrder ? 'Placing…' : 'Buy'}
                </button>

              </div>
            </div>
          </article>
        ))}
      </section>}

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
