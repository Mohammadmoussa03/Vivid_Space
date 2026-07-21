import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import logoColor from '../assets/vividspace-logo.png';
import logoWhite from '../assets/vividspace-logo-white.png';
import { useAuth } from '../context/AuthContext';
import { MS, TONES, useVW, buildCalendar, fmtDate, apiError, safeUrl, todayIso } from '../lib/ms';
import { Reveal, RevealCard, CountUp } from '../lib/motion';
import {
  getSite, getPublicPackages, getCategories, getPublicSpaces, getFaqs,
  getAvailability, createBooking, createOrder, submitTour, submitCustomization, getOverview, getBookings, cancelBooking,
  requestBookingChange, requestScheduleChange,
} from '../lib/services';

/* ---------------- static design content (no backend equivalent) ---------------- */
const NAV_MENUS = [
  {
    label: 'Solutions', key: 'solutions',
    promo: { text: " Every way you work, perfectly accommodated. Flexible workspaces and business solutions designed to help you succeed.", cta: 'Explore All Solutions' },
    columns: [
      { heading: 'Workspace Solutions', links: ['Private Office', 'Dedicated Desk', 'Membership', 'Daily Cowork'] },
      { heading: 'Business Solutions', links: ['Virtual Office', 'Virtual Plus', 'Daily Private Office', 'Meeting Rooms'] },
       
    ],
  },

  {
    label: 'Who we are', key: 'about',
    promo: { text: 'Our workspaces build connection, belonging, and excitement.', cta: 'Our approach to work' },
    columns: [{ heading: 'Company', links: ['About', 'Members', 'FAQ'] }],
  },
  
];
const TESTIMONIALS = [
  { quote: "Moving into Vivid Space changed how our team feels about coming in. The rooms are calm, the light is incredible, and there's a real sense of belonging.", author: 'Amara Okafor', company: 'Founder, Ostro Studio', grad: 'linear-gradient(140deg,#8E7CA8,#6E5E86)' },
  { quote: 'We scaled from four people to fourteen without ever changing buildings. They just handed us the right room at the right time.', author: 'Daniel Reyes', company: 'CEO, Northbeam', grad: 'linear-gradient(140deg,#A88C7C,#7C6252)' },
  { quote: "The community isn't a marketing line here. I've hired two people and found a client in the kitchen line.", author: 'Sofia Bianchi', company: 'Principal, Field & Form', grad: 'linear-gradient(140deg,#7C93A8,#566E86)' },
];
const GALLERY_GRADS = [
  'linear-gradient(140deg,#8E7CA8,#6E5E86)', 'linear-gradient(140deg,#A88C7C,#7C6252)',
  'linear-gradient(140deg,#7C93A8,#566E86)', 'linear-gradient(140deg,#9C8AA8,#6E5E86)',
  'linear-gradient(140deg,#8AA88C,#5E866A)', 'linear-gradient(140deg,#A8907C,#866A52)',
  'linear-gradient(140deg,#7C86A8,#565E86)',
];
const FALLBACK_FAQS = [
  { question: 'How do memberships work?', answer: "Choose a plan, pick your home location, and you're in. Memberships are month-to-month — upgrade, downgrade, or pause with 30 days' notice." },
  { question: 'Can I upgrade or downgrade my plan?', answer: 'Anytime, from your member dashboard. Changes take effect at the start of your next billing cycle.' },
  { question: "What's included in meeting-room hours?", answer: 'Every plan includes a monthly allowance of meeting-room time you can book across any location.' },
  { question: 'Do you offer day passes?', answer: 'Yes — the Flex Desk gives you a full day at any open seat, with access to every lounge and unlimited coffee.' },
  { question: 'How do I book a tour?', answer: 'Use the "Find your space" button or the form below. Our team reaches out within one business day.' },
];
const SPACE_STATUS = {
  available: { label: 'Available', tone: 'green' },
  fully_booked: { label: 'Fully booked', tone: 'neutral' },
  blocked: { label: 'Blocked', tone: 'red' },
  temporarily_unavailable: { label: 'Temporarily unavailable', tone: 'amber' },
};
const FOOTER_COLS = [
  { title: 'Solutions', links: ['Private offices', 'Coworking', 'Meeting rooms', 'Virtual office'] },
  { title: 'Company', links: ['About', 'Contact'] },
  
];

// Cache the public site config so a refresh renders the correct hero media
// immediately, instead of flashing the bundled fallback while /site/ loads.
const SITE_CACHE = 'ms_site';
const loadSiteCache = () => { try { return JSON.parse(localStorage.getItem(SITE_CACHE)); } catch { return null; } };

const HERO_STATS = [
  { value: 500, suffix: '+', label: 'Members' },
  { value: 12, suffix: 'k+', label: 'Hours booked' },
  { value: 4.9, suffix: '/5', label: 'Member rating' },
  { value: 98, suffix: '%', label: 'Would recommend' },
];
// Offline fallbacks — the live content comes from /api/site/ (all admin-editable).
const INTRO_FALLBACK = 'Our workspaces build connection, belonging, and an excitement to be part of something bigger. All in an atmosphere that looks after people, and makes them feel excited about coming in. Even on a Monday.';
const FOOTER_NOTE = 'Premium flexible workspaces that foster genuine community and human connection in vibrant city locations.';

const money = (v) => {
  const n = Number(v);
  if (!isFinite(n)) return '$0';
  return Number.isInteger(n) ? `$${n}` : `$${n.toFixed(2)}`;
};

