import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { saveUserProfile } from "@/lib/database";
import "./login.css";

/* ── Glyph icon (VisionGuard shield logo) ────────────────────────── */
function Glyph() {
  return (
    <img
      src="/visionguard-shield.png"
      alt="VisionGuard"
      className="vg-glyph inline-block object-contain drop-shadow-[0_0_8px_rgba(56,189,248,0.4)]"
      style={{ width: 26, height: 26 }}
    />
  );
}

/* ── Live UTC clock ────────────────────────────────────────────── */
function Clock() {
  const [mounted, setMounted] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    setMounted(true);
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const d = new Date(now);
  const f = (n: number) => String(n).padStart(2, "0");
  return (
    <div className="vg-login-clock" aria-hidden="true">
      <i />
      <span>
        {mounted
          ? `${f(d.getUTCHours())}:${f(d.getUTCMinutes())}:${f(d.getUTCSeconds())} UTC`
          : "00:00:00 UTC"}
      </span>
      <span>·</span>
      <span>Model reliability</span>
    </div>
  );
}

/* ── Porthole ring SVG (reused as corner deco) ─────────────────── */
function RingDeco() {
  return (
    <svg viewBox="-130 -130 260 260" aria-hidden="true">
      <circle r="112" fill="none" stroke="#c99a5b" strokeWidth="10" />
      <circle r="112" fill="none" stroke="#2b1a0e" strokeWidth="1.5" opacity="0.9" />
      <circle r="119" fill="none" stroke="#2b1a0e" strokeWidth="1.2" opacity="0.7" />
      <circle r="105" fill="none" stroke="#2b1a0e" strokeWidth="1.2" opacity="0.7" />
      <g>
        {Array.from({ length: 12 }, (_, i) => {
          const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
          return (
            <g
              key={i}
              transform={`translate(${Math.cos(a) * 112} ${Math.sin(a) * 112}) rotate(${i * 30})`}
            >
              <circle r="7.5" fill="#6b4a2c" stroke="#2b1a0e" strokeWidth="1.2" />
              <path d="M-4 0H4" stroke="#2b1a0e" strokeWidth="1.6" />
            </g>
          );
        })}
      </g>
    </svg>
  );
}

/* ── Shard shapes (same as landing) ───────────────────────────── */
function Shard({ kind }: { kind: number }) {
  if (kind === 1)
    return (
      <svg viewBox="0 0 40 14">
        <path d="M0 3h34l6 4-6 4H0Z" fill="#cfeee4" stroke="#06181d" strokeWidth="1.6" />
        <path d="M0 7h40l-6 4H0Z" fill="#8fcfc0" stroke="#06181d" strokeWidth="1.6" />
      </svg>
    );
  if (kind === 2)
    return (
      <svg viewBox="0 0 30 30">
        <path d="M15 0 30 9 26 27 4 27 0 9Z" fill="#c9fbe9" stroke="#06181d" strokeWidth="1.6" />
        <path d="M15 0 15 14 30 9ZM15 14 26 27 4 27Z" fill="#8ee8cb" stroke="#06181d" strokeWidth="1.6" />
      </svg>
    );
  if (kind === 3)
    return (
      <svg viewBox="0 0 20 40">
        <path d="M10 0 20 16 10 40 0 16Z" fill="#cfeee4" stroke="#06181d" strokeWidth="1.6" />
        <path d="M10 0 20 16 10 40Z" fill="#8fcfc0" stroke="#06181d" strokeWidth="1.6" />
      </svg>
    );
  if (kind === 4)
    return (
      <svg viewBox="0 0 40 14">
        <path d="M0 3h34l6 4-6 4H0Z" fill="#ff9a7c" stroke="#06181d" strokeWidth="1.4" />
        <path d="M0 7h40l-6 4H0Z" fill="#c9442f" stroke="#06181d" strokeWidth="1.4" />
      </svg>
    );
  return (
    <svg viewBox="0 0 20 40">
      <path d="M10 0 20 16 10 40 0 16Z" fill="#ff7b58" stroke="#06181d" strokeWidth="1.6" />
      <path d="M10 0 20 16 10 40Z" fill="#c9442f" stroke="#06181d" strokeWidth="1.6" />
    </svg>
  );
}

