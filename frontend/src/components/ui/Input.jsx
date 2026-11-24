import Icon from '../Icon.jsx'
import { cx } from './cx.js'

// A 32 px text input. With `icon`, the icon sits inside the field on the left.
export default function Input({ icon, className, ref, ...props }) {
  if (!icon) return <input ref={ref} className={cx('input', className)} {...props}/>
  return <span className={cx('input-group', className)}><Icon name={icon}/><input ref={ref} className="input" {...props}/></span>
}
