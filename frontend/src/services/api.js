const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const TOKEN_KEYS = {
  dashboard: 'ci_dashboard_token',
  shop: 'ci_shop_token'
};

export function getAuthToken(site = 'dashboard') {
  return window.localStorage.getItem(TOKEN_KEYS[site] || TOKEN_KEYS.dashboard);
}

export function getAuthUser(site = 'dashboard') {
  const raw = window.localStorage.getItem(`${TOKEN_KEYS[site] || TOKEN_KEYS.dashboard}_user`);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
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
  validateAuthFields({ email, password });
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, 'Unable to sign in'));
  }

  const payload = await response.json();
  setAuthSession(site, payload);
  return payload;
}

export async function registerUser({ email, password, site = 'dashboard' }) {
  validateAuthFields({ email, password });
  const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ email, password, site })
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, 'Unable to create account'));
  }

  const payload = await response.json();
  setAuthSession(site, payload);
  return payload;
}

function validateAuthFields({ email, password }) {
  if (!String(email || '').trim().includes('@')) {
    throw new Error('Enter a valid email address');
  }
  if (String(password || '').length < 8) {
    throw new Error('Password must be at least 8 characters');
  }
}

async function responseErrorMessage(response, fallback) {
  const payload = await response.json().catch(() => null);
  return detailToMessage(payload?.detail) || fallback;
}

function detailToMessage(detail) {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map(validationIssueToMessage).filter(Boolean).join('; ');
  }
  if (typeof detail === 'object') {
    return detail.msg || JSON.stringify(detail);
  }
  return String(detail);
}

function validationIssueToMessage(issue) {
  if (typeof issue === 'string') return issue;
  const field = Array.isArray(issue?.loc) ? issue.loc[issue.loc.length - 1] : '';
  if (field === 'email') return 'Enter a valid email address';
  if (field === 'password') return 'Password must be at least 8 characters';
  if (field === 'site') return 'Choose either dashboard or shop registration';
  return issue?.msg || '';
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

export async function fetchFeatureAttribution({ customerId, segment, recentCategories }) {
  const response = await fetch(`${API_BASE_URL}/api/intelligence/explainability`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders('dashboard')
    },
    body: JSON.stringify({
      customer_id: customerId,
      segment,
      recent_categories: recentCategories
    })
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, 'Unable to compute feature attribution'));
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

export async function fetchRegisteredCustomers() {
  const response = await fetch(`${API_BASE_URL}/api/auth/customers`, {
    headers: authHeaders('dashboard')
  });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, 'Unable to load customers'));
  }
  return response.json();
}

export async function forecastRevenue(recentRevenue) {
  const response = await fetch(`${API_BASE_URL}/api/ml/forecast`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders('dashboard')
    },
    body: JSON.stringify({ recent_revenue: recentRevenue })
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, 'Unable to run forecast'));
  }

  return response.json();
}

export async function fetchProductRecommendations({ customerId, segment, recentCategories }) {
  const response = await fetch(`${API_BASE_URL}/api/ml/recommendations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders('dashboard')
    },
    body: JSON.stringify({
      customer_id: customerId,
      segment,
      recent_categories: recentCategories
    })
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, 'Unable to run recommendations'));
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

export async function submitProductReview({ customerId, productId, rating, text }) {
  const response = await fetch(`${API_BASE_URL}/api/ecommerce/reviews`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders('shop')
    },
    body: JSON.stringify({
      customer_id: customerId,
      product_id: productId,
      rating,
      text
    })
  });

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, 'Unable to submit review'));
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