const BG_SHARDS = [
  { lx: "8%",  ly: "18%", tx: "-14px", ty: "-10px", r: "-22deg", w: 20, d: 0,    kind: 0 },
  { lx: "88%", ly: "12%", tx: "8px",   ty: "-6px",  r: "38deg",  w: 26, d: -1.5, kind: 1 },
  { lx: "92%", ly: "75%", tx: "-6px",  ty: "10px",  r: "10deg",  w: 18, d: -3,   kind: 2 },
  { lx: "5%",  ly: "80%", tx: "10px",  ty: "-8px",  r: "-48deg", w: 14, d: -2,   kind: 3 },
  { lx: "48%", ly: "88%", tx: "-4px",  ty: "-12px", r: "65deg",  w: 16, d: -4,   kind: 4 },
  { lx: "75%", ly: "48%", tx: "6px",   ty: "8px",   r: "18deg",  w: 22, d: -2.5, kind: 0 },
] as const;

/* ── Eye icon (show/hide password) ───────────────────────────── */
function EyeIcon({ open }: { open: boolean }) {
  if (open)
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
        <line x1="1" y1="1" x2="23" y2="23" />
      </svg>
    );
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

/* ── Suggested roles for VisionGuard researchers ───────────────── */
export const SUGGESTED_ROLES = [
  "Lead Reliability Engineer",
  "Computer Vision Researcher",
  "AI Safety & Robustness Auditor",
  "Autonomous Systems Specialist",
  "MLOps & Evaluation Lead",
  "Perception Systems Engineer",
] as const;