/* ---------------- shared style atoms ---------------- */
const sectionPad = 'clamp(64px,10vw,128px) clamp(16px,4vw,32px)';
const eyebrow = { color: MS.accent, fontSize: 14, fontWeight: 600, letterSpacing: '0.18em', textTransform: 'uppercase', margin: '0 0 14px' };
const h2 = { fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(28px,4vw,40px)', lineHeight: 1.3, letterSpacing: '-0.01em', margin: 0 };
const chip = (active) => ({
  flex: '0 0 auto', border: `1px solid ${active ? MS.accent : 'rgba(26,26,26,0.15)'}`,
  background: active ? MS.ink : 'transparent', color: active ? MS.panel : '#5A554F',
  fontSize: 15, fontWeight: 500, padding: '10px 22px', borderRadius: 9999, cursor: 'pointer', whiteSpace: 'nowrap',
});
const inputStyle = {
  background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 10, padding: '12px 14px',
  fontFamily: MS.sans, fontSize: 15, color: MS.ink, outline: 'none', width: '100%',
};
const purpleBtn = {
  background: MS.accent, color: '#fff', border: 'none', fontFamily: MS.sans, fontSize: 15,
  fontWeight: 600, padding: '13px 28px', borderRadius: 9999, cursor: 'pointer',
};
const ghostBtn = {
  background: 'none', border: '2px solid rgba(26,26,26,0.2)', color: MS.ink, fontFamily: MS.sans,
  fontSize: 15, fontWeight: 600, padding: '12px 26px', borderRadius: 9999, cursor: 'pointer',
};

/* ---------------- luxury nav tokens ---------------- */
const MANROPE = "'Manrope', 'Inter', system-ui, sans-serif";
const NAV_ACCENT = '#C8A4FF';
const NAV_EASE = 'cubic-bezier(.22,.61,.36,1)';

/* ============================ PAGE ============================ */
export default function Landing() {
  const vw = useVW();
  const nav = useNavigate();
  const { user, isAuthed, role, loading: authLoading } = useAuth();

  const [site, setSite] = useState(loadSiteCache);
  // True once we can trust the hero content: immediately if we have a cached
  // site, otherwise after the first /site/ fetch settles. Prevents the hero
  // flashing the bundled fallback before the real content arrives.
  const [siteReady, setSiteReady] = useState(() => !!loadSiteCache());
  const [packages, setPackages] = useState([]);
  const [categories, setCategories] = useState([]);
  const [spaces, setSpaces] = useState([]);
  const [faqs, setFaqs] = useState(FALLBACK_FAQS);

  const [openMenu, setOpenMenu] = useState(null);
  const [scrolled, setScrolled] = useState(false);
  const [navHover, setNavHover] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);   // hamburger panel open
  const [mobileSub, setMobileSub] = useState(null);     // expanded menu key inside the panel

  const [pkgCat, setPkgCat] = useState('All');
  const [tIdx, setTIdx] = useState(0);
  const [faqOpen, setFaqOpen] = useState(0);

  const [authOpen, setAuthOpen] = useState(false);
  const [resetInfo, setResetInfo] = useState(null);   // { uid, token } from an emailed reset link
  const [bookingSpace, setBookingSpace] = useState(null);
  const [dashOpen, setDashOpen] = useState(false);
  const [pkgDetail, setPkgDetail] = useState(null);   // package whose gallery/benefits modal is open
  const [customizeOpen, setCustomizeOpen] = useState(false);

  const contactRef = useRef(null);
  const packagesRef = useRef(null);
  const spacesRef = useRef(null);
  const aboutRef = useRef(null);

  // members / testimonials — admin-managed, falling back to the built-in set.
  const testimonials = (site?.testimonials && site.testimonials.length) ? site.testimonials : TESTIMONIALS;
  const tActive = testimonials[tIdx] || testimonials[0];

  // Hero copy/media, the intro statement and members are admin-editable; the rest is static.
  const introText = site?.intro_text || INTRO_FALLBACK;
  // About us — admin-editable. Body is stored as plain text; blank lines separate
  // paragraphs, matching how the admin types it into the textarea.
  const about = site?.about || {};
  const aboutParas = String(about.body || '').split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  const aboutPoints = (about.points || []).filter(Boolean);
  const stats = HERO_STATS;
  const footer = { note: FOOTER_NOTE, columns: FOOTER_COLS };

  // Google Maps in the Book-a-Tour section (admin-set maps URL / address).
  // safeUrl strips any non-http(s) scheme (e.g. javascript:) before it reaches
  // an href/iframe — defense-in-depth over the server-side URL validation.
  const mapUrl = safeUrl(site?.contact?.maps_url) || '';
  const mapAddr = site?.contact?.address || '';
  const mapSrc = (() => {
    if (/(\/maps\/embed|output=embed)/.test(mapUrl)) return mapUrl; // already an embed URL
    const q = /[?&]q=([^&]+)/.exec(mapUrl)?.[1];                    // ?q=lat,lng or ?q=place
    if (q) {
      const z = /[?&]z=(\d+)/.exec(mapUrl)?.[1];
      return `https://www.google.com/maps?q=${q}${z ? `&z=${z}` : ''}&output=embed`;
    }
    if (mapAddr) return `https://www.google.com/maps?q=${encodeURIComponent(mapAddr)}&output=embed`;
    return '';
  })();

  // Live availability: spaces (and their availability_status) are recomputed from
  // the DB on every fetch, so re-pulling reflects new/cancelled/rescheduled bookings.
  const refreshSpaces = useCallback(() => {
    getPublicSpaces().then((d) => Array.isArray(d) && setSpaces(d)).catch(() => {});
  }, []);

  /* ---- load public data ---- */
  useEffect(() => {
    getSite().then((d) => { setSite(d); try { localStorage.setItem(SITE_CACHE, JSON.stringify(d)); } catch { /* ignore */ } }).catch(() => {}).finally(() => setSiteReady(true));
    getPublicPackages().then((d) => Array.isArray(d) && setPackages(d)).catch(() => {});
    getCategories().then((d) => Array.isArray(d) && setCategories(d)).catch(() => {});
    getFaqs().then((d) => { if (Array.isArray(d) && d.length) setFaqs(d); }).catch(() => {});
  }, []);

  // Spaces are pulled per-session, not just on mount: the API only returns prices
  // to a signed-in caller, so a member who logs in mid-visit needs a fresh payload
  // (the anonymous one has no prices in it) — and a logout needs the reverse.
  // Waits for the session check so we don't fetch twice on every load.
  useEffect(() => {
    if (authLoading) return;
    refreshSpaces();
  }, [authLoading, isAuthed, refreshSpaces]);

  // Keep the home page current — re-pull availability whenever the tab regains
  // focus (e.g. after booking/cancelling/rescheduling in another tab or the portal).
  useEffect(() => {
    const onFocus = () => refreshSpaces();
    const onVisible = () => { if (!document.hidden) refreshSpaces(); };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisible);
    return () => { window.removeEventListener('focus', onFocus); document.removeEventListener('visibilitychange', onVisible); };
  }, [refreshSpaces]);

  /* ---- password-reset link: open the "set new password" modal, then strip the token from the URL ---- */
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const uid = p.get('reset_uid'), token = p.get('reset_token');
    if (!uid || !token) return;
    setResetInfo({ uid, token });
    setAuthOpen(true);
    p.delete('reset_uid'); p.delete('reset_token');
    const qs = p.toString();
    window.history.replaceState({}, '', window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash);
  }, []);

  /* ---- nav scroll + outside click ---- */
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  /* ---- testimonial autoplay ---- */
  useEffect(() => {
    if (bookingSpace || authOpen || dashOpen || pkgDetail || customizeOpen) return;
    const id = setInterval(() => setTIdx((i) => (i + 1) % testimonials.length), 6500);
    return () => clearInterval(id);
  }, [bookingSpace, authOpen, dashOpen, pkgDetail, customizeOpen, testimonials.length]);

  const scrollToContact = (e) => { e?.preventDefault?.(); setOpenMenu(null); contactRef.current?.scrollIntoView({ behavior: 'smooth' }); };
  const scrollToPackages = (e) => { e?.preventDefault?.(); setOpenMenu(null); packagesRef.current?.scrollIntoView({ behavior: 'smooth' }); };
  const scrollToSpaces = (e) => { e?.preventDefault?.(); setOpenMenu(null); spacesRef.current?.scrollIntoView({ behavior: 'smooth' }); };
  const scrollToAbout = (e) => { e?.preventDefault?.(); setOpenMenu(null); aboutRef.current?.scrollIntoView({ behavior: 'smooth' }); };
  // Where each nav menu lands: its own section when it has one, else the contact form.
  const menuScrollFor = (key) => (key === 'solutions' ? scrollToPackages : key === 'about' ? scrollToAbout : scrollToContact);

  // Nav links collapse into a hamburger below the desktop threshold.
  const showDesktopNav = vw >= 980;

  // Close the mobile panel (and lock body scroll while it's open) as the viewport changes.
  useEffect(() => {
    if (showDesktopNav && mobileNav) { setMobileNav(false); setMobileSub(null); }
  }, [showDesktopNav, mobileNav]);
  useEffect(() => {
    if (!mobileNav) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [mobileNav]);

  // Transparent (light text) over the hero; fades to a solid warm-cream bar with dark text
  // once you scroll past the hero, open a mega-menu, or hover the header.
  const navSolid = scrolled || !!openMenu || navHover || mobileNav;

  // package categories -> chip items
  const catItems = ['All', ...categories.map((c) => c.name)];
  const visiblePackages = pkgCat === 'All'
    ? packages
    : packages.filter((p) => (p.category?.name || '') === pkgCat);

  // Bespoke "custom" packages from the backend are folded into the single
  // "Customized Package" card below, so we never list them as their own tile.
  const isCustomPkg = (p) => /custom/i.test(p?.name || '') || /custom/i.test(p?.category?.name || '');
  const realPackages = visiblePackages.filter((p) => !isCustomPkg(p));
  // Offices a visitor can mix when building a custom package (the real spaces).
  const officeOptions = Array.from(new Set(packages.filter((p) => !isCustomPkg(p)).map((p) => p.name)));



  const openBooking = (space) => {
    if (!isAuthed) { setAuthOpen(true); return; }
    setBookingSpace(space);
  };

  const goDashboard = () => { setAuthOpen(false); setDashOpen(true); };
  const onAuthed = (u) => {
    setAuthOpen(false);
    if (u?.role === 'admin') nav('/admin');
    else setDashOpen(true);
  };

  return (
    <div style={{ fontFamily: MS.sans, background: MS.bg, color: MS.ink }}>
      {/* ===== NAV ===== */}
      <header
        onMouseEnter={() => setNavHover(true)}
        onMouseLeave={() => { setNavHover(false); setOpenMenu(null); }}
        style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 60,
          background: navSolid ? 'rgba(250,248,243,0.92)' : 'transparent',
          backdropFilter: navSolid ? 'blur(12px)' : 'none',
          WebkitBackdropFilter: navSolid ? 'blur(12px)' : 'none',
          borderBottom: `1px solid ${navSolid ? MS.line : 'transparent'}`,
          boxShadow: navSolid ? '0 10px 30px -18px rgba(20,18,16,0.30)' : '0 0 0 rgba(0,0,0,0)',
          transition: 'background 300ms ease-out, backdrop-filter 300ms ease-out, border-color 300ms ease-out, box-shadow 300ms ease-out' }}
      >
        <div style={{ position: 'relative', maxWidth: 1600, margin: '0 auto', height: 84, padding: '0 clamp(20px,4vw,48px)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <a href="#top" onMouseEnter={() => setOpenMenu(null)} onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
            aria-label="VividSpace — home" style={{ display: 'flex', alignItems: 'center', textDecoration: 'none' }}>
            {/* Colour logo on the solid cream bar; white logo over the dark hero — crossfaded. */}
            <span style={{ position: 'relative', display: 'block', height: 62 }}>
              <img src={logoColor} alt="VividSpace" style={{ height: '100%', width: 'auto', display: 'block', opacity: navSolid ? 1 : 0, transition: 'opacity 300ms ease-out' }} />
              <img src={logoWhite} alt="" aria-hidden="true" style={{ position: 'absolute', top: 0, left: 0, height: '100%', width: 'auto', display: 'block', opacity: navSolid ? 0 : 1, transition: 'opacity 300ms ease-out' }} />
            </span>
          </a>

          {showDesktopNav ? (
            <>
              <nav style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', display: 'flex', alignItems: 'center', gap: 64 }}>
                {NAV_MENUS.map((m) => (
                  <NavItem key={m.key} menu={m} active={openMenu === m.key} onEnter={() => setOpenMenu(m.key)}
                    onSelect={m.key === 'solutions' || m.key === 'about' ? menuScrollFor(m.key) : undefined} solid={navSolid} />
                ))}
                {/* Plain link — no mega-menu panel, so hovering it closes any open one. */}
                <span onMouseEnter={() => setOpenMenu(null)} style={{ display: 'inline-flex' }}>
                  <NavTextBtn label="Daily Bookings" onClick={scrollToSpaces} solid={navSolid} />
                </span>
              </nav>

              <div onMouseEnter={() => setOpenMenu(null)} style={{ display: 'flex', alignItems: 'center', gap: 'clamp(16px,2vw,28px)' }}>
                {isAuthed ? (
                  role === 'admin'
                    ? <NavTextBtn label="Admin" onClick={() => nav('/admin')} solid={navSolid} />
                    : <NavTextBtn label="Dashboard" onClick={() => setDashOpen(true)} solid={navSolid} />
                ) : (
                  <NavTextBtn label="Log in" onClick={() => setAuthOpen(true)} solid={navSolid} />
                )}
                <CTAButton onClick={scrollToContact}>Find your space</CTAButton>
              </div>
            </>
          ) : (
            <button onClick={() => setMobileNav((o) => !o)} aria-label={mobileNav ? 'Close menu' : 'Open menu'} aria-expanded={mobileNav}
              style={{ width: 44, height: 44, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', background: 'none', border: 'none', cursor: 'pointer', color: navSolid ? MS.ink : '#fff', padding: 0 }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ transition: 'transform 250ms ease-out' }}>
                {mobileNav ? (
                  <>
                    <line x1="5" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    <line x1="19" y1="5" x2="5" y2="19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </>
                ) : (
                  <>
                    <line x1="3" y1="7" x2="21" y2="7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    <line x1="3" y1="12" x2="21" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    <line x1="3" y1="17" x2="21" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </>
                )}
              </svg>
            </button>
          )}
        </div>

        {openMenu && (() => {
          const menu = NAV_MENUS.find((m) => m.key === openMenu);
          if (!menu) return null;
          const menuScroll = menuScrollFor(menu.key);
          return (
            <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, background: MS.panel, borderBottom: `1px solid ${MS.line}`,
              boxShadow: '0 26px 44px rgba(20,18,16,0.09)', animation: 'ms-dropdown 220ms ease-out both' }}>
              <div style={{ maxWidth: 1440, margin: '0 auto', padding: 'clamp(32px,4vw,52px) clamp(16px,4vw,44px)', display: 'flex', gap: 'clamp(32px,5vw,80px)' }}>
                <div style={{ flex: '0 0 clamp(280px,32%,440px)', background: '#DCB8EE', borderRadius: 4, padding: 'clamp(28px,3vw,48px)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 44 }}>
                  <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(24px,2.3vw,32px)', lineHeight: 1.32, margin: 0 }}>{menu.promo.text}</p>
                  <a href="#contact" onClick={menuScroll} style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 10, background: '#FAF3DF', color: MS.ink, textDecoration: 'none', fontSize: 15, fontWeight: 600, padding: '13px 26px', borderRadius: 9999 }}>{menu.promo.cta} <span>→</span></a>
                </div>
                <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 'clamp(24px,3vw,52px)', alignContent: 'start' }}>
                  {menu.columns.map((col) => (
                    <div key={col.heading}>
                      <p style={{ fontSize: 13, color: MS.faint, margin: '0 0 22px' }}>{col.heading}</p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 18, alignItems: 'flex-start' }}>
                        {col.links.map((l) => (
                          <a key={l} href="#contact" onClick={menuScroll} style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(18px,1.5vw,23px)', lineHeight: 1.18, color: MS.ink, textDecoration: 'none' }}>{l}</a>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })()}
      </header>

      {/* Mobile slide-down nav panel (sibling of the header so its fixed
          positioning is relative to the viewport, not the blurred header). */}
      {!showDesktopNav && mobileNav && (
        <div style={{ position: 'fixed', top: 84, left: 0, right: 0, bottom: 0, zIndex: 55, background: MS.panel, overflowY: 'auto', WebkitOverflowScrolling: 'touch', animation: 'ms-fade 220ms ease-out both' }}>
          <div style={{ padding: '18px clamp(20px,5vw,32px) 40px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            {NAV_MENUS.map((m) => {
              const open = mobileSub === m.key;
              const menuScroll = menuScrollFor(m.key);
              return (
                <div key={m.key} style={{ borderBottom: `1px solid ${MS.line}` }}>
                  <button onClick={() => setMobileSub(open ? null : m.key)} aria-expanded={open}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, width: '100%', minHeight: 52, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: '4px 0', fontFamily: MS.serif, fontWeight: 700, fontSize: 20, color: MS.ink }}>
                    <span>{m.label}</span>
                    <span style={{ fontSize: 22, fontWeight: 400, color: MS.accent, transition: 'transform 220ms ease-out', transform: open ? 'rotate(45deg)' : 'none' }}>+</span>
                  </button>
                  <div style={{ overflow: 'hidden', maxHeight: open ? 600 : 0, opacity: open ? 1 : 0, transition: 'max-height 300ms ease-out, opacity 260ms ease-out' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, padding: '2px 0 14px' }}>
                      {m.columns.flatMap((col) => col.links).map((l) => (
                        <a key={l} href="#contact" onClick={(e) => { menuScroll(e); setMobileNav(false); setMobileSub(null); }}
                          style={{ display: 'flex', alignItems: 'center', minHeight: 44, color: MS.muted, textDecoration: 'none', fontSize: 16 }}>{l}</a>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Plain link — no sub-list to expand, so it navigates straight away. */}
            <div style={{ borderBottom: `1px solid ${MS.line}` }}>
              <button onClick={(e) => { scrollToSpaces(e); setMobileNav(false); setMobileSub(null); }}
                style={{ display: 'flex', alignItems: 'center', width: '100%', minHeight: 52, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: '4px 0', fontFamily: MS.serif, fontWeight: 700, fontSize: 20, color: MS.ink }}>
                Daily Bookings
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 22 }}>
              {isAuthed ? (
                role === 'admin'
                  ? <button onClick={() => { setMobileNav(false); nav('/admin'); }} style={{ ...ghostBtn, width: '100%', minHeight: 48 }}>Admin</button>
                  : <button onClick={() => { setMobileNav(false); setDashOpen(true); }} style={{ ...ghostBtn, width: '100%', minHeight: 48 }}>Dashboard</button>
              ) : (
                <button onClick={() => { setMobileNav(false); setAuthOpen(true); }} style={{ ...ghostBtn, width: '100%', minHeight: 48 }}>Log in</button>
              )}
              <button onClick={(e) => { scrollToContact(e); setMobileNav(false); }}
                style={{ width: '100%', minHeight: 52, borderRadius: 9999, border: 'none', cursor: 'pointer', fontFamily: MANROPE, fontWeight: 600, fontSize: 16, color: '#1B1B1B', background: 'linear-gradient(135deg,#DFC0FF 0%,#C89FFF 100%)', boxShadow: '0 12px 30px rgba(194,160,255,0.28)' }}>Find your space</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== HERO ===== */}
      <section id="top" className="ms-hero" style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', background: MS.ink }}>
        {siteReady && (
          site?.hero?.media_type === 'video' && site?.hero?.media_url ? (
            <video src={site.hero.media_url} autoPlay muted loop playsInline
              style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center', animation: 'ms-fade 700ms ease-out both' }} />
          ) : site?.hero?.media_url ? (
            <img src={site.hero.media_url} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center', animation: 'ms-fade 700ms ease-out both' }} />
          ) : null
        )}
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(20,18,16,0.55), rgba(20,18,16,0.35) 40%, rgba(20,18,16,0.6))' }} />
        {siteReady && (
        <div style={{ position: 'relative', zIndex: 2, textAlign: 'center', padding: '0 24px', maxWidth: 900 }}>
          <p style={{ color: 'rgba(255,255,255,0.9)', fontSize: 'clamp(15px,1.5vw,19px)', fontWeight: 500, margin: '0 0 20px', animation: 'ms-fade 700ms ease-out both', animationDelay: '80ms' }}>
            {site?.hero?.subheading || 'Flexible offices, co-working, event and meeting spaces'}
          </p>
          <h1 style={{ fontFamily: MS.serif, fontWeight: 700, color: '#fff', fontSize: 'clamp(26px, 6.5vw, 72px)', lineHeight: 1.12, letterSpacing: '-0.02em', margin: '0 0 40px', animation: 'ms-fade 700ms ease-out both', animationDelay: '200ms' }}>
            {site?.hero?.headline || 'Unique workspaces alive with the buzz of your city and people'}
          </h1>

          <div style={{ marginTop: 'clamp(36px,5vw,56px)', display: 'flex', flexWrap: 'wrap', justifyContent: 'center', alignItems: 'center', gap: 'clamp(20px,4vw,48px)', animation: 'ms-fade 700ms ease-out both', animationDelay: '320ms' }}>
            {stats.flatMap((s, i) => {
              const stat = (
                <div key={s.label} style={{ textAlign: 'center' }}>
                  <div style={{ fontFamily: MS.serif, fontWeight: 700, color: '#fff', fontSize: 'clamp(24px,3.4vw,44px)', lineHeight: 1, textShadow: '0 1px 3px rgba(0,0,0,0.25)' }}>
                    <CountUp value={Number(s.value)} decimals={Number.isInteger(Number(s.value)) ? 0 : 1} suffix={s.suffix} delay={i * 180} />
                  </div>
                  <div style={{ marginTop: 8, fontFamily: MS.sans, fontSize: 12.5, color: 'rgba(255,255,255,0.75)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{s.label}</div>
                </div>
              );
              if (i === 0) return [stat];
              return vw >= 768
                ? [<span key={`div-${i}`} style={{ width: 1, height: 42, background: 'rgba(255,255,255,0.25)' }} />, stat]
                : [stat];
            })}
          </div>

        </div>
        )}
      </section>

      {/* ===== INTRO / STATEMENT ===== */}
      <section style={{ background: '#F7F1E1', padding: 'clamp(72px,10vw,130px) clamp(24px,6vw,96px)' }}>
        <div style={{ maxWidth: 1600, margin: '0 auto' }}>
          <Reveal as="p" style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(30px,4.4vw,52px)', lineHeight: 1.28, letterSpacing: '-0.01em', color: '#1E3A2B', margin: 0 }}>
            {introText}
          </Reveal>
        </div>
      </section>

      {/* ===== ABOUT US ===== */}
      {(about.title || aboutParas.length > 0) && (
        <section id="about" ref={aboutRef} style={{ background: MS.bg, padding: sectionPad, scrollMarginTop: 84 }}>
          <div style={{ maxWidth: 1180, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 'clamp(28px,5vw,64px)', alignItems: 'start' }}>
            <Reveal>
              {about.eyebrow && <p style={eyebrow}>{about.eyebrow}</p>}
              <h2 style={h2}>{about.title}</h2>
            </Reveal>
            <Reveal delay={90}>
              {aboutParas.map((p, i) => (
                <p key={i} style={{ color: 'rgba(26,26,26,0.72)', fontSize: 'clamp(15px,1.3vw,17px)', lineHeight: 1.7, margin: i === 0 ? 0 : '16px 0 0' }}>{p}</p>
              ))}
              {aboutPoints.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 26 }}>
                  {aboutPoints.map((pt, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}>
                      <span style={{ flex: '0 0 auto', width: 19, height: 19, marginTop: 2, borderRadius: 9999, background: 'rgba(155,126,189,0.16)', color: MS.accent, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 }}>✓</span>
                      <span style={{ fontSize: 15, lineHeight: 1.45 }}>{pt}</span>
                    </div>
                  ))}
                </div>
              )}
            </Reveal>
          </div>
        </section>
      )}

      {/* ===== PACKAGES ===== */}
      <section id="packages" ref={packagesRef} style={{ background: MS.bg2, padding: sectionPad, scrollMarginTop: 84 }}>
        <div style={{ maxWidth: 1280, margin: '0 auto' }}>
          <Reveal style={{ maxWidth: 640, marginBottom: 40 }}>
            <p style={eyebrow}>Packages</p>
            <h2 style={h2}>Room for how you work</h2>
          </Reveal>
          {catItems.length > 1 && (
            <div className="ms-rail" style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 6, marginBottom: 40 }}>
              {catItems.map((c) => (
                <button key={c} onClick={() => setPkgCat(c)} style={chip(pkgCat === c)}>{c}</button>
              ))}
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(268px, 1fr))', gap: 'clamp(20px,2.5vw,28px)', alignItems: 'stretch' }}>
            {realPackages.length === 0 && <p style={{ color: MS.faint }}>No packages published yet.</p>}
            {realPackages.map((p, pi) => (
              <RevealCard key={p.id} delay={pi * 90} onClick={() => setPkgDetail(p)} style={{ position: 'relative', display: 'flex', flexDirection: 'column', cursor: 'pointer', background: p.featured ? '#fff' : MS.panel, border: `1.5px solid ${p.featured ? MS.accent : MS.line}`, borderRadius: 20, padding: 'clamp(24px,3vw,34px)' }}>
                <p style={{ color: MS.accent, fontSize: 12, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', margin: '0 0 12px' }}>{p.category?.name || 'Package'}</p>
                <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 26, lineHeight: 1.2, margin: '0 0 10px' }}>{p.name}</h3>
                <p style={{ color: 'rgba(26,26,26,0.68)', fontSize: 15, lineHeight: 1.55, margin: '0 0 22px', minHeight: 46 }}>{p.description}</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 13, marginBottom: 28 }}>
                  {(p.features || []).slice(0, 5).map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}>
                      <span style={{ flex: '0 0 auto', width: 19, height: 19, marginTop: 1, borderRadius: 9999, background: 'rgba(155,126,189,0.16)', color: MS.accent, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 }}>✓</span>
                      <span style={{ fontSize: 15, lineHeight: 1.45 }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button onClick={(e) => { e.stopPropagation(); setPkgDetail(p); }}
                  style={{ marginTop: 'auto', background: MS.accent, color: '#fff', border: 'none', fontFamily: MS.sans, fontSize: 15, fontWeight: 600, padding: '13px 24px', borderRadius: 9999, cursor: 'pointer' }}>
                  View photos &amp; details
                </button>
              </RevealCard>
            ))}

            {/* The single "build your own" tile — mix any spaces across any days. */}
            <RevealCard key="__customized" delay={realPackages.length * 90} onClick={() => setCustomizeOpen(true)}
              style={{ position: 'relative', display: 'flex', flexDirection: 'column', cursor: 'pointer', background: 'linear-gradient(165deg,#2A2536 0%,#1C1A22 100%)', border: `1.5px solid ${MS.accent}`, borderRadius: 20, padding: 'clamp(24px,3vw,34px)', color: '#F5F1ED' }}>
              <span style={{ position: 'absolute', top: 20, right: 20, background: MS.accent2, color: MS.ink, fontSize: 12, fontWeight: 600, padding: '6px 13px', borderRadius: 9999 }}>No limits</span>
              <p style={{ color: MS.accent2, fontSize: 12, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', margin: '0 0 12px' }}>Build your own</p>
              <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 26, lineHeight: 1.2, margin: '0 0 10px' }}>Customized Package</h3>
              <p style={{ color: 'rgba(245,241,237,0.72)', fontSize: 15, lineHeight: 1.55, margin: '0 0 22px', minHeight: 46 }}>Mix any spaces across any days — say 3 days of a private office, 2 at a dedicated desk and a day of virtual office. Built exactly how you work.</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 13, marginBottom: 28 }}>
                {['Combine any office types', 'Choose the exact days for each', 'No limits — as much as you need'].map((f, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 11 }}>
                    <span style={{ flex: '0 0 auto', width: 19, height: 19, marginTop: 1, borderRadius: 9999, background: 'rgba(224,192,255,0.22)', color: MS.accent2, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 }}>✓</span>
                    <span style={{ fontSize: 15, lineHeight: 1.45 }}>{f}</span>
                  </div>
                ))}
              </div>
              <button onClick={(e) => { e.stopPropagation(); setCustomizeOpen(true); }}
                style={{ marginTop: 'auto', background: MS.accent2, color: MS.ink, border: 'none', fontFamily: MS.sans, fontSize: 15, fontWeight: 700, padding: '13px 24px', borderRadius: 9999, cursor: 'pointer' }}>
                Customize your package
              </button>
            </RevealCard>
          </div>
        </div>
      </section>

      {/* ===== SPACES ===== */}
      <section id="daily-bookings" ref={spacesRef} style={{ background: MS.bg, padding: sectionPad, scrollMarginTop: 84 }}>
        <div style={{ maxWidth: 1280, margin: '0 auto' }}>
          <Reveal style={{ maxWidth: 640, marginBottom: 44 }}>
            <p style={eyebrow}>Daily Bookings</p>
            <h2 style={h2}>Rooms for every kind of work</h2>
          </Reveal>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(272px, 1fr))', gap: 'clamp(20px,2.5vw,28px)' }}>
            {spaces.length === 0 && <p style={{ color: MS.faint }}>No spaces published yet.</p>}
            {spaces.map((sp, i) => {
              const st = SPACE_STATUS[sp.availability_status] || SPACE_STATUS.available;
              const tone = TONES[st.tone];
              const canBook = sp.booking_enabled && sp.availability_status === 'available';
              const img = (sp.images || [])[0];
              return (
                <RevealCard key={sp.key} delay={i * 90} style={{ display: 'flex', flexDirection: 'column', background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 18, overflow: 'hidden' }}>
                  <div className="ms-zoom" style={{ position: 'relative', height: 190, background: GALLERY_GRADS[i % GALLERY_GRADS.length] }}>
                    {img && <img src={img} alt={sp.name} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />}
                    <span style={{ position: 'absolute', top: 13, left: 13, background: tone.bg, color: tone.color, fontSize: 12, fontWeight: 600, padding: '6px 12px', borderRadius: 9999, backdropFilter: 'blur(6px)' }}>{st.label}</span>
                  </div>
                  <div style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
                    <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 22, margin: 0 }}>{sp.name}</h3>
                    <p style={{ color: 'rgba(26,26,26,0.68)', fontSize: 14.5, lineHeight: 1.55, margin: 0 }}>{sp.description}</p>
                    <div style={{ display: 'flex', gap: 24, padding: '4px 0' }}>
                      <SpaceStat label="Capacity" value={sp.capacity || '—'} />
                      <SpaceStat label="Size" value={sp.size || '—'} />
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
                      {(sp.amenities || []).slice(0, 4).map((a) => (
                        <span key={a} style={{ fontSize: 12.5, color: '#5A554F', background: MS.line2, padding: '5px 11px', borderRadius: 9999 }}>{a}</span>
                      ))}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 'auto', paddingTop: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 3, flexWrap: 'wrap' }}>
                        {/* Rates are members-only — the backend also blanks them for
                            anonymous callers, so this branch has nothing to show anyway.
                            "Free" stays: it's a selling point, not a rate. */}
                        {sp.free ? <span style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 24 }}>Free</span>
                          : !isAuthed ? <span style={{ color: MS.muted, fontSize: 14 }}>Sign in to Book Your Space</span> : (
                          <>
                            {sp.day_price != null && <><span style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 24 }}>{money(sp.day_price)}</span><span style={{ color: MS.muted, fontSize: 14 }}>/ day</span></>}
                            {sp.day_price != null && sp.hour_price != null && <span style={{ color: MS.muted, fontSize: 14, margin: '0 2px' }}>·</span>}
                            {sp.hour_price != null && <><span style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 24 }}>{money(sp.hour_price)}</span><span style={{ color: MS.muted, fontSize: 14 }}>/ hr</span></>}
                          </>
                        )}
                      </div>
                      <button onClick={() => canBook && openBooking(sp)} disabled={!canBook}
                        style={{ background: canBook ? MS.accent : '#ECE8E2', color: canBook ? '#fff' : '#A9A39C', border: 'none', fontFamily: MS.sans, fontSize: 14, fontWeight: 600, padding: '10px 20px', borderRadius: 9999, cursor: canBook ? 'pointer' : 'not-allowed' }}>
                        {canBook ? 'Book' : st.label}
                      </button>
                    </div>
                  </div>
                </RevealCard>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===== TESTIMONIALS ===== */}
      <section style={{ background: MS.bg2, padding: sectionPad }}>
        <div style={{ maxWidth: 1180, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'clamp(32px,5vw,64px)', alignItems: 'center' }}>
          <Reveal>
            <p style={{ ...eyebrow, margin: '0 0 28px' }}>Members</p>
            <blockquote style={{ fontFamily: MS.sans, fontStyle: 'italic', fontSize: 'clamp(20px,2.6vw,26px)', lineHeight: 1.55, margin: '0 0 32px', minHeight: 150 }}>“{tActive.quote}”</blockquote>
            <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(22px,2.6vw,26px)', margin: '0 0 4px' }}>{tActive.author}</p>
            <p style={{ color: MS.muted, fontSize: 15, margin: '0 0 28px' }}>{tActive.company}</p>
            <div style={{ display: 'flex', gap: 10 }}>
              {testimonials.map((_, i) => (
                <button key={i} onClick={() => setTIdx(i)} aria-label="Testimonial" style={{ height: 8, width: i === tIdx ? 28 : 8, border: 'none', borderRadius: 9999, cursor: 'pointer', padding: 0, transition: 'width 300ms, background 300ms', background: i === tIdx ? MS.accent : 'rgba(26,26,26,0.2)' }} />
              ))}
            </div>
          </Reveal>
          <div className="ms-zoom" style={{ position: 'relative', height: 384, borderRadius: 18, overflow: 'hidden', boxShadow: '0 16px 40px rgba(20,18,16,0.14)', background: tActive.grad || GALLERY_GRADS[tIdx % GALLERY_GRADS.length], transition: 'background 400ms' }}>
            {tActive.image && <img src={tActive.image} alt={tActive.author || ''} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />}
          </div>
        </div>
      </section>

      {/* ===== FAQ ===== */}
      <section style={{ background: MS.bg, padding: sectionPad }}>
        <div style={{ maxWidth: 820, margin: '0 auto' }}>
          <Reveal style={{ textAlign: 'center', marginBottom: 48 }}>
            <p style={eyebrow}>FAQ</p>
            <h2 style={h2}>Questions, answered</h2>
          </Reveal>
          <div style={{ borderBottom: `1px solid ${MS.line}` }}>
            {faqs.map((f, i) => {
              const open = faqOpen === i;
              return (
                <Reveal key={f.id ?? i} delay={i * 70} style={{ borderTop: `1px solid ${MS.line}` }}>
                  <button onClick={() => setFaqOpen(open ? -1 : i)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20, width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: '24px 0', fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(18px,2vw,22px)', color: MS.ink }}>
                    <span>{f.question}</span>
                    <span style={{ flex: '0 0 auto', fontSize: 24, fontWeight: 400, color: MS.accent }}>{open ? '−' : '+'}</span>
                  </button>
                  <div style={{ overflow: 'hidden', maxHeight: open ? 400 : 0, opacity: open ? 1 : 0, transition: 'max-height 320ms, opacity 280ms' }}>
                    <p style={{ color: 'rgba(26,26,26,0.7)', fontSize: 16, lineHeight: 1.65, margin: 0, padding: '0 40px 26px 0' }}>{f.answer}</p>
                  </div>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===== CONTACT / TOUR ===== */}
      <section id="contact" ref={contactRef} style={{ background: MS.bg, padding: sectionPad, scrollMarginTop: 80 }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 'clamp(40px,6vw,80px)' }}>
          <div>
            <p style={{ ...eyebrow, margin: '0 0 20px' }}>Book a tour</p>
            <h2 style={{ ...h2, margin: '0 0 24px' }}>Come see your next workspace</h2>
            <p style={{ color: 'rgba(26,26,26,0.72)', fontSize: 18, lineHeight: 1.6, margin: '0 0 36px' }}>Tell us a little about your team and we'll set up a walkthrough at the location that fits you best.</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {[
                { icon: '✉', text: site?.contact?.email || 'hello@mindspace.co' },
                { icon: '☎', text: (site?.contact?.phones && site.contact.phones[0]) || '+1 (212) 555-0148' },
                { icon: '⌖', text: site?.contact?.address || '208 Hudson St, New York, NY' },
              ].map((fact) => (
                <div key={fact.text} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <span style={{ width: 40, height: 40, borderRadius: 9999, background: 'rgba(155,126,189,0.14)', color: MS.accent, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 17, flexShrink: 0 }}>{fact.icon}</span>
                  <span style={{ fontSize: 15 }}>{fact.text}</span>
                </div>
              ))}
            </div>

            {mapSrc ? (
              <div style={{ marginTop: 30 }}>
                <LocationMap src={mapSrc} url={mapUrl} address={mapAddr || 'Beirut, Lebanon'} />
              </div>
            ) : mapUrl ? (
              <a href={mapUrl} target="_blank" rel="noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 24, ...purpleBtn, textDecoration: 'none' }}>Open in Google Maps <span>↗</span></a>
            ) : null}
          </div>
          <TourForm />
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer style={{ background: MS.ink, color: MS.bg, padding: 'clamp(56px,8vw,88px) clamp(16px,4vw,32px) 40px' }}>
        <div style={{ maxWidth: 1280, margin: '0 auto' }}>
          <div style={{ display: 'grid', gridTemplateColumns: vw < 720 ? '1fr' : '1.8fr repeat(3, 1fr)', gap: 'clamp(24px,4vw,48px)', paddingBottom: 48 }}>
            <Reveal>
              <img src={logoWhite} alt="VividSpace" style={{ height: 68, width: 'auto', display: 'block', marginBottom: 18 }} />
              <p style={{ color: 'rgba(245,241,237,0.7)', fontSize: 15, lineHeight: 1.6, margin: 0, maxWidth: 300 }}>{footer.note || FOOTER_NOTE}</p>
            </Reveal>
            {(footer.columns || FOOTER_COLS).map((col, i) => (
              <Reveal key={col.title} delay={(i + 1) * 90}>
                <h4 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 18px' }}>{col.title}</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {col.links.map((l) => <a key={l} href="#contact" onClick={scrollToContact} style={{ color: 'rgba(245,241,237,0.7)', textDecoration: 'none', fontSize: 14 }}>{l}</a>)}
                </div>
              </Reveal>
            ))}
          </div>
          <div style={{ borderTop: '1px solid rgba(245,241,237,0.18)', paddingTop: 28, display: 'flex', flexWrap: 'wrap', gap: 16, justifyContent: 'space-between', alignItems: 'center' }}>
            <p style={{ color: 'rgba(245,241,237,0.55)', fontSize: 13, margin: 0 }}>© 2026 VIVIDSPACE. All rights reserved.</p>
            <p style={{ color: 'rgba(245,241,237,0.55)', fontSize: 13, margin: 0 }}>Privacy · Terms · Cookies</p>
          </div>
        </div>
      </footer>

      {/* ===== MODALS ===== */}
      {pkgDetail && <PackageModal pkg={pkgDetail} onClose={() => setPkgDetail(null)} onContact={() => { setPkgDetail(null); scrollToContact(); }} />}
      {customizeOpen && <CustomizeModal offices={officeOptions} onClose={() => setCustomizeOpen(false)} />}
      {bookingSpace && <BookingModal space={bookingSpace} whishEnabled={!!site?.payments?.whish_enabled}
        payAtCenter={site?.payments?.pay_at_center !== false} onClose={() => { setBookingSpace(null); refreshSpaces(); }} />}
      {authOpen && <AuthModal onClose={() => { setAuthOpen(false); setResetInfo(null); }} onAuthed={onAuthed} goDashboard={goDashboard} resetInfo={resetInfo} />}
      {dashOpen && <DashboardModal user={user} onClose={() => setDashOpen(false)} />}

      {/* Floating WhatsApp click-to-chat (hidden while the dashboard is open). */}
      {!dashOpen && <WhatsAppBubble number={site?.contact?.whatsapp} message={site?.contact?.whatsapp_message} />}
    </div>
  );
}

