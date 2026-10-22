import { Component, Fragment } from 'react'

// Last-resort containment for an unexpected adapter value/render failure.
// No payload, exception text or stack is exposed; retry remounts the read view.
export default class ReadBoundary extends Component {
  state = { failed: false, revision: 0 }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.notice?.focus({ preventScroll: true }) }
  render() {
    if (this.state.failed) return <section className="boundary" role="alert" tabIndex="-1" ref={element => { this.notice = element }}><h1>View unavailable</h1><p>The supplied data could not be displayed safely. Retry the read or return to Runs.</p><button className="button" onClick={() => this.setState(state => ({ failed: false, revision: state.revision + 1 }))}>Retry view</button><a className="button" href={this.props.back}>Back to Runs</a></section>
    return <Fragment key={this.state.revision}>{this.props.children}</Fragment>
  }
}
