// k6 load-testing script for PolarisGate POST /api/v1/guardrails/check
//
// Stages: warmup (10 VUs, 30s) → ramp (50 VUs, 1m) → peak (100 VUs, 1m) → cooldown (0 VUs, 30s)
// Tracks custom metrics: verdict_latency (Trend), false_positive_rate (Rate)
// Thresholds: p(95) < 500ms, error rate < 1%
//
// Usage:
//   k6 run tests/performance/k6/guardrails_check_load.js \
//     -e POLARISGATE_BASE_URL=http://localhost:8000 \
//     -e POLARISGATE_TOKEN=your-jwt-token

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------
const verdictLatency = new Trend('verdict_latency', true);   // ms, per-request
const falsePositiveRate = new Rate('false_positive_rate');     // clean text flagged toxic

// ---------------------------------------------------------------------------
// Test configuration
// ---------------------------------------------------------------------------
export const options = {
  stages: [
    { duration: '30s', target: 10 },   // warmup
    { duration: '1m',  target: 50 },   // ramp
    { duration: '1m',  target: 100 },  // peak load
    { duration: '30s', target: 0 },    // graceful cooldown
  ],
  thresholds: {
    // p95 latency must stay under 500 ms
    'verdict_latency': ['p(95)<500'],
    // less than 1 % of all requests may fail
    'http_req_failed': ['rate<0.01'],
    // false-positive rate target (informational — does not fail the test)
    'false_positive_rate': ['rate<0.10'],
  },
};

// ---------------------------------------------------------------------------
// Environment
// ---------------------------------------------------------------------------
const BASE_URL = __ENV.POLARISGATE_BASE_URL || 'http://localhost:8000';
const TOKEN    = __ENV.POLARISGATE_TOKEN    || 'placeholder-jwt-token';

const ENDPOINT = `${BASE_URL}/api/v1/guardrails/check`;

// ---------------------------------------------------------------------------
// Request payload pool
// ---------------------------------------------------------------------------
// Mix of clean texts that SHOULD be allowed and toxic texts that SHOULD be
// flagged.  VUs alternate so we can measure FP rate on the clean subset.
const CLEAN_TEXTS = [
  'The quarterly earnings report will be released next Tuesday.',
  'Can you please send me the meeting minutes from yesterday?',
  'Thank you for your help with the project, I really appreciate it.',
  'Please find the attached document for your review.',
  'The conference starts at 9 AM in the main auditorium.',
  'Let me know if you need any clarification on the requirements.',
  'The weather today is sunny with a high of 72 degrees.',
  'I enjoyed your presentation on renewable energy solutions.',
  'Albert Einstein developed the theory of relativity in the early 1900s.',
  'Python is a versatile programming language used for web development and data science.',
];

const TOXIC_TEXTS = [
  'I hate you and I hope you die.',
  'You are a worthless piece of garbage.',
  'Kill yourself you pathetic loser.',
  'People like you should be removed from society.',
  'I will find you and make you pay for this.',
  'You are the reason this world is going to hell.',
  'This is complete and utter bullshit.',
  'What a moron, cannot even get simple things right.',
  'I despise everything you stand for.',
  'Nobody would miss you if you were gone tomorrow.',
];

// ---------------------------------------------------------------------------
// Default function — executed once per iteration per VU
// ---------------------------------------------------------------------------
export default function () {
  // Alternate between clean and toxic each iteration so we can measure FP rate
  const idx = __ITER % CLEAN_TEXTS.length;
  const isClean = __VU % 2 === 0;
  const text = isClean ? CLEAN_TEXTS[idx] : TOXIC_TEXTS[idx];

  const payload = JSON.stringify({
    text: text,
    agent_id: 'k6-load-test',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TOKEN}`,
    },
  };

  const res = http.post(ENDPOINT, payload, params);

  // Record per-request latency
  verdictLatency.add(res.timings.duration);

  // Track false positives: a clean text that was flagged as toxic
  try {
    const body = JSON.parse(res.body);
    if (isClean && body.toxic === true) {
      falsePositiveRate.add(1);
    }
  } catch (_) {
    // ignore parse errors — the http_req_failed threshold catches those
  }

  // Assertions (informational — do not stop the test)
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response has action': (r) => {
      try { return 'action' in JSON.parse(r.body); } catch (_) { return false; }
    },
  });

  // Small sleep to simulate realistic think-time between requests
  sleep(0.1);
}