/* ---------------- Floating WhatsApp bubble ---------------- */
// Renders nothing unless an admin has set a WhatsApp number. Opens wa.me in a new
// tab with the digits-only number and an optional prefilled message.
function WhatsAppBubble({ number, message }) {
  const [hover, setHover] = useState(false);
  const digits = String(number || '').replace(/[^\d]/g, '');
  if (!digits) return null;
  const href = `https://wa.me/${digits}${message ? `?text=${encodeURIComponent(message)}` : ''}`;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label="Chat with us on WhatsApp"
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ position: 'fixed', right: 'clamp(16px,3vw,28px)', bottom: 'clamp(16px,3vw,28px)', zIndex: 80,
        display: 'flex', alignItems: 'center', gap: 12, textDecoration: 'none' }}>
      {/* Slide-in "Chat with us" label — collapses to width 0 when not hovered. */}
      <span style={{ overflow: 'hidden', maxWidth: hover ? 200 : 0, opacity: hover ? 1 : 0,
        background: '#fff', color: MS.ink, fontFamily: MS.sans, fontSize: 14.5, fontWeight: 600, whiteSpace: 'nowrap',
        padding: hover ? '11px 16px' : '11px 0', borderRadius: 9999, boxShadow: '0 8px 24px rgba(20,18,16,0.16)',
        transition: 'max-width 300ms cubic-bezier(.22,.61,.36,1), opacity 220ms ease-out, padding 300ms cubic-bezier(.22,.61,.36,1)' }}>
        Chat with us
      </span>
      <span style={{ flex: '0 0 auto', width: 60, height: 60, borderRadius: 9999, background: '#25D366', display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: hover ? '0 14px 34px rgba(37,211,102,0.5)' : '0 10px 26px rgba(37,211,102,0.38)',
        transform: hover ? 'translateY(-2px) scale(1.06)' : 'translateY(0) scale(1)',
        transition: 'transform 220ms cubic-bezier(.22,.61,.36,1), box-shadow 220ms ease-out' }}>
        <svg width="30" height="30" viewBox="0 0 24 24" fill="#fff" aria-hidden="true">
          <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.885-9.885 9.885M20.52 3.449C18.24 1.245 15.24 0 12.045 0 5.463 0 .104 5.359.101 11.944c0 2.096.548 4.142 1.588 5.945L0 24l6.335-1.652a11.882 11.882 0 005.71 1.447h.005c6.585 0 11.946-5.359 11.949-11.945a11.821 11.821 0 00-3.481-8.4"/>
        </svg>
      </span>
    </a>
  );
}

/* ---------------- luxury nav components ---------------- */
// Minimal 12px "+" that rotates to "×" on hover/active.
function PlusMark({ color, rotate }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"
      style={{ display: 'block', transform: `rotate(${rotate}deg)`, transition: `transform 250ms ${NAV_EASE}` }}>
      <line x1="6" y1="1.75" x2="6" y2="10.25" stroke={color} strokeWidth="1.5" strokeLinecap="round" style={{ transition: `stroke 250ms ${NAV_EASE}` }} />
      <line x1="1.75" y1="6" x2="10.25" y2="6" stroke={color} strokeWidth="1.5" strokeLinecap="round" style={{ transition: `stroke 250ms ${NAV_EASE}` }} />
    </svg>
  );
}

// Colour set for the two header states: solid (dark text over cream) vs. transparent (light text over hero).
const navPalette = (solid) => solid
  ? { base: 'rgba(26,26,26,0.82)', hover: MS.ink, active: MS.accent, plus: 'rgba(26,26,26,0.5)', plusOn: MS.accent, glow: 'rgba(155,126,189,0.16)' }
  : { base: 'rgba(255,255,255,0.88)', hover: '#FFFFFF', active: NAV_ACCENT, plus: 'rgba(255,255,255,0.70)', plusOn: NAV_ACCENT, glow: 'rgba(200,164,255,0.18)' };

function NavItem({ menu, active, onEnter, onSelect, solid }) {
  const [hover, setHover] = useState(false);
  const c = navPalette(solid);
  const textColor = active ? c.active : (hover ? c.hover : c.base);
  const plusColor = (hover || active) ? c.plusOn : c.plus;
  return (
    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
      <button onMouseEnter={() => { setHover(true); onEnter(); }} onMouseLeave={() => setHover(false)} onClick={onSelect}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', cursor: 'pointer',
          fontFamily: MANROPE, fontSize: 15, fontWeight: 500, letterSpacing: '0.2px', lineHeight: 1.2,
          padding: '6px 8px', borderRadius: 10, color: textColor,
          transform: hover ? 'translateY(-2px)' : 'translateY(0)',
          boxShadow: hover ? `0 0 12px ${c.glow}` : '0 0 0 rgba(0,0,0,0)',
          transition: `transform 250ms ${NAV_EASE}, color 300ms ease-out, box-shadow 250ms ${NAV_EASE}` }}>
        <span>{menu.label}</span>
        <PlusMark color={plusColor} rotate={(hover || active) ? 45 : 0} />
      </button>
    </div>
  );
}

function NavTextBtn({ label, onClick, solid }) {
  const [hover, setHover] = useState(false);
  const c = navPalette(solid);
  return (
    <button onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ background: 'none', border: 'none', cursor: 'pointer', fontFamily: MANROPE, fontSize: 15, fontWeight: 500,
        letterSpacing: '0.2px', lineHeight: 1.2, padding: '6px 4px', color: hover ? c.hover : c.base,
        transform: hover ? 'translateY(-2px)' : 'translateY(0)', transition: `transform 250ms ${NAV_EASE}, color 300ms ease-out` }}>
      {label}
    </button>
  );
}

function CTAButton({ onClick, children }) {
  const [hover, setHover] = useState(false);
  return (
    <a href="#contact" onClick={onClick} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', height: 48, padding: '0 30px',
        borderRadius: 999, textDecoration: 'none', whiteSpace: 'nowrap', fontFamily: MANROPE, fontWeight: 600, fontSize: 15, color: '#1B1B1B',
        background: hover ? 'linear-gradient(135deg,#E8CCFF 0%,#D4AEFF 100%)' : 'linear-gradient(135deg,#DFC0FF 0%,#C89FFF 100%)',
        boxShadow: hover ? '0 18px 45px rgba(194,160,255,0.38)' : '0 12px 30px rgba(194,160,255,0.28)',
        transform: hover ? 'translateY(-2px) scale(1.04)' : 'translateY(0) scale(1)',
        transition: 'transform 250ms ease, box-shadow 250ms ease, background 250ms ease' }}>
      {children}
    </a>
  );
}

