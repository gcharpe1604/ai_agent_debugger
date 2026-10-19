// Authored Milestone 1 sample records. Not emitted telemetry or a wire schema.
export const projects = Object.freeze([
  { id: 'agent-examples', name: 'Agent examples', environment: 'Development', initial: 'A' },
  { id: 'sandbox', name: 'Sandbox', environment: 'Development', initial: 'S' },
  { id: 'new-integration', name: 'New integration', environment: 'Development', initial: 'N' },
])

const record = (id, name, time, durationMs, traceId, service, extras = {}) => Object.freeze({
  id: `R-${id}`, projectId: 'agent-examples', name, startedAt: `2026-10-15T${time}Z`,
  durationMs, traceId, service, outcome: 'Completed', completeness: 'Complete',
  recordedErrorCount: 0, investigation: 'Completed', findingCount: 0, recovered: false,
  ...extras,
})

export const runs = Object.freeze([
  record(1042, 'refund-policy-review', '10:42:18', 4284, '7b83c2d94e1a4f0e9a6710c24d86b519', 'refund-agent', { findingCount: 1 }),
  record(1041, 'refund-eligibility-check', '10:39:04', 3176, 'c4168f27a9534b1e86d0fa320b57ec14', 'refund-agent', { findingCount: 1 }),
  record(1040, 'order-status-lookup', '10:36:52', 2418, 'a9e5d271604b4c8fb38a16d20c79e543', 'refund-agent', { recordedErrorCount: 1, recovered: true }),
  record(1039, 'workspace-recovery-answer', '10:31:27', 6812, '5d20f89c731a4e62b14c0958e7a306df', 'novacloud-rag', { completeness: 'Partial' }),
  record(1038, 'inventory-availability-check', '10:26:10', 1428, 'ef398a6027d14b9c85a60d319c47e2b1', 'fulfillment-agent', { outcome: 'Failed', recordedErrorCount: 1, investigation: 'Failed', findingCount: null }),
  record(1037, 'plan-change-policy-answer', '10:20:43', 5106, '2a6e970bd4184c83b0917d63fe25a940', 'novacloud-rag'),
  record(1036, 'field-station-research-brief', '10:14:06', 8440, '94d21fa608b34e97ac165b20d873cf49', 'meridian-research', { investigation: 'Not requested', findingCount: null }),
  record(1035, 'order-fulfillment-validation', '10:09:11', 3872, 'b8064c13e2594f0d97a1346c50eb28d7', 'fulfillment-agent'),
  record(2042, 'sandbox-policy-check', '10:44:00', 1832, '24625366085e44858d41989466713c01', 'policy-agent', { projectId: 'sandbox', investigation: 'Not requested', findingCount: null }),
  record(2041, 'sandbox-document-answer', '10:28:00', 4100, '24625366085e44858d41989466713c02', 'document-agent', { projectId: 'sandbox', completeness: 'Partial', investigation: 'Skipped', findingCount: null }),
  record(2040, 'sandbox-catalog-lookup', '10:12:00', 720, '24625366085e44858d41989466713c03', 'catalog-agent', { projectId: 'sandbox', outcome: 'Unknown', completeness: 'Unknown', investigation: 'Pending', findingCount: null, recordedErrorCount: null }),
])

// These are supplied error-operation group counts from the approved fixtures.
// They are not recomputed from child-span statuses. Production units await approval.
export const sampleWindow = { start: '2026-10-15T09:00:00Z', end: '2026-10-15T11:00:00Z' }
