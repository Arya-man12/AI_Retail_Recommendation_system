const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const TOKEN_KEYS = {
  dashboard: 'ci_dashboard_token',
  shop: 'ci_shop_token'
};

export function getAuthToken(site = 'dashboard') {
  return window.localStorage.getItem(TOKEN_KEYS[site] || TOKEN_KEYS.dashboard);
}

export function setAuthSession(site, payload) {
  window.localStorage.setItem(TOKEN_KEYS[site] || TOKEN_KEYS.dashboard, payload.access_token);
  window.localStorage.setItem(`${TOKEN_KEYS[site] || TOKEN_KEYS.dashboard}_user`, JSON.stringify(payload.user));
}

export function clearAuthSession(site = 'dashboard') {
  window.localStorage.removeItem(TOKEN_KEYS[site] || TOKEN_KEYS.dashboard);
  window.localStorage.removeItem(`${TOKEN_KEYS[site] || TOKEN_KEYS.dashboard}_user`);
}

export async function loginUser({ email, password, site = 'dashboard' }) {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    throw new Error('Unable to sign in');
  }

  const payload = await response.json();
  setAuthSession(site, payload);
  return payload;
}

function authHeaders(site = 'dashboard') {
  const token = getAuthToken(site);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchDashboardData() {
  const response = await fetch(`${API_BASE_URL}/api/dashboard`, {
    headers: authHeaders('dashboard')
  });
  if (!response.ok) {
    throw new Error('Unable to load dashboard data');
  }
  return response.json();
}

export async function askCopilot(question) {
  const response = await fetch(`${API_BASE_URL}/api/copilot/ask`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders('dashboard')
    },
    body: JSON.stringify({ question })
  });

  if (!response.ok) {
    throw new Error('Unable to query copilot');
  }

  return response.json();
}

export async function fetchIntelligenceSnapshot() {
  const response = await fetch(`${API_BASE_URL}/api/intelligence/snapshot`, {
    headers: authHeaders('dashboard')
  });
  if (!response.ok) {
    throw new Error('Unable to load intelligence snapshot');
  }
  return response.json();
}

export async function fetchCustomer360(customerId = 'cust-maya-chen') {
  const response = await fetch(`${API_BASE_URL}/api/graph/customers/${customerId}`, {
    headers: authHeaders('dashboard')
  });
  if (!response.ok) {
    throw new Error('Unable to load customer graph');
  }
  return response.json();
}

export async function fetchShopProducts() {
  const response = await fetch(`${API_BASE_URL}/api/ecommerce/products`, {
    headers: authHeaders('shop')
  });
  if (!response.ok) {
    throw new Error('Unable to load shop products');
  }
  return response.json();
}

export async function placeShopOrder({ customerId, productId, quantity }) {
  const response = await fetch(`${API_BASE_URL}/api/ecommerce/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders('shop')
    },
    body: JSON.stringify({
      customer_id: customerId,
      product_id: productId,
      quantity
    })
  });

  if (!response.ok) {
    throw new Error('Unable to place order');
  }

  return response.json();
}

export async function fetchShopOrders({ customerId }) {
  const url = new URL(`${API_BASE_URL}/api/ecommerce/orders`);
  if (customerId) url.searchParams.set('customer_id', customerId);

  const response = await fetch(url.toString(), {
    headers: authHeaders('shop')
  });

  if (!response.ok) {
    throw new Error('Unable to load orders');
  }

  return response.json();
}

