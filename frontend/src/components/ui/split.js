export const SPLIT_STEP = 16

// Next width of the right-hand pane for a key on the divider, or undefined.
// Left widens the right pane, Right narrows it; Home/End jump to the limits.
export function splitKeyWidth(key, width, min, max) {
  const next = { ArrowLeft: width + SPLIT_STEP, ArrowRight: width - SPLIT_STEP, Home: min, End: max }[key]
  return next === undefined ? undefined : Math.max(min, Math.min(max, next))
}