/* ══════════════════════════════════════════════════════════════
   Main Login / Sign Up component
══════════════════════════════════════════════════════════════ */
export function Login({ initialMode = "signin" }: { initialMode?: "signin" | "signup" | undefined }) {
  const navigate = useNavigate();
  const dotRef  = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const roleDropdownRef = useRef<HTMLDivElement>(null);

  const [mode,            setMode]            = useState<"signin" | "signup">(initialMode);
  const [name,            setName]            = useState("");
  const [email,           setEmail]           = useState("");
  const [role,            setRole]            = useState<string>("Lead Reliability Engineer");
  const [isRoleOpen,      setIsRoleOpen]      = useState(false);
  const [password,        setPassword]        = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPw,          setShowPw]          = useState(false);
  const [showConfirmPw,   setShowConfirmPw]   = useState(false);
  const [remember,        setRemember]        = useState(false);
  const [termsAgreed,     setTermsAgreed]     = useState(false);
  const [loading,         setLoading]         = useState(false);
  const [error,           setError]           = useState<string | null>(null);
  const [success,         setSuccess]         = useState(false);
  const [cursorOn,        setCursorOn]        = useState(false);

  /* Close role popdown on click outside */
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (roleDropdownRef.current && !roleDropdownRef.current.contains(e.target as Node)) {
        setIsRoleOpen(false);
      }
    };
    if (isRoleOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isRoleOpen]);

  /* Cursor tracking */
  useEffect(() => {
    const dot  = dotRef.current;
    const ring = ringRef.current;
    if (!dot || !ring) return;
    const pos = { x: innerWidth / 2, y: innerHeight / 2 };
    const sm  = { x: pos.x, y: pos.y };
    let raf = 0;
    const onMove = (e: PointerEvent) => { pos.x = e.clientX; pos.y = e.clientY; };
    const loop = () => {
      sm.x += (pos.x - sm.x) * 0.14;
      sm.y += (pos.y - sm.y) * 0.14;
      dot.style.transform  = `translate(${pos.x - 3.5}px, ${pos.y - 3.5}px)`;
      const half = ring.offsetWidth / 2;
      ring.style.transform = `translate(${sm.x - half}px, ${sm.y - half}px)`;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    addEventListener("pointermove", onMove);
    return () => { cancelAnimationFrame(raf); removeEventListener("pointermove", onMove); };
  }, []);

  /* Form submission */
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (mode === "signup") {
      if (!name.trim()) {
        setError("Please enter your full name or team name.");
        return;
      }
      if (!email.trim()) {
        setError("Email address is required.");
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        setError("Please enter a valid email address.");
        return;
      }
      if (!password) {
        setError("Password is required.");
        return;
      }
      if (password.length < 6) {
        setError("Password must be at least 6 characters.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
      if (!termsAgreed) {
        setError("Please agree to the Terms of Service & Privacy Policy.");
        return;
      }
    } else {
      if (!email.trim()) {
        setError("Email address is required.");
        return;
      }
      if (!password) {
        setError("Password is required.");
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        setError("Please enter a valid email address.");
        return;
      }
    }

    setLoading(true);
    /* Simulate async auth and store profile in database */
    await new Promise((r) => setTimeout(r, 1400));

    const displayName = mode === "signup" && name.trim() ? name.trim() : email.split("@")[0] || "Evaluation Lead";
    const userRole = role.trim() || "Lead Reliability Engineer";
    saveUserProfile({
      id: `USR-${Date.now().toString(36).toUpperCase()}`,
      name: displayName,
      email: email.trim(),
      role: userRole,
      organization: "VisionGuard Evaluation Lab",
      createdAt: new Date().toISOString(),
    });

    setLoading(false);
    setSuccess(true);

    /* Smooth redirection to the starting vision guard circle landing page */
    setTimeout(() => {
      navigate({ to: "/" });
    }, 1000);
  };

  const handleOAuth = async () => {
    setError(null);
    setLoading(true);
    await new Promise((r) => setTimeout(r, 1200));

    const userRole = role.trim() || "Principal AI Safety Architect";
    saveUserProfile({
      id: `USR-OAUTH-${Date.now().toString(36).toUpperCase()}`,
      name: "Alex Vance",
      email: "alex.vance@visionguard.ai",
      role: userRole,
      organization: "VisionGuard Partner Lab",
      createdAt: new Date().toISOString(),
    });

    setLoading(false);
    setSuccess(true);
    setTimeout(() => {
      navigate({ to: "/" });
    }, 1000);
  };

  const handleTabSwitch = (newMode: "signin" | "signup") => {
    setMode(newMode);
    setError(null);
  };

  return (
    <div className="vg-login">
      {/* Layered background */}
      <div className="vg-login-bg" />
      <div className="vg-login-still" />
      <div className="vg-login-vignette" />
      <div className="vg-login-grain" />

      {/* Custom cursor */}
      <div className="vg-login-cursor-dot"  ref={dotRef}  aria-hidden="true" />
      <div className={`vg-login-cursor-ring${cursorOn ? " on" : ""}`} ref={ringRef} aria-hidden="true" />

      {/* Porthole ring corner decorations */}
      <div className="vg-login-ring-bg tl" aria-hidden="true"><RingDeco /></div>
      <div className="vg-login-ring-bg br" aria-hidden="true"><RingDeco /></div>

      {/* Floating shards */}
      {BG_SHARDS.map((s, i) => (
        <div
          key={i}
          className="vg-login-shard"
          style={{
            "--lx": s.lx,
            "--ly": s.ly,
            "--tx": s.tx,
            "--ty": s.ty,
            "--r":  s.r,
            "--w":  `${s.w}px`,
            "--d":  `${s.d}s`,
          } as React.CSSProperties}
          aria-hidden="true"
        >
          <Shard kind={s.kind} />
        </div>
      ))}

      {/* Header */}
      <header className="vg-login-header">
        <Link to="/" className="vg-logo" aria-label="VisionGuard, home">
          <Glyph />
          <span className="wm">
            <b>VisionGuard</b> <span>AI</span>
          </span>
        </Link>
        <Clock />
        <Link className="vg-pill" to="/dashboard" style={{ fontSize: 13, height: 36, padding: "0 16px" }}>
          Open workspace
        </Link>
      </header>

      {/* ── Auth card ────────────────────────────────────────── */}
      <main className="vg-login-wrap" role="main">
        <div className="vg-login-card">
          {/* Success overlay */}
          {success && (
            <div className="vg-login-success-overlay" role="status">
              <div className="vg-login-success-inner">
                <div className="vg-login-success-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <div className="vg-login-success-text">
                  {mode === "signin" ? "Welcome back" : "Account created"}
                </div>
                <div className="vg-login-success-sub">
                  Entering VisionGuard…
                </div>
              </div>
            </div>
          )}

          {/* Card brand */}
          <div className="vg-login-brand">
            <Glyph />
            <div className="vg-login-brand-name">
              VisionGuard <span>AI</span>
            </div>
          </div>
          <p className="vg-login-tagline">
            {mode === "signin"
              ? "Sign in to access your evaluation workspace."
              : "Create your account to start evaluating AI model reliability."}
          </p>

          {/* Mode Switcher Tabs */}
          <div className="vg-login-tabs" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signin"}
              className={`vg-login-tab ${mode === "signin" ? "active" : ""}`}
              onClick={() => handleTabSwitch("signin")}
              disabled={loading || success}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "signup"}
              className={`vg-login-tab ${mode === "signup" ? "active" : ""}`}
              onClick={() => handleTabSwitch("signup")}
              disabled={loading || success}
            >
              Create account
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="vg-login-error" role="alert" key={error}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error}
            </div>
          )}

          {/* Form */}
          <form className="vg-login-form" onSubmit={handleSubmit} noValidate>
            {/* Full Name (Sign Up only) */}
            {mode === "signup" && (
              <div className="vg-login-field">
                <label htmlFor="vg-login-name" className="vg-login-label">
                  Full name or team
                </label>
                <div className="vg-login-input-wrap">
                  <svg className="vg-login-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                  <input
                    id="vg-login-name"
                    type="text"
                    className="vg-login-input"
                    placeholder="Ada Lovelace"
                    autoComplete="name"
                    value={name}
                    onChange={(e) => { setName(e.target.value); setError(null); }}
                    disabled={loading || success}
                    aria-required="true"
                  />
                </div>
              </div>
            )}

            {/* Email */}
            <div className="vg-login-field">
              <label htmlFor="vg-login-email" className="vg-login-label">
                {mode === "signup" ? "Work email" : "Email address"}
              </label>
              <div className="vg-login-input-wrap">
                <svg className="vg-login-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="2" y="4" width="20" height="16" rx="2" />
                  <polyline points="2 4 12 13 22 4" />
                </svg>
                <input
                  id="vg-login-email"
                  type="email"
                  className="vg-login-input"
                  placeholder="you@example.com"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setError(null); }}
                  disabled={loading || success}
                  aria-required="true"
                />
              </div>
            </div>

            {/* Role & Specialization with Dropdown Popdown */}
            <div className="vg-login-field" ref={roleDropdownRef}>
              <div className="vg-login-role-header">
                <label htmlFor="vg-login-role" className="vg-login-label">
                  Role / Specialization
                </label>
                <span className="vg-login-role-hint">
                  {isRoleOpen ? "Select from suggestions" : "Click to view roles"}
                </span>
              </div>
              <div className="vg-login-input-wrap">
                <svg className="vg-login-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                <input
                  id="vg-login-role"
                  type="text"
                  className="vg-login-input"
                  placeholder="Select or type your role…"
                  autoComplete="organization-title"
                  value={role}
                  onClick={() => setIsRoleOpen(true)}
                  onFocus={() => setIsRoleOpen(true)}
                  onChange={(e) => { setRole(e.target.value); setError(null); }}
                  disabled={loading || success}
                />
                <button
                  type="button"
                  className={`vg-login-role-toggle${isRoleOpen ? " open" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsRoleOpen((prev) => !prev);
                  }}
                  aria-label="Toggle role suggestions"
                  tabIndex={0}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>

                {/* Popdown Menu */}
                {isRoleOpen && (
                  <div className="vg-login-role-popdown" role="listbox" aria-label="Suggested roles">
                    <div className="vg-login-role-popdown-header">
                      <span>Suggested Roles</span>
                      <span style={{ fontSize: 10, opacity: 0.7, textTransform: "none", fontWeight: 400 }}>Click to select</span>
                    </div>
                    <div className="vg-login-role-options-list">
                      {SUGGESTED_ROLES.map((sRole) => {
                        const isSelected = role.trim().toLowerCase() === sRole.toLowerCase();
                        return (
                          <button
                            key={sRole}
                            type="button"
                            className={`vg-login-role-option${isSelected ? " selected" : ""}`}
                            onClick={() => {
                              setRole(sRole);
                              setIsRoleOpen(false);
                            }}
                            role="option"
                            aria-selected={isSelected}
                          >
                            <span>{sRole}</span>
                            {isSelected && (
                              <svg className="vg-login-role-option-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                            )}
                          </button>
                        );
                      })}
                    </div>
                    <div className="vg-login-role-popdown-footer">
                      Tip: You can also type any custom role in the box above
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Password */}
            <div className="vg-login-field">
              <label htmlFor="vg-login-password" className="vg-login-label">
                Password
              </label>
              <div className="vg-login-input-wrap">
                <svg className="vg-login-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <input
                  id="vg-login-password"
                  type={showPw ? "text" : "password"}
                  className="vg-login-input"
                  placeholder={mode === "signup" ? "At least 6 characters" : "••••••••"}
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(null); }}
                  disabled={loading || success}
                  aria-required="true"
                />
                <button
                  type="button"
                  className="vg-login-pw-toggle"
                  aria-label={showPw ? "Hide password" : "Show password"}
                  onClick={() => setShowPw((v) => !v)}
                  tabIndex={0}
                >
                  <EyeIcon open={showPw} />
                </button>
              </div>
            </div>

            {/* Confirm Password (Sign Up only) */}
            {mode === "signup" && (
              <div className="vg-login-field">
                <label htmlFor="vg-login-confirm-password" className="vg-login-label">
                  Confirm password
                </label>
                <div className="vg-login-input-wrap">
                  <svg className="vg-login-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    <path d="m9 12 2 2 4-4" />
                  </svg>
                  <input
                    id="vg-login-confirm-password"
                    type={showConfirmPw ? "text" : "password"}
                    className="vg-login-input"
                    placeholder="Repeat password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => { setConfirmPassword(e.target.value); setError(null); }}
                    disabled={loading || success}
                    aria-required="true"
                  />
                  <button
                    type="button"
                    className="vg-login-pw-toggle"
                    aria-label={showConfirmPw ? "Hide password" : "Show password"}
                    onClick={() => setShowConfirmPw((v) => !v)}
                    tabIndex={0}
                  >
                    <EyeIcon open={showConfirmPw} />
                  </button>
                </div>
              </div>
            )}

            {/* Terms checkbox for signup */}
            {mode === "signup" && (
              <label className="vg-login-terms">
                <input
                  id="vg-login-terms"
                  type="checkbox"
                  checked={termsAgreed}
                  onChange={(e) => setTermsAgreed(e.target.checked)}
                  disabled={loading || success}
                />
                <span>
                  I agree to the VisionGuard <a href="#terms" onClick={(e) => e.preventDefault()}>Terms</a> &amp;{" "}
                  <a href="#privacy" onClick={(e) => e.preventDefault()}>Privacy Policy</a>.
                </span>
              </label>
            )}

            {/* Meta: remember + forgot for signin */}
            {mode === "signin" && (
              <div className="vg-login-meta">
                <label className="vg-login-remember">
                  <input
                    id="vg-login-remember"
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    disabled={loading || success}
                  />
                  Remember me
                </label>
                <a href="#forgot" onClick={(e) => e.preventDefault()} className="vg-login-forgot">Forgot password?</a>
              </div>
            )}

            {/* Submit */}
            <button
              id="vg-login-submit"
              type="submit"
              className="vg-login-submit"
              disabled={loading || success}
              onMouseEnter={() => setCursorOn(true)}
              onMouseLeave={() => setCursorOn(false)}
            >
              <span className="vg-login-submit-inner">
                {loading ? (
                  <div className="vg-login-spinner" aria-hidden="true" />
                ) : (
                  <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M3 9h11M10 4.5 14.5 9 10 13.5" />
                  </svg>
                )}
                {loading
                  ? mode === "signin" ? "Signing in…" : "Creating account…"
                  : mode === "signin" ? "Sign in" : "Create account"}
              </span>
            </button>

            {/* Divider */}
            <div className="vg-login-divider" aria-hidden="true">
              {mode === "signin" ? "or continue with" : "or sign up with"}
            </div>

            {/* OAuth */}
            <div className="vg-login-oauth">
              <button
                type="button"
                id="vg-login-google"
                className="vg-login-oauth-btn"
                aria-label={mode === "signin" ? "Sign in with Google" : "Sign up with Google"}
                disabled={loading || success}
                onClick={handleOAuth}
              >
                {/* Google icon */}
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Google
              </button>
              <button
                type="button"
                id="vg-login-github"
                className="vg-login-oauth-btn"
                aria-label={mode === "signin" ? "Sign in with GitHub" : "Sign up with GitHub"}
                disabled={loading || success}
                onClick={handleOAuth}
              >
                {/* GitHub icon */}
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
                GitHub
              </button>
            </div>
          </form>
        </div>

        {/* Footer switcher */}
        <p className="vg-login-footer">
          {mode === "signin" ? (
            <>
              Don't have an account?{" "}
              <button
                type="button"
                onClick={() => handleTabSwitch("signup")}
                style={{ color: "var(--coral2)", textDecoration: "underline", textUnderlineOffset: 3, fontWeight: 500 }}
              >
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => handleTabSwitch("signin")}
                style={{ color: "var(--coral2)", textDecoration: "underline", textUnderlineOffset: 3, fontWeight: 500 }}
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </main>
    </div>
  );
}