// Premium Google Maps embed: toned map that warms to full colour on hover, with a
// glass location chip and a "Get directions" button overlaid at the bottom.
function LocationMap({ src, url, address }) {
  const [hover, setHover] = useState(false);
  return (
    <div onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ position: 'relative', borderRadius: 20, overflow: 'hidden', border: `1px solid ${MS.line}`,
        boxShadow: hover ? '0 28px 60px -20px rgba(20,18,16,0.42)' : '0 20px 50px -22px rgba(20,18,16,0.30)',
        transition: 'box-shadow 300ms ease-out' }}>
      <iframe title="Our location on Google Maps" src={src} loading="lazy" referrerPolicy="no-referrer-when-downgrade" allowFullScreen
        style={{ border: 0, display: 'block', width: '100%', height: 320,
          filter: hover ? 'none' : 'grayscale(0.3) contrast(1.03) saturate(0.9)', transition: 'filter 450ms ease-out' }} />
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'linear-gradient(180deg, rgba(20,18,16,0.16), rgba(20,18,16,0) 26%, rgba(20,18,16,0) 66%, rgba(20,18,16,0.22))' }} />
      <div style={{ position: 'absolute', left: 14, right: 14, bottom: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap',
        background: 'rgba(255,255,255,0.16)', backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)', border: '1px solid rgba(255,255,255,0.35)', borderRadius: 14, padding: '11px 14px', boxShadow: '0 8px 24px rgba(0,0,0,0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
          <span style={{ width: 36, height: 36, borderRadius: 9999, background: MS.accent, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z" stroke="#fff" strokeWidth="2" strokeLinejoin="round" />
              <circle cx="12" cy="10" r="2.5" fill="#fff" />
            </svg>
          </span>
          <div style={{ minWidth: 0 }}>
            <p style={{ margin: 0, fontFamily: MS.serif, fontWeight: 700, fontSize: 16, color: '#fff', textShadow: '0 1px 3px rgba(0,0,0,0.4)' }}>Vivid Space</p>
            <p style={{ margin: '2px 0 0', fontSize: 13, color: 'rgba(255,255,255,0.9)', textShadow: '0 1px 3px rgba(0,0,0,0.4)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{address}</p>
          </div>
        </div>
        {url && (
          <a href={url} target="_blank" rel="noreferrer" style={{ flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 6, background: '#fff', color: MS.ink, textDecoration: 'none', fontSize: 13.5, fontWeight: 600, padding: '9px 16px', borderRadius: 9999, boxShadow: '0 4px 12px rgba(0,0,0,0.16)' }}>Get directions <span>→</span></a>
        )}
      </div>
    </div>
  );
}

/* ---------------- small view components ---------------- */
function SpaceStat({ label, value }) {
  return (
    <div>
      <p style={{ fontSize: 11, color: MS.faint, letterSpacing: '0.1em', textTransform: 'uppercase', margin: '0 0 3px' }}>{label}</p>
      <p style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>{value}</p>
    </div>
  );
}

const overlay = (dark = 0.62) => ({ position: 'fixed', inset: 0, zIndex: 100, background: `rgba(20,18,16,${dark})`, backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'clamp(14px,4vw,40px)', animation: 'ms-fade 220ms ease-out both' });
/* ---------------- Tour form (POST /tours/) ---------------- */
function TourForm() {
  const [f, setF] = useState({ first: '', last: '', email: '', phone: '', promo: '' });
  const [err, setErr] = useState({});
  const [status, setStatus] = useState('idle'); // idle | loading | success | failure
  const set = (k) => (e) => { setF((s) => ({ ...s, [k]: e.target.value })); setErr((s) => ({ ...s, [k]: undefined })); };
  const bd = (k) => (err[k] ? '#C77' : MS.line);

  const submit = async (e) => {
    e.preventDefault();
    const er = {};
    if (!f.first.trim()) er.first = 'Required';
    if (!f.last.trim()) er.last = 'Required';
    if (!f.email.trim()) er.email = 'Required';
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email)) er.email = 'Enter a valid email';
    if (!f.phone.trim()) er.phone = 'Required';
    if (Object.keys(er).length) { setErr(er); return; }
    setStatus('loading');
    try {
      await submitTour({ first_name: f.first, last_name: f.last, email: f.email, phone: f.phone, promo_code: f.promo });
      setStatus('success');
    } catch { setStatus('failure'); }
  };

  // Premium raised card shared by the form and its result states.
  const shell = {
    position: 'relative', background: 'linear-gradient(180deg, #FFFFFF 0%, #FCFAF6 100%)',
    border: `1px solid ${MS.line}`, borderRadius: 22, padding: 'clamp(26px,4vw,38px)',
    boxShadow: '0 30px 60px -34px rgba(20,18,16,0.35)', animation: 'ms-rise 550ms ease-out both',
  };
  const accentBar = { position: 'absolute', top: 0, left: 0, right: 0, height: 4, background: 'linear-gradient(90deg,#DFC0FF,#9B7EBD)', borderRadius: '22px 22px 0 0' };
  const resultCard = { ...shell, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', minHeight: 400 };

  if (status === 'success') return (
    <div style={resultCard}>
      <div style={accentBar} />
      <span style={{ width: 60, height: 60, borderRadius: 9999, background: 'rgba(63,122,90,0.14)', color: MS.green, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, marginBottom: 20, animation: 'ms-pop 500ms ease-out both' }}>✓</span>
      <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 26, margin: '0 0 10px' }}>Thanks — we're on it</h3>
      <p style={{ color: 'rgba(26,26,26,0.72)', fontSize: 16, lineHeight: 1.6, margin: '0 0 28px', maxWidth: 320 }}>A member of our team will reach out within one business day to schedule your tour.</p>
      <button onClick={() => { setF({ first: '', last: '', email: '', phone: '', promo: '' }); setStatus('idle'); }} className="ms-ghost" style={ghostBtn}>Send another</button>
    </div>
  );
  if (status === 'failure') return (
    <div style={resultCard}>
      <div style={accentBar} />
      <span style={{ width: 60, height: 60, borderRadius: 9999, background: 'rgba(168,90,74,0.14)', color: MS.red, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, marginBottom: 20, animation: 'ms-pop 500ms ease-out both' }}>!</span>
      <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 26, margin: '0 0 10px' }}>Something went wrong</h3>
      <p style={{ color: 'rgba(26,26,26,0.72)', fontSize: 16, lineHeight: 1.6, margin: '0 0 28px', maxWidth: 320 }}>We couldn't submit your request just now. Please try again in a moment.</p>
      <button onClick={() => setStatus('idle')} className="ms-submit" style={{ ...purpleBtn, background: 'linear-gradient(135deg,#B48FD6,#9B7EBD)' }}>Try again</button>
    </div>
  );

  // Rendered as a function call (not a nested component) so inputs keep focus between keystrokes.
  const field = ({ label, k, type = 'text', placeholder, optional, delay = 0, row = false }) => (
    <div key={k} style={{ flex: row ? '1 1 140px' : '0 0 auto', display: 'flex', flexDirection: 'column', gap: 7, animation: 'ms-rise 480ms ease-out both', animationDelay: `${delay}ms` }}>
      <label style={{ fontSize: 14, fontWeight: 600, letterSpacing: '0.01em', color: '#3A362F' }}>{label}{optional && <span style={{ color: '#A9A39C', fontWeight: 400 }}> (optional)</span>}</label>
      <input className="ms-input" value={f[k]} onChange={set(k)} type={type} placeholder={placeholder} style={{ ...inputStyle, border: `1px solid ${bd(k)}`, padding: '13px 15px' }} />
      {err[k] && <span style={{ fontSize: 12.5, color: MS.red }}>{err[k]}</span>}
    </div>
  );

  return (
    <form onSubmit={submit} style={{ ...shell, alignSelf: 'start', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {field({ label: 'First name', k: 'first', placeholder: 'Jane', delay: 60, row: true })}
        {field({ label: 'Last name', k: 'last', placeholder: 'Doe', delay: 120, row: true })}
      </div>
      {field({ label: 'Email', k: 'email', type: 'email', placeholder: 'jane@company.com', delay: 180 })}
      {field({ label: 'Phone number', k: 'phone', placeholder: '+1 555 000 1234', delay: 240 })}
      {field({ label: 'Promo code', k: 'promo', placeholder: 'WELCOME25', optional: true, delay: 300 })}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8, animation: 'ms-rise 480ms ease-out both', animationDelay: '360ms' }}>
        <button type="submit" disabled={status === 'loading'} className="ms-submit"
          style={{ ...purpleBtn, background: 'linear-gradient(135deg,#B48FD6,#9B7EBD)', boxShadow: '0 12px 26px -12px rgba(155,126,189,0.55)', opacity: status === 'loading' ? 0.75 : 1, cursor: status === 'loading' ? 'default' : 'pointer' }}>
          {status === 'loading' ? 'Sending…' : 'Request a tour'}
        </button>
        <button type="button" onClick={() => { setF({ first: '', last: '', email: '', phone: '', promo: '' }); setErr({}); }} className="ms-ghost" style={ghostBtn}>Clear</button>
      </div>
    </form>
  );
}

