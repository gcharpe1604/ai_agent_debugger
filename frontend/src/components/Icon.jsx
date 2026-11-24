import {
  ArrowLeft, ArrowLeftRight, ArrowRight, Bot, Calendar, Check, ChevronDown, ChevronRight, ChevronUp, ChevronsUpDown, CircleAlert,
  Clock, Code, Columns3, Copy, Cpu, Database, Diamond, Download, Ellipsis, ExternalLink, Eye, EyeOff, FileSearch, FileText,
  Funnel, GitBranch, House, IndentIncrease, Info, Keyboard, KeyRound, Layers, ListTree, Lock, LogOut, Monitor, Moon, PanelLeft, PanelRight, Pin,
  Play, RefreshCw, RotateCcw, Rows3, Rows4, Search, Settings, Shapes, Sun, Timer, User, Wrench, X,
} from 'lucide-react'

// One icon set (Lucide), one size and stroke. Callers keep using names, so the
// set can change without touching them.
const icons = {
  // Span types; coloured by their --type-* token (see .icon[data-span-type]).
  run: Play, agent: Bot, model: Cpu, tool: Wrench, retrieval: FileSearch, api: ArrowLeftRight, state: Database, custom: Diamond,
  chevron: ChevronRight, close: X, pin: Pin, retry: RotateCcw, branch: GitBranch, runs: ListTree, panel: PanelRight,
  setup: Code, settings: Settings, search: Search, refresh: RefreshCw, error: CircleAlert, check: Check, copy: Copy,
  arrow: ArrowRight, back: ArrowLeft, filter: Funnel, theme: Monitor, eye: Eye, 'eye-off': EyeOff, lock: Lock,
  download: Download, external: ExternalLink, docs: FileText, user: User, key: KeyRound, home: House, info: Info,
  'panel-left': PanelLeft, 'chevron-down': ChevronDown, up: ChevronUp, down: ChevronDown, columns: Columns3,
  rows: Rows3, 'rows-compact': Rows4, keyboard: Keyboard, clock: Clock, 'sign-out': LogOut, sun: Sun, moon: Moon,
  'chevrons-up-down': ChevronsUpDown, more: Ellipsis, calendar: Calendar, timer: Timer, layers: Layers, depth: IndentIncrease, shapes: Shapes,
}
const spanTypes = new Set(['run', 'agent', 'model', 'tool', 'retrieval', 'api', 'state', 'custom'])

export default function Icon({ name }) {
  const Glyph = icons[name] || ListTree
  return <Glyph className="icon" size={16} strokeWidth={1.75} aria-hidden="true" data-span-type={spanTypes.has(name) ? name : undefined}/>
}
