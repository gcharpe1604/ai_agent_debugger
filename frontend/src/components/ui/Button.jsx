import { cx } from './cx.js'

// variant: 'default' (outlined), 'solid' (primary) or 'ghost' (no border).
// size: 'default' (32 px high) or 'icon' (32 × 32, label in aria-label).
export default function Button({ variant = 'default', size = 'default', className, type = 'button', ref, ...props }) {
  return <button ref={ref} type={type} className={cx('button', variant !== 'default' && variant, size === 'icon' && 'icon-only', className)} {...props}/>
}