/* ---------------- Package detail modal (photos + shared benefits) ---------------- */
function PackageModal({ pkg, onClose, onContact }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const offices = Array.isArray(pkg.details?.offices) ? pkg.details.offices : [];
  // All photos for this package family: the package's own images plus each office's.
  const shots = [
    ...(pkg.images || []),
    ...offices.flatMap((o) => o.photos || []),
  ].filter(Boolean);
  const benefits = (pkg.details?.common_benefits?.length ? pkg.details.common_benefits : pkg.features) || [];

  const card = {
    position: 'relative', width: 'min(920px, 100%)', maxHeight: '88vh', overflowY: 'auto',
    background: 'linear-gradient(180deg,#FFFFFF 0%,#FCFAF6 100%)', border: `1px solid ${MS.line}`,
    borderRadius: 22, padding: 'clamp(22px,4vw,38px)', boxShadow: '0 30px 60px -34px rgba(20,18,16,0.4)',
    animation: 'ms-modal 220ms ease-out both',
  };

  // Two large tiles per row on desktop. `min(300px, 100%)` keeps the track from
  // outgrowing a narrow phone — a bare 300px minimum would overflow the modal.
  const photoGrid = {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(300px, 100%), 1fr))',
    gap: 14, marginBottom: 26,
  };

  return (
    <div onClick={onClose} style={overlay(0.62)}>
      <div onClick={(e) => e.stopPropagation()} style={card}>
        <button onClick={onClose} aria-label="Close" style={{ position: 'absolute', top: 16, right: 16, width: 38, height: 38, borderRadius: 9999, border: 'none', background: MS.line2, color: MS.ink, fontSize: 18, cursor: 'pointer' }}>✕</button>

        <p style={{ color: MS.accent, fontSize: 12, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', margin: '0 0 10px' }}>{pkg.category?.name || 'Package'}</p>
        <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(24px,3.4vw,32px)', lineHeight: 1.2, margin: '0 0 12px', paddingRight: 40 }}>{pkg.name}</h3>
        {pkg.description && <p style={{ color: 'rgba(26,26,26,0.72)', fontSize: 16, lineHeight: 1.6, margin: '0 0 24px' }}>{pkg.description}</p>}

        {/* Photo gallery */}
        {shots.length > 0 ? (
          <div style={photoGrid}>
            {shots.map((src, i) => (
              <div key={i} style={{ aspectRatio: '4 / 3', borderRadius: 14, overflow: 'hidden', background: GALLERY_GRADS[i % GALLERY_GRADS.length] }}>
                <img src={src} alt={`${pkg.name} ${i + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
              </div>
            ))}
          </div>
        ) : (
          <div style={photoGrid}>
            {[0, 1, 2].map((i) => (
              <div key={i} style={{ aspectRatio: '4 / 3', borderRadius: 14, background: GALLERY_GRADS[i % GALLERY_GRADS.length], display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,0.9)', fontSize: 13, fontWeight: 600, textAlign: 'center', padding: 10 }}>Photos coming soon</div>
            ))}
          </div>
        )}

        {/* Shared-benefits callout */}
        {benefits.length > 0 && (
          <div style={{ background: 'rgba(155,126,189,0.08)', border: `1px solid ${MS.line}`, borderRadius: 16, padding: 'clamp(18px,3vw,24px)', marginBottom: 22 }}>
            <p style={{ margin: '0 0 14px', fontFamily: MS.serif, fontWeight: 700, fontSize: 18 }}>Every {pkg.name.toLowerCase()} shares the same benefits</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
              {benefits.map((b, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <span style={{ flex: '0 0 auto', width: 19, height: 19, marginTop: 1, borderRadius: 9999, background: 'rgba(155,126,189,0.18)', color: MS.accent, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11 }}>✓</span>
                  <span style={{ fontSize: 15, lineHeight: 1.45 }}>{b}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Individual offices (name / capacity only — no pricing) */}
        {offices.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <p style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: MS.muted }}>Choose the size that fits your team</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {offices.map((o, i) => (
                <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 14, color: '#3A362F', background: MS.line2, padding: '9px 15px', borderRadius: 9999 }}>
                  <strong style={{ fontWeight: 600 }}>{o.name}</strong>{o.capacity ? ` · ${o.capacity}` : ''}
                </span>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8 }}>
          <button onClick={onContact} style={{ ...purpleBtn, background: 'linear-gradient(135deg,#B48FD6,#9B7EBD)' }}>Book a tour</button>
        </div>
      </div>
    </div>
  );
}

/* ---------------- Customize-your-package modal (POST /customize/) ---------------- */
// Distinct swatches so each office type reads clearly on the shared calendar.
const OFFICE_COLORS = ['#9B7EBD', '#4F8A76', '#C0844E', '#5E79A8', '#B0678E', '#6E9E52', '#A85C5C', '#7C6FB0'];
// Selectable start times for hourly offices (07:00–21:00).
const TIME_OPTIONS = Array.from({ length: 15 }, (_, i) => `${String(7 + i).padStart(2, '0')}:00`);
function CustomizeModal({ offices, onClose }) {
  const [f, setF] = useState({ name: '', email: '', phone: '', details: '' });
  const [assign, setAssign] = useState({});             // iso day -> office name (one office per day)
  const [timing, setTiming] = useState({});             // office name -> { duration, start_time, hours }
  const [active, setActive] = useState(offices[0] || ''); // office the calendar taps assign to
  const [monthOffset, setMonthOffset] = useState(0);
  const [err, setErr] = useState({});
  const [status, setStatus] = useState('idle'); // idle | loading | success | failure
  const set = (k) => (e) => { setF((s) => ({ ...s, [k]: e.target.value })); setErr((s) => ({ ...s, [k]: undefined })); };
  const bd = (k) => (err[k] ? '#C77' : MS.line);
  const colorOf = (office) => OFFICE_COLORS[Math.max(0, offices.indexOf(office)) % OFFICE_COLORS.length];
  // Time of day chosen for each office (defaults to a full day).
  const timeOf = (office) => timing[office] || { duration: 'fullday', start_time: '09:00', hours: 2 };
  const setTime = (office, patch) => setTiming((t) => ({ ...t, [office]: { ...timeOf(office), ...patch } }));
  const timeLabel = (office) => { const t = timeOf(office); return t.duration === 'hourly' ? `${t.start_time} · ${t.hours}h` : 'Full day'; };

  const cal = buildCalendar(monthOffset, null);
  // Selectable (non-empty, not-past) cells in the month currently shown.
  const monthCells = cal.cells.filter((c) => !c.empty && !c.past);
  const monthFull = monthCells.length > 0 && monthCells.every((c) => assign[c.iso] === active);
  const counts = offices.reduce((acc, o) => ({ ...acc, [o]: 0 }), {});
  Object.values(assign).forEach((o) => { counts[o] = (counts[o] || 0) + 1; });
  const totalDays = Object.keys(assign).length;

  const clearDatesErr = () => setErr((s) => ({ ...s, days: undefined }));
  const toggleDay = (iso) => {
    if (!active) return;
    clearDatesErr();
    setAssign((a) => { const n = { ...a }; if (n[iso] === active) delete n[iso]; else n[iso] = active; return n; });
  };
  const toggleMonth = () => {
    if (!active) return;
    clearDatesErr();
    setAssign((a) => {
      const n = { ...a };
      monthCells.forEach((c) => { if (monthFull) { if (n[c.iso] === active) delete n[c.iso]; } else { n[c.iso] = active; } });
      return n;
    });
  };

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const submit = async (e) => {
    e.preventDefault();
    const er = {};
    if (!f.name.trim()) er.name = 'Required';
    if (!f.email.trim()) er.email = 'Required';
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email)) er.email = 'Enter a valid email';
    if (totalDays === 0) er.days = 'Add at least one day for one office';
    if (Object.keys(er).length) { setErr(er); return; }
    // Group the assigned days back into one line per office, carrying its time of day.
    const byOffice = {};
    Object.entries(assign).forEach(([iso, off]) => { (byOffice[off] = byOffice[off] || []).push(iso); });
    const items = Object.entries(byOffice).map(([office, ds]) => {
      const t = timeOf(office);
      const item = { office, dates: ds.sort(), duration: t.duration };
      if (t.duration === 'hourly') { item.start_time = t.start_time; item.hours = t.hours; }
      return item;
    });
    setStatus('loading');
    try {
      await submitCustomization({ name: f.name, email: f.email, phone: f.phone, details: f.details, items });
      setStatus('success');
    } catch { setStatus('failure'); }
  };

  const card = {
    position: 'relative', width: 'min(560px, 100%)', maxHeight: '88vh', overflowY: 'auto',
    background: 'linear-gradient(180deg,#FFFFFF 0%,#FCFAF6 100%)', border: `1px solid ${MS.line}`,
    borderRadius: 22, padding: 'clamp(24px,4vw,38px)', boxShadow: '0 30px 60px -34px rgba(20,18,16,0.4)',
    animation: 'ms-modal 220ms ease-out both',
  };
  const label = { fontSize: 14, fontWeight: 600, letterSpacing: '0.01em', color: '#3A362F', marginBottom: 7, display: 'block' };
  const close = (
    <button onClick={onClose} aria-label="Close" style={{ position: 'absolute', top: 16, right: 16, width: 38, height: 38, borderRadius: 9999, border: 'none', background: MS.line2, color: MS.ink, fontSize: 18, cursor: 'pointer' }}>✕</button>
  );

  if (status === 'success') return (
    <div onClick={onClose} style={overlay(0.62)}>
      <div onClick={(e) => e.stopPropagation()} style={{ ...card, textAlign: 'center' }}>
        {close}
        <span style={{ width: 60, height: 60, borderRadius: 9999, background: 'rgba(63,122,90,0.14)', color: MS.green, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, margin: '10px 0 20px', animation: 'ms-pop 500ms ease-out both' }}>✓</span>
        <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 26, margin: '0 0 10px' }}>Request sent</h3>
        <p style={{ color: 'rgba(26,26,26,0.72)', fontSize: 16, lineHeight: 1.6, margin: '0 0 26px' }}>Thanks — we've emailed your custom setup to our team. We'll be in touch within one business day to shape the perfect package.</p>
        <button onClick={onClose} className="ms-submit" style={{ ...purpleBtn, background: 'linear-gradient(135deg,#B48FD6,#9B7EBD)' }}>Done</button>
      </div>
    </div>
  );

  return (
    <div onClick={onClose} style={overlay(0.62)}>
      <form onClick={(e) => e.stopPropagation()} onSubmit={submit} style={card}>
        {close}
        <p style={{ color: MS.accent, fontSize: 12, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', margin: '0 0 10px' }}>Build your own</p>
        <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(23px,3.2vw,30px)', lineHeight: 1.2, margin: '0 0 8px', paddingRight: 40 }}>Customize your package</h3>
        <p style={{ color: 'rgba(26,26,26,0.68)', fontSize: 15, lineHeight: 1.55, margin: '0 0 24px' }}>Mix any spaces across any days — pick an office, then tap the days you want it. Add as many as you like.</p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* 1 — choose which office you're assigning days to */}
          <div>
            <label style={label}>1. Pick an office, then choose its days</label>
            {offices.length === 0 ? <p style={{ color: MS.faint, fontSize: 14 }}>No offices available.</p> : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {offices.map((o) => {
                  const on = active === o;
                  const col = colorOf(o);
                  return (
                    <button key={o} type="button" onClick={() => setActive(o)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 8, border: `1.5px solid ${on ? col : MS.line}`, background: on ? col : '#fff', color: on ? '#fff' : MS.ink, borderRadius: 9999, padding: '9px 15px', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                      <span style={{ width: 11, height: 11, borderRadius: 9999, background: on ? '#fff' : col, flex: '0 0 auto' }} />
                      {o}{counts[o] ? <span style={{ fontWeight: 600, opacity: 0.9 }}>· {counts[o]}</span> : null}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* 2 — set the time of day for the active office (full day or specific hours) */}
          {active && (
            <div>
              <label style={label}>2. Set the time for {active}</label>
              <div style={{ display: 'inline-flex', gap: 4, background: MS.line2, padding: 3, borderRadius: 10, marginBottom: 12 }}>
                {[['fullday', 'Full day'], ['hourly', 'Specific hours']].map(([v, l]) => {
                  const on = timeOf(active).duration === v;
                  return (
                    <button key={v} type="button" onClick={() => setTime(active, { duration: v })}
                      style={{ padding: '7px 15px', borderRadius: 8, border: 'none', cursor: 'pointer', fontFamily: MS.sans, fontSize: 13, fontWeight: 600, background: on ? '#fff' : 'transparent', color: on ? MS.ink : MS.faint, boxShadow: on ? '0 1px 2px rgba(20,18,16,0.12)' : 'none' }}>{l}</button>
                  );
                })}
              </div>
              {timeOf(active).duration === 'hourly' && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, alignItems: 'flex-end' }}>
                  <div>
                    <p style={{ fontSize: 12.5, color: MS.faint, margin: '0 0 6px' }}>Start time</p>
                    <select value={timeOf(active).start_time} onChange={(e) => setTime(active, { start_time: e.target.value })}
                      style={{ ...inputStyle, width: 'auto', padding: '10px 12px' }}>
                      {TIME_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div>
                    <p style={{ fontSize: 12.5, color: MS.faint, margin: '0 0 6px' }}>Hours</p>
                    <Stepper value={timeOf(active).hours} min={1} max={12} onChange={(v) => setTime(active, { hours: v })} suffix={timeOf(active).hours > 1 ? 'hrs' : 'hr'} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 3 — the shared calendar; taps colour a day for the active office */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
              <label style={{ ...label, marginBottom: 0 }}>3. Select your days</label>
              <button type="button" onClick={toggleMonth} disabled={!active} style={{ flex: '0 0 auto', background: monthFull ? MS.accent : 'transparent', color: monthFull ? '#fff' : MS.accent, border: `1.5px solid ${MS.accent}`, borderRadius: 9999, padding: '7px 16px', fontSize: 13, fontWeight: 600, cursor: active ? 'pointer' : 'not-allowed', opacity: active ? 1 : 0.5 }}>
                {monthFull ? 'Clear this month' : 'Select full month'}
              </button>
            </div>
            <div style={{ background: '#fff', border: `1px solid ${bd('days')}`, borderRadius: 14, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <button type="button" onClick={() => setMonthOffset((o) => Math.max(0, o - 1))} style={calNavBtn(monthOffset > 0)}>‹</button>
                <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 16, margin: 0, minWidth: 128, textAlign: 'center' }}>{cal.label}</p>
                <button type="button" onClick={() => setMonthOffset((o) => o + 1)} style={calNavBtn(true)}>›</button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3, marginBottom: 4 }}>
                {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((w) => <div key={w} style={{ textAlign: 'center', fontSize: 11, color: '#A9A39C', padding: '3px 0' }}>{w}</div>)}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3 }}>
                {cal.cells.map((c, i) => {
                  if (c.empty) return <div key={i} style={{ aspectRatio: '1' }} />;
                  const off = assign[c.iso];
                  return (
                    <div key={i} style={{ aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <button type="button" disabled={c.past || !active} onClick={() => toggleDay(c.iso)} title={off || ''} style={{ width: '100%', height: '100%', border: off === active ? '2px solid rgba(0,0,0,0.35)' : 'none', borderRadius: 9, background: off ? colorOf(off) : 'transparent', color: off ? '#fff' : (c.past ? '#C4BEB6' : MS.ink), fontSize: 13.5, fontWeight: off ? 600 : 400, cursor: (c.past || !active) ? 'not-allowed' : 'pointer' }}>{c.day}</button>
                    </div>
                  );
                })}
              </div>
            </div>
            {/* Summary of the mix so far */}
            {totalDays > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '12px 0 0' }}>
                {offices.filter((o) => counts[o]).map((o) => (
                  <span key={o} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 13, color: '#3A362F', background: MS.line2, padding: '6px 12px', borderRadius: 9999 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 9999, background: colorOf(o), flex: '0 0 auto' }} />
                    {counts[o]} day{counts[o] > 1 ? 's' : ''} · {o} · {timeLabel(o)}
                  </span>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 13, color: '#A9A39C', margin: '10px 0 0' }}>Tap days to add them for the selected office — or pick a whole month.</p>
            )}
            {err.days && <span style={{ fontSize: 12.5, color: MS.red }}>{err.days}</span>}
          </div>

          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 160px' }}>
              <label style={label}>Your name</label>
              <input value={f.name} onChange={set('name')} placeholder="Jane Doe" className="ms-input" style={{ ...inputStyle, border: `1px solid ${bd('name')}` }} />
              {err.name && <span style={{ fontSize: 12.5, color: MS.red }}>{err.name}</span>}
            </div>
            <div style={{ flex: '1 1 160px' }}>
              <label style={label}>Email</label>
              <input type="email" value={f.email} onChange={set('email')} placeholder="jane@company.com" className="ms-input" style={{ ...inputStyle, border: `1px solid ${bd('email')}` }} />
              {err.email && <span style={{ fontSize: 12.5, color: MS.red }}>{err.email}</span>}
            </div>
          </div>
          <div>
            <label style={label}>Phone <span style={{ color: '#A9A39C', fontWeight: 400 }}>(optional)</span></label>
            <input value={f.phone} onChange={set('phone')} placeholder="+1 555 000 1234" className="ms-input" style={inputStyle} />
          </div>
          <div>
            <label style={label}>Tell us more <span style={{ color: '#A9A39C', fontWeight: 400 }}>(optional)</span></label>
            <textarea value={f.details} onChange={set('details')} rows={4} placeholder="What does your team need? Meeting rooms, dedicated desks, specific dates…" className="ms-input" style={{ ...inputStyle, resize: 'vertical', minHeight: 96 }} />
          </div>
        </div>

        {status === 'failure' && <p style={{ color: MS.red, fontSize: 14, margin: '14px 0 0' }}>Couldn't send your request just now — please try again.</p>}

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 22 }}>
          <button type="submit" disabled={status === 'loading'} className="ms-submit"
            style={{ ...purpleBtn, background: 'linear-gradient(135deg,#B48FD6,#9B7EBD)', opacity: status === 'loading' ? 0.75 : 1, cursor: status === 'loading' ? 'default' : 'pointer' }}>
            {status === 'loading' ? 'Sending…' : 'Send request'}
          </button>
          <button type="button" onClick={onClose} className="ms-ghost" style={ghostBtn}>Cancel</button>
        </div>
      </form>
    </div>
  );
}

/* ---------------- Auth modal (login / register / forgot) ---------------- */
function AuthModal({ onClose, onAuthed, goDashboard, resetInfo }) {
  const { login, register, requestReset, confirmReset, logout, user, isAuthed } = useAuth();
  const [view, setView] = useState(resetInfo ? 'reset' : (isAuthed ? 'profile' : 'login'));
  const [email, setEmail] = useState('');
  const [pass, setPass] = useState('');
  const [pass2, setPass2] = useState('');
  const [name, setName] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const go = (v) => () => { setView(v); setErr(''); };
  const field = (label, value, onChange, type = 'text', placeholder = '') => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      <label style={{ fontSize: 14, fontWeight: 500 }}>{label}</label>
      <input value={value} onChange={(e) => { onChange(e.target.value); setErr(''); }} type={type} placeholder={placeholder} style={inputStyle} />
    </div>
  );

  const doLogin = async (e) => {
    e.preventDefault();
    if (!email.trim() || !pass.trim()) { setErr('Please enter your email and password.'); return; }
    setBusy(true);
    try { const u = await login(email, pass); onAuthed(u); }
    catch (ex) {
      const msg = apiError(ex, 'Invalid email or password.');
      if (/pending/i.test(msg)) setView('pending'); else setErr(msg);
    } finally { setBusy(false); }
  };
  const doRegister = async (e) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !pass.trim()) { setErr('Please fill in every field.'); return; }
    const [first, ...rest] = name.trim().split(' ');
    setBusy(true);
    try {
      await register({ first_name: first, last_name: rest.join(' ') || first, email, password: pass });
      // Accounts are auto-approved — sign the new member in immediately.
      const u = await login(email, pass);
      onAuthed(u);
    } catch (ex) {
      // Registration responds generically (anti-enumeration); if auto sign-in
      // didn't go through, send them to the login screen.
      setView('login'); setErr(apiError(ex, 'Please sign in with your new account.'));
    } finally { setBusy(false); }
  };
  const doForgot = async (e) => {
    e.preventDefault();
    if (!email.trim()) { setErr('Enter the email for your account.'); return; }
    setBusy(true);
    try { await requestReset(email); setView('sent'); } catch { setView('sent'); } finally { setBusy(false); }
  };
  const doReset = async (e) => {
    e.preventDefault();
    if (pass.length < 8) { setErr('Password must be at least 8 characters.'); return; }
    if (pass !== pass2) { setErr('The two passwords don\'t match.'); return; }
    setBusy(true);
    try { await confirmReset(resetInfo.uid, resetInfo.token, pass); setErr(''); setPass(''); setPass2(''); setView('reset_done'); }
    catch (ex) { setErr(apiError(ex, 'This reset link is invalid or has expired. Request a new one.')); }
    finally { setBusy(false); }
  };

  const submitBtn = (label) => (
    <button type="submit" disabled={busy} style={{ ...purpleBtn, width: '100%', padding: 14, marginTop: 4, opacity: busy ? 0.7 : 1 }}>{busy ? 'Please wait…' : label}</button>
  );
  const linkBtn = (label, onClick) => (
    <button type="button" onClick={onClick} style={{ background: 'none', border: 'none', color: MS.accent, fontSize: 14, fontWeight: 600, cursor: 'pointer', padding: 0 }}>{label}</button>
  );
  const heading = (t) => <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 24, margin: '0 0 4px', textAlign: 'center' }}>{t}</h3>;

  return (
    <div onClick={onClose} style={overlay()}>
      <div onClick={(e) => e.stopPropagation()} style={{ position: 'relative', background: MS.panel, width: 'min(440px, 100%)', borderRadius: 22, padding: 'clamp(28px,4vw,40px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)', animation: 'ms-modal 220ms ease-out both' }}>
        <button onClick={onClose} aria-label="Close" style={{ position: 'absolute', top: 18, right: 20, width: 38, height: 38, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
        <div style={{ textAlign: 'center', marginBottom: 26 }}>
          <img src={logoColor} alt="VividSpace" style={{ height: 66, width: 'auto', display: 'inline-block' }} />
        </div>
        {err && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13.5, fontWeight: 500, padding: '11px 14px', borderRadius: 10, margin: '0 0 18px', lineHeight: 1.4 }}>{err}</p>}

        {view === 'login' && (
          <form onSubmit={doLogin} style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
            {heading('Welcome back')}
            {field('Email', email, setEmail, 'text', 'you@company.com')}
            {field('Password', pass, setPass, 'password', '••••••••')}
            <div style={{ alignSelf: 'flex-end' }}>{linkBtn('Forgot password?', go('forgot'))}</div>
            {submitBtn('Log in')}
            <p style={{ textAlign: 'center', fontSize: 14, color: MS.muted, margin: '6px 0 0' }}>New here? {linkBtn('Create an account', go('register'))}</p>
          </form>
        )}
        {view === 'register' && (
          <form onSubmit={doRegister} style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
            {heading('Create your account')}
            {field('Full name', name, setName, 'text', 'Alex Rivera')}
            {field('Email', email, setEmail, 'text', 'you@company.com')}
            {field('Password', pass, setPass, 'password', 'At least 8 characters')}
            {submitBtn('Create account')}
            <p style={{ textAlign: 'center', fontSize: 14, color: MS.muted, margin: '6px 0 0' }}>Already a member? {linkBtn('Log in', go('login'))}</p>
          </form>
        )}
        {view === 'forgot' && (
          <form onSubmit={doForgot} style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
            {heading('Reset your password')}
            <p style={{ textAlign: 'center', fontSize: 14.5, color: MS.muted, margin: '0 0 6px', lineHeight: 1.5 }}>Enter your account email and we'll send a reset link.</p>
            {field('Email', email, setEmail, 'text', 'you@company.com')}
            {submitBtn('Send reset link')}
            <div style={{ textAlign: 'center' }}>{linkBtn('Back to log in', go('login'))}</div>
          </form>
        )}
        {view === 'reset' && (
          <form onSubmit={doReset} style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
            {heading('Set a new password')}
            <p style={{ textAlign: 'center', fontSize: 14.5, color: MS.muted, margin: '0 0 6px', lineHeight: 1.5 }}>Choose a new password for your Vivid Space account.</p>
            {field('New password', pass, setPass, 'password', 'At least 8 characters')}
            {field('Confirm password', pass2, setPass2, 'password', 'Re-enter password')}
            {submitBtn('Update password')}
            <div style={{ textAlign: 'center' }}>{linkBtn('Back to log in', go('login'))}</div>
          </form>
        )}
        {view === 'reset_done' && (
          <Centered icon="✓" tone="green" title="Password updated"
            body="Your password has been changed. You can now log in with your new password."
            action={<button onClick={go('login')} style={{ ...purpleBtn, padding: '12px 28px' }}>Log in</button>} />
        )}
        {view === 'pending' && (
          <Centered icon="◷" tone="amber" title="Account pending approval"
            body="Our team reviews every new member. You'll get an email as soon as your account is approved — usually within a day."
            action={<button onClick={go('login')} style={{ ...purpleBtn, padding: '12px 28px' }}>Back to log in</button>} />
        )}
        {view === 'sent' && (
          <Centered icon="✉" tone="green" title="Check your inbox"
            body={<>We've sent a password reset link to <strong style={{ color: MS.ink }}>{email}</strong>.</>}
            action={<button onClick={go('login')} style={{ ...purpleBtn, padding: '12px 28px' }}>Back to log in</button>} />
        )}
        {view === 'profile' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 14 }}>
            <span style={{ width: 68, height: 68, borderRadius: 9999, background: MS.accent2, color: MS.ink, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: MS.serif, fontWeight: 700, fontSize: 30 }}>{(user?.first_name || user?.email || 'A')[0].toUpperCase()}</span>
            <div>
              <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 23, margin: '0 0 2px' }}>{user?.full_name || `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || 'Member'}</h3>
              <p style={{ fontSize: 14, color: MS.muted, margin: 0 }}>{user?.email}</p>
            </div>
            <p style={{ fontSize: 13, color: MS.green, background: 'rgba(63,122,90,0.12)', padding: '6px 14px', borderRadius: 9999, margin: 0 }}>Signed in</p>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center', width: '100%', marginTop: 4 }}>
              <button onClick={goDashboard} style={{ ...purpleBtn, flex: '1 1 auto', padding: '12px 20px' }}>Go to dashboard</button>
              <button onClick={async () => { await logout(); setView('login'); setPass(''); }} style={{ ...ghostBtn, flex: '0 0 auto' }}>Log out</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Centered({ icon, tone, title, body, action }) {
  const t = TONES[tone] || TONES.neutral;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 12 }}>
      <span style={{ width: 56, height: 56, borderRadius: 9999, background: t.bg, color: t.color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26 }}>{icon}</span>
      <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 23, margin: 0 }}>{title}</h3>
      <p style={{ fontSize: 15, color: MS.muted, lineHeight: 1.55, margin: '0 0 8px' }}>{body}</p>
      {action}
    </div>
  );
}

/* ---------------- Booking modal (availability + create) ---------------- */
const MAX_HOURS = 12;

function BookingModal({ space, onClose, whishEnabled, payAtCenter = true }) {
  const navigate = useNavigate();
  // Which modes this space allows: by the hour and/or by the day.
  const modes = (() => {
    const d = space.durations && space.durations.length ? space.durations : ['hourly', 'fullday'];
    return ['hourly', 'fullday'].filter((x) => d.includes(x));
  })();
  const [mode, setMode] = useState(modes[0] || 'hourly');
  const [monthOffset, setMonthOffset] = useState(0);
  const [date, setDate] = useState(null);   // hourly: the single chosen date
  const [hours, setHours] = useState(1);     // hourly: how many hours the member wants
  const [dayset, setDayset] = useState([]);  // full day: the set of days chosen on the calendar
  const [slot, setSlot] = useState(null);
  const [unit, setUnit] = useState(null);    // which physical unit (rooms/desks) is booked
  const [attendees, setAttendees] = useState(1);
  const [avail, setAvail] = useState(null);
  const [fdTaken, setFdTaken] = useState([]);   // full-day: unit labels booked on selected days
  const [mem, setMem] = useState(null);         // member's plan/free-hours balance
  const [memLoading, setMemLoading] = useState(!!space.uses_free_hours);
  const [fdLoading, setFdLoading] = useState(false);  // full-day unit availability in flight
  const [availLoading, setAvailLoading] = useState(false);
  const [result, setResult] = useState(null); // { count, failed, first }
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const isHourly = mode === 'hourly';
  const cal = buildCalendar(monthOffset, isHourly ? date : null);
  const cap = Number(space.capacity) || null;
  const overCap = cap ? attendees > cap : false;
  const dayCount = dayset.length;
  const toggleDay = (iso) => setDayset((s) => (s.includes(iso) ? s.filter((x) => x !== iso) : [...s, iso].sort()));

  useEffect(() => {
    if (!isHourly || !date) { setAvail(null); return; }
    let alive = true;
    setAvailLoading(true); setSlot(null);
    getAvailability(space.key, date)
      .then((d) => { if (alive) setAvail(d); })
      .catch(() => { if (alive) setAvail(null); })
      .finally(() => { if (alive) setAvailLoading(false); });
    return () => { alive = false; };
  }, [date, space.key, isHourly]);

  // Which physical unit to book. Spaces with more than one unit make the member
  // pick a specific one so two people can't take the same room/desk at once.
  const unitLabels = space.unit_labels || [];
  const needsUnit = (Number(space.units) || 1) > 1 && unitLabels.length > 0;

  // For full-day bookings, load each selected day's availability so units already
  // booked on ANY chosen day are shown as taken (a full day occupies the whole day).
  const daysKey = dayset.join(',');
  useEffect(() => {
    if (isHourly || !needsUnit || dayset.length === 0) { setFdTaken([]); setFdLoading(false); return; }
    let alive = true;
    setFdLoading(true);
    Promise.all(dayset.map((d) => getAvailability(space.key, d).catch(() => null)))
      .then((results) => {
        if (!alive) return;
        const taken = new Set();
        for (const r of results) for (const t of (r?.taken || [])) if (t.unit) taken.add(t.unit);
        setFdTaken([...taken]);
      })
      .finally(() => { if (alive) setFdLoading(false); });
    return () => { alive = false; };
  }, [isHourly, needsUnit, space.key, daysKey]);

  // Units already taken for the current selection. Hourly: units overlapping the
  // chosen start → +hours window. Full day: units booked on any selected day.
  const toMin = (t) => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
  const occupied = new Set();
  if (isHourly && slot) {
    const s = toMin(slot);
    const e = s + hours * 60;
    for (const t of (avail?.taken || [])) {
      if (!t.unit) continue;
      const clash = t.fullday || !t.start || !t.end || (s < toMin(t.end) && toMin(t.start) < e);
      if (clash) occupied.add(t.unit);
    }
  } else if (!isHourly) {
    for (const u of fdTaken) occupied.add(u);
  }
  // Re-pick the unit whenever the slot/length/date/mode changes (availability shifts).
  useEffect(() => { setUnit(null); }, [slot, hours, date, mode]);

  // Cap the hours to the run of consecutive open slots from the chosen start, so a
  // booking can't stretch into a taken/blocked slot or past the center's closing time.
  const maxHours = (() => {
    const list = avail?.slots || [];
    if (!slot || !list.length) return MAX_HOURS;
    const idx = list.findIndex((s) => s.time === slot);
    if (idx < 0) return MAX_HOURS;
    let run = 0;
    for (let i = idx; i < list.length && list[i].available; i++) run++;
    return Math.max(1, Math.min(MAX_HOURS, run));
  })();
  useEffect(() => { setHours((h) => Math.min(h, maxHours)); }, [maxHours]);

  // Don't allow confirming a full-day booking while its per-day unit availability
  // is still loading (the `occupied` set would be stale).
  const unitReady = !needsUnit || (isHourly ? true : !fdLoading);
  const unitOk = (!needsUnit || (!!unit && !occupied.has(unit))) && unitReady;
  // Free meeting-room hours: for spaces that draw them down, load the member's
  // balance so we can show hours-used instead of a price when it's covered.
  const loadMem = useCallback(() => {
    if (!space.uses_free_hours) { setMem(null); setMemLoading(false); return; }
    setMemLoading(true);
    getOverview().then((o) => setMem(o?.membership || null)).catch(() => {}).finally(() => setMemLoading(false));
  }, [space.uses_free_hours]);
  useEffect(() => { loadMem(); }, [loadMem]);

  const freeTotal = mem ? (mem.effective_hours ?? mem.plan?.room_hours ?? 0) : 0;
  const freeLeft = mem ? (mem.room_hours_left ?? 0) : 0;
  const usesFree = space.uses_free_hours && isHourly && !!mem;   // member booking a free-hours space
  const coveredByFree = usesFree && freeLeft >= hours;
  const notEnoughFree = usesFree && freeLeft < hours;

  const rate = space.hour_price != null ? space.hour_price : space.day_price;
  const rateNum = space.hour_price != null ? Number(space.hour_price) : Number(space.day_price);
  // The amount actually payable (0 when free or covered by the plan's free hours).
  const amountNum = (space.free || coveredByFree) ? 0
    : (isHourly ? (rateNum || 0) * hours : (Number(space.day_price) || 0) * dayCount);
  let price = 'Pay at center';
  if (space.free) price = 'Free';
  else if (isHourly) price = money((rate || 0) * hours);
  else price = money((space.day_price || 0) * dayCount);

  // Paid bookings are settled online via Whish (when the center has it enabled and
  // once we know the member's free-hours balance, so a plan-covered slot is free).
  const canPayWhish = whishEnabled && amountNum > 0 && !memLoading;
  const payMethod = 'whish';
  // With "pay at center" switched off, a priced booking has to be paid online —
  // so if Whish can't take it either, there's no way to settle this one and the
  // backend would reject it. Say so instead of offering a button that fails.
  const noWayToPay = amountNum > 0 && !payAtCenter && !canPayWhish && !memLoading;

  const canConfirm = !overCap && unitOk && !notEnoughFree && !noWayToPay
    && (isHourly ? (!!date && !!slot) : dayCount >= 1);

  const confirm = async () => {
    if (!canConfirm || busy) return;
    setErr(''); setBusy(true);
    try {
      const unitField = needsUnit ? { unit } : {};
      // Pay with Whish → create one order (backend makes the held bookings), then
      // send the customer to the dedicated payment page.
      if (canPayWhish && payMethod === 'whish') {
        const list = isHourly
          ? [{ space: space.key, date, duration: 'hourly', start_time: slot, hours, attendees, ...unitField }]
          : [...dayset].sort().map((d) => ({ space: space.key, date: d, duration: 'fullday', attendees, ...unitField }));
        const order = await createOrder({ payment_method: 'whish', bookings: list });
        onClose();
        navigate(`/pay/${order.order_number}`);
        return;
      }
      if (isHourly) {
        const booking = await createBooking({ space: space.key, date, duration: 'hourly', start_time: slot, hours, attendees, ...unitField });
        setResult({ count: 1, failed: [], first: booking });
      } else {
        // Book each selected day as its own full-day booking.
        const dates = [...dayset].sort();
        const failed = []; let first = null;
        for (const d of dates) {
          try { const b = await createBooking({ space: space.key, date: d, duration: 'fullday', attendees, ...unitField }); if (!first) first = b; }
          catch (ex) { failed.push({ date: d, msg: apiError(ex, 'Unavailable') }); }
        }
        if (!first) { setErr(dates.length > 1 ? `None of the ${dates.length} days could be booked — they may be unavailable.` : (failed[0]?.msg || 'Could not complete the booking.')); setBusy(false); return; }
        setResult({ count: dates.length - failed.length, failed, first });
      }
    } catch (ex) { setErr(apiError(ex, 'Could not complete the booking.')); }
    finally { setBusy(false); }
  };

  const slots = avail?.slots || [];

  return (
    <div onClick={onClose} style={overlay()}>
      <div onClick={(e) => e.stopPropagation()} style={{ background: MS.panel, width: 'min(980px, 100%)', maxHeight: '92vh', overflowY: 'auto', borderRadius: 22, boxShadow: '0 30px 80px rgba(20,18,16,0.32)', animation: 'ms-modal 220ms ease-out both' }}>
        <div style={{ position: 'sticky', top: 0, zIndex: 2, background: MS.panel, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: 'clamp(20px,3vw,28px) clamp(20px,3vw,32px)', borderBottom: `1px solid ${MS.line}` }}>
          <div>
            <p style={{ color: MS.accent, fontSize: 12, fontWeight: 600, letterSpacing: '0.16em', textTransform: 'uppercase', margin: '0 0 6px' }}>Book a space</p>
            <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(22px,2.6vw,28px)', margin: 0 }}>{space.name}</h3>
            <p style={{ color: MS.muted, fontSize: 14, margin: '4px 0 0' }}>{space.capacity ? `${space.capacity} people` : ''}{space.size ? ` · ${space.size}` : ''}</p>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ flex: '0 0 auto', width: 42, height: 42, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 18, cursor: 'pointer' }}>✕</button>
        </div>

        {result ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: 'clamp(36px,6vw,64px) clamp(24px,4vw,40px)' }}>
            <span style={{ width: 64, height: 64, borderRadius: 9999, background: 'rgba(63,122,90,0.14)', color: MS.green, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 30, marginBottom: 22 }}>✓</span>
            <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(24px,3vw,30px)', margin: '0 0 12px' }}>Booking confirmed</h3>
            <p style={{ color: 'rgba(26,26,26,0.7)', fontSize: 16, lineHeight: 1.6, margin: '0 0 8px', maxWidth: 380 }}>{isHourly
              ? `${space.name}${needsUnit && unit ? ` · ${unit}` : ''} · ${fmtDate(date)}${slot ? ` at ${slot}` : ''} · ${hours} hr${hours > 1 ? 's' : ''}`
              : `${space.name}${needsUnit && unit ? ` · ${unit}` : ''} · ${result.count} full day${result.count > 1 ? 's' : ''} booked`}</p>
            {result.failed && result.failed.length > 0 && (
              <p style={{ color: MS.red, fontSize: 13.5, margin: '0 0 8px', maxWidth: 380 }}>{result.failed.length} day{result.failed.length > 1 ? 's were' : ' was'} unavailable and skipped.</p>
            )}
            <p style={{ color: MS.faint, fontSize: 14, margin: '0 0 30px' }}>Confirmation {result.first?.id ? `MS-${result.first.id}` : ''} — we've emailed you the details.</p>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
              <button onClick={() => { setResult(null); setDate(null); setSlot(null); setDayset([]); loadMem(); }} style={ghostBtn}>Book another slot</button>
              <button onClick={onClose} style={{ ...purpleBtn, padding: '12px 28px' }}>Done</button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 'clamp(24px,3vw,40px)', padding: 'clamp(22px,3vw,32px)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 30 }}>
              {/* Calendar */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                  <p style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: 0 }}>{isHourly ? 'Select a date' : 'Select full days'}</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <button onClick={() => setMonthOffset((o) => Math.max(0, o - 1))} style={calNavBtn(monthOffset > 0)}>‹</button>
                    <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 17, margin: 0, minWidth: 128, textAlign: 'center' }}>{cal.label}</p>
                    <button onClick={() => setMonthOffset((o) => o + 1)} style={calNavBtn(true)}>›</button>
                  </div>
                </div>
                {!isHourly && <p style={{ fontSize: 13, color: MS.faint, margin: '0 0 10px' }}>Tap each full day you want — pick as many as you like.</p>}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginBottom: 6 }}>
                  {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((w) => <div key={w} style={{ textAlign: 'center', fontSize: 12, color: '#A9A39C', padding: '4px 0' }}>{w}</div>)}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
                  {cal.cells.map((c, i) => c.empty ? <div key={i} style={{ aspectRatio: '1' }} /> : (
                    <div key={i} style={{ aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {(() => {
                        const sel = isHourly ? c.sel : dayset.includes(c.iso);
                        // Full-day bookings are for upcoming days only — today's is already under way.
                        const off = c.past || (!isHourly && c.iso === todayIso());
                        return (
                        <button disabled={off} onClick={() => (isHourly ? setDate(c.iso) : toggleDay(c.iso))} style={{ width: '100%', height: '100%', border: 'none', borderRadius: 10, background: sel ? MS.accent : 'transparent', color: sel ? '#fff' : (off ? '#C4BEB6' : MS.ink), fontSize: 14, fontWeight: sel ? 600 : 400, cursor: off ? 'not-allowed' : 'pointer' }}>{c.day}</button>
                      ); })()}
                    </div>
                  ))}
                </div>
              </div>

              {/* Time slots */}
              {isHourly && (
                <div>
                  <p style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: '0 0 14px' }}>Available time slots</p>
                  {!date ? <p style={{ color: MS.faint, fontSize: 14 }}>Pick a date to see open slots.</p>
                    : availLoading ? <p style={{ color: MS.faint, fontSize: 14 }}>Loading…</p>
                    : avail?.closed ? <p style={{ color: MS.red, fontSize: 14 }}>Closed on this day.</p>
                    : slots.length === 0 ? <p style={{ color: MS.faint, fontSize: 14 }}>No slots available.</p>
                    : (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(74px, 1fr))', gap: 8 }}>
                        {slots.map((s) => {
                          const sel = slot === s.time;
                          const disabled = !s.available;
                          return (
                            <button key={s.time} onClick={() => s.available && setSlot(s.time)} disabled={disabled}
                              style={{ padding: '11px 0', borderRadius: 10, border: `1px solid ${sel ? MS.accent : (disabled ? '#EAE5DE' : MS.line)}`, background: sel ? 'rgba(155,126,189,0.18)' : (disabled ? MS.line2 : '#fff'), color: disabled ? '#B4AEA6' : MS.ink, fontSize: 14, fontWeight: 500, cursor: disabled ? 'not-allowed' : 'pointer', textDecoration: disabled ? 'line-through' : 'none' }}>{s.time}</button>
                          );
                        })}
                      </div>
                    )}
                </div>
              )}

              {/* Unit picker — spaces with several rooms/desks book one specific unit */}
              {needsUnit && (() => {
                const ready = isHourly ? !!slot : dayCount >= 1;
                return (
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: '0 0 14px' }}>Select a unit</p>
                    {!ready ? (
                      <p style={{ color: MS.faint, fontSize: 14 }}>{isHourly ? 'Pick a date and a time slot to see which units are open.' : 'Pick at least one day to choose a unit.'}</p>
                    ) : (
                      <>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(88px, 1fr))', gap: 8 }}>
                          {unitLabels.map((u) => {
                            const taken = occupied.has(u);
                            const sel = unit === u;
                            return (
                              <button key={u} onClick={() => !taken && setUnit(u)} disabled={taken} title={taken ? `${u} — already booked` : u}
                                style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, minHeight: 52, padding: '8px 6px', borderRadius: 10, border: `1px solid ${sel ? MS.accent : (taken ? '#E4DED6' : MS.line)}`, background: sel ? 'rgba(155,126,189,0.18)' : (taken ? MS.line2 : '#fff'), color: taken ? '#A9A39C' : MS.ink, fontSize: 14, fontWeight: 500, cursor: taken ? 'not-allowed' : 'pointer', opacity: taken ? 0.85 : 1 }}>
                                <span style={{ maxWidth: '100%', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textDecoration: taken ? 'line-through' : 'none' }}>{u}</span>
                                {taken && <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: MS.red }}>● Booked</span>}
                              </button>
                            );
                          })}
                        </div>
                        {!isHourly && fdLoading && (
                          <p style={{ color: MS.faint, fontSize: 13, margin: '10px 0 0' }}>Checking availability for the selected day(s)…</p>
                        )}
                        {!fdLoading && occupied.size >= unitLabels.length && (
                          <p style={{ color: MS.red, fontSize: 13.5, margin: '10px 0 0' }}>All units are booked{isHourly ? ' for this time — try another slot.' : ' for the selected day(s) — try another day.'}</p>
                        )}
                        {!isHourly && !fdLoading && <p style={{ color: MS.faint, fontSize: 13, margin: '10px 0 0' }}>This unit will be booked for each selected day.</p>}
                      </>
                    )}
                  </div>
                );
              })()}

              {/* Booking type + how much (hours) + attendees */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 28 }}>
                {modes.length > 1 && (
                  <div>
                    <p style={capLabel}>Booking type</p>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {modes.map((mo) => {
                        const on = mode === mo;
                        return <button key={mo} onClick={() => { setMode(mo); setSlot(null); }} style={{ padding: '9px 16px', borderRadius: 9999, border: `1px solid ${on ? MS.accent : MS.line}`, background: on ? MS.accent : '#fff', color: on ? '#fff' : MS.ink, fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>{mo === 'hourly' ? 'By the hour' : 'By the day'}</button>;
                      })}
                    </div>
                  </div>
                )}
                {isHourly ? (
                  <div>
                    <p style={capLabel}>Hours</p>
                    <Stepper value={hours} min={1} max={maxHours} onChange={setHours} suffix={hours > 1 ? 'hrs' : 'hr'} />
                    <p style={{ fontSize: 12, color: MS.faint, margin: '8px 0 0', whiteSpace: 'nowrap', visibility: (slot && hours >= maxHours) ? 'visible' : 'hidden' }}>Max for this slot</p>
                  </div>
                ) : (
                  <div>
                    <p style={capLabel}>Full days selected</p>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 22 }}>{dayCount}</span>
                      {dayCount > 0 && <button onClick={() => setDayset([])} style={{ background: 'none', border: `1px solid ${MS.line}`, color: MS.muted, fontSize: 13, fontWeight: 500, padding: '6px 14px', borderRadius: 9999, cursor: 'pointer' }}>Clear</button>}
                    </div>
                  </div>
                )}
                <div>
                  <p style={capLabel}>Attendees</p>
                  <Stepper value={attendees} min={1} max={cap || 999} onChange={setAttendees} />
                </div>
              </div>
            </div>

            {/* Summary */}
            <div style={{ alignSelf: 'start' }}>
              <div style={{ background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 16, padding: 24 }}>
                <h4 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 20, margin: '0 0 18px' }}>Booking summary</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 15 }}>
                  <SumRow label="Space" value={space.name} />
                  {isHourly
                    ? <><SumRow label="Date" value={fmtDate(date)} /><SumRow label="Time" value={slot || '—'} /></>
                    : <SumRow label="Days" value={dayCount ? dayset.map((d) => fmtDate(d)).join(', ') : '—'} />}
                  <SumRow label="Duration" value={isHourly ? `${hours} hr${hours > 1 ? 's' : ''}` : `${dayCount} full day${dayCount > 1 ? 's' : ''}`} />
                  <SumRow label="Attendees" value={String(attendees)} />
                </div>
                {coveredByFree ? (
                  /* Covered by the member's free meeting-room hours — show hours used, not a price. */
                  <div style={{ background: 'rgba(63,122,90,0.12)', color: MS.green, borderRadius: 12, padding: '16px 18px', margin: '18px 0', lineHeight: 1.5 }}>
                    <div style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 20 }}>Free with your plan</div>
                    <div style={{ fontSize: 13.5, fontWeight: 500, marginTop: 4 }}>
                      Using <strong>{hours} of your {freeTotal} free meeting-room hour{freeTotal === 1 ? '' : 's'}</strong> · {Math.max(0, freeLeft - hours)} hr{Math.max(0, freeLeft - hours) === 1 ? '' : 's'} left after this
                    </div>
                  </div>
                ) : notEnoughFree ? (
                  <div style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13, fontWeight: 500, padding: '12px 14px', borderRadius: 10, margin: '18px 0', lineHeight: 1.4 }}>
                    You have {freeLeft} free hour{freeLeft === 1 ? '' : 's'} left, but this booking needs {hours}. Lower the hours to book it with your plan.
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', borderTop: `1px solid ${MS.line}`, paddingTop: 16, margin: '18px 0' }}>
                    <span style={{ fontSize: 15, color: MS.muted }}>Total</span>
                    <span style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 28 }}>{price}</span>
                  </div>
                )}
                {/* Paid bookings are settled online via Whish */}
                {canPayWhish && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 14px', borderRadius: 12, border: `1.5px solid ${MS.accent}`, background: 'rgba(155,126,189,0.10)', margin: '4px 0 18px' }}>
                    <span style={{ flex: '0 0 auto', width: 16, height: 16, borderRadius: 9999, background: MS.accent }} />
                    <span><span style={{ fontWeight: 600, fontSize: 14.5 }}>Pay with Whish</span><br /><span style={{ fontSize: 12.5, color: MS.muted }}>Transfer now & upload your receipt to confirm</span></span>
                  </div>
                )}
                {noWayToPay && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13, fontWeight: 500, padding: '10px 14px', borderRadius: 10, margin: '0 0 14px', lineHeight: 1.4 }}>Online payment is required for this booking, but it isn’t available right now. Please contact the center to book it.</p>}
                {overCap && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13, fontWeight: 500, padding: '10px 14px', borderRadius: 10, margin: '0 0 14px', lineHeight: 1.4 }}>Capacity exceeded — max is {cap}.</p>}
                {err && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13, fontWeight: 500, padding: '10px 14px', borderRadius: 10, margin: '0 0 14px', lineHeight: 1.4 }}>{err}</p>}
                <button onClick={confirm} disabled={!canConfirm || busy} style={{ width: '100%', background: (canConfirm && !busy) ? MS.accent : '#ECE8E2', color: (canConfirm && !busy) ? '#fff' : '#A9A39C', border: 'none', fontSize: 16, fontWeight: 600, padding: 15, borderRadius: 9999, cursor: (canConfirm && !busy) ? 'pointer' : 'not-allowed' }}>{busy ? 'Working…' : (canPayWhish && payMethod === 'whish' ? 'Continue to Whish payment' : 'Confirm booking')}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
