// Mock data + fake "engine" responses for the clickable prototype.
// Everything here is hardcoded. When the real backend exists, replace the
// functions below with fetch() calls to the orchestrator; the component code
// and types do not need to change.

import type {
  ChartSpec,
  ChatMessage,
  Profile,
  ReportItem,
  ReportSection,
} from './types'

let idCounter = 0
export const nextId = (prefix = 'id') => `${prefix}-${++idCounter}`

// ── The Telco Customer Churn profile (matches data/telco_churn.csv) ──────────
export const TELCO_PROFILE: Profile = {
  fileName: 'telco_churn.csv',
  nRows: 7043,
  nCols: 21,
  columns: [
    { name: 'customerID', dtype: 'object', nNull: 0, nUnique: 7043, samples: ['7590-VHVEG', '5575-GNVDE'] },
    { name: 'gender', dtype: 'object', nNull: 0, nUnique: 2, samples: ['Female', 'Male'] },
    { name: 'SeniorCitizen', dtype: 'int64', nNull: 0, nUnique: 2, samples: [0, 1] },
    { name: 'Partner', dtype: 'object', nNull: 0, nUnique: 2, samples: ['Yes', 'No'] },
    { name: 'Dependents', dtype: 'object', nNull: 0, nUnique: 2, samples: ['No', 'Yes'] },
    { name: 'tenure', dtype: 'int64', nNull: 0, nUnique: 73, samples: [1, 34, 72] },
    { name: 'PhoneService', dtype: 'object', nNull: 0, nUnique: 2, samples: ['No', 'Yes'] },
    { name: 'Contract', dtype: 'object', nNull: 0, nUnique: 3, samples: ['Month-to-month', 'One year', 'Two year'] },
    { name: 'PaperlessBilling', dtype: 'object', nNull: 0, nUnique: 2, samples: ['Yes', 'No'] },
    { name: 'PaymentMethod', dtype: 'object', nNull: 0, nUnique: 4, samples: ['Electronic check', 'Mailed check'] },
    { name: 'MonthlyCharges', dtype: 'float64', nNull: 0, nUnique: 1585, samples: [29.85, 56.95, 53.85] },
    {
      name: 'TotalCharges',
      dtype: 'object',
      nNull: 0,
      nUnique: 6531,
      samples: ['29.85', '1889.5', ' '],
      issue: 'numeric-looking but contains 11 blank strings → naive .mean() raises',
    },
    { name: 'Churn', dtype: 'object', nNull: 0, nUnique: 2, samples: ['No', 'Yes'] },
  ],
}

// Questions surfaced as starter chips in the chat view.
export const SUGGESTED_QUESTIONS = [
  'What is the overall churn rate?',
  'Does contract type affect churn?',
  'Average monthly charges: churned vs retained?',
  'What is the average TotalCharges?',
]

// ── Fake chat engine ─────────────────────────────────────────────────────────
// Returns the assistant reply for a user question. Pattern-matched on keywords;
// falls back to a generic answer. Charts are inline so the UI can render them.
export function mockAnswer(question: string): { text: string; chart?: ChartSpec } {
  const q = question.toLowerCase()

  if (q.includes('contract')) {
    return {
      text:
        'Churn is heavily concentrated in month-to-month contracts (42.7% churn), ' +
        'versus 11.3% for one-year and just 2.8% for two-year contracts. Longer ' +
        'commitments retain customers far better.',
      chart: {
        kind: 'bar',
        title: 'Churn rate by contract type',
        unit: '%',
        data: [
          { label: 'Month-to-month', value: 42.7 },
          { label: 'One year', value: 11.3 },
          { label: 'Two year', value: 2.8 },
        ],
      },
    }
  }

  if (q.includes('monthly') || (q.includes('charge') && !q.includes('total'))) {
    return {
      text:
        'Churned customers pay more per month on average ($74.44) than retained ' +
        'customers ($61.27) — higher monthly charges correlate with churn.',
      chart: {
        kind: 'bar',
        title: 'Avg monthly charges: churned vs retained',
        unit: '$',
        data: [
          { label: 'Churned', value: 74.44 },
          { label: 'Retained', value: 61.27 },
        ],
      },
    }
  }

  if (q.includes('total')) {
    return {
      text:
        'Average TotalCharges is $2283.30. Note: this column is stored as text and ' +
        'contains 11 blank strings, so it must be coerced to numeric (dropping or ' +
        'imputing the blanks) before averaging — a naive .mean() would raise.',
    }
  }

  if (q.includes('churn rate') || q.includes('overall') || q.includes('how many churn')) {
    return {
      text:
        '1,869 of 7,043 customers churned — an overall churn rate of 26.5%.',
      chart: {
        kind: 'pie',
        title: 'Overall churn',
        data: [
          { label: 'Retained', value: 73.5 },
          { label: 'Churned', value: 26.5 },
        ],
      },
    }
  }

  return {
    text:
      `Here's a first look at "${question.trim()}". (Prototype: this answer is ` +
      `mocked — the real engine will compute it from the data and narrate the result.)`,
    chart: {
      kind: 'bar',
      title: 'Sample distribution',
      data: [
        { label: 'Group A', value: 58 },
        { label: 'Group B', value: 31 },
        { label: 'Group C', value: 11 },
      ],
    },
  }
}

