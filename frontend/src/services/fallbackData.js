export const fallbackDashboard = {
  metrics: [
    { label: 'Revenue today', value: '$428.6k', delta: '+18.4%', icon: 'revenue' },
    { label: 'Active customers', value: '42,918', delta: '+6.7%', icon: 'users' },
    { label: 'Conversion rate', value: '9.8%', delta: '+1.9%', icon: 'users' },
    { label: 'Churn risk', value: '3.2%', delta: '-0.8%', icon: 'users' }
  ],
  revenueSeries: [
    { hour: '08', value: 32 },
    { hour: '09', value: 48 },
    { hour: '10', value: 42 },
    { hour: '11', value: 62 },
    { hour: '12', value: 71 },
    { hour: '13', value: 66 },
    { hour: '14', value: 84 },
    { hour: '15', value: 78 },
    { hour: '16', value: 92 }
  ],
  signals: [
    { title: 'Cart recovery lift', detail: 'Personalized bundle offers are outperforming baseline by 12%.', intent: 'good' },
    { title: 'Northeast surge', detail: 'Demand clustering around premium replenishment products.', intent: 'good' },
    { title: 'Inventory watch', detail: 'Two recommended SKUs may stock out within 36 hours.', intent: 'warn' }
  ],
  recommendations: [
    {
      segment: 'High-LTV wellness buyers',
      product: 'Smart Hydration Bundle',
      reason: 'Similar customers recently purchased after viewing connected health products.',
      score: 91,
      gradient: 'linear-gradient(135deg, #0f766e, #22c55e)'
    },
    {
      segment: 'Urban commuters',
      product: 'Compact Power Kit',
      reason: 'Location, repeat purchase cadence, and accessory affinity are aligned.',
      score: 84,
      gradient: 'linear-gradient(135deg, #2563eb, #06b6d4)'
    },
    {
      segment: 'Premium home accounts',
      product: 'Air Quality Monitor Pro',
      reason: 'Graph neighbors show strong conversion after smart home purchases.',
      score: 79,
      gradient: 'linear-gradient(135deg, #7c3aed, #db2777)'
    }
  ],
  forecast: [
    { day: 'Mon', actual: 220, predicted: 218 },
    { day: 'Tue', actual: 236, predicted: 242 },
    { day: 'Wed', actual: 251, predicted: 257 },
    { day: 'Thu', actual: 268, predicted: 276 },
    { day: 'Fri', actual: 294, predicted: 304 },
    { day: 'Sat', actual: 318, predicted: 334 },
    { day: 'Sun', actual: 0, predicted: 352 }
  ],
  explainability: {
    explanation: 'The recommendation is mostly driven by high recent category engagement, strong regional demand, and a low discount sensitivity score. Churn risk slightly reduces confidence.',
    features: [
      { name: 'Recent product views', impact: 0.38 },
      { name: 'Regional demand index', impact: 0.29 },
      { name: 'Bundle affinity', impact: 0.21 },
      { name: 'Discount sensitivity', impact: 0.14 },
      { name: 'Churn risk', impact: -0.12 }
    ]
  },
  customers: [
    {
      name: 'Maya Chen',
      initials: 'MC',
      segment: 'High-LTV wellness buyer',
      ltv: '$18,420',
      churnRisk: 'Low',
      lastEvent: 'Viewed hydration bundle'
    }
  ],
  graph: {
    nodes: [
      { id: 'customer', label: 'Maya', kind: 'customer', x: 45, y: 44 },
      { id: 'product', label: 'Bundle', kind: 'product', x: 16, y: 22 },
      { id: 'region', label: 'NE', kind: 'region', x: 73, y: 21 },
      { id: 'campaign', label: 'Email', kind: 'campaign', x: 22, y: 73 },
      { id: 'segment', label: 'Wellness', kind: 'segment', x: 75, y: 72 }
    ],
    edges: [
      { id: 'a', type: 'VIEWED', source_position: { x: 45, y: 44 }, target_position: { x: 16, y: 22 } },
      { id: 'b', type: 'LOCATED_IN', source_position: { x: 45, y: 44 }, target_position: { x: 73, y: 21 } },
      { id: 'c', type: 'TARGETED', source_position: { x: 45, y: 44 }, target_position: { x: 22, y: 73 } },
      { id: 'd', type: 'BELONGS_TO', source_position: { x: 45, y: 44 }, target_position: { x: 75, y: 72 } }
    ]
  },
  geo: [
    { name: 'West', revenue: '$102k', trend: '+7.4%', heat: 0.62, x: 18, y: 46 },
    { name: 'Midwest', revenue: '$84k', trend: '+4.2%', heat: 0.5, x: 46, y: 42 },
    { name: 'Northeast', revenue: '$148k', trend: '+21.6%', heat: 0.96, x: 72, y: 32 },
    { name: 'South', revenue: '$94k', trend: '+8.9%', heat: 0.58, x: 58, y: 70 }
  ],
  copilot: {
    tools: ['Forecast tool', 'Recommendation tool', 'Feature attribution tool', 'Neo4j graph tool', 'Geo analytics tool'],
    sampleAnswer: 'Northeast revenue is rising because recent premium bundle views, regional demand, and campaign engagement are all above baseline. The recommendation tool would prioritize hydration and air quality bundles for this region.'
  }
};