const calNavBtn = (enabled) => ({ width: 34, height: 34, borderRadius: 9999, border: `1px solid ${MS.line}`, background: enabled ? '#fff' : '#F3F1EC', color: enabled ? MS.ink : '#C4BEB6', cursor: enabled ? 'pointer' : 'not-allowed', fontSize: 18 });
const stepBtn = { width: 34, height: 34, borderRadius: 9999, border: 'none', background: MS.line2, color: MS.ink, fontSize: 18, cursor: 'pointer' };
const capLabel = { fontSize: 13, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: '0 0 12px' };
function Stepper({ value, min = 1, max = 99, onChange, suffix }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: `1px solid ${MS.line}`, borderRadius: 9999, padding: 4, background: '#fff' }}>
      <button onClick={() => onChange(Math.max(min, value - 1))} style={stepBtn}>−</button>
      <span style={{ minWidth: suffix ? 60 : 28, textAlign: 'center', fontSize: 16, fontWeight: 600 }}>{value}{suffix ? ` ${suffix}` : ''}</span>
      <button onClick={() => onChange(Math.min(max, value + 1))} style={stepBtn}>+</button>
    </div>
  );
}
function SumRow({ label, value }) {
  return <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><span style={{ color: MS.muted }}>{label}</span><span style={{ fontWeight: 500, textAlign: 'right' }}>{value}</span></div>;
}