export function makeAssistantMessage(question: string): ChatMessage {
  const { text, chart } = mockAnswer(question)
  return { id: nextId('msg'), role: 'assistant', text, chart }
}

// ── Report builder checklist ─────────────────────────────────────────────────
export const REPORT_CHECKLIST: ReportItem[] = [
  { id: 'r1', label: 'Overall churn rate (pie)', kind: 'chart', selected: true },
  { id: 'r2', label: 'Churn by contract type (bar)', kind: 'chart', selected: true },
  { id: 'r3', label: 'Monthly charges: churned vs retained', kind: 'chart', selected: true },
  { id: 'r4', label: 'Tenure distribution', kind: 'chart', selected: false },
  { id: 'r5', label: 'Average TotalCharges (stat)', kind: 'stat', selected: true },
  { id: 'r6', label: 'Churn by payment method', kind: 'chart', selected: false },
]

// Builds the report sections from the selected checklist items.
export function buildReport(items: ReportItem[]): ReportSection[] {
  const sections: ReportSection[] = []
  for (const it of items.filter((i) => i.selected)) {
    switch (it.id) {
      case 'r1':
        sections.push({
          id: it.id,
          title: 'Overall churn',
          prose:
            'Roughly one in four customers (26.5%) has churned — 1,869 of 7,043. ' +
            'That is a high baseline that the rest of this report breaks down.',
          chart: mockAnswer('overall churn rate').chart,
        })
        break
      case 'r2':
        sections.push({
          id: it.id,
          title: 'Churn by contract type',
          prose:
            'Contract length is the single strongest signal in the data. Month-to-month ' +
            'customers churn at 42.7%, versus 2.8% on two-year contracts.',
          chart: mockAnswer('contract').chart,
        })
        break
      case 'r3':
        sections.push({
          id: it.id,
          title: 'Monthly charges vs churn',
          prose:
            'Customers who churned paid noticeably more per month ($74.44 vs $61.27), ' +
            'suggesting price sensitivity at the higher end of the plan range.',
          chart: mockAnswer('monthly charges').chart,
        })
        break
      case 'r4':
        sections.push({
          id: it.id,
          title: 'Tenure distribution',
          prose:
            'Churn is front-loaded: most departures happen in the first year of tenure, ' +
            'after which retention stabilises.',
          chart: {
            kind: 'line',
            title: 'Customers by tenure (months)',
            data: [
              { label: '0', value: 100 },
              { label: '12', value: 62 },
              { label: '24', value: 48 },
              { label: '48', value: 40 },
              { label: '72', value: 55 },
            ],
          },
        })
        break
      case 'r5':
        sections.push({
          id: it.id,
          title: 'Average total charges',
          prose:
            'Across all customers, average lifetime TotalCharges is $2,283.30. The column ' +
            'required cleaning first — 11 blank strings were coerced before averaging.',
          stat: { value: '$2,283.30', caption: 'avg TotalCharges (after cleaning 11 blanks)' },
        })
        break
      case 'r6':
        sections.push({
          id: it.id,
          title: 'Churn by payment method',
          prose:
            'Electronic-check payers churn far more than customers on automatic payment ' +
            'methods, a useful operational lever.',
          chart: {
            kind: 'bar',
            title: 'Churn rate by payment method',
            unit: '%',
            data: [
              { label: 'Electronic check', value: 45.3 },
              { label: 'Mailed check', value: 19.1 },
              { label: 'Bank transfer (auto)', value: 16.7 },
              { label: 'Credit card (auto)', value: 15.2 },
            ],
          },
        })
        break
    }
  }
  return sections
}
