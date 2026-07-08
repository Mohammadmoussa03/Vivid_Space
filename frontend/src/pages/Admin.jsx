import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import logoColor from '../assets/vividspace-logo.png';
import { useAuth } from '../context/AuthContext';
import { MS, TONES, useVW, apiError, buildCalendar, fmtDate } from '../lib/ms';
import {
  adminDashboard, adminUsers, adminApproveUser, adminRejectUser, adminSetUserActive,
  adminUserMembership, adminSetUserMembership, adminApproveScheduleChange, adminRejectScheduleChange,
  adminReservations, adminApproveReservation, adminCancelReservation, adminTogglePaid,
  adminApproveChange, adminRejectChange,
  adminSpaces, adminCreateSpace, adminUpdateSpace, adminToggleSpace, adminDeleteSpace,
  adminPackages, adminCreatePackage, adminUpdatePackage, adminDeletePackage,
  adminDuplicatePackage, adminToggleArchivePackage, adminCategories,
  adminUploadImage,
  adminFaqs, adminCreateFaq, adminUpdateFaq, adminDeleteFaq,
  adminPromoCodes, adminCreatePromo, adminUpdatePromo, adminDeletePromo,
  adminTours, adminUpdateTour, adminDeleteTour,
  adminCustomizations, adminUpdateCustomization, adminDeleteCustomization,
  adminBlockedSlots, adminCreateBlockedSlot, adminDeleteBlockedSlot,
  adminContent, adminSaveContent, adminSettings, adminSaveSettings,
} from '../lib/services';

const NAV = [
  { key: 'overview', label: 'Overview', icon: '◧' },
  { key: 'users', label: 'Users', icon: '◔' },
  { key: 'reservations', label: 'Reservations', icon: '▤' },
  { key: 'spaces', label: 'Spaces', icon: '◈' },
  { key: 'packages', label: 'Packages', icon: '❏' },
  { key: 'faq', label: 'FAQ', icon: '?' },
  { key: 'promos', label: 'Promo codes', icon: '%' },
  { key: 'tours', label: 'Tour requests', icon: '⚑' },
  { key: 'customizations', label: 'Custom requests', icon: '◇' },
  { key: 'calendar', label: 'Calendar blocking', icon: '▣' },
  { key: 'content', label: 'Website content', icon: '✎' },
];
const TITLES = {
  overview: 'Dashboard overview', users: 'User management', reservations: 'Reservation management',
  spaces: 'Space management', packages: 'Package management',
  faq: 'FAQ management', promos: 'Promo code management', tours: 'Tour requests',
  customizations: 'Custom package requests',
  calendar: 'Calendar blocking', content: 'Website content',
};
// Sections where the header "+ New" button applies.
const CREATABLE = { spaces: 'space', packages: 'package', faq: 'faq', promos: 'promo', calendar: 'block' };

const card = { background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 16 };
const pill = (bg, color, text) => <span style={{ background: bg, color, fontSize: 12, fontWeight: 600, padding: '4px 11px', borderRadius: 9999 }}>{text}</span>;
const smallBtn = (variant = 'ghost') => {
  const base = { fontFamily: MS.sans, fontSize: 12.5, fontWeight: 600, padding: '6px 12px', borderRadius: 9999, cursor: 'pointer', flex: '0 0 auto', whiteSpace: 'nowrap' };
  if (variant === 'green') return { ...base, background: MS.green, color: '#fff', border: 'none' };
  if (variant === 'danger') return { ...base, background: 'none', border: '1px solid rgba(168,90,74,0.4)', color: MS.red };
  return { ...base, background: 'none', border: `1px solid ${MS.line}`, color: MS.ink };
};
const th = { fontSize: 12, letterSpacing: '0.06em', textTransform: 'uppercase', color: MS.faint, fontWeight: 600 };

const matches = (row, q) => !q || JSON.stringify(row).toLowerCase().includes(q.toLowerCase());