/* ---------------- Member dashboard (overview + bookings) ---------------- */
const RES_TONE = { Upcoming: 'green', Confirmed: 'green', Pending: 'amber', Completed: 'neutral', Cancelled: 'red' };
function DashboardModal({ user, onClose }) {
  const { logout } = useAuth();
  const [overview, setOverview] = useState(null);
  const [tab, setTab] = useState('upcoming');
  const [bookings, setBookings] = useState([]);
  const [detail, setDetail] = useState(null);
  const [reschedule, setReschedule] = useState(null);   // booking being rescheduled
  const [allocMonthIdx, setAllocMonthIdx] = useState(0);

  const name = user?.first_name || user?.full_name?.split(' ')[0] || 'there';
  const load = useCallback((when) => getBookings(when).then((d) => setBookings(Array.isArray(d) ? d : [])).catch(() => setBookings([])), []);

  useEffect(() => { getOverview().then(setOverview).catch(() => {}); }, []);
  useEffect(() => { load(tab); }, [tab, load]);

  const doCancel = async (id) => {
    try { await cancelBooking(id); load(tab); getOverview().then(setOverview).catch(() => {}); setDetail(null); }
    catch { /* ignore */ }
  };
  // A reschedule request was submitted — reflect the now-locked booking.
  const onRescheduled = () => { setReschedule(null); setDetail(null); load(tab); };

  const [scheduleEdit, setScheduleEdit] = useState(false);   // package-schedule editor open
  // A schedule change was submitted — refresh the membership to show the pending state.
  const onScheduleRequested = () => { setScheduleEdit(false); getOverview().then(setOverview).catch(() => {}); };

  const m = overview?.membership;
  const stats = overview?.stats || {};
  const freeTotal = m?.effective_hours ?? m?.plan?.room_hours ?? 0;
  const freeLeft = m?.room_hours_left ?? 0;
  const freePct = freeTotal ? Math.round((freeLeft / freeTotal) * 100) : 0;

  // The admin can split a member's month across several packages (dated
  // custom_components). Colour each package's days and let the member browse
  // the months the allocation covers.
  const allocComps = (m?.custom_components || []).filter((c) => c && (c.lifetime || (Array.isArray(c.dates) && c.dates.length)));
  const dayColor = {}, dayName = {};
  allocComps.forEach((c, ci) => {
    const col = OFFICE_COLORS[ci % OFFICE_COLORS.length];
    (c.dates || []).forEach((iso) => { dayColor[iso] = col; dayName[iso] = c.name; });
  });
  // Packages whose days the member is allowed to rearrange (lifetime ones are fixed).
  const editableComps = (m?.custom_components || []).filter((c) => c && !c.lifetime && c.name);
  const schedulePending = !!m?.schedule_change_requested;
  const allocMonths = Array.from(new Set(Object.keys(dayColor).map((iso) => iso.slice(0, 7)))).sort();
  const selMonth = allocMonths[Math.min(allocMonthIdx, allocMonths.length - 1)] || null;
  let allocCal = null;
  if (selMonth) {
    const now = new Date();
    const [sy, sm] = selMonth.split('-').map(Number);
    allocCal = buildCalendar((sy - now.getFullYear()) * 12 + (sm - 1 - now.getMonth()), null);
  }
  const monthLabel = (ym) => { const [y, mo] = ym.split('-').map(Number); return new Date(y, mo - 1, 1).toLocaleString('en-US', { month: 'short', year: 'numeric' }); };

  const kpi = (label, big, small) => (
    <div style={{ background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 16, padding: '22px 24px' }}>
      <p style={{ fontSize: 12, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: '0 0 12px' }}>{label}</p>
      {big}{small}
    </div>
  );

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 90, background: MS.bg, overflowY: 'auto', animation: 'ms-appear 240ms ease-out both' }}>
      <div style={{ position: 'sticky', top: 0, zIndex: 2, background: 'rgba(245,241,237,0.92)', backdropFilter: 'blur(12px)', borderBottom: `1px solid ${MS.line}` }}>
        <div style={{ maxWidth: 1180, margin: '0 auto', height: 72, padding: '0 clamp(16px,4vw,32px)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
          <img src={logoColor} alt="VividSpace" style={{ height: 46, width: 'auto', display: 'block' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
              <span style={{ width: 34, height: 34, flex: '0 0 auto', borderRadius: 9999, background: MS.accent2, color: MS.ink, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: MS.serif, fontWeight: 700, fontSize: 16 }}>{(name[0] || 'M').toUpperCase()}</span>
              <span style={{ fontSize: 14, fontWeight: 500, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.full_name || name}</span>
            </span>
            <button onClick={onClose} style={{ flex: '0 0 auto', background: 'none', border: `1px solid ${MS.line}`, borderRadius: 9999, padding: '9px 18px', fontSize: 14, fontWeight: 500, color: MS.ink, cursor: 'pointer' }}>Back to site</button>
            <button onClick={async () => { await logout(); onClose(); }} style={{ flex: '0 0 auto', background: MS.ink, border: `1px solid ${MS.ink}`, borderRadius: 9999, padding: '9px 18px', fontSize: 14, fontWeight: 500, color: MS.panel, cursor: 'pointer' }}>Log out</button>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1180, margin: '0 auto', padding: 'clamp(28px,4vw,48px) clamp(16px,4vw,32px)' }}>
        <p style={{ color: MS.accent, fontSize: 13, fontWeight: 600, letterSpacing: '0.16em', textTransform: 'uppercase', margin: '0 0 10px' }}>Member dashboard</p>
        <h1 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(28px,4vw,40px)', margin: '0 0 36px' }}>Welcome back, {name}</h1>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 18, marginBottom: 44 }}>
          {kpi('Current membership',
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 24, margin: 0 }}>{m?.display_name || m?.plan?.name || 'No plan'}</p>
              {m?.is_custom && <span style={{ background: 'rgba(155,126,189,0.16)', color: MS.accent, fontSize: 11, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', padding: '3px 9px', borderRadius: 9999 }}>Custom</span>}
            </div>,
            <p style={{ color: MS.muted, fontSize: 14, margin: '6px 0 0' }}>{m ? `${m.price_display ? `${m.price_display} · ` : ''}${m.member_since ? `Member since ${new Date(m.member_since).getFullYear()}` : ''}` : '—'}</p>)}
          {kpi('Free meeting-room hours',
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}><span style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 24 }}><CountUp value={Number(freeLeft) || 0} /></span><span style={{ color: MS.muted, fontSize: 14 }}>/ {freeTotal} left</span></div>,
            <div style={{ height: 8, background: '#E9E4DD', borderRadius: 9999, marginTop: 14, overflow: 'hidden' }}><div style={{ height: '100%', background: MS.accent, borderRadius: 9999, width: `${freePct}%` }} /></div>)}
          {kpi('Bookings this month',
            <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 24, margin: 0 }}><CountUp value={Number(stats.this_month) || 0} /></p>,
            <p style={{ color: MS.muted, fontSize: 14, margin: '6px 0 0' }}>confirmed daily bookings</p>)}
          {kpi('Upcoming bookings',
            <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 24, margin: 0 }}><CountUp value={(overview?.upcoming || []).length} /></p>,
            <p style={{ color: MS.muted, fontSize: 14, margin: '6px 0 0' }}>scheduled ahead</p>)}
        </div>

        {allocComps.length > 0 && (
          <div style={{ background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 16, padding: 'clamp(20px,3vw,28px)', marginBottom: 44 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 18 }}>
              <h2 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(20px,2.6vw,24px)', margin: 0 }}>Your package{m?.display_name ? ` · ${m.display_name}` : ''}</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <span style={{ color: MS.muted, fontSize: 14 }}>{[Object.keys(dayColor).length > 0 ? `${Object.keys(dayColor).length} days planned` : '', allocComps.some((c) => c.lifetime) ? 'lifetime access' : ''].filter(Boolean).join(' · ')}</span>
                {schedulePending
                  ? <span style={{ background: TONES.lilac.bg, color: TONES.lilac.color, fontSize: 12.5, fontWeight: 600, padding: '6px 13px', borderRadius: 9999 }}>Change pending review</span>
                  : editableComps.length > 0 && <button onClick={() => setScheduleEdit(true)} style={{ background: 'none', border: `1px solid ${MS.accent}`, color: MS.accent, fontSize: 13.5, fontWeight: 600, padding: '8px 16px', borderRadius: 9999, cursor: 'pointer' }}>Edit schedule</button>}
              </div>
            </div>
            {schedulePending && (
              <p style={{ background: TONES.lilac.bg, color: TONES.lilac.color, fontSize: 13.5, fontWeight: 500, padding: '11px 15px', borderRadius: 12, margin: '0 0 18px', lineHeight: 1.5 }}>You've requested changes to your schedule below. Our team is reviewing them — your current schedule stays in place until they're approved.</p>
            )}
            {/* Legend — days per package */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 20 }}>
              {allocComps.map((c, ci) => (
                <span key={ci} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 13.5, color: '#3A362F', background: MS.line2, padding: '7px 13px', borderRadius: 9999 }}>
                  <span style={{ width: 11, height: 11, borderRadius: 9999, background: OFFICE_COLORS[ci % OFFICE_COLORS.length], flex: '0 0 auto' }} />
                  <strong style={{ fontWeight: 600 }}>{c.lifetime ? 'Lifetime ∞' : `${c.dates.length} day${c.dates.length > 1 ? 's' : ''}`}</strong> · {c.name}
                </span>
              ))}
            </div>
            {/* Read-only month calendar showing which package covers each day */}
            {allocCal && (
              <div style={{ maxWidth: 460 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <button onClick={() => setAllocMonthIdx((i) => Math.max(0, i - 1))} disabled={allocMonthIdx <= 0} aria-label="Previous month" style={calNavBtn(allocMonthIdx > 0)}>‹</button>
                  <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 16, margin: 0 }}>{monthLabel(selMonth)}</p>
                  <button onClick={() => setAllocMonthIdx((i) => Math.min(allocMonths.length - 1, i + 1))} disabled={allocMonthIdx >= allocMonths.length - 1} aria-label="Next month" style={calNavBtn(allocMonthIdx < allocMonths.length - 1)}>›</button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginBottom: 5 }}>
                  {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((w) => <div key={w} style={{ textAlign: 'center', fontSize: 11, color: '#A9A39C' }}>{w}</div>)}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
                  {allocCal.cells.map((c, i) => {
                    if (c.empty) return <div key={i} style={{ aspectRatio: '1' }} />;
                    const col = dayColor[c.iso];
                    return (
                      <div key={i} title={col ? dayName[c.iso] : ''} style={{ aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, background: col || 'transparent', color: col ? '#fff' : MS.muted, fontSize: 13, fontWeight: col ? 600 : 400 }}>{c.day}</div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        <h2 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(22px,3vw,28px)', margin: '0 0 20px' }}>Your daily bookings</h2>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 22 }}>
          {['upcoming', 'past', 'cancelled'].map((k) => (
            <button key={k} onClick={() => setTab(k)} style={chip(tab === k)}>{k[0].toUpperCase() + k.slice(1)}</button>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {bookings.length === 0 && <div style={{ background: '#fff', border: '1px dashed #D8D2CA', borderRadius: 16, padding: '48px 24px', textAlign: 'center', color: MS.faint, fontSize: 15 }}>No bookings in this list yet.</div>}
          {bookings.map((r) => {
            const tone = TONES[RES_TONE[r.status] || 'neutral'];
            const payTone = r.free ? TONES.green : TONES.amber;
            const locked = !!r.change_requested;            // awaiting admin review — no further edits
            const cancellable = r.when === 'upcoming' && !locked;
            const reschedulable = r.when === 'upcoming' && !locked;
            return (
              <div key={r.id} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '16px 24px', background: '#fff', border: `1px solid ${locked ? MS.accent : MS.line}`, borderRadius: 16, padding: '20px 24px' }}>
                <div style={{ flex: '1 1 220px', minWidth: 0 }}>
                  <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 20, margin: '0 0 5px' }}>{r.space}</h3>
                  <p style={{ color: MS.muted, fontSize: 14, margin: 0 }}>{r.mon} {r.day} · {r.time} · {r.duration === 'fullday' ? 'Full day' : 'Hourly'}{r.attendees ? ` · ${r.attendees} guests` : ''}</p>
                  {locked && r.requested && (
                    <p style={{ color: MS.accent, fontSize: 13, fontWeight: 500, margin: '7px 0 0' }}>Change requested → {r.requested.mon} {r.requested.day} · {r.requested.time} — awaiting review</p>
                  )}
                </div>
                {locked
                  ? <span style={{ flex: '0 0 auto', background: TONES.lilac.bg, color: TONES.lilac.color, fontSize: 12.5, fontWeight: 600, padding: '5px 13px', borderRadius: 9999 }}>Change pending</span>
                  : <span style={{ flex: '0 0 auto', background: tone.bg, color: tone.color, fontSize: 12.5, fontWeight: 600, padding: '5px 13px', borderRadius: 9999 }}>{r.status}</span>}
                <span style={{ flex: '0 0 auto', background: payTone.bg, color: payTone.color, fontSize: 12.5, fontWeight: 600, padding: '5px 13px', borderRadius: 9999 }}>{r.cost}</span>
                <div style={{ flex: '0 0 auto', display: 'flex', gap: 8 }}>
                  <button onClick={() => setDetail(r)} style={{ background: 'none', border: `1px solid ${MS.line}`, color: MS.ink, fontSize: 13.5, fontWeight: 600, padding: '8px 16px', borderRadius: 9999, cursor: 'pointer' }}>Details</button>
                  {reschedulable && <button onClick={() => setReschedule(r)} style={{ background: 'none', border: `1px solid ${MS.accent}`, color: MS.accent, fontSize: 13.5, fontWeight: 600, padding: '8px 16px', borderRadius: 9999, cursor: 'pointer' }}>Reschedule</button>}
                  {cancellable && <button onClick={() => doCancel(r.id)} style={{ background: 'none', border: '1px solid rgba(168,90,74,0.4)', color: MS.red, fontSize: 13.5, fontWeight: 600, padding: '8px 16px', borderRadius: 9999, cursor: 'pointer' }}>Cancel</button>}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {detail && (
        <div onClick={() => setDetail(null)} style={overlay()}>
          <div onClick={(e) => e.stopPropagation()} style={{ position: 'relative', background: MS.panel, width: 'min(460px, 100%)', borderRadius: 22, padding: 'clamp(26px,4vw,36px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)', animation: 'ms-modal 220ms ease-out both' }}>
            <button onClick={() => setDetail(null)} aria-label="Close" style={{ position: 'absolute', top: 18, right: 20, width: 38, height: 38, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
            <p style={{ color: MS.accent, fontSize: 12, fontWeight: 600, letterSpacing: '0.16em', textTransform: 'uppercase', margin: '0 0 8px' }}>Booking details</p>
            <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 26, margin: '0 0 4px' }}>{detail.space}</h3>
            <p style={{ color: MS.faint, fontSize: 14, margin: '0 0 22px' }}>Ref MS-{detail.id}</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 13, fontSize: 15, borderTop: `1px solid ${MS.line}`, paddingTop: 18 }}>
              <SumRow label="Date" value={`${detail.mon} ${detail.day}`} />
              <SumRow label="Time" value={detail.time} />
              <SumRow label="Duration" value={detail.duration === 'fullday' ? 'Full day' : 'Hourly'} />
              <SumRow label="Attendees" value={String(detail.attendees || 1)} />
              <SumRow label="Status" value={detail.change_requested ? 'Change pending' : detail.status} />
              <SumRow label="Payment" value={detail.cost} />
              {detail.change_requested && detail.requested && (
                <SumRow label="Requested" value={`${detail.requested.mon} ${detail.requested.day} · ${detail.requested.time}`} />
              )}
            </div>
            {detail.change_requested ? (
              <p style={{ marginTop: 22, background: TONES.lilac.bg, color: TONES.lilac.color, fontSize: 13.5, fontWeight: 500, padding: '11px 14px', borderRadius: 10, textAlign: 'center' }}>Your reschedule request is awaiting admin review.</p>
            ) : detail.when === 'upcoming' && (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 24 }}>
                <button onClick={() => setReschedule(detail)} style={{ flex: '1 1 auto', background: MS.accent, border: 'none', color: '#fff', fontSize: 15, fontWeight: 600, padding: 13, borderRadius: 9999, cursor: 'pointer' }}>Reschedule</button>
                <button onClick={() => doCancel(detail.id)} style={{ flex: '1 1 auto', background: 'none', border: '1.5px solid rgba(168,90,74,0.5)', color: MS.red, fontSize: 15, fontWeight: 600, padding: 13, borderRadius: 9999, cursor: 'pointer' }}>Cancel booking</button>
              </div>
            )}
          </div>
        </div>
      )}

      {reschedule && <RescheduleModal booking={reschedule} onClose={() => setReschedule(null)} onDone={onRescheduled} />}
      {scheduleEdit && <ScheduleEditModal components={editableComps} onClose={() => setScheduleEdit(false)} onDone={onScheduleRequested} />}
    </div>
  );
}

/* ---------------- Schedule editor (member reallocates package days) ---------------- */
// Members can rearrange which of their packages covers which day, then submit the
// new schedule for admin review. Only the packages they already have are editable
// (lifetime ones are fixed and handled server-side); nothing changes until approved.
function ScheduleEditModal({ components, onClose, onDone }) {
  // Stable package list (name is the identity the backend validates against).
  const packages = components.map((c) => c.name);
  const planOf = (name) => components.find((c) => c.name === name)?.plan;
  const colorOf = (name) => OFFICE_COLORS[Math.max(0, packages.indexOf(name)) % OFFICE_COLORS.length];

  const [assign, setAssign] = useState(() => {
    const a = {};
    components.forEach((c) => (c.dates || []).forEach((iso) => { a[iso] = c.name; }));
    return a;
  });
  const [active, setActive] = useState(packages[0] || '');
  const [monthOffset, setMonthOffset] = useState(0);
  const [err, setErr] = useState('');
  const [status, setStatus] = useState('idle'); // idle | loading | success | failure

  const cal = buildCalendar(monthOffset, null);
  const monthCells = cal.cells.filter((c) => !c.empty && !c.past);
  const monthFull = monthCells.length > 0 && monthCells.every((c) => assign[c.iso] === active);
  const counts = packages.reduce((acc, p) => ({ ...acc, [p]: 0 }), {});
  Object.values(assign).forEach((p) => { counts[p] = (counts[p] || 0) + 1; });
  const totalDays = Object.keys(assign).length;

  const toggleDay = (iso) => {
    if (!active) return;
    setErr('');
    setAssign((a) => { const n = { ...a }; if (n[iso] === active) delete n[iso]; else n[iso] = active; return n; });
  };
  const toggleMonth = () => {
    if (!active) return;
    setErr('');
    setAssign((a) => {
      const n = { ...a };
      monthCells.forEach((c) => { if (monthFull) { if (n[c.iso] === active) delete n[c.iso]; } else { n[c.iso] = active; } });
      return n;
    });
  };

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const submit = async () => {
    setErr(''); setStatus('loading');
    // One line per package (including any the member emptied, so those days clear).
    const payload = { components: packages.map((name) => ({
      name, plan: planOf(name),
      dates: Object.entries(assign).filter(([, p]) => p === name).map(([iso]) => iso).sort(),
    })) };
    try { await requestScheduleChange(payload); setStatus('success'); }
    catch (ex) { setErr(apiError(ex, 'Could not submit your request.')); setStatus('failure'); }
  };

  const card = {
    position: 'relative', background: MS.panel, width: 'min(560px, 100%)', maxHeight: '90vh', overflowY: 'auto',
    borderRadius: 22, padding: 'clamp(24px,4vw,36px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)', animation: 'ms-modal 220ms ease-out both',
  };
  const close = (
    <button onClick={onClose} aria-label="Close" style={{ position: 'absolute', top: 16, right: 16, width: 38, height: 38, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
  );

  if (status === 'success') return (
    <div onClick={onClose} style={overlay()}>
      <div onClick={(e) => e.stopPropagation()} style={{ ...card, textAlign: 'center' }}>
        {close}
        <span style={{ width: 60, height: 60, borderRadius: 9999, background: 'rgba(63,122,90,0.14)', color: MS.green, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, margin: '10px 0 20px', animation: 'ms-pop 500ms ease-out both' }}>✓</span>
        <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 26, margin: '0 0 10px' }}>Request sent for review</h3>
        <p style={{ color: 'rgba(26,26,26,0.72)', fontSize: 16, lineHeight: 1.6, margin: '0 0 26px' }}>Our team will review your new schedule and apply it once approved. Your current schedule stays in place until then.</p>
        <button onClick={onDone} className="ms-submit" style={{ ...purpleBtn, background: 'linear-gradient(135deg,#B48FD6,#9B7EBD)' }}>Done</button>
      </div>
    </div>
  );

  return (
    <div onClick={onClose} style={overlay()}>
      <div onClick={(e) => e.stopPropagation()} style={card}>
        {close}
        <p style={{ color: MS.accent, fontSize: 12, fontWeight: 600, letterSpacing: '0.16em', textTransform: 'uppercase', margin: '0 0 8px' }}>Edit your schedule</p>
        <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(22px,3vw,28px)', margin: '0 0 6px', paddingRight: 40 }}>Rearrange your package days</h3>
        <p style={{ color: MS.muted, fontSize: 14.5, lineHeight: 1.55, margin: '0 0 22px' }}>Pick a package, then tap the days you want it — the change is sent to our team for review and your current schedule stays until it's approved.</p>

        {/* Package picker */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
          {packages.map((p) => {
            const on = active === p;
            const col = colorOf(p);
            return (
              <button key={p} type="button" onClick={() => setActive(p)}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 8, border: `1.5px solid ${on ? col : MS.line}`, background: on ? col : '#fff', color: on ? '#fff' : MS.ink, borderRadius: 9999, padding: '9px 15px', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
                <span style={{ width: 11, height: 11, borderRadius: 9999, background: on ? '#fff' : col, flex: '0 0 auto' }} />
                {p}{counts[p] ? <span style={{ fontWeight: 600, opacity: 0.9 }}>· {counts[p]}</span> : null}
              </button>
            );
          })}
        </div>

        {/* Calendar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          <p style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: 0 }}>Select days</p>
          <button type="button" onClick={toggleMonth} disabled={!active} style={{ flex: '0 0 auto', background: monthFull ? MS.accent : 'transparent', color: monthFull ? '#fff' : MS.accent, border: `1.5px solid ${MS.accent}`, borderRadius: 9999, padding: '7px 16px', fontSize: 13, fontWeight: 600, cursor: active ? 'pointer' : 'not-allowed', opacity: active ? 1 : 0.5 }}>
            {monthFull ? 'Clear this month' : 'Select full month'}
          </button>
        </div>
        <div style={{ background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 14, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <button type="button" onClick={() => setMonthOffset((o) => Math.max(0, o - 1))} style={calNavBtn(monthOffset > 0)}>‹</button>
            <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 16, margin: 0, minWidth: 128, textAlign: 'center' }}>{cal.label}</p>
            <button type="button" onClick={() => setMonthOffset((o) => o + 1)} style={calNavBtn(true)}>›</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3, marginBottom: 4 }}>
            {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((w) => <div key={w} style={{ textAlign: 'center', fontSize: 11, color: '#A9A39C', padding: '3px 0' }}>{w}</div>)}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 3 }}>
            {cal.cells.map((c, i) => {
              if (c.empty) return <div key={i} style={{ aspectRatio: '1' }} />;
              const p = assign[c.iso];
              return (
                <div key={i} style={{ aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <button type="button" disabled={c.past || !active} onClick={() => toggleDay(c.iso)} title={p || ''} style={{ width: '100%', height: '100%', border: p === active ? '2px solid rgba(0,0,0,0.35)' : 'none', borderRadius: 9, background: p ? colorOf(p) : 'transparent', color: p ? '#fff' : (c.past ? '#C4BEB6' : MS.ink), fontSize: 13.5, fontWeight: p ? 600 : 400, cursor: (c.past || !active) ? 'not-allowed' : 'pointer' }}>{c.day}</button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Summary */}
        {totalDays > 0 ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '14px 0 0' }}>
            {packages.filter((p) => counts[p]).map((p) => (
              <span key={p} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 13, color: '#3A362F', background: MS.line2, padding: '6px 12px', borderRadius: 9999 }}>
                <span style={{ width: 10, height: 10, borderRadius: 9999, background: colorOf(p), flex: '0 0 auto' }} />
                {counts[p]} day{counts[p] > 1 ? 's' : ''} · {p}
              </span>
            ))}
          </div>
        ) : (
          <p style={{ fontSize: 13, color: '#A9A39C', margin: '12px 0 0' }}>Tap days to assign them — leaving a package empty clears its days.</p>
        )}

        {err && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13.5, fontWeight: 500, padding: '11px 14px', borderRadius: 10, margin: '18px 0 0', lineHeight: 1.4 }}>{err}</p>}

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 22 }}>
          <button onClick={submit} disabled={status === 'loading'} className="ms-submit"
            style={{ ...purpleBtn, flex: '1 1 auto', background: 'linear-gradient(135deg,#B48FD6,#9B7EBD)', opacity: status === 'loading' ? 0.75 : 1, cursor: status === 'loading' ? 'default' : 'pointer' }}>
            {status === 'loading' ? 'Submitting…' : 'Submit for review'}
          </button>
          <button onClick={onClose} className="ms-ghost" style={ghostBtn}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

