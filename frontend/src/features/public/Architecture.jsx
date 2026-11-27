import { Fragment } from 'react'

// Section 06: how spans move. Two lanes into one ClickHouse, PostgreSQL beside
// the API (docs/frontend/landing-spec.md §3, row 7). From 1280 px it is one CSS
// grid; below it the lanes stack. Facts only: no numbers or timings.

// A break opportunity after each '/', '.' and '_', so paths and names wrap at segments.
const paths = text => text.split(/(?<=[/._])/).map((part, index, parts) => <Fragment key={index}>{part}{index < parts.length - 1 && <wbr/>}</Fragment>)

function Node({ name, detail, col, span = 1, className = '' }) {
  return <li className={`lp-node ${className}`} style={{ '--col': col, '--span': span }}>
    <strong>{name}</strong>
    <span className="lp-node-detail">{paths(detail)}</span>
  </li>
}

// `edge`: 'in' or 'out' when the connector meets the dashed API group, so its label clears the border.
function Connector({ label, col, span = 1, edge }) {
  return <li className="lp-conn" data-edge={edge} style={{ '--col': col, '--span': span }}>
    <span className="lp-conn-label">{label}</span>
    <span className="lp-conn-line" aria-hidden="true"/>
  </li>
}

export default function Architecture() {
  return <div className="lp-arch">
    <div className="lp-arch-grid">
      <span className="lp-api-group" aria-hidden="true"><span>one FastAPI app</span></span>

      <div className="lp-lane" data-lane="write">
        <p className="lp-lane-name">write</p>
        <ol aria-label="Write path">
          <Node col={2} name="Agent + SDK" detail="TraceSession"/>
          <Connector col={3} edge="in" label="HTTPS · Bearer API key"/>
          <Node col={4} name="Ingest API" detail="/api/v1/traces"/>
          <Connector col={5} edge="out" label="publish"/>
          <Node col={6} name="Kafka" detail="agentdbg.traces.v1"/>
          <Connector col={7} label="consume"/>
          <Node col={8} name="Trace writer" detail="Kafka consumer"/>
          <Connector col={9} label="insert"/>
          <Node col={10} name="ClickHouse" detail="telemetry_spans" className="lp-node-store"/>
        </ol>
      </div>

      <div className="lp-lane" data-lane="read">
        <p className="lp-lane-name">read</p>
        <ol aria-label="Read path">
          <Node col={2} name="Web UI" detail="React"/>
          <Connector col={3} edge="in" label="session cookie"/>
          <Node col={4} name="Read API" detail="/api/v1/projects/…"/>
          <Connector col={5} span={5} edge="out" label="SQL"/>
          <Node col={10} name="ClickHouse" detail="the same node as above" className="lp-node-ref lp-stack-only"/>
        </ol>
      </div>

      <div className="lp-lane" data-lane="side">
        <p className="lp-lane-name">side</p>
        <ol aria-label="Accounts">
          <Node col={4} name="Ingest API + Read API" detail="the same app as above" className="lp-node-ref lp-stack-only"/>
          <Connector col={4} label="user lookup: key hash, session user_id"/>
          <Node col={4} span={3} name="PostgreSQL" detail="Accounts and API key hashes. Spans never go here." className="lp-node-db"/>
        </ol>
      </div>
    </div>

    <dl className="lp-facts lp-arch-notes">
      <div><dt>Kafka</dt><dd>The agent never waits on ClickHouse; a writer restart loses nothing.</dd></div>
      <div><dt>ClickHouse</dt><dd>Column store for time-range scans of spans.</dd></div>
      <div><dt>PostgreSQL</dt><dd>Accounts only.</dd></div>
    </dl>
  </div>
}
