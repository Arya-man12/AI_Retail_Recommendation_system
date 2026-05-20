const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export async function fetchDashboardData() {
  const response = await fetch(`${API_BASE_URL}/api/dashboard`);
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
      'X-User-Role': 'marketing_analyst'
    },
    body: JSON.stringify({ question })
  });

  if (!response.ok) {
    throw new Error('Unable to query copilot');
  }

  return response.json();
}