/* ---------------- Reschedule modal (member requests a new date/time) ---------------- */
// Submitting sends the request to the admin for review — the booking is locked
// as "change pending" until it's approved or rejected. Space/length are kept;
// only the date (and, for hourly bookings, the start time) can change.
function RescheduleModal({ booking, onClose, onDone }) {
  // A reschedule may also change the booking's shape: which durations the space
  // supports decides whether the member can switch between hourly and full day.
  const modes = (() => {
    const d = booking.space_durations && booking.space_durations.length ? booking.space_durations : ['hourly', 'fullday'];
    return ['hourly', 'fullday'].filter((x) => d.includes(x));
  })();
  // The booking's current hourly length, used as the default for the stepper.
  const initHours = (() => {
    if (booking.start_time && booking.end_time) {
      const [h1, m1] = booking.start_time.split(':').map(Number);
      const [h2, m2] = booking.end_time.split(':').map(Number);
      const len = Math.round(((h2 * 60 + m2) - (h1 * 60 + m1)) / 60);
      return Math.max(1, Math.min(MAX_HOURS, len));
    }
    return 1;
  })();
  const [mode, setMode] = useState(booking.duration === 'fullday' ? 'fullday' : 'hourly');
  const [monthOffset, setMonthOffset] = useState(0);
  const [date, setDate] = useState(null);
  const [slot, setSlot] = useState(null);
  const [hours, setHours] = useState(initHours);
  const [avail, setAvail] = useState(null);
  const [availLoading, setAvailLoading] = useState(false);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const isHourly = mode === 'hourly';
  const cal = buildCalendar(monthOffset, date);

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  useEffect(() => {
    if (!isHourly || !date) { setAvail(null); return undefined; }
    let alive = true;
    setAvailLoading(true); setSlot(null);
    getAvailability(booking.space_key, date)
      .then((d) => { if (alive) setAvail(d); })
      .catch(() => { if (alive) setAvail(null); })
      .finally(() => { if (alive) setAvailLoading(false); });
    return () => { alive = false; };
  }, [date, booking.space_key, isHourly]);

  // Full-day can't fall on a day already under way; drop a today selection on switch.
  useEffect(() => { if (!isHourly && date === todayIso()) setDate(null); }, [isHourly, date]);

  // Cap hours to the run of consecutive open slots from the chosen start (can't
  // stretch into a taken/blocked slot or past closing).
  const maxHours = (() => {
    const list = avail?.slots || [];
    if (!slot || !list.length) return MAX_HOURS;
    const idx = list.findIndex((s) => s.time === slot);
    if (idx < 0) return MAX_HOURS;
    let run = 0;
    for (let i = idx; i < list.length && list[i].available; i++) run++;
    return Math.max(1, Math.min(MAX_HOURS, run));
  })();
  useEffect(() => { setHours((h) => Math.min(h, maxHours)); }, [maxHours]);

  const canSubmit = !!date && (!isHourly || !!slot) && !busy;
  const slots = avail?.slots || [];

  const submit = async () => {
    if (!canSubmit) return;
    setErr(''); setBusy(true);
    try {
      const payload = isHourly
        ? { date, start_time: slot, duration: 'hourly', hours }
        : { date, duration: 'fullday' };
      await requestBookingChange(booking.id, payload);
      onDone();
    } catch (ex) { setErr(apiError(ex, 'Could not submit your request.')); setBusy(false); }
  };

  const card = {
    position: 'relative', background: MS.panel, width: 'min(560px, 100%)', maxHeight: '90vh', overflowY: 'auto',
    borderRadius: 22, padding: 'clamp(24px,4vw,36px)', boxShadow: '0 30px 80px rgba(20,18,16,0.32)', animation: 'ms-modal 220ms ease-out both',
  };

  return (
    <div onClick={onClose} style={overlay()}>
      <div onClick={(e) => e.stopPropagation()} style={card}>
        <button onClick={onClose} aria-label="Close" style={{ position: 'absolute', top: 16, right: 16, width: 38, height: 38, borderRadius: 9999, border: `1px solid ${MS.line}`, background: '#fff', color: MS.ink, fontSize: 16, cursor: 'pointer' }}>✕</button>
        <p style={{ color: MS.accent, fontSize: 12, fontWeight: 600, letterSpacing: '0.16em', textTransform: 'uppercase', margin: '0 0 8px' }}>Request a change</p>
        <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(22px,3vw,28px)', margin: '0 0 6px', paddingRight: 40 }}>Reschedule {booking.space}</h3>
        <p style={{ color: MS.muted, fontSize: 14.5, lineHeight: 1.55, margin: '0 0 22px' }}>Currently {booking.mon} {booking.day} · {booking.time}. Pick a new {isHourly ? 'date and time' : 'day'} — your request goes to our team for review and the booking stays as-is until it's approved.</p>

        {/* Booking type + hours (when the space supports both) */}
        {(modes.length > 1 || isHourly) && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, marginBottom: 22 }}>
            {modes.length > 1 && (
              <div>
                <p style={capLabel}>Booking type</p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {modes.map((mo) => {
                    const on = mode === mo;
                    return <button key={mo} type="button" onClick={() => { setMode(mo); setSlot(null); }} style={{ padding: '9px 16px', borderRadius: 9999, border: `1px solid ${on ? MS.accent : MS.line}`, background: on ? MS.accent : '#fff', color: on ? '#fff' : MS.ink, fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>{mo === 'hourly' ? 'By the hour' : 'By the day'}</button>;
                  })}
                </div>
              </div>
            )}
            {isHourly && (
              <div>
                <p style={capLabel}>Hours</p>
                <Stepper value={hours} min={1} max={maxHours} onChange={setHours} suffix={hours > 1 ? 'hrs' : 'hr'} />
                <p style={{ fontSize: 12, color: MS.faint, margin: '8px 0 0', whiteSpace: 'nowrap', visibility: (slot && hours >= maxHours) ? 'visible' : 'hidden' }}>Max for this slot</p>
              </div>
            )}
          </div>
        )}

        {/* Calendar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <p style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: 0 }}>New date</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button onClick={() => setMonthOffset((o) => Math.max(0, o - 1))} style={calNavBtn(monthOffset > 0)}>‹</button>
            <p style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 16, margin: 0, minWidth: 128, textAlign: 'center' }}>{cal.label}</p>
            <button onClick={() => setMonthOffset((o) => o + 1)} style={calNavBtn(true)}>›</button>
          </div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginBottom: 6 }}>
          {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((w) => <div key={w} style={{ textAlign: 'center', fontSize: 12, color: '#A9A39C', padding: '4px 0' }}>{w}</div>)}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
          {cal.cells.map((c, i) => c.empty ? <div key={i} style={{ aspectRatio: '1' }} /> : (
            <div key={i} style={{ aspectRatio: '1', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {(() => {
                const off = c.past || (!isHourly && c.iso === todayIso());
                return (
                <button disabled={off} onClick={() => setDate(c.iso)} style={{ width: '100%', height: '100%', border: 'none', borderRadius: 10, background: c.sel ? MS.accent : 'transparent', color: c.sel ? '#fff' : (off ? '#C4BEB6' : MS.ink), fontSize: 14, fontWeight: c.sel ? 600 : 400, cursor: off ? 'not-allowed' : 'pointer' }}>{c.day}</button>
              ); })()}
            </div>
          ))}
        </div>

        {/* Time slots (hourly only) */}
        {isHourly && (
          <div style={{ marginTop: 24 }}>
            <p style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: '0 0 12px' }}>New time</p>
            {!date ? <p style={{ color: MS.faint, fontSize: 14 }}>Pick a date to see open slots.</p>
              : availLoading ? <p style={{ color: MS.faint, fontSize: 14 }}>Loading…</p>
              : avail?.closed ? <p style={{ color: MS.red, fontSize: 14 }}>Closed on this day.</p>
              : slots.length === 0 ? <p style={{ color: MS.faint, fontSize: 14 }}>No slots available.</p>
              : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(74px, 1fr))', gap: 8 }}>
                  {slots.map((s) => {
                    const sel = slot === s.time;
                    const disabled = !s.available;
                    return (
                      <button key={s.time} onClick={() => s.available && setSlot(s.time)} disabled={disabled}
                        style={{ padding: '11px 0', borderRadius: 10, border: `1px solid ${sel ? MS.accent : (disabled ? '#EAE5DE' : MS.line)}`, background: sel ? 'rgba(155,126,189,0.18)' : (disabled ? MS.line2 : '#fff'), color: disabled ? '#B4AEA6' : MS.ink, fontSize: 14, fontWeight: 500, cursor: disabled ? 'not-allowed' : 'pointer', textDecoration: disabled ? 'line-through' : 'none' }}>{s.time}</button>
                    );
                  })}
                </div>
              )}
          </div>
        )}

        {err && <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 13.5, fontWeight: 500, padding: '11px 14px', borderRadius: 10, margin: '20px 0 0', lineHeight: 1.4 }}>{err}</p>}

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 24 }}>
          <button onClick={submit} disabled={!canSubmit} style={{ flex: '1 1 auto', background: canSubmit ? MS.accent : '#ECE8E2', color: canSubmit ? '#fff' : '#A9A39C', border: 'none', fontSize: 15, fontWeight: 600, padding: 14, borderRadius: 9999, cursor: canSubmit ? 'pointer' : 'not-allowed' }}>{busy ? 'Submitting…' : 'Submit for review'}</button>
          <button onClick={onClose} style={ghostBtn}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
