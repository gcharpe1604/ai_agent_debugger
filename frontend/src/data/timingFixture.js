// Deliberately authored timing-quality study. Not captured telemetry or an API schema.
const leaf = (key, name, start, end, duration) => ({ key, name, parent: 'root', id: `aa000008${key.padStart(8, '0')}`, type: 'tool', status: 'OK', start, end, duration, input: { study: key }, output: { recorded: true }, attributes: { 'sample.study': 'timing-quality' } })
export const timingFixture = {
  traceId: 'aa0000087b3d4e519cfa81d20e347a65', name: 'timing-quality-study', service: 'sample-timing', duration: 1000,
  quality: 'Authored timing study: zero, overlapping, missing and invalid intervals; two operations lie outside reported run bounds.',
  spans: [
    { key: 'root', parent: null, id: 'aa00000800000001', name: 'timing-quality-study', type: 'run', status: 'OK', start: 0, end: 1000, duration: 1000, input: { sample: true }, output: null },
    leaf('2', 'recorded-zero-duration-checkpoint', 0, 0, 0),
    leaf('3', 'concurrent-catalog-read', 100, 500, 400),
    leaf('4', 'concurrent-policy-read', 250, 650, 400),
    leaf('5', 'start-not-captured', null, 750, null),
    leaf('6', 'reversed-recorded-interval', 500, 450, -50),
    leaf('7', 'outside-reported-end', 1100, 1200, 100),
    leaf('8', 'before-reported-origin', -200, -100, 100),
  ],
}