export default function Admin() {
  const nav = useNavigate();
  const vw = useVW();
  const { user, isAuthed, role, logout } = useAuth();
  const [view, setView] = useState('overview');
  const [query, setQuery] = useState('');
  const [modal, setModal] = useState(null); // { type, initial }
  const [drawer, setDrawer] = useState(false); // mobile sidebar drawer

  // Below this width the fixed sidebar becomes a slide-in drawer.
  const mobile = vw < 900;

  useEffect(() => {
    if (!isAuthed) nav('/');
    else if (role && role !== 'admin') nav('/');
  }, [isAuthed, role, nav]);

  useEffect(() => { setQuery(''); }, [view]);
  useEffect(() => { if (!mobile) setDrawer(false); }, [mobile]);

  const openNew = () => { const t = CREATABLE[view]; if (t) setModal({ type: t, initial: null }); };

  const adminName = user?.full_name || `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || 'Admin';

  return (
    <div style={{ display: 'flex', minHeight: '100vh', fontFamily: MS.sans, background: MS.bg, color: MS.ink }}>
      {/* Drawer overlay (mobile only) */}
      {mobile && drawer && (
        <div onClick={() => setDrawer(false)} style={{ position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(20,18,16,0.5)', backdropFilter: 'blur(2px)', animation: 'ms-fade 200ms ease-out both' }} />
      )}
      {/* SIDEBAR (fixed drawer on mobile, sticky column on desktop) */}
      <aside style={mobile
        ? { position: 'fixed', top: 0, left: 0, width: 246, height: '100vh', zIndex: 80, background: '#fff', borderRight: `1px solid ${MS.line}`, display: 'flex', flexDirection: 'column', transform: drawer ? 'translateX(0)' : 'translateX(-100%)', transition: 'transform 260ms ease-out', boxShadow: drawer ? '0 20px 60px rgba(20,18,16,0.28)' : 'none' }
        : { flex: '0 0 246px', background: '#fff', borderRight: `1px solid ${MS.line}`, display: 'flex', flexDirection: 'column', position: 'sticky', top: 0, height: '100vh' }}>
        <div style={{ padding: '22px 24px', borderBottom: `1px solid ${MS.line}`, display: 'flex', alignItems: 'center', gap: 10 }}>
          <img src={logoColor} alt="VividSpace" style={{ height: 42, width: 'auto', display: 'block' }} />
          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.accent, background: 'rgba(155,126,189,0.14)', padding: '3px 8px', borderRadius: 6 }}>Admin</span>
        </div>
        <nav className="adm-scroll" style={{ flex: 1, overflowY: 'auto', padding: '14px 12px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV.map((n) => {
            const on = view === n.key;
            return (
              <button key={n.key} onClick={() => { setView(n.key); setDrawer(false); }} style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%', textAlign: 'left', background: on ? 'rgba(155,126,189,0.14)' : 'transparent', border: 'none', borderRadius: 10, padding: '11px 14px', fontSize: 14.5, fontWeight: on ? 600 : 500, color: on ? MS.ink : '#5A554F', cursor: 'pointer' }}>
                <span style={{ width: 18, textAlign: 'center', opacity: 0.85 }}>{n.icon}</span>
                <span>{n.label}</span>
              </button>
            );
          })}
        </nav>
        <div style={{ padding: '16px 18px', borderTop: `1px solid ${MS.line}`, display: 'flex', alignItems: 'center', gap: 11 }}>
          <span style={{ width: 36, height: 36, borderRadius: 9999, background: MS.ink, color: MS.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: MS.serif, fontWeight: 700, fontSize: 15 }}>{(adminName[0] || 'A').toUpperCase()}</span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <p style={{ fontSize: 13.5, fontWeight: 600, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{adminName}</p>
            <p style={{ fontSize: 12, color: MS.faint, margin: '1px 0 0' }}>Administrator</p>
          </div>
          <button onClick={async () => { await logout(); nav('/'); }} title="Log out" style={{ background: 'none', border: `1px solid ${MS.line}`, borderRadius: 9, width: 32, height: 32, cursor: 'pointer', color: MS.muted }}>⏻</button>
        </div>
      </aside>

      {/* MAIN */}
      <main className="adm-scroll" style={{ flex: 1, minWidth: 0, height: '100vh', overflowY: 'auto' }}>
        <header style={{ position: 'sticky', top: 0, zIndex: 5, background: 'rgba(245,241,237,0.9)', backdropFilter: 'blur(12px)', borderBottom: `1px solid ${MS.line}`, padding: mobile ? '12px clamp(14px,4vw,24px)' : '0 clamp(18px,3vw,36px)', minHeight: 72, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
            {mobile && (
              <button onClick={() => setDrawer(true)} aria-label="Open menu" style={{ flex: '0 0 auto', width: 44, height: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: `1px solid ${MS.line}`, borderRadius: 10, cursor: 'pointer', color: MS.ink }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <line x1="3" y1="7" x2="21" y2="7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <line x1="3" y1="12" x2="21" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <line x1="3" y1="17" x2="21" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </button>
            )}
            <h1 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(19px,2.6vw,26px)', margin: 0, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{TITLES[view]}</h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: mobile ? '1 1 100%' : '0 0 auto' }}>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search…" style={{ background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 9999, padding: '9px 18px', fontSize: 14, color: MS.ink, outline: 'none', flex: mobile ? '1 1 auto' : '0 0 auto', minWidth: 0, width: mobile ? 'auto' : 'clamp(120px,20vw,220px)' }} />
            {CREATABLE[view] && <button onClick={openNew} style={{ flex: '0 0 auto', background: MS.accent, color: '#fff', border: 'none', fontSize: 14, fontWeight: 600, padding: '10px 20px', borderRadius: 9999, cursor: 'pointer' }}>+ New</button>}
          </div>
        </header>

        <div style={{ padding: 'clamp(20px,3vw,36px)' }}>
          {view === 'overview' && <Overview />}
          {view === 'users' && <Users query={query} />}
          {view === 'reservations' && <Reservations query={query} />}
          {view === 'spaces' && <Spaces query={query} onEdit={(s) => setModal({ type: 'space', initial: s })} modalClosed={modal} />}
          {view === 'packages' && <Packages query={query} onEdit={(p) => setModal({ type: 'package', initial: p })} modalClosed={modal} />}
          {view === 'faq' && <Faqs query={query} onEdit={(f) => setModal({ type: 'faq', initial: f })} modalClosed={modal} />}
          {view === 'promos' && <Promos query={query} onEdit={(p) => setModal({ type: 'promo', initial: p })} modalClosed={modal} />}
          {view === 'tours' && <Tours query={query} onEdit={(t) => setModal({ type: 'tour', initial: t })} modalClosed={modal} />}
          {view === 'customizations' && <Customizations query={query} onEdit={(c) => setModal({ type: 'customization', initial: c })} modalClosed={modal} />}
          {view === 'calendar' && <Calendar modalClosed={modal} onNew={() => setModal({ type: 'block', initial: null })} />}
          {view === 'content' && <Content />}
        </div>
      </main>

      {modal && <RecordModal state={modal} onClose={() => setModal(null)} />}
    </div>
  );
}

/* ---------------- data hook ---------------- */
function useData(fn, deps = []) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const reload = useCallback(() => {
    fn().then((d) => { setData(d); setErr(''); }).catch((e) => setErr(apiError(e, 'Could not load data.')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { reload(); }, [reload]);
  return [data, reload, err];
}
const Empty = ({ text = 'Nothing here yet.' }) => <div style={{ ...card, padding: '40px 24px', textAlign: 'center', color: MS.faint, fontSize: 15 }}>{text}</div>;

/* ---------------- Overview ---------------- */
function Overview() {
  const [d] = useData(adminDashboard);
  const vw = useVW();
  if (!d) return <Empty text="Loading dashboard…" />;
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 16, marginBottom: 24 }}>
        {(d.kpis || []).map((k) => (
          <div key={k.label} style={{ ...card, padding: '22px 24px' }}>
            <p style={{ fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase', color: MS.faint, margin: '0 0 14px' }}>{k.label}</p>
            <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 32, margin: '0 0 8px' }}>{k.value}</p>
            {k.trend && <span style={{ fontSize: 13, fontWeight: 600, color: k.trendUp ? MS.green : MS.red }}>{k.trendUp ? '▲' : '▼'} {k.trend}</span>}
          </div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: vw < 768 ? '1fr' : 'minmax(0,1.6fr) minmax(0,1fr)', gap: 16, marginBottom: 24 }}>
        <div style={{ ...card, padding: 24 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: '#5A554F', margin: '0 0 22px' }}>Bookings by month</p>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, height: 180 }}>
            {(d.chart || []).map((b) => (
              <div key={b.label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, height: '100%', justifyContent: 'flex-end' }}>
                <div style={{ width: '100%', maxWidth: 40, background: MS.accent, borderRadius: '8px 8px 0 0', height: `${Math.max(4, b.v)}%` }} title={`${b.count} bookings`} />
                <span style={{ fontSize: 12, color: MS.faint }}>{b.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{ ...card, padding: 24 }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: '#5A554F', margin: '0 0 22px' }}>Occupancy by space</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {(d.occupancy || []).map((o) => (
              <div key={o.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13.5, marginBottom: 7 }}><span>{o.name}</span><span style={{ fontWeight: 600 }}>{o.pct}</span></div>
                <div style={{ height: 8, background: '#EDE7E0', borderRadius: 9999, overflow: 'hidden' }}><div style={{ height: '100%', background: MS.accent2, borderRadius: 9999, width: o.pct }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div style={{ ...card, padding: 24 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: '#5A554F', margin: '0 0 18px' }}>Recent activity</p>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {(d.activity || []).map((a, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 0', borderTop: i ? `1px solid ${MS.line2}` : 'none' }}>
              <span style={{ width: 34, height: 34, flex: '0 0 auto', borderRadius: 9999, background: 'rgba(155,126,189,0.14)', color: MS.accent, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 }}>•</span>
              <span style={{ flex: 1, fontSize: 14.5 }}>{a.text}</span>
              <span style={{ fontSize: 13, color: MS.faint, whiteSpace: 'nowrap' }}>{a.time}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

/* ---------------- Users ---------------- */
const userStatus = (u) => {
  if (!u.is_active) return u.is_approved ? 'Deactivated' : 'Rejected';
  return u.is_approved ? 'Active' : 'Pending';
};
const USER_TONE = { Active: 'green', Pending: 'amber', Deactivated: 'neutral', Rejected: 'red' };
function Users({ query }) {
  const [rows, reload] = useData(() => adminUsers());
  const [filter, setFilter] = useState('All');
  const [customizeUser, setCustomizeUser] = useState(null);
  const [reviewUser, setReviewUser] = useState(null);   // member whose schedule-change review modal is open
  if (!rows) return <Empty text="Loading users…" />;
  const act = (fn) => (id) => fn(id).then(reload).catch((e) => window.alert(apiError(e) || 'Action failed.'));
  const approve = act(adminApproveUser), reject = act(adminRejectUser);
  const approveSchedule = act(adminApproveScheduleChange), rejectSchedule = act(adminRejectScheduleChange);
  const toggle = (u) => adminSetUserActive(u.id, !u.is_active).then(reload).catch(() => {});
  // Members with a package-schedule change awaiting the admin's decision.
  const pendingSchedule = rows.filter((u) => u.schedule_change_requested);
  const filtered = rows.filter((u) => {
    if (filter === 'schedule') return u.schedule_change_requested && matches(u, query);
    return (filter === 'All' || userStatus(u) === filter) && matches(u, query);
  });
  // One fixed template shared by the header and every row so columns line up
  // regardless of how many action buttons a row shows (fixed-width Actions col).
  const cols = 'minmax(180px,2fr) minmax(110px,1.2fr) 110px 110px 250px';

  return (
    <>
      {/* Prominent queue of pending package-schedule change requests. */}
      {pendingSchedule.length > 0 && (
        <div style={{ ...card, borderLeft: `4px solid ${MS.accent}`, padding: '18px 22px', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <span style={{ fontSize: 15.5, fontWeight: 700 }}>Package schedule change requests</span>
            {pill(TONES.lilac.bg, TONES.lilac.color, `${pendingSchedule.length} awaiting review`)}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {pendingSchedule.map((u) => (
              <div key={u.id} style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', justifyContent: 'space-between', background: MS.bg2, borderRadius: 12, padding: '12px 16px' }}>
                <div style={{ minWidth: 0 }}>
                  <p style={{ fontSize: 14.5, fontWeight: 600, margin: 0 }}>{u.full_name || u.email}</p>
                  <p style={{ fontSize: 12.5, color: MS.muted, margin: '2px 0 0' }}>{u.plan || '—'} · {u.schedule_change_days || 0} day{u.schedule_change_days === 1 ? '' : 's'} requested</p>
                </div>
                <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
                  <button onClick={() => setReviewUser(u)} style={smallBtn()}>Review</button>
                  <button onClick={() => approveSchedule(u.id)} style={smallBtn('green')}>Approve</button>
                  <button onClick={() => rejectSchedule(u.id)} style={smallBtn('danger')}>Reject</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap', marginBottom: 20 }}>
        {['All', 'Active', 'Pending', 'Deactivated'].map((f) => <FilterPill key={f} label={f} active={filter === f} onClick={() => setFilter(f)} />)}
        {pendingSchedule.length > 0 && <FilterPill label={`Schedule changes (${pendingSchedule.length})`} active={filter === 'schedule'} onClick={() => setFilter('schedule')} />}
      </div>
      <div style={{ ...card, overflowX: 'auto' }}>
       <div style={{ minWidth: 760 }}>
        <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 16, padding: '14px 22px', borderBottom: `1px solid ${MS.line}`, ...th }}>
          <span>Member</span><span>Plan</span><span>Status</span><span>Joined</span><span style={{ textAlign: 'right' }}>Actions</span>
        </div>
        {filtered.length === 0 && <div style={{ padding: 30, textAlign: 'center', color: MS.faint }}>No matching users.</div>}
        {filtered.map((u) => {
          const status = userStatus(u), tone = TONES[USER_TONE[status]];
          const pending = status === 'Pending';
          return (
            <div key={u.id} style={{ display: 'grid', gridTemplateColumns: cols, gap: 16, alignItems: 'center', padding: '15px 22px', borderTop: `1px solid ${MS.line2}` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
                <span style={{ width: 34, height: 34, flex: '0 0 auto', borderRadius: 9999, background: '#EDE7F3', color: '#7A5E9A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: 14 }}>{(u.full_name || u.email)[0].toUpperCase()}</span>
                <div style={{ minWidth: 0 }}>
                  <p style={{ fontSize: 14.5, fontWeight: 600, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.full_name || '—'}</p>
                  <p style={{ fontSize: 12.5, color: MS.faint, margin: '1px 0 0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.email}</p>
                </div>
              </div>
              <span style={{ fontSize: 14, minWidth: 0 }}>
                {u.plan || '—'}
                {u.schedule_change_requested && <span style={{ marginLeft: 8, display: 'inline-block' }}>{pill(TONES.lilac.bg, TONES.lilac.color, `Schedule change${u.schedule_change_days ? ` · ${u.schedule_change_days}d` : ''}`)}</span>}
              </span>
              <span>{pill(tone.bg, tone.color, status)}</span>
              <span style={{ fontSize: 14, color: MS.muted }}>{new Date(u.date_joined).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
              <div style={{ display: 'flex', gap: 7, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                {u.schedule_change_requested && (
                  <>
                    <button onClick={() => approveSchedule(u.id)} style={smallBtn('green')}>Approve change</button>
                    <button onClick={() => rejectSchedule(u.id)} style={smallBtn('danger')}>Reject</button>
                  </>
                )}
                {pending ? (
                  <>
                    <button onClick={() => approve(u.id)} style={smallBtn('green')}>Approve</button>
                    <button onClick={() => reject(u.id)} style={smallBtn('danger')}>Reject</button>
                  </>
                ) : (
                  <button onClick={() => toggle(u)} style={smallBtn()}>{u.is_active ? 'Deactivate' : 'Activate'}</button>
                )}
                <button onClick={() => setCustomizeUser(u)} style={smallBtn()}>Customize</button>
              </div>
            </div>
          );
        })}
       </div>
      </div>
      {customizeUser && (
        <CustomizeModal user={customizeUser} onClose={(changed) => { setCustomizeUser(null); if (changed) reload(); }} />
      )}
      {reviewUser && (
        <ScheduleReviewModal user={reviewUser} onClose={() => setReviewUser(null)}
          onResolved={() => { setReviewUser(null); reload(); }} />
      )}
    </>
  );
}

/* Review a member's proposed package-schedule change: current vs requested days
   per package, so the admin can approve or reject with full context. */
function ScheduleReviewModal({ user, onClose, onResolved }) {
  const [ms, setMs] = useState(null);   // null while loading, {} on error
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    adminUserMembership(user.id)
      .then((d) => setMs(d?.membership || {}))
      .catch((e) => { setErr(apiError(e, 'Could not load this request.')); setMs({}); });
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [user.id, onClose]);

  const decide = (fn) => { setBusy(true); setErr(''); fn(user.id).then(onResolved).catch((e) => { setErr(apiError(e, 'Action failed.')); setBusy(false); }); };

  // Map each package name -> {current: [dates], requested: [dates]} for a diff view.
  const norm = (list) => (list || []).filter((c) => c && !c.lifetime && c.name);
  const current = norm(ms?.custom_components);
  const requested = norm(ms?.pending_components);
  const names = Array.from(new Set([...current, ...requested].map((c) => c.name)));
  const datesFor = (list, name) => (list.find((c) => c.name === name)?.dates || []).map(String).sort();

  const col = (title, list) => (
    <div style={{ flex: '1 1 220px', minWidth: 0 }}>
      <p style={{ fontSize: 12, letterSpacing: '0.06em', textTransform: 'uppercase', color: MS.faint, fontWeight: 600, margin: '0 0 10px' }}>{title}</p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {names.map((name, i) => {
          const ds = datesFor(list, name);
          return (
            <div key={name} style={{ ...card, padding: '12px 14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: ds.length ? 8 : 0 }}>
                <span style={{ width: 10, height: 10, borderRadius: 9999, background: ALLOC_COLORS[i % ALLOC_COLORS.length], flex: '0 0 auto' }} />
                <span style={{ fontSize: 14, fontWeight: 600 }}>{name}</span>
                <span style={{ fontSize: 12.5, color: MS.faint, marginLeft: 'auto' }}>{ds.length} day{ds.length === 1 ? '' : 's'}</span>
              </div>
              {ds.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                  {ds.map((d) => <span key={d} style={{ fontSize: 11.5, color: '#3A362F', background: MS.line2, padding: '3px 8px', borderRadius: 7, whiteSpace: 'nowrap' }}>{fmtDate(d)}</span>)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 120, background: 'rgba(20,18,16,0.62)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'clamp(14px,4vw,40px)', animation: 'ms-fade 200ms ease-out both' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: MS.panel, width: 'min(720px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 20, padding: 'clamp(24px,4vw,32px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 18 }}>
          <div>
            <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 22, margin: 0 }}>Schedule change request</h3>
            <p style={{ fontSize: 13, color: MS.faint, margin: '3px 0 0' }}>{user.full_name || user.email}{ms?.display_name ? ` · ${ms.display_name}` : ''}</p>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ width: 36, height: 36, flex: '0 0 auto', borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
        </div>

        {err && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13.5, fontWeight: 500, padding: '11px 14px', borderRadius: 10, margin: '0 0 16px' }}>{err}</p>}
        {ms === null ? (
          <p style={{ color: MS.faint, fontSize: 14, padding: '24px 0' }}>Loading…</p>
        ) : !requested.length && !current.length ? (
          <p style={{ color: MS.faint, fontSize: 14 }}>No schedule details to show.</p>
        ) : (
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
            {col('Current schedule', current)}
            {col('Requested schedule', requested)}
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 24 }}>
          <button onClick={() => decide(adminApproveScheduleChange)} disabled={busy} style={{ ...smallBtn('green'), padding: '11px 22px', fontSize: 14, opacity: busy ? 0.6 : 1 }}>Approve change</button>
          <button onClick={() => decide(adminRejectScheduleChange)} disabled={busy} style={{ ...smallBtn('danger'), padding: '11px 22px', fontSize: 14, opacity: busy ? 0.6 : 1 }}>Reject</button>
          <button onClick={onClose} style={{ ...smallBtn(), padding: '11px 22px', fontSize: 14, marginLeft: 'auto' }}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

/* ---------------- Customize a member's package ---------------- */
const ALLOC_COLORS = ['#9B7EBD', '#4F8A76', '#C0844E', '#5E79A8', '#B0678E', '#6E9E52', '#A85C5C', '#7C6FB0'];
function CustomizeModal({ user, onClose }) {
  const [plans, setPlans] = useState([]);
  const [form, setForm] = useState(null); // null while loading
  const [mode, setMode] = useState('existing'); // 'existing' | 'custom'
  const [existingPlan, setExistingPlan] = useState('');
  const [alloc, setAlloc] = useState([]);     // ordered plan ids in the mix (drives colours)
  const [assign, setAssign] = useState({});   // iso day -> plan id
  const [lifetime, setLifetime] = useState({}); // plan id -> true when granted for lifetime
  const [active, setActive] = useState('');   // plan id the calendar taps assign to
  const [monthOffset, setMonthOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    Promise.all([adminPackages(true), adminUserMembership(user.id)])
      .then(([pk, ms]) => {
        const list = Array.isArray(pk) ? pk : [];
        setPlans(list);
        const m = ms?.membership;
        setMode(m?.custom_plan_name ? 'custom' : 'existing');
        setExistingPlan(m?.plan ?? (list[0]?.id ?? ''));
        // Rebuild the allocation from stored components (dated or lifetime).
        const comps = (m?.custom_components || []).filter((c) => c && c.plan != null);
        const order = [];
        const a = {};
        const life = {};
        comps.forEach((c) => {
          const pid = c.plan;
          if (!order.includes(pid)) order.push(pid);
          if (c.lifetime) life[pid] = true;
          (Array.isArray(c.dates) ? c.dates : []).forEach((d) => { a[d] = pid; });
        });
        setAlloc(order);
        setAssign(a);
        setLifetime(life);
        setActive(order[0] ?? '');
        setForm({
          custom_plan_name: m?.custom_plan_name ?? '',
          status: m?.status ?? 'active',
          monthly_hours: m?.monthly_hours ?? '',
          custom_price: m?.custom_price ?? '',
          custom_price_label: m?.custom_price_label ?? '',
        });
      })
      .catch((e) => { setErr(apiError(e, 'Could not load this member.')); setForm({}); });
  }, [user.id]);

  const set = (k, v) => setForm((s) => ({ ...s, [k]: v }));
  const planName = (pid) => plans.find((p) => String(p.id) === String(pid))?.name || 'Package';
  const colorOf = (pid) => ALLOC_COLORS[Math.max(0, alloc.indexOf(pid)) % ALLOC_COLORS.length];
  const countFor = (pid) => Object.values(assign).filter((v) => String(v) === String(pid)).length;
  const datesFor = (pid) => Object.entries(assign).filter(([, v]) => String(v) === String(pid)).map(([iso]) => iso).sort();
  const totalDays = Object.keys(assign).length;

  const addPackage = (pid) => {
    if (!pid || alloc.some((x) => String(x) === String(pid))) return;
    const id = Number(pid);
    setAlloc((a) => [...a, id]);
    setActive(id);
  };
  const removePackage = (pid) => {
    setAlloc((a) => a.filter((x) => String(x) !== String(pid)));
    setAssign((a) => Object.fromEntries(Object.entries(a).filter(([, v]) => String(v) !== String(pid))));
    setLifetime((l) => { const n = { ...l }; delete n[pid]; return n; });
    setActive((cur) => (String(cur) === String(pid) ? '' : cur));
  };
  const isLifetime = (pid) => !!lifetime[pid];
  const setDurationMode = (pid, life) => {
    setLifetime((l) => { const n = { ...l }; if (life) n[pid] = true; else delete n[pid]; return n; });
    // A lifetime package holds no specific days.
    if (life) setAssign((a) => Object.fromEntries(Object.entries(a).filter(([, v]) => String(v) !== String(pid))));
  };
  const toggleDay = (iso) => {
    if (!active || isLifetime(active)) return;
    setAssign((a) => { const n = { ...a }; if (String(n[iso]) === String(active)) delete n[iso]; else n[iso] = active; return n; });
  };

  const cal = buildCalendar(monthOffset, null);
  const monthCells = cal.cells.filter((c) => !c.empty && !c.past);
  const monthFull = monthCells.length > 0 && monthCells.every((c) => String(assign[c.iso]) === String(active));
  const toggleMonth = () => {
    if (!active || isLifetime(active)) return;
    setAssign((a) => {
      const n = { ...a };
      monthCells.forEach((c) => { if (monthFull) { if (String(n[c.iso]) === String(active)) delete n[c.iso]; } else { n[c.iso] = active; } });
      return n;
    });
  };

  const save = async () => {
    setErr('');
    let planFk = existingPlan;
    let components = [];
    if (mode === 'custom') {
      if (!String(form.custom_plan_name).trim()) { setErr('Give the custom package a name.'); return; }
      // Include packages that are lifetime or have at least one assigned day.
      const inUse = alloc.filter((pid) => isLifetime(pid) || countFor(pid) > 0);
      if (inUse.length === 0) { setErr('Add a package, then pick its days or mark it lifetime.'); return; }
      planFk = inUse[0];
      components = inUse.map((pid) => (isLifetime(pid)
        ? { plan: pid, name: planName(pid), lifetime: true, dates: [] }
        : { plan: pid, name: planName(pid), dates: datesFor(pid) }));
    } else if (!planFk) { setErr('Choose a base plan.'); return; }

    const payload = {
      plan: planFk,
      custom_plan_name: mode === 'custom' ? String(form.custom_plan_name).trim() : '',
      status: form.status,
      monthly_hours: form.monthly_hours === '' ? null : Number(form.monthly_hours),
      custom_price: form.custom_price === '' ? null : Number(form.custom_price),
      custom_price_label: form.custom_price_label || '',
      custom_components: components,
    };
    setBusy(true);
    try { await adminSetUserMembership(user.id, payload); onClose(true); }
    catch (e) { setErr(apiError(e, 'Could not save.')); setBusy(false); }
  };

  const label = (t) => <label style={{ fontSize: 13.5, fontWeight: 500, color: MS.ink }}>{t}</label>;
  const inp = { background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 10, padding: '10px 12px', fontFamily: MS.sans, fontSize: 14.5, color: MS.ink, outline: 'none', width: '100%' };
  const navBtn = (on) => ({ width: 34, height: 34, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: on ? MS.ink : '#C4BEB6', fontSize: 16, cursor: on ? 'pointer' : 'not-allowed' });
  const basePlan = plans.find((p) => String(p.id) === String(existingPlan));
  const unpicked = plans.filter((p) => !alloc.some((x) => String(x) === String(p.id)));

  return (
    <div onClick={() => onClose(false)} style={{ position: 'fixed', inset: 0, zIndex: 120, background: 'rgba(20,18,16,0.62)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'clamp(14px,4vw,40px)', animation: 'ms-fade 200ms ease-out both' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: MS.panel, width: 'min(560px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 20, padding: 'clamp(24px,4vw,32px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 6 }}>
          <div>
            <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 22, margin: 0 }}>Customize package</h3>
            <p style={{ fontSize: 13, color: MS.faint, margin: '3px 0 0' }}>{user.full_name || user.email}</p>
          </div>
          <button onClick={() => onClose(false)} aria-label="Close" style={{ width: 36, height: 36, flex: '0 0 auto', borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
        </div>
        {err && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13, fontWeight: 500, padding: '10px 14px', borderRadius: 10, margin: '14px 0 0' }}>{err}</p>}
        {!form ? (
          <p style={{ color: MS.faint, fontSize: 14, padding: '24px 0' }}>Loading…</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 18 }}>
            <div style={{ display: 'flex', gap: 8, background: MS.line2, padding: 4, borderRadius: 12 }}>
              {[['existing', 'Existing package'], ['custom', 'Custom package']].map(([v, l]) => (
                <button key={v} type="button" onClick={() => setMode(v)}
                  style={{ flex: 1, padding: '9px 10px', borderRadius: 9, border: 'none', cursor: 'pointer', fontFamily: MS.sans, fontSize: 13.5, fontWeight: 600, background: mode === v ? '#fff' : 'transparent', color: mode === v ? MS.ink : MS.faint, boxShadow: mode === v ? '0 1px 3px rgba(20,18,16,0.12)' : 'none' }}>{l}</button>
              ))}
            </div>

            {mode === 'existing' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {label('Base plan')}
                <select value={existingPlan} onChange={(e) => setExistingPlan(e.target.value)} style={inp}>
                  {plans.length === 0 && <option value="">No packages exist yet</option>}
                  {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                  {label('Package name')}
                  <input value={form.custom_plan_name} onChange={(e) => set('custom_plan_name', e.target.value)} placeholder="e.g. Northwind Bespoke" style={inp} />
                </div>

                {/* Multi-package day allocation */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                  {label('Packages in this month')}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {alloc.map((pid) => {
                      const on = String(active) === String(pid);
                      const col = colorOf(pid);
                      return (
                        <button key={pid} type="button" onClick={() => setActive(pid)}
                          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, border: `1.5px solid ${on ? col : MS.line}`, background: on ? col : '#fff', color: on ? '#fff' : MS.ink, borderRadius: 9999, padding: '8px 12px', fontSize: 13.5, fontWeight: 600, cursor: 'pointer' }}>
                          <span style={{ width: 10, height: 10, borderRadius: 9999, background: on ? '#fff' : col, flex: '0 0 auto' }} />
                          {planName(pid)}{isLifetime(pid) ? <span style={{ opacity: 0.9 }}>· ∞</span> : (countFor(pid) ? <span style={{ opacity: 0.9 }}>· {countFor(pid)}</span> : null)}
                          <span onClick={(e) => { e.stopPropagation(); removePackage(pid); }} aria-label="Remove" style={{ marginLeft: 2, opacity: 0.75, cursor: 'pointer' }}>✕</span>
                        </button>
                      );
                    })}
                    {unpicked.length > 0 && (
                      <select value="" onChange={(e) => addPackage(e.target.value)} style={{ ...inp, width: 'auto', padding: '8px 12px' }}>
                        <option value="">+ Add package…</option>
                        {unpicked.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    )}
                  </div>
                  {active && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 13, color: MS.muted }}>{planName(active)} duration:</span>
                      <div style={{ display: 'inline-flex', gap: 4, background: MS.line2, padding: 3, borderRadius: 9 }}>
                        {[['days', 'Specific days'], ['life', 'Lifetime']].map(([v, l]) => {
                          const on = (v === 'life') === isLifetime(active);
                          return (
                            <button key={v} type="button" onClick={() => setDurationMode(active, v === 'life')}
                              style={{ padding: '5px 12px', borderRadius: 7, border: 'none', cursor: 'pointer', fontFamily: MS.sans, fontSize: 12.5, fontWeight: 600, background: on ? '#fff' : 'transparent', color: on ? MS.ink : MS.faint, boxShadow: on ? '0 1px 2px rgba(20,18,16,0.12)' : 'none' }}>{l}</button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Calendar — taps colour a day for the active package */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                    {label(active ? (isLifetime(active) ? `${planName(active)} is lifetime — covers every day` : `Tap days for ${planName(active)}`) : 'Pick a package above, then tap its days')}
                    {(() => { const canDays = active && !isLifetime(active); return (
                      <button type="button" onClick={toggleMonth} disabled={!canDays} style={{ flex: '0 0 auto', background: monthFull && canDays ? MS.accent : 'transparent', color: monthFull && canDays ? '#fff' : MS.accent, border: `1.5px solid ${MS.accent}`, borderRadius: 9999, padding: '6px 13px', fontSize: 12.5, fontWeight: 600, cursor: canDays ? 'pointer' : 'not-allowed', opacity: canDays ? 1 : 0.5 }}>{monthFull && canDays ? 'Clear month' : 'Whole month'}</button>
                    ); })()}
                  </div>
                  <div style={{ background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 14, padding: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                      <button type="button" onClick={() => setMonthOffset((o) => Math.max(0, o - 1))} style={navBtn(monthOffset > 0)}>‹</button>
                      <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 15.5, margin: 0 }}>{cal.label}</p>
                      <button type="button" onClick={() => setMonthOffset((o) => o + 1)} style={navBtn(true)}>›</button>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3, marginBottom: 4 }}>
                      {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((w) => <div key={w} style={{ textAlign: 'center', fontSize: 11, color: '#A9A39C', padding: '2px 0' }}>{w}</div>)}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3 }}>
                      {cal.cells.map((c, i) => {
                        if (c.empty) return <div key={i} style={{ aspectRatio: '1' }} />;
                        const pid = assign[c.iso];
                        const on = pid != null;
                        return (
                          <div key={i} style={{ aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <button type="button" disabled={c.past || !active || isLifetime(active)} onClick={() => toggleDay(c.iso)} title={on ? planName(pid) : ''}
                              style={{ width: '100%', height: '100%', border: String(pid) === String(active) ? '2px solid rgba(0,0,0,0.35)' : 'none', borderRadius: 9, background: on ? colorOf(pid) : 'transparent', color: on ? '#fff' : (c.past ? '#C4BEB6' : MS.ink), fontSize: 13, fontWeight: on ? 600 : 400, cursor: (c.past || !active || isLifetime(active)) ? 'not-allowed' : 'pointer' }}>{c.day}</button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  {(totalDays > 0 || alloc.some((pid) => isLifetime(pid))) ? (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 2 }}>
                      {alloc.filter((pid) => isLifetime(pid) || countFor(pid)).map((pid) => (
                        <span key={pid} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: '#3A362F', background: MS.line2, padding: '6px 11px', borderRadius: 9999 }}>
                          <span style={{ width: 9, height: 9, borderRadius: 9999, background: colorOf(pid), flex: '0 0 auto' }} />
                          {isLifetime(pid) ? 'Lifetime' : `${countFor(pid)} day${countFor(pid) > 1 ? 's' : ''}`} · {planName(pid)}
                        </span>
                      ))}
                      {totalDays > 0 && <span style={{ fontSize: 12.5, color: MS.faint, alignSelf: 'center' }}>· {totalDays} days total</span>}
                    </div>
                  ) : (
                    <p style={{ fontSize: 12.5, color: '#A9A39C', margin: 0 }}>Add packages, then tap days (or “Whole month”) — or mark a package lifetime.</p>
                  )}
                </div>
              </>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {label('Status')}
              <select value={form.status} onChange={(e) => set('status', e.target.value)} style={inp}>
                {[['active', 'Active'], ['paused', 'Paused'], ['cancelled', 'Cancelled']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {label('Monthly meeting-room hours (blank = plan default)')}
              <input type="number" min="0" value={form.monthly_hours} onChange={(e) => set('monthly_hours', e.target.value)}
                placeholder={basePlan ? `Plan default: ${basePlan.room_hours}` : ''} style={inp} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {label('Custom price (blank = plan price)')}
                <input type="number" min="0" value={form.custom_price} onChange={(e) => set('custom_price', e.target.value)}
                  placeholder={basePlan ? `Plan: ${basePlan.display_price}` : ''} style={inp} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {label('Price label (optional)')}
                <input value={form.custom_price_label} onChange={(e) => set('custom_price_label', e.target.value)} placeholder='e.g. "Custom"' style={inp} />
              </div>
            </div>
            <button onClick={save} disabled={busy} style={{ width: '100%', marginTop: 6, background: MS.accent, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600, padding: 13, borderRadius: 9999, cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1 }}>{busy ? 'Saving…' : 'Save package'}</button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------------- Reservations ---------------- */
function Reservations({ query }) {
  const [filter, setFilter] = useState('all');
  const [rows, reload] = useData(() => adminReservations(filter === 'all' ? '' : filter), [filter]);
  const act = (fn) => (id) => fn(id).then(reload).catch((e) => window.alert(apiError(e) || 'Action failed.'));
  const approve = act(adminApproveReservation), cancel = act(adminCancelReservation), pay = act(adminTogglePaid);
  const approveChange = act(adminApproveChange), rejectChange = act(adminRejectChange);
  const FILTERS = [['all', 'All'], ['pending', 'Pending'], ['change', 'Change requests'], ['confirmed', 'Confirmed'], ['cancelled', 'Cancelled'], ['past', 'Past']];
  // Shared fixed template — identical for header + every row. The Actions column
  // is a fixed width (fits Approve + Mark paid + Cancel) so button count never
  // shifts the other columns.
  const cols = '90px minmax(160px,1.4fr) minmax(140px,1.2fr) 110px 100px 110px 240px';
  return (
    <>
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap', marginBottom: 20 }}>
        {FILTERS.map(([k, l]) => <FilterPill key={k} label={l} active={filter === k} onClick={() => setFilter(k)} />)}
      </div>
      <div style={{ ...card, overflowX: 'auto' }}>
        <div style={{ minWidth: 950 }}>
          <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, padding: '14px 22px', borderBottom: `1px solid ${MS.line}`, ...th }}>
            <span>Ref</span><span>Member</span><span>Space</span><span>Date</span><span>Payment</span><span>Status</span><span style={{ textAlign: 'right' }}>Actions</span>
          </div>
          {!rows && <div style={{ padding: 30, textAlign: 'center', color: MS.faint }}>Loading…</div>}
          {rows && rows.filter((r) => matches(r, query)).length === 0 && <div style={{ padding: 30, textAlign: 'center', color: MS.faint }}>No reservations.</div>}
          {(rows || []).filter((r) => matches(r, query)).map((r) => {
            const payText = r.is_paid ? 'Paid' : (r.is_free ? 'Free' : 'Pending');
            const payTone = r.is_paid ? TONES.green : (r.is_free ? TONES.lilac : TONES.amber);
            return (
              <div key={r.id} style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, alignItems: 'center', padding: '15px 22px', borderTop: `1px solid ${MS.line2}` }}>
                <span style={{ fontSize: 13, color: MS.muted, fontVariantNumeric: 'tabular-nums' }}>MS-{r.id}</span>
                <span style={{ fontSize: 14, fontWeight: 500, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.client}</span>
                <span style={{ fontSize: 14 }}>{r.space_label}</span>
                <span style={{ fontSize: 13.5, color: MS.muted }}>
                  {r.date_label}
                  {r.change_requested && r.requested_label && <span style={{ display: 'block', color: MS.accent, fontWeight: 600, fontSize: 12.5, marginTop: 2 }}>→ {r.requested_label}</span>}
                </span>
                <span>{pill(payTone.bg, payTone.color, payText)}</span>
                <span>{pill(r.status_bg, r.status_color, r.status_label)}</span>
                <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                  {r.change_requested ? (
                    <>
                      <button onClick={() => approveChange(r.id)} style={smallBtn('green')}>Approve</button>
                      <button onClick={() => rejectChange(r.id)} style={smallBtn('danger')}>Reject</button>
                    </>
                  ) : (
                    <>
                      {r.pending && <button onClick={() => approve(r.id)} style={smallBtn('green')}>Approve</button>}
                      {!r.is_paid && !r.is_free && <button onClick={() => pay(r.id)} style={smallBtn()}>Mark paid</button>}
                      {r.cancellable && <button onClick={() => cancel(r.id)} style={smallBtn('danger')}>Cancel</button>}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

/* ---------------- Spaces ---------------- */
function Spaces({ query, onEdit, modalClosed }) {
  const [rows, reload] = useData(adminSpaces);
  useEffect(() => { if (modalClosed === null) reload(); }, [modalClosed]); // refresh after modal closes
  if (!rows) return <Empty text="Loading spaces…" />;
  const del = (id) => {
    if (!window.confirm('Delete this space? This cannot be undone.')) return;
    adminDeleteSpace(id).then(reload).catch((e) => window.alert(apiError(e) || 'Could not delete this space.'));
  };
  const toggleActive = (id) => adminToggleSpace(id).then(reload).catch(() => {});
  const toggleBooking = (s) => adminUpdateSpace(s.id, { booking_enabled: !s.booking_enabled }).then(reload).catch(() => {});
  const filtered = rows.filter((s) => matches(s, query));
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
      {filtered.map((s) => {
        const tone = s.is_active ? TONES.green : TONES.amber;
        return (
          <div key={s.id} style={{ ...card, padding: '22px 24px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
              <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 20, margin: 0 }}>{s.name}</h3>
              {pill(tone.bg, tone.color, s.is_active ? 'Active' : 'Inactive')}
            </div>
            <p style={{ fontSize: 13.5, color: MS.muted, margin: '0 0 18px' }}>Capacity {s.capacity || '—'} · {s.size || '—'}{s.day_price != null ? ` · $${s.day_price}/day` : ''}{s.hour_price != null ? ` · $${s.hour_price}/hr` : ''}</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <button onClick={() => onEdit(s)} style={smallBtn()}>Edit</button>
              <button onClick={() => toggleActive(s.id)} style={smallBtn()}>{s.is_active ? 'Deactivate' : 'Activate'}</button>
              <button onClick={() => toggleBooking(s)} style={smallBtn()}>{s.booking_enabled ? 'Disable booking' : 'Enable booking'}</button>
              <button onClick={() => del(s.id)} style={smallBtn('danger')}>Delete</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ---------------- Packages ---------------- */
function Packages({ query, onEdit, modalClosed }) {
  const [rows, reload] = useData(() => adminPackages(true));
  useEffect(() => { if (modalClosed === null) reload(); }, [modalClosed]);
  if (!rows) return <Empty text="Loading packages…" />;
  const del = (id) => { if (window.confirm('Delete this package?')) adminDeletePackage(id).then(reload).catch(() => {}); };
  const dup = (id) => adminDuplicatePackage(id).then(reload).catch(() => {});
  const arch = (id) => adminToggleArchivePackage(id).then(reload).catch(() => {});
  const filtered = rows.filter((p) => matches(p, query));
  // Shared fixed template — Actions wide enough for Edit + Duplicate + Archive + Delete.
  const cols = 'minmax(180px,1.6fr) minmax(120px,1fr) 110px 310px';
  return (
    <div style={{ ...card, overflowX: 'auto' }}>
     <div style={{ minWidth: 730 }}>
      <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, padding: '14px 22px', borderBottom: `1px solid ${MS.line}`, ...th }}>
        <span>Package</span><span>Category</span><span>Status</span><span style={{ textAlign: 'right' }}>Actions</span>
      </div>
      {filtered.map((p) => {
        const tone = p.is_archived ? TONES.neutral : TONES.green;
        return (
          <div key={p.id} style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, alignItems: 'center', padding: '15px 22px', borderTop: `1px solid ${MS.line2}` }}>
            <span style={{ fontSize: 14.5, fontWeight: 600 }}>{p.name}</span>
            <span style={{ fontSize: 14, color: MS.muted }}>{p.category_name || '—'}</span>
            <span>{pill(tone.bg, tone.color, p.is_archived ? 'Archived' : 'Live')}</span>
            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
              <button onClick={() => onEdit(p)} style={smallBtn()}>Edit</button>
              <button onClick={() => dup(p.id)} style={smallBtn()}>Duplicate</button>
              <button onClick={() => arch(p.id)} style={smallBtn()}>{p.is_archived ? 'Unarchive' : 'Archive'}</button>
              <button onClick={() => del(p.id)} style={smallBtn('danger')}>Delete</button>
            </div>
          </div>
        );
      })}
     </div>
    </div>
  );
}

/* ---------------- FAQ ---------------- */
function Faqs({ query, onEdit, modalClosed }) {
  const [rows, reload] = useData(adminFaqs);
  useEffect(() => { if (modalClosed === null) reload(); }, [modalClosed]);
  if (!rows) return <Empty text="Loading FAQs…" />;
  const del = (id) => adminDeleteFaq(id).then(reload).catch(() => {});
  const filtered = rows.filter((f) => matches(f, query));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {filtered.map((f) => (
        <div key={f.id} style={{ ...card, borderRadius: 14, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ flex: 1, fontSize: 15, fontWeight: 500 }}>{f.question}</span>
          <button onClick={() => onEdit(f)} style={smallBtn()}>Edit</button>
          <button onClick={() => del(f.id)} style={smallBtn('danger')}>Delete</button>
        </div>
      ))}
    </div>
  );
}

/* ---------------- Promo codes ---------------- */
function Promos({ query, onEdit, modalClosed }) {
  const [rows, reload] = useData(adminPromoCodes);
  useEffect(() => { if (modalClosed === null) reload(); }, [modalClosed]);
  if (!rows) return <Empty text="Loading promo codes…" />;
  const del = (id) => adminDeletePromo(id).then(reload).catch(() => {});
  const toggle = (p) => adminUpdatePromo(p.id, { is_active: !p.is_active }).then(reload).catch(() => {});
  const filtered = rows.filter((p) => matches(p, query));
  // Shared fixed template — Actions fits Edit + Disable/Enable + Delete.
  const cols = 'minmax(120px,1fr) minmax(150px,1.4fr) minmax(120px,1.2fr) 80px 220px';
  return (
    <div style={{ ...card, overflowX: 'auto' }}>
     <div style={{ minWidth: 690 }}>
      <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, padding: '14px 22px', borderBottom: `1px solid ${MS.line}`, ...th }}>
        <span>Code</span><span>Campaign</span><span>Sales rep</span><span>Uses</span><span style={{ textAlign: 'right' }}>Actions</span>
      </div>
      {filtered.map((p) => (
        <div key={p.id} style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, alignItems: 'center', padding: '15px 22px', borderTop: `1px solid ${MS.line2}` }}>
          <span style={{ fontSize: 14, fontWeight: 600, fontFamily: 'monospace' }}>{p.code}{!p.is_active && <span style={{ color: MS.faint, fontWeight: 400 }}> (off)</span>}</span>
          <span style={{ fontSize: 14, color: MS.muted }}>{p.campaign || '—'}</span>
          <span style={{ fontSize: 14, color: MS.muted }}>{p.sales_rep || '—'}</span>
          <span style={{ fontSize: 14 }}>{p.tour_count}</span>
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
            <button onClick={() => onEdit(p)} style={smallBtn()}>Edit</button>
            <button onClick={() => toggle(p)} style={smallBtn('danger')}>{p.is_active ? 'Disable' : 'Enable'}</button>
            <button onClick={() => del(p.id)} style={smallBtn('danger')}>Delete</button>
          </div>
        </div>
      ))}
     </div>
    </div>
  );
}

/* ---------------- Tours ---------------- */
const TOUR_TONE = { new: 'lilac', contacted: 'amber', scheduled: 'green', closed: 'neutral' };
function Tours({ query, onEdit, modalClosed }) {
  const [rows, reload] = useData(adminTours);
  useEffect(() => { if (modalClosed === null) reload(); }, [modalClosed]);
  if (!rows) return <Empty text="Loading tour requests…" />;
  const del = (id) => adminDeleteTour(id).then(reload).catch(() => {});
  const filtered = rows.filter((t) => matches(t, query));
  // Shared fixed template — Actions fits Update + Delete.
  const cols = 'minmax(140px,1.4fr) minmax(160px,1.6fr) minmax(100px,1fr) 110px 150px';
  return (
    <div style={{ ...card, overflowX: 'auto' }}>
      <div style={{ minWidth: 680 }}>
        <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, padding: '14px 22px', borderBottom: `1px solid ${MS.line}`, ...th }}>
          <span>Visitor</span><span>Email</span><span>Promo</span><span>Status</span><span style={{ textAlign: 'right' }}>Actions</span>
        </div>
        {filtered.map((t) => {
          const tone = TONES[TOUR_TONE[t.status] || 'neutral'];
          return (
            <div key={t.id} style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, alignItems: 'center', padding: '15px 22px', borderTop: `1px solid ${MS.line2}` }}>
              <span style={{ fontSize: 14.5, fontWeight: 600, minWidth: 0 }}>{t.full_name}</span>
              <span style={{ fontSize: 13.5, color: MS.muted, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.email}</span>
              <span style={{ fontSize: 13.5, color: MS.muted }}>{t.promo_code || t.promo_code_text || '—'}</span>
              <span>{pill(tone.bg, tone.color, t.status_label)}</span>
              <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                <button onClick={() => onEdit(t)} style={smallBtn()}>Update</button>
                <button onClick={() => del(t.id)} style={smallBtn('danger')}>Delete</button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------- Custom package requests ---------------- */
function Customizations({ query, onEdit, modalClosed }) {
  const [rows, reload] = useData(adminCustomizations);
  const [detail, setDetail] = useState(null);   // request whose full breakdown modal is open
  useEffect(() => { if (modalClosed === null) reload(); }, [modalClosed]);
  if (!rows) return <Empty text="Loading custom requests…" />;
  const del = (id) => { if (window.confirm('Delete this request?')) adminDeleteCustomization(id).then(reload).catch(() => {}); };
  const filtered = rows.filter((c) => matches(c, query));
  const timeOf = (it) => (it.duration === 'hourly' && it.start_time) ? `${it.start_time}·${it.hours || 1}h` : 'full day';
  const summary = (items) => (items || []).map((it) => `${it.office} · ${(it.dates || []).length}d · ${timeOf(it)}`).join(', ') || '—';
  const datesTip = (items) => (items || []).map((it) => `${it.office} [${timeOf(it)}]: ${(it.dates || []).join(', ')}`).join('\n');
  // Shared fixed template — Actions fits Details + Update + Delete.
  const cols = 'minmax(150px,1.3fr) minmax(170px,1.6fr) minmax(190px,1.9fr) 70px 110px 230px';
  return (
    <div style={{ ...card, overflowX: 'auto' }}>
      <div style={{ minWidth: 900 }}>
        <div style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, padding: '14px 22px', borderBottom: `1px solid ${MS.line}`, ...th }}>
          <span>Name</span><span>Contact</span><span>Requested mix</span><span>Days</span><span>Status</span><span style={{ textAlign: 'right' }}>Actions</span>
        </div>
        {filtered.length === 0 && <div style={{ padding: 30, textAlign: 'center', color: MS.faint }}>No custom package requests yet.</div>}
        {filtered.map((c) => {
          const tone = TONES[TOUR_TONE[c.status] || 'neutral'];
          return (
            <div key={c.id} style={{ display: 'grid', gridTemplateColumns: cols, gap: 14, alignItems: 'center', padding: '15px 22px', borderTop: `1px solid ${MS.line2}` }}>
              <div style={{ minWidth: 0 }}>
                <p style={{ fontSize: 14.5, fontWeight: 600, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</p>
                {c.details ? <p title={c.details} style={{ fontSize: 12.5, color: MS.faint, margin: '1px 0 0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.details}</p> : null}
              </div>
              <div style={{ minWidth: 0 }}>
                <p style={{ fontSize: 13.5, color: MS.muted, margin: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.email}</p>
                {c.phone ? <p style={{ fontSize: 12.5, color: MS.faint, margin: '1px 0 0' }}>{c.phone}</p> : null}
              </div>
              <button onClick={() => setDetail(c)} title="View full breakdown" style={{ textAlign: 'left', background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 13.5, color: MS.accent, fontWeight: 600, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{summary(c.items)}</button>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{c.total_days}</span>
              <span>{pill(tone.bg, tone.color, c.status_label)}</span>
              <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                <button onClick={() => setDetail(c)} style={smallBtn()}>Details</button>
                <button onClick={() => onEdit(c)} style={smallBtn()}>Update</button>
                <button onClick={() => del(c.id)} style={smallBtn('danger')}>Delete</button>
              </div>
            </div>
          );
        })}
      </div>
      {detail && <CustomizationDetailModal req={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}

/* Full breakdown of one custom request — everything the visitor sent, so large
   day/office mixes that don't fit the table row are fully readable here. */
function CustomizationDetailModal({ req, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const timeOf = (it) => (it.duration === 'hourly' && it.start_time) ? `${it.start_time} · ${it.hours || 1} hr${(it.hours || 1) > 1 ? 's' : ''}` : 'Full day';
  const items = req.items || [];
  const tone = TONES[TOUR_TONE[req.status] || 'neutral'];
  const fact = (k, v) => v ? (
    <div style={{ display: 'flex', gap: 10, fontSize: 14 }}>
      <span style={{ flex: '0 0 88px', color: MS.faint }}>{k}</span>
      <span style={{ color: MS.ink, wordBreak: 'break-word' }}>{v}</span>
    </div>
  ) : null;
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 120, background: 'rgba(20,18,16,0.62)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'clamp(14px,4vw,40px)', animation: 'ms-fade 200ms ease-out both' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: MS.panel, width: 'min(620px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 20, padding: 'clamp(24px,4vw,32px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
          <div style={{ minWidth: 0 }}>
            <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 22, margin: 0 }}>{req.name}</h3>
            <p style={{ fontSize: 13, color: MS.faint, margin: '3px 0 0' }}>Custom package request · {req.total_days} day{req.total_days === 1 ? '' : 's'} across {items.length} office{items.length === 1 ? '' : 's'}</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: '0 0 auto' }}>
            {pill(tone.bg, tone.color, req.status_label)}
            <button onClick={onClose} aria-label="Close" style={{ width: 36, height: 36, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
          {fact('Email', req.email)}
          {fact('Phone', req.phone)}
          {fact('Notes', req.details)}
        </div>

        <p style={{ fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase', color: MS.faint, fontWeight: 600, margin: '0 0 12px' }}>Requested schedule</p>
        {items.length === 0 && <p style={{ color: MS.faint, fontSize: 14 }}>No days were assigned.</p>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {items.map((it, i) => {
            const dates = (it.dates || []).slice().sort();
            const col = ALLOC_COLORS[i % ALLOC_COLORS.length];
            return (
              <div key={i} style={{ ...card, padding: '14px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
                  <span style={{ width: 11, height: 11, borderRadius: 9999, background: col, flex: '0 0 auto' }} />
                  <span style={{ fontSize: 15, fontWeight: 600 }}>{it.office}</span>
                  <span style={{ fontSize: 12.5, color: MS.muted, background: MS.line2, padding: '3px 10px', borderRadius: 9999 }}>{timeOf(it)}</span>
                  <span style={{ fontSize: 12.5, color: MS.faint }}>{dates.length} day{dates.length === 1 ? '' : 's'}</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {dates.map((d) => (
                    <span key={d} style={{ fontSize: 12.5, color: '#3A362F', background: MS.line2, padding: '4px 10px', borderRadius: 8, whiteSpace: 'nowrap' }}>{fmtDate(d)}</span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ---------------- Calendar blocking ---------------- */
function Calendar({ onNew, modalClosed }) {
  const [rows, reload] = useData(() => adminBlockedSlots({ upcoming: 1 }));
  useEffect(() => { if (modalClosed === null) reload(); }, [modalClosed]);
  if (!rows) return <Empty text="Loading blocks…" />;
  const del = (id) => adminDeleteBlockedSlot(id).then(reload).catch(() => {});
  return (
    <div style={{ ...card, padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        <p style={{ fontSize: 14, fontWeight: 600, color: '#5A554F', margin: 0 }}>Upcoming availability blocks</p>
        <button onClick={onNew} style={{ background: MS.accent, color: '#fff', border: 'none', fontSize: 13, fontWeight: 600, padding: '8px 16px', borderRadius: 9999, cursor: 'pointer' }}>+ Block a slot</button>
      </div>
      {rows.length === 0 ? <p style={{ color: MS.faint, fontSize: 14 }}>No upcoming blocks. Add one to close a space for a date or time.</p> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {rows.map((b) => (
            <div key={b.id} style={{ display: 'flex', alignItems: 'center', gap: 14, border: `1px solid ${MS.line}`, borderRadius: 12, padding: '12px 16px' }}>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 14.5, fontWeight: 600, margin: 0 }}>{b.space_name} · {b.date}</p>
                <p style={{ fontSize: 13, color: MS.muted, margin: '2px 0 0' }}>{b.start_time ? `${b.start_time}–${b.end_time || '…'}` : 'Full day'}{b.reason ? ` · ${b.reason}` : ''}</p>
              </div>
              <button onClick={() => del(b.id)} style={smallBtn('danger')}>Remove</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------- Website content ---------------- */
function Content() {
  const [content, setContent] = useState(null);
  const [settings, setSettings] = useState(null);
  const [modal, setModal] = useState(null);
  const load = useCallback(() => {
    adminContent().then(setContent).catch(() => {});
    adminSettings().then(setSettings).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const SECTIONS = [
    { title: 'Hero', desc: 'Headline, subtext and background image/video', edit: () => setModal('hero') },
    { title: 'Intro statement', desc: 'The large statement under the hero', edit: () => setModal('intro') },
    { title: 'Members', desc: 'Testimonials — quotes, names and photos', edit: () => setModal('testimonials') },
    { title: 'Contact information', desc: 'Email, phone, address and map', edit: () => setModal('contact') },
    { title: 'Business hours', desc: 'Opening times and tour notifications', edit: () => setModal('hours') },
    { title: 'Booking rules', desc: 'Same-day, auto-approve, pay-at-center', edit: () => setModal('rules') },
  ];

  const saveContent = (payload) => adminSaveContent(payload).then((d) => { setContent(d); });
  const saveSettings = (payload) => adminSaveSettings(payload).then((d) => { setSettings(d); });

  const FORMS = {
    hero: { title: 'Edit hero', save: saveContent, initial: content, fields: [
      { name: 'hero_headline', label: 'Headline', type: 'text' },
      { name: 'hero_subheading', label: 'Subheading', type: 'text' },
      { name: 'hero_media_type', label: 'Background type', type: 'select', options: [['image', 'Image'], ['video', 'Video']] },
      { name: 'hero_media_url', label: 'Background media (upload a file or paste a URL)', type: 'media', typeField: 'hero_media_type' },
    ] },
    intro: { title: 'Intro statement', save: saveContent, initial: content, fields: [
      { name: 'intro_text', label: 'Statement text', type: 'textarea' },
    ] },
    contact: { title: 'Contact information', save: saveSettings, initial: settings, fields: [
      { name: 'contact_email', label: 'Email', type: 'text' },
      { name: 'phones', label: 'Phone numbers (one per line)', type: 'list' },
      { name: 'address', label: 'Address', type: 'text' },
      { name: 'maps_url', label: 'Google Maps URL', type: 'text' },
      { name: 'whatsapp_number', label: 'WhatsApp number (e.g. +961 70 123 456 — blank hides the bubble)', type: 'text' },
      { name: 'whatsapp_message', label: 'WhatsApp prefilled message (optional)', type: 'text' },
    ] },
    hours: { title: 'Business hours', save: saveSettings, initial: settings, fields: [
      { name: 'center_name', label: 'Center name', type: 'text' },
      { name: 'opening_hours', label: 'Opening hours (display text)', type: 'text' },
      { name: 'notification_email', label: 'Tour notification email', type: 'text' },
    ] },
    rules: { title: 'Booking rules', save: saveSettings, initial: settings, fields: [
      { name: 'allow_sameday', label: 'Allow same-day bookings', type: 'checkbox' },
      { name: 'auto_approve', label: 'Auto-approve bookings', type: 'checkbox' },
      { name: 'pay_at_center', label: 'Pay at center', type: 'checkbox' },
      { name: 'sameday_cutoff', label: 'Same-day cutoff (HH:MM)', type: 'text' },
    ] },
  };
  const active = modal && FORMS[modal];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 720 }}>
      {SECTIONS.map((s) => (
        <div key={s.title} style={{ ...card, borderRadius: 14, padding: '20px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
          <div>
            <p style={{ fontSize: 15.5, fontWeight: 600, margin: '0 0 3px' }}>{s.title}</p>
            <p style={{ fontSize: 13, color: MS.faint, margin: 0 }}>{s.desc}</p>
          </div>
          <button onClick={s.edit} style={{ background: 'none', border: `1px solid ${MS.line}`, color: MS.ink, fontSize: 13.5, fontWeight: 600, padding: '9px 20px', borderRadius: 9999, cursor: 'pointer', whiteSpace: 'nowrap' }}>Edit</button>
        </div>
      ))}
      {active && <FormModal title={active.title} fields={active.fields} initial={active.initial || {}} onSubmit={active.save} onClose={() => setModal(null)} />}
      {modal === 'testimonials' && (
        <TestimonialsModal initial={content?.testimonials || []} onSave={(list) => saveContent({ testimonials: list })} onClose={() => setModal(null)} />
      )}
    </div>
  );
}

// Editor for the "Members" testimonials list (quote + author + company + photo per row).
function TestimonialsModal({ initial, onSave, onClose }) {
  const [rows, setRows] = useState(() => (initial.length ? initial.map((t) => ({ ...t })) : [{ quote: '', author: '', company: '', image: '' }]));
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(-1);
  const [err, setErr] = useState('');
  const set = (i, k, v) => setRows((s) => s.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const add = () => setRows((s) => [...s, { quote: '', author: '', company: '', image: '' }]);
  const remove = (i) => setRows((s) => s.filter((_, j) => j !== i));
  const upload = async (i, file) => {
    if (!file) return;
    setUploading(i); setErr('');
    try { const up = await adminUploadImage(file); set(i, 'image', up.url); }
    catch (e) { setErr(apiError(e, 'Upload failed.')); }
    finally { setUploading(-1); }
  };
  const save = async () => {
    setBusy(true); setErr('');
    // drop fully-empty rows
    const clean = rows.filter((r) => (r.quote || r.author || r.company || r.image));
    try { await onSave(clean); onClose(); }
    catch (e) { setErr(apiError(e, 'Could not save.')); setBusy(false); }
  };
  const inp = { background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 10, padding: '10px 12px', fontFamily: MS.sans, fontSize: 14.5, color: MS.ink, outline: 'none', width: '100%' };

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 120, background: 'rgba(20,18,16,0.62)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'clamp(14px,4vw,40px)', animation: 'ms-fade 200ms ease-out both' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: MS.panel, width: 'min(620px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 20, padding: 'clamp(24px,4vw,32px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 22, margin: 0 }}>Members / testimonials</h3>
          <button onClick={onClose} aria-label="Close" style={{ width: 36, height: 36, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
        </div>
        {err && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13, fontWeight: 500, padding: '10px 14px', borderRadius: 10, margin: '0 0 16px' }}>{err}</p>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {rows.map((r, i) => (
            <div key={i} style={{ border: `1px solid ${MS.line}`, borderRadius: 14, padding: 16, display: 'flex', flexDirection: 'column', gap: 10, background: '#fff' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: MS.faint, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Member {i + 1}</span>
                <button onClick={() => remove(i)} style={smallBtn('danger')}>Remove</button>
              </div>
              <textarea rows={3} value={r.quote} onChange={(e) => set(i, 'quote', e.target.value)} placeholder="Quote" style={{ ...inp, resize: 'vertical' }} />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <input value={r.author} onChange={(e) => set(i, 'author', e.target.value)} placeholder="Name" style={inp} />
                <input value={r.company} onChange={(e) => set(i, 'company', e.target.value)} placeholder="Role, Company" style={inp} />
              </div>
              <input value={r.image || ''} onChange={(e) => set(i, 'image', e.target.value)} placeholder="Photo URL (or upload below)" style={inp} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <input type="file" accept="image/*" onChange={(e) => upload(i, e.target.files?.[0])} style={{ fontSize: 13 }} />
                {uploading === i && <span style={{ fontSize: 12, color: MS.faint }}>Uploading…</span>}
                {r.image && <img src={r.image} alt="" style={{ width: 54, height: 54, objectFit: 'cover', borderRadius: 10, marginLeft: 'auto' }} />}
              </div>
            </div>
          ))}
        </div>
        <button onClick={add} style={{ ...smallBtn(), marginTop: 14 }}>+ Add member</button>
        <button onClick={save} disabled={busy} style={{ width: '100%', marginTop: 18, background: MS.accent, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600, padding: 13, borderRadius: 9999, cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.7 : 1 }}>{busy ? 'Saving…' : 'Save'}</button>
      </div>
    </div>
  );
}

/* ---------------- shared UI ---------------- */
function FilterPill({ label, active, onClick }) {
  return <button onClick={onClick} style={{ border: `1px solid ${active ? MS.ink : 'rgba(26,26,26,0.18)'}`, background: active ? MS.ink : 'transparent', color: active ? MS.panel : '#5A554F', fontSize: 13.5, fontWeight: 500, padding: '8px 18px', borderRadius: 9999, cursor: 'pointer' }}>{label}</button>;
}

// Field configs for the entity create/edit modal.
const RECORD_FORMS = {
  space: {
    title: (i) => i ? 'Edit space' : 'New space',
    create: adminCreateSpace, update: adminUpdateSpace,
    fields: [
      { name: 'name', label: 'Name', type: 'text', required: true },
      { name: 'key', label: 'Key (slug, unique)', type: 'text', required: true },
      { name: 'description', label: 'Description', type: 'textarea' },
      { name: 'capacity', label: 'Capacity', type: 'number' },
      { name: 'size', label: 'Size (e.g. 36 m²)', type: 'text' },
      { name: 'day_price', label: 'Price per day', type: 'number' },
      { name: 'hour_price', label: 'Price per hour', type: 'number' },
      { name: 'units', label: 'Units (identical rooms)', type: 'number' },
      { name: 'amenities', label: 'Amenities (one per line)', type: 'list' },
      { name: 'equipment', label: 'Equipment (one per line)', type: 'list' },
      { name: 'durations', label: 'Durations (hourly / fullday, one per line)', type: 'list' },
      { name: 'images', label: 'Photos', type: 'images' },
      { name: 'is_free', label: 'Free space', type: 'checkbox' },
      { name: 'uses_free_hours', label: 'Uses free meeting-room hours', type: 'checkbox' },
      { name: 'booking_enabled', label: 'Booking enabled', type: 'checkbox' },
    ],
  },
  package: {
    title: (i) => i ? 'Edit package' : 'New package',
    create: adminCreatePackage, update: adminUpdatePackage,
    fields: [
      { name: 'name', label: 'Name', type: 'text', required: true },
      { name: 'description', label: 'Description', type: 'textarea' },
      { name: 'room_hours', label: 'Meeting-room hours / mo', type: 'number' },
      { name: 'guest_passes', label: 'Guest passes', type: 'number' },
      { name: 'features', label: 'Features (one per line)', type: 'list' },
      { name: 'images', label: 'Photos', type: 'images' },
      { name: 'featured', label: 'Featured', type: 'checkbox' },
      { name: 'is_visible', label: 'Visible on site', type: 'checkbox' },
      { name: 'booking_enabled', label: 'Booking enabled', type: 'checkbox' },
    ],
  },
  faq: {
    title: (i) => i ? 'Edit FAQ' : 'New FAQ',
    create: adminCreateFaq, update: adminUpdateFaq,
    fields: [
      { name: 'question', label: 'Question', type: 'text', required: true },
      { name: 'answer', label: 'Answer', type: 'textarea', required: true },
      { name: 'order', label: 'Order', type: 'number' },
      { name: 'is_visible', label: 'Visible', type: 'checkbox' },
    ],
  },
  promo: {
    title: (i) => i ? 'Edit promo code' : 'New promo code',
    create: adminCreatePromo, update: adminUpdatePromo,
    fields: [
      { name: 'code', label: 'Code', type: 'text', required: true },
      { name: 'campaign', label: 'Campaign', type: 'text' },
      { name: 'sales_rep', label: 'Sales rep', type: 'text' },
      { name: 'is_active', label: 'Active', type: 'checkbox' },
    ],
  },
  block: {
    title: () => 'Block availability',
    create: adminCreateBlockedSlot, update: null,
    fields: [
      { name: 'space_key', label: 'Space', type: 'space' },
      { name: 'date', label: 'Date', type: 'date', required: true },
      { name: 'start_time', label: 'Start time (blank = full day)', type: 'time' },
      { name: 'end_time', label: 'End time', type: 'time' },
      { name: 'reason', label: 'Reason', type: 'text' },
    ],
  },
  tour: {
    title: () => 'Update tour request',
    create: null, update: adminUpdateTour,
    fields: [
      { name: 'status', label: 'Status', type: 'select', options: [['new', 'New'], ['contacted', 'Contacted'], ['scheduled', 'Scheduled'], ['closed', 'Closed']] },
    ],
  },
  customization: {
    title: () => 'Update custom request',
    create: null, update: adminUpdateCustomization,
    fields: [
      { name: 'status', label: 'Status', type: 'select', options: [['new', 'New'], ['contacted', 'Contacted'], ['scheduled', 'Scheduled'], ['closed', 'Closed']] },
    ],
  },
};

// Entity create/edit modal, driven by RECORD_FORMS.
function RecordModal({ state, onClose }) {
  const cfg = RECORD_FORMS[state.type];
  const initial = state.initial;
  const [categories, setCategories] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [file, setFile] = useState(null);

  useEffect(() => {
    if (cfg.fields.some((f) => f.type === 'category')) adminCategories().then(setCategories).catch(() => {});
    if (cfg.fields.some((f) => f.type === 'space')) adminSpaces().then(setSpaces).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (payload) => {
    if (cfg.upload) {
      if (!file) throw new Error('Choose an image to upload.');
      const up = await adminUploadImage(file);
      payload.image = up.url;
      if (!payload.caption) payload.caption = up.label;
    }
    if ('category' in payload && payload.category === '') payload.category = null;
    if (initial && cfg.update) return cfg.update(initial.id, payload);
    return cfg.create(payload);
  };

  return (
    <FormModal
      title={cfg.title(initial)}
      fields={cfg.fields}
      initial={initial || {}}
      categories={categories}
      spaces={spaces}
      showUpload={cfg.upload}
      onFile={setFile}
      onSubmit={submit}
      onClose={onClose}
    />
  );
}

// Generic form modal used by both RecordModal and the Content editor.
function FormModal({ title, fields, initial, categories = [], spaces = [], showUpload, onFile, onSubmit, onClose }) {
  const [form, setForm] = useState(() => {
    const seed = {};
    fields.forEach((f) => {
      let v = initial?.[f.name];
      if (f.type === 'list') v = Array.isArray(v) ? v.join('\n') : (v || '');
      else if (f.type === 'images') v = Array.isArray(v) ? v : [];
      else if (f.type === 'checkbox') v = !!v;
      else if (f.type === 'category') v = initial?.category ?? '';
      else if (f.type === 'json') v = (v === null || v === undefined) ? '' : JSON.stringify(v, null, 2);
      else if (v === null || v === undefined) v = '';
      seed[f.name] = v;
    });
    return seed;
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [uploading, setUploading] = useState(false);
  const set = (name, val) => setForm((s) => ({ ...s, [name]: val }));
  const isVid = (u) => /\.(mp4|webm|ogg|mov)(\?|$)/i.test(u || '');
  const onMedia = async (f, file) => {
    if (!file) return;
    setUploading(true); setErr('');
    try {
      const up = await adminUploadImage(file);
      set(f.name, up.url);
      if (f.typeField && up.kind) set(f.typeField, up.kind);
    } catch (e) { setErr(apiError(e, 'Upload failed.')); }
    finally { setUploading(false); }
  };
  // Multi-image field: upload each chosen file and append its URL to the array.
  const onImages = async (f, files) => {
    const list = Array.from(files || []);
    if (!list.length) return;
    setUploading(true); setErr('');
    try {
      const urls = [];
      for (const file of list) { const up = await adminUploadImage(file); urls.push(up.url); }
      setForm((s) => ({ ...s, [f.name]: [...(s[f.name] || []), ...urls] }));
    } catch (e) { setErr(apiError(e, 'Upload failed.')); }
    finally { setUploading(false); }
  };
  const removeImage = (f, idx) =>
    setForm((s) => ({ ...s, [f.name]: (s[f.name] || []).filter((_, i) => i !== idx) }));

  const save = async () => {
    setErr('');
    const payload = {};
    for (const f of fields) {
      let v = form[f.name];
      if (f.type === 'list') v = String(v).split('\n').map((x) => x.trim()).filter(Boolean);
      else if (f.type === 'number') v = v === '' ? null : Number(v);
      else if (f.type === 'json') {
        try { v = String(v).trim() ? JSON.parse(v) : null; }
        catch { setErr(`${f.label}: invalid JSON — ${''}please check the syntax.`); return; }
      }
      payload[f.name] = v;
    }
    setBusy(true);
    try { await onSubmit(payload); onClose(); }
    catch (e) { setErr(e?.message && !e.response ? e.message : apiError(e, 'Could not save.')); setBusy(false); }
  };

  const label = (t) => <label style={{ fontSize: 13.5, fontWeight: 500, color: MS.ink }}>{t}</label>;
  const inp = { background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 10, padding: '10px 12px', fontFamily: MS.sans, fontSize: 14.5, color: MS.ink, outline: 'none', width: '100%' };

  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 120, background: 'rgba(20,18,16,0.62)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'clamp(14px,4vw,40px)', animation: 'ms-fade 200ms ease-out both' }}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: MS.panel, width: 'min(520px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 20, padding: 'clamp(24px,4vw,32px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 22, margin: 0 }}>{title}</h3>
          <button onClick={onClose} aria-label="Close" style={{ width: 36, height: 36, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
        </div>
        {err && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13, fontWeight: 500, padding: '10px 14px', borderRadius: 10, margin: '0 0 16px' }}>{err}</p>}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {showUpload && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {label('Image file')}
              <input type="file" accept="image/*" onChange={(e) => onFile?.(e.target.files?.[0] || null)} style={{ fontSize: 14 }} />
            </div>
          )}
          {fields.map((f) => (
            <div key={f.name} style={{ display: 'flex', flexDirection: f.type === 'checkbox' ? 'row' : 'column', alignItems: f.type === 'checkbox' ? 'center' : 'stretch', gap: f.type === 'checkbox' ? 10 : 7 }}>
              {f.type === 'checkbox' ? (
                <>
                  <input type="checkbox" checked={!!form[f.name]} onChange={(e) => set(f.name, e.target.checked)} style={{ width: 18, height: 18 }} />
                  {label(f.label)}
                </>
              ) : f.type === 'textarea' || f.type === 'list' ? (
                <>{label(f.label)}<textarea rows={f.type === 'list' ? 4 : 3} value={form[f.name]} onChange={(e) => set(f.name, e.target.value)} style={{ ...inp, resize: 'vertical' }} /></>
              ) : f.type === 'json' ? (
                <>{label(f.label)}<textarea rows={14} value={form[f.name]} onChange={(e) => set(f.name, e.target.value)} spellCheck={false} style={{ ...inp, resize: 'vertical', fontFamily: 'monospace', fontSize: 12.5, lineHeight: 1.5 }} /></>
              ) : f.type === 'select' ? (
                <>{label(f.label)}<select value={form[f.name]} onChange={(e) => set(f.name, e.target.value)} style={inp}>{f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></>
              ) : f.type === 'category' ? (
                <>{label(f.label)}<select value={form[f.name]} onChange={(e) => set(f.name, e.target.value)} style={inp}><option value="">— none —</option>{categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></>
              ) : f.type === 'space' ? (
                <>{label(f.label)}<select value={form[f.name]} onChange={(e) => set(f.name, e.target.value)} style={inp}><option value="">All spaces</option>{spaces.map((s) => <option key={s.id} value={s.key}>{s.name}</option>)}</select></>
              ) : f.type === 'media' ? (
                <>{label(f.label)}
                  <input value={form[f.name]} onChange={(e) => set(f.name, e.target.value)} placeholder="/media/… or https://…" style={inp} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 2 }}>
                    <input type="file" accept="image/*,video/*" onChange={(e) => onMedia(f, e.target.files?.[0])} style={{ fontSize: 13 }} />
                    {uploading && <span style={{ fontSize: 12, color: MS.faint }}>Uploading…</span>}
                  </div>
                  {form[f.name] && (isVid(form[f.name])
                    ? <video src={form[f.name]} muted loop autoPlay playsInline style={{ width: '100%', maxHeight: 150, objectFit: 'cover', borderRadius: 10, marginTop: 4 }} />
                    : <img src={form[f.name]} alt="" style={{ width: '100%', maxHeight: 150, objectFit: 'cover', borderRadius: 10, marginTop: 4 }} />)}
                </>
              ) : f.type === 'images' ? (
                <>{label(f.label)}
                  {(form[f.name] || []).length > 0 && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(88px, 1fr))', gap: 8 }}>
                      {(form[f.name] || []).map((url, i) => (
                        <div key={i} style={{ position: 'relative', aspectRatio: '1', borderRadius: 10, overflow: 'hidden', background: MS.line2 }}>
                          <img src={url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          <button type="button" onClick={() => removeImage(f, i)} aria-label="Remove image"
                            style={{ position: 'absolute', top: 4, right: 4, width: 22, height: 22, borderRadius: 9999, border: 'none', background: 'rgba(20,18,16,0.6)', color: '#fff', cursor: 'pointer', fontSize: 12, lineHeight: 1 }}>✕</button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 2 }}>
                    <input type="file" accept="image/*" multiple onChange={(e) => onImages(f, e.target.files)} style={{ fontSize: 13 }} />
                    {uploading && <span style={{ fontSize: 12, color: MS.faint }}>Uploading…</span>}
                  </div>
                </>
              ) : (
                <>{label(f.label)}<input type={f.type === 'number' ? 'number' : (f.type === 'date' ? 'date' : (f.type === 'time' ? 'time' : 'text'))} value={form[f.name]} onChange={(e) => set(f.name, e.target.value)} style={inp} /></>
              )}
            </div>
          ))}
        </div>
        <button onClick={save} disabled={busy} style={{ width: '100%', marginTop: 22, background: MS.accent, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600, padding: 13, borderRadius: 9999, cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.7 : 1 }}>{busy ? 'Saving…' : 'Save'}</button>
      </div>
    </div>
  );
}
