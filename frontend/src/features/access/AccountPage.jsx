import { useEffect, useRef, useState } from 'react'
import { accountHref, safeReturn, runsHref } from '../../app/routes.jsx'
import { failureKind } from '../../data/accessAdapters.js'
import { useTheme } from '../../app/preferences.js'
import AccessState from './AccessState.jsx'
import Icon from '../../components/Icon.jsx'
import './access.css'

function PasswordField({ id, label, value, onChange, visible, onToggle, busy, error, inputRef, autocomplete }) {
  const action = `${visible ? 'Hide' : 'Show'} ${id === 'confirm-password' ? 'confirm password' : 'password'}`
  return <div className="form-field"><label htmlFor={id}>{label}</label><div className="password-field" data-invalid={!!error}>
    <input ref={inputRef} id={id} type={visible ? 'text' : 'password'} autoComplete={autocomplete} required value={value} readOnly={busy} onChange={onChange} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined}/>
    <button type="button" className="password-toggle" disabled={busy} aria-label={action} aria-controls={id} aria-pressed={visible} title={action} onClick={onToggle}><Icon name={visible ? 'eye-off' : 'eye'}/></button>
  </div>{error && <p id={`${id}-error`} className="field-error">{error}</p>}</div>
}

export default function AccountPage({ route, adapter }) {
  const target = safeReturn(new URLSearchParams(route.search).get('returnTo'))
  const register = route.account === 'register'
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [visible, setVisible] = useState(false)
  const [step, setStep] = useState(1), [name, setName] = useState(''), [username, setUsername] = useState('')
  const [confirmation, setConfirmation] = useState(''), [confirmationVisible, setConfirmationVisible] = useState(false), [agreed, setAgreed] = useState(false)
  const [errors, setErrors] = useState({}), [message, setMessage] = useState(''), [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState(null)
  const main = useRef(null), emailInput = useRef(null), passwordInput = useRef(null), active = useRef(true), submitting = useRef(false), controller = useRef(null)
  const nameInput = useRef(null), usernameInput = useRef(null), confirmationInput = useRef(null), termsInput = useRef(null)
  const theme = useTheme()
  useEffect(() => { if (route.account === 'login' || route.account === 'register') main.current?.focus(); document.title = `${register ? 'Register' : route.account === 'login' ? 'Sign in' : route.account === 'session-expired' ? 'Session expired' : 'Access denied'} · Agent Debugger`; active.current = true; return () => { active.current = false; controller.current?.abort() } }, [register, route.account])
  useEffect(() => { if (register) (step === 1 ? nameInput : usernameInput).current?.focus() }, [register, step])
  useEffect(() => { if (register) document.title = `Step ${step} of 2: Create an account · Agent Debugger` }, [register, step])
  function back() {
    setStep(1); setPassword(''); setConfirmation(''); setVisible(false); setConfirmationVisible(false); setAgreed(false); setErrors({}); setMessage('')
  }
  async function submit(event) {
    event.preventDefault()
    if (submitting.current) return
    const next = {}
    if (register && step === 1 && !name.trim()) next.name = 'Enter your name.'
    if (!register || step === 1) {
      if (!email.trim()) next.email = 'Enter your email address.'
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = 'Enter a valid email address.'
    }
    if (!register || step === 2) {
      if (register && !username.trim()) next.username = 'Enter a username.'
      if (!password) next.password = 'Enter your password.'
      if (register) {
        if (!confirmation) next.confirmation = 'Confirm your password.'
        else if (password !== confirmation) next.confirmation = 'Passwords do not match.'
        if (!agreed) next.terms = 'Accept the Terms and Conditions to continue.'
      }
    }
    setErrors(next); setMessage('')
    const fields = { name: nameInput, email: emailInput, username: usernameInput, password: passwordInput, confirmation: confirmationInput, terms: termsInput }
    if (Object.keys(next).length) { fields[Object.keys(next)[0]].current?.focus(); return }
    if (register && step === 1) { setStep(2); return }
    submitting.current = true; setBusy(true); controller.current = new AbortController()
    try {
      // In-process form adapter only; these fields do not define a FastAPI wire contract.
      await adapter[register ? 'register' : 'signIn']({ ...(register ? { name: name.trim(), username: username.trim() } : {}), email: email.trim(), password, signal: controller.current.signal })
      // No approved session/completion contract yet: never interpret a fulfilled call as authorization.
      if (active.current) setMessage('Account access is not connected. No signed-in session has been established.')
    } catch (error) {
      if (!active.current) return
      const kind = failureKind(error)
      if (kind === 'expired' || kind === 'forbidden') setFailure(kind)
      else setMessage(kind === 'disconnected' ? `${register ? 'Registration' : 'Authentication'} is not connected in this preview. No credentials were sent.` : `Could not ${register ? 'register' : 'sign in'}. Try again. Your password has been cleared.`)
    } finally {
      submitting.current = false
      if (active.current) { setPassword(''); setConfirmation(''); setVisible(false); setConfirmationVisible(false); setBusy(false) }
    }
  }
  const state = failure || (route.account === 'session-expired' ? 'expired' : route.account === 'access-denied' ? 'forbidden' : null)
  return <div className="account-shell">
    <a className="skip-link" href="#account-content" onClick={event => { event.preventDefault(); main.current?.focus() }}>Skip to content</a>
    <header className="account-header"><a className="account-brand" href={runsHref('agent-examples')}><span className="brand-mark"><Icon name="branch"/></span>Agent Debugger</a><div className="account-utilities"><label className="sr-only" htmlFor="account-appearance">Appearance</label><select id="account-appearance" value={theme.preference} onChange={event => theme.setPreference(event.target.value)}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select></div></header>
    <main id="account-content" ref={main} tabIndex="-1" className="account-main" data-registration={register && !state}>{state ? <AccessState kind={state} target={target}/> : <section className="account-form" aria-labelledby="account-title">
      <h1 id="account-title">{register ? 'Create an account' : 'Sign in'}</h1>
      <p className="account-description">{register ? step === 1 ? 'Start with your name and email.' : <>Create credentials for <strong className="registration-email">{email.trim()}</strong>.</> : 'Continue to your projects and executions.'}</p>
      {register && <>
        <ol className="registration-progress" aria-label="Registration steps">
          <li aria-current={step === 1 ? 'step' : undefined} data-complete={step > 1}><span className="step-number" aria-hidden="true">{step > 1 ? <Icon name="check"/> : '1'}</span>Your details<span className="sr-only">{step > 1 ? ', completed' : ', current step'}</span></li>
          <li aria-current={step === 2 ? 'step' : undefined}><span className="step-number" aria-hidden="true">2</span>Credentials{step === 2 && <span className="sr-only">, current step</span>}</li>
        </ol>
        <span className="sr-only" role="status">Step {step} of 2</span>
      </>}
      <form noValidate onSubmit={submit} aria-busy={busy}>
        {register && step === 1 && <div className="form-field"><label htmlFor="name">Name</label><input ref={nameInput} id="name" autoComplete="name" required value={name} onChange={e => setName(e.target.value)} aria-invalid={!!errors.name} aria-describedby={errors.name ? 'name-error' : undefined}/>{errors.name && <p id="name-error" className="field-error">{errors.name}</p>}</div>}
        {(!register || step === 1) && <div className="form-field"><label htmlFor="email">Email</label><input ref={emailInput} id="email" type="email" autoComplete={register ? 'email' : 'username'} autoCapitalize="none" spellCheck={false} inputMode="email" placeholder="you@example.com" required value={email} readOnly={busy} onChange={e => setEmail(e.target.value)} aria-invalid={!!errors.email} aria-describedby={errors.email ? 'email-error' : undefined}/>{errors.email && <p id="email-error" className="field-error">{errors.email}</p>}</div>}
        {register && step === 2 && <div className="form-field"><label htmlFor="username">Username</label><input ref={usernameInput} id="username" autoComplete="username" autoCapitalize="none" spellCheck={false} required value={username} readOnly={busy} onChange={e => setUsername(e.target.value)} aria-invalid={!!errors.username} aria-describedby={errors.username ? 'username-error' : undefined}/>{errors.username && <p id="username-error" className="field-error">{errors.username}</p>}</div>}
        {(!register || step === 2) && <PasswordField id="password" label="Password" value={password} onChange={e => setPassword(e.target.value)} visible={visible} onToggle={() => setVisible(value => !value)} busy={busy} error={errors.password} inputRef={passwordInput} autocomplete={register ? 'new-password' : 'current-password'}/>}
        {register && step === 2 && <>
          <PasswordField id="confirm-password" label="Confirm password" value={confirmation} onChange={e => setConfirmation(e.target.value)} visible={confirmationVisible} onToggle={() => setConfirmationVisible(value => !value)} busy={busy} error={errors.confirmation} inputRef={confirmationInput} autocomplete="new-password"/>
          <div className="registration-agreement"><label className="registration-terms"><input ref={termsInput} type="checkbox" required disabled={busy} checked={agreed} onChange={e => setAgreed(e.target.checked)} aria-invalid={!!errors.terms} aria-describedby={errors.terms ? 'terms-error' : undefined}/><span>I agree to the Terms and Conditions</span></label>{errors.terms && <p id="terms-error" className="field-error">{errors.terms}</p>}</div>
        </>}
        {message && <p className="form-error" role="alert">{message}</p>}
        <div className={register && step === 2 ? 'registration-actions' : undefined}>
          {register && step === 2 && <button type="button" className="button" onClick={back} disabled={busy}><Icon name="back"/>Back</button>}
          <button className="button solid account-submit" disabled={busy}>{busy ? register ? 'Creating account…' : 'Signing in…' : register ? step === 1 ? 'Continue' : 'Create account' : 'Sign in'}</button>
        </div>
        <span className="sr-only" role="status">{busy ? register ? 'Submitting registration' : 'Submitting sign in' : ''}</span>
      </form>
      <div className="account-links"><span>{register ? 'Already have an account?' : 'New to Agent Debugger?'} <a href={accountHref(register ? 'login' : 'register', target)}>{register ? 'Sign in' : 'Register'}</a></span><a className="sample-entry" href={runsHref('agent-examples')}>Explore sample runs<Icon name="arrow"/></a></div>
    </section>}</main>
    <footer className="account-footer">Development preview · Authentication is not connected.{register && ' Terms are not published yet.'}</footer>
  </div>
}
