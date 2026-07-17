import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MS, apiError, imgUrl } from '../lib/ms';
import { getOrder, uploadReceipt } from '../lib/services';
import logoColor from '../assets/vividspace-logo.png';

/* Dedicated Whish payment page — the customer lands here after placing a Whish
   order. Shows the exact amount, receiving number, QR, order number + transfer
   message, step-by-step instructions, and a receipt uploader. */
export default function WhishPayment() {
  const { orderNumber } = useParams();
  const navigate = useNavigate();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState('');

  useEffect(() => {
    let alive = true;
    getOrder(orderNumber)
      .then((d) => { if (alive) setOrder(d); })
      .catch((ex) => { if (alive) setErr(apiError(ex, 'Order not found.')); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [orderNumber]);

  const copy = (label, value) => {
    navigator.clipboard?.writeText(String(value)).then(() => {
      setCopied(label); setTimeout(() => setCopied(''), 1400);
    }).catch(() => {});
  };

  const submitReceipt = async () => {
    if (!file || busy) return;
    setErr(''); setBusy(true);
    try {
      const updated = await uploadReceipt(orderNumber, file);
      setOrder(updated); setFile(null);
    } catch (ex) { setErr(apiError(ex, 'Could not upload your receipt.')); }
    finally { setBusy(false); }
  };

  const page = { minHeight: '100vh', background: MS.bg || '#F7F5F1', color: MS.ink, padding: 'clamp(20px,4vw,48px) clamp(16px,4vw,24px)' };
  const card = { background: '#fff', border: `1px solid ${MS.line}`, borderRadius: 20, padding: 'clamp(20px,3vw,30px)', boxShadow: '0 20px 60px rgba(20,18,16,0.10)' };

  if (loading) return <div style={{ ...page, display: 'grid', placeItems: 'center' }}><p style={{ color: MS.faint }}>Loading your payment…</p></div>;

  if (err && !order) {
    return (
      <div style={{ ...page, display: 'grid', placeItems: 'center' }}>
        <div style={{ ...card, maxWidth: 460, textAlign: 'center' }}>
          <h2 style={{ fontFamily: MS.serif, margin: '0 0 10px' }}>Payment unavailable</h2>
          <p style={{ color: MS.muted, margin: '0 0 20px' }}>{err}</p>
          <button onClick={() => navigate('/')} style={btn(true)}>Back to home</button>
        </div>
      </div>
    );
  }

  const w = order.whish || {};
  const amt = Number(order.amount || 0).toFixed(2);
  const paid = order.status === 'paid';
  const submitted = order.status === 'submitted';
  const rejected = order.status === 'rejected';

  return (
    <div style={page}>
      <div style={{ maxWidth: 880, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <img src={logoColor} alt="Vivid Space" style={{ height: 38 }} />
          <button onClick={() => navigate('/')} style={{ background: 'none', border: `1px solid ${MS.line}`, color: MS.muted, borderRadius: 9999, padding: '8px 16px', fontSize: 14, cursor: 'pointer' }}>Home</button>
        </div>

        <p style={{ color: MS.accent, fontSize: 12, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', margin: '0 0 8px' }}>Whish payment</p>
        <h1 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 'clamp(28px,4vw,40px)', margin: '0 0 6px' }}>Complete Your Whish Payment</h1>
        <p style={{ color: MS.muted, fontSize: 15.5, margin: '0 0 28px' }}>Order <strong>{order.order_number}</strong> · <StatusPill status={order.status} label={order.status_label} /></p>

        {paid ? (
          <div style={{ ...card, borderColor: 'rgba(63,122,90,0.35)', background: 'rgba(63,122,90,0.08)', textAlign: 'center' }}>
            <span style={{ fontSize: 40 }}>✓</span>
            <h2 style={{ fontFamily: MS.serif, margin: '8px 0 6px', color: MS.green }}>Payment confirmed</h2>
            <p style={{ color: MS.muted, margin: 0 }}>Your booking is confirmed. We've emailed you the details.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 22 }}>
            {/* Payment details */}
            <div style={card}>
              <Row label="Amount" value={`$${amt}`} big onCopy={() => copy('amount', amt)} copied={copied === 'amount'} copyLabel="Copy Amount" />
              <Row label="Send To" value={w.number || '—'} onCopy={() => copy('phone', w.number)} copied={copied === 'phone'} copyLabel="Copy Phone Number" />
              {w.name ? <Row label="Account" value={w.name} /> : null}
              <Row label="Order Number" value={order.order_number} onCopy={() => copy('order', order.order_number)} copied={copied === 'order'} copyLabel="Copy Order Number" />
              <Row label="Transfer Message" value={w.message || order.order_number} onCopy={() => copy('msg', w.message || order.order_number)} copied={copied === 'msg'} copyLabel="Copy Message" last />
              {w.qr ? (
                <div style={{ marginTop: 18, textAlign: 'center' }}>
                  <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: MS.faint, margin: '0 0 10px' }}>Scan to pay</p>
                  <img src={imgUrl(w.qr)} alt="Whish QR" style={{ width: 180, height: 180, objectFit: 'contain', border: `1px solid ${MS.line}`, borderRadius: 12, padding: 8, background: '#fff' }} />
                </div>
              ) : null}
            </div>

            {/* Instructions + receipt */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
              <div style={card}>
                <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 19, margin: '0 0 14px' }}>Payment instructions</h3>
                <ol style={{ margin: 0, paddingLeft: 20, color: '#3A362F', fontSize: 14.5, lineHeight: 1.7 }}>
                  <li>Open the <strong>Whish</strong> application.</li>
                  <li>Transfer exactly <strong>${amt}</strong>.</li>
                  <li>Send the money to <strong>{w.number || '—'}</strong>.</li>
                  <li>When Whish asks for a message, enter exactly <strong>{order.order_number}</strong>.</li>
                  <li>Complete the transfer.</li>
                  <li>Return here and upload your payment receipt below.</li>
                </ol>
              </div>

              <div style={card}>
                <h3 style={{ fontFamily: MS.serif, fontWeight: 700, fontSize: 19, margin: '0 0 6px' }}>Upload payment receipt</h3>
                {submitted ? (
                  <p style={{ background: 'rgba(240,130,46,0.12)', color: '#B7701F', fontSize: 14, fontWeight: 500, padding: '12px 14px', borderRadius: 10, margin: '10px 0 0', lineHeight: 1.5 }}>
                    Receipt received — your payment is under review. We'll confirm your booking shortly. You can re-upload a clearer copy below if needed.
                  </p>
                ) : rejected ? (
                  <p style={{ background: 'rgba(168,90,74,0.12)', color: MS.red, fontSize: 14, fontWeight: 500, padding: '12px 14px', borderRadius: 10, margin: '10px 0 0', lineHeight: 1.5 }}>
                    This payment was declined{order.note ? `: ${order.note}` : ''}. Please re-transfer and upload a valid receipt.
                  </p>
                ) : (
                  <p style={{ color: MS.muted, fontSize: 14, margin: '4px 0 12px' }}>After transferring, upload a screenshot or photo of the Whish confirmation.</p>
                )}
                <div style={{ marginTop: 14 }}>
                  <input type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)}
                    style={{ display: 'block', fontSize: 14, marginBottom: 12 }} />
                  <button onClick={submitReceipt} disabled={!file || busy} style={btn(!!file && !busy)}>
                    {busy ? 'Uploading…' : (submitted || rejected ? 'Re-upload receipt' : 'Submit receipt')}
                  </button>
                </div>
                {err ? <p style={{ color: MS.red, fontSize: 13.5, margin: '12px 0 0' }}>{err}</p> : null}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value, big, onCopy, copyLabel, copied, last }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '12px 0', borderBottom: last ? 'none' : `1px solid ${MS.line}` }}>
      <div style={{ minWidth: 0 }}>
        <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: MS.faint, margin: '0 0 3px' }}>{label}</p>
        <p style={{ fontFamily: big ? MS.serif : 'inherit', fontWeight: big ? 700 : 600, fontSize: big ? 26 : 16, margin: 0, wordBreak: 'break-word' }}>{value}</p>
      </div>
      {onCopy ? (
        <button onClick={onCopy} style={{ flex: '0 0 auto', background: copied ? MS.green : '#fff', color: copied ? '#fff' : MS.ink, border: `1px solid ${copied ? MS.green : MS.line}`, borderRadius: 9999, padding: '8px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }}>
          {copied ? 'Copied ✓' : (copyLabel || 'Copy')}
        </button>
      ) : null}
    </div>
  );
}

function StatusPill({ status, label }) {
  const map = {
    awaiting_payment: ['rgba(240,130,46,0.16)', '#B7701F'],
    submitted: ['rgba(46,115,224,0.16)', '#2E73E0'],
    paid: ['rgba(63,122,90,0.16)', '#3F7A5A'],
    rejected: ['rgba(168,90,74,0.16)', '#A85A4A'],
  };
  const [bg, fg] = map[status] || map.awaiting_payment;
  return <span style={{ background: bg, color: fg, fontSize: 12.5, fontWeight: 700, padding: '3px 10px', borderRadius: 9999 }}>{label || status}</span>;
}

const btn = (active) => ({ width: '100%', background: active ? MS.accent : '#ECE8E2', color: active ? '#fff' : '#A9A39C', border: 'none', fontSize: 15, fontWeight: 600, padding: 13, borderRadius: 9999, cursor: active ? 'pointer' : 'not-allowed' });
