/**
 * TDD test for Tinyfish SSE event parsing in the build-night-agent frontend.
 *
 * Bug: Tinyfish API sends `streaming_url` (snake_case) but the frontend
 * checked for `evt.streamingUrl` (camelCase), so the iframe never appeared.
 *
 * Run: node tests/test_tinyfish_sse_parsing.mjs
 */

import assert from 'node:assert/strict';
import { test, describe } from 'node:test';

// Simulate the SSE event extraction logic as it exists in index.html
// This mirrors the loop in runTinyfishAndContinue()

function parseSSEEvents(sseText) {
  let streamingUrl = null;
  let runId = null;
  let purpose = null;
  let result = null;
  let errorMsg = null;

  const frames = sseText.split('\n\n').filter(Boolean);
  for (const frame of frames) {
    const trimmed = frame.trim();
    if (!trimmed.startsWith('data:')) continue;
    let evt;
    try { evt = JSON.parse(trimmed.slice(5).trim()); } catch { continue; }

    if (evt.runId || evt.run_id) runId = evt.runId || evt.run_id;
    // FIXED: check both camelCase and snake_case
    if (evt.streamingUrl || evt.streaming_url) streamingUrl = evt.streamingUrl || evt.streaming_url;
    if (evt.purpose) purpose = evt.purpose;
    if (evt.type === 'COMPLETE') {
      const rj = evt.resultJson || evt.result_json || {};
      if (rj.parsed) { try { result = JSON.parse(rj.parsed); } catch { result = rj.parsed; } }
      else if (rj.input) { try { result = JSON.parse(rj.input); } catch { result = rj.input; } }
      else if (evt.result) result = evt.result;
    }
    if (evt.type === 'ERROR') errorMsg = evt.message || 'Tinyfish error';
  }
  return { streamingUrl, runId, purpose, result, errorMsg };
}

// BROKEN version (original code — only checks camelCase)
function parseSSEEventsBroken(sseText) {
  let streamingUrl = null;
  let runId = null;
  let purpose = null;
  let result = null;
  let errorMsg = null;

  const frames = sseText.split('\n\n').filter(Boolean);
  for (const frame of frames) {
    const trimmed = frame.trim();
    if (!trimmed.startsWith('data:')) continue;
    let evt;
    try { evt = JSON.parse(trimmed.slice(5).trim()); } catch { continue; }

    if (evt.runId) runId = evt.runId;
    // BUG: only checks camelCase, but Tinyfish sends snake_case
    if (evt.streamingUrl) streamingUrl = evt.streamingUrl;
    if (evt.purpose) purpose = evt.purpose;
    if (evt.type === 'COMPLETE') {
      const rj = evt.resultJson || {};
      if (rj.parsed) { try { result = JSON.parse(rj.parsed); } catch { result = rj.parsed; } }
      else if (rj.input) { try { result = JSON.parse(rj.input); } catch { result = rj.input; } }
      else if (evt.result) result = evt.result;
    }
    if (evt.type === 'ERROR') errorMsg = evt.message || 'Tinyfish error';
  }
  return { streamingUrl, runId, purpose, result, errorMsg };
}

// --- Test data (matches real Tinyfish API SSE output) ---
const TINYFISH_SSE_SNAKE_CASE = [
  'data: {"type":"STARTED","run_id":"run_abc123","timestamp":"2026-04-20T01:00:00Z"}',
  '',
  'data: {"type":"STREAMING_URL","run_id":"run_abc123","streaming_url":"https://stream.tinyfish.ai/live/run_abc123","timestamp":"2026-04-20T01:00:01Z"}',
  '',
  'data: {"type":"PROGRESS","run_id":"run_abc123","purpose":"Navigating to target page","timestamp":"2026-04-20T01:00:02Z"}',
  '',
  'data: {"type":"PROGRESS","run_id":"run_abc123","purpose":"Clicking submit button","timestamp":"2026-04-20T01:00:05Z"}',
  '',
  'data: {"type":"COMPLETE","run_id":"run_abc123","status":"COMPLETED","result":{"submitted":true},"timestamp":"2026-04-20T01:00:10Z"}',
  '',
].join('\n');

// Legacy camelCase format (for backwards compat)
const TINYFISH_SSE_CAMEL_CASE = [
  'data: {"type":"STARTED","runId":"run_xyz789","timestamp":"2026-04-20T01:00:00Z"}',
  '',
  'data: {"streamingUrl":"https://stream.tinyfish.ai/live/run_xyz789"}',
  '',
  'data: {"type":"PROGRESS","runId":"run_xyz789","purpose":"Filling form fields"}',
  '',
  'data: {"type":"COMPLETE","runId":"run_xyz789","resultJson":{"parsed":"{\\"ok\\":true}"}}',
  '',
].join('\n');

describe('Tinyfish SSE parsing', () => {
  describe('broken version (camelCase only)', () => {
    test('fails to extract streaming_url from snake_case events', () => {
      const { streamingUrl } = parseSSEEventsBroken(TINYFISH_SSE_SNAKE_CASE);
      // This is the BUG — streamingUrl is null because field was snake_case
      assert.equal(streamingUrl, null);
    });

    test('works only with legacy camelCase events', () => {
      const { streamingUrl } = parseSSEEventsBroken(TINYFISH_SSE_CAMEL_CASE);
      assert.equal(streamingUrl, 'https://stream.tinyfish.ai/live/run_xyz789');
    });
  });

  describe('fixed version (handles both cases)', () => {
    test('extracts streaming_url from snake_case events', () => {
      const { streamingUrl, runId, purpose } = parseSSEEvents(TINYFISH_SSE_SNAKE_CASE);
      assert.equal(streamingUrl, 'https://stream.tinyfish.ai/live/run_abc123');
      assert.equal(runId, 'run_abc123');
      assert.equal(purpose, 'Clicking submit button');
    });

    test('still works with legacy camelCase events', () => {
      const { streamingUrl, runId } = parseSSEEvents(TINYFISH_SSE_CAMEL_CASE);
      assert.equal(streamingUrl, 'https://stream.tinyfish.ai/live/run_xyz789');
      assert.equal(runId, 'run_xyz789');
    });

    test('extracts result from COMPLETE event', () => {
      const { result } = parseSSEEvents(TINYFISH_SSE_SNAKE_CASE);
      assert.deepEqual(result, { submitted: true });
    });

    test('extracts parsed resultJson', () => {
      const { result } = parseSSEEvents(TINYFISH_SSE_CAMEL_CASE);
      assert.deepEqual(result, { ok: true });
    });

    test('handles ERROR events', () => {
      const errSSE = 'data: {"type":"ERROR","message":"Timeout waiting for page"}\n\n';
      const { errorMsg } = parseSSEEvents(errSSE);
      assert.equal(errorMsg, 'Timeout waiting for page');
    });
  });
});
