/**
 * EventsCalendar.jsx
 *
 * Drop-in replacement for the Events tab in HydraCast web UI.
 *
 * API calls made:
 *   GET  /api/streams          — list of configured streams
 *   GET  /api/events           — list of OneShotEvents
 *   GET  /api/library          — media file list (lazy, on modal open)
 *   GET  /api/settings         — app settings (holiday_country, holiday_subdiv)
 *   GET  /api/holidays         — holiday list from Python 'holidays' library
 *   POST /api/events/bulk      — create one or more events at a timestamp
 *   POST /api/settings         — persist holiday country preference
 *
 * Embed in web_html.py by replacing the events tab's innerHTML with:
 *   <div id="events-calendar-root"></div>
 * then mounting:
 *   ReactDOM.createRoot(document.getElementById("events-calendar-root"))
 *           .render(<EventsCalendar />);
 */

import { useState, useEffect, useRef } from "react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];
const DAYS_SHORT = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

const COUNTRIES = [
  {code:"AE",name:"UAE"},{code:"AR",name:"Argentina"},{code:"AT",name:"Austria"},
  {code:"AU",name:"Australia"},{code:"BD",name:"Bangladesh"},{code:"BE",name:"Belgium"},
  {code:"BR",name:"Brazil"},{code:"CA",name:"Canada"},{code:"CH",name:"Switzerland"},
  {code:"CN",name:"China"},{code:"CO",name:"Colombia"},{code:"CZ",name:"Czech Republic"},
  {code:"DE",name:"Germany"},{code:"DK",name:"Denmark"},{code:"EG",name:"Egypt"},
  {code:"ES",name:"Spain"},{code:"FI",name:"Finland"},{code:"FR",name:"France"},
  {code:"GB",name:"United Kingdom"},{code:"GH",name:"Ghana"},{code:"GR",name:"Greece"},
  {code:"HU",name:"Hungary"},{code:"ID",name:"Indonesia"},{code:"IE",name:"Ireland"},
  {code:"IL",name:"Israel"},{code:"IN",name:"India"},{code:"IQ",name:"Iraq"},
  {code:"IR",name:"Iran"},{code:"IT",name:"Italy"},{code:"JP",name:"Japan"},
  {code:"KE",name:"Kenya"},{code:"KR",name:"South Korea"},{code:"KW",name:"Kuwait"},
  {code:"LK",name:"Sri Lanka"},{code:"MA",name:"Morocco"},{code:"MX",name:"Mexico"},
  {code:"MY",name:"Malaysia"},{code:"NG",name:"Nigeria"},{code:"NL",name:"Netherlands"},
  {code:"NO",name:"Norway"},{code:"NP",name:"Nepal"},{code:"NZ",name:"New Zealand"},
  {code:"OM",name:"Oman"},{code:"PH",name:"Philippines"},{code:"PK",name:"Pakistan"},
  {code:"PL",name:"Poland"},{code:"PT",name:"Portugal"},{code:"QA",name:"Qatar"},
  {code:"RO",name:"Romania"},{code:"RU",name:"Russia"},{code:"SA",name:"Saudi Arabia"},
  {code:"SE",name:"Sweden"},{code:"SG",name:"Singapore"},{code:"TH",name:"Thailand"},
  {code:"TN",name:"Tunisia"},{code:"TR",name:"Turkey"},{code:"TZ",name:"Tanzania"},
  {code:"UA",name:"Ukraine"},{code:"UG",name:"Uganda"},{code:"US",name:"United States"},
  {code:"VN",name:"Vietnam"},{code:"ZA",name:"South Africa"},{code:"ZW",name:"Zimbabwe"},
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function fmtDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}

function getEventDate(ev) {
  return (ev.play_at_iso || ev.play_at || "").slice(0,10);
}

function getEventTime(ev) {
  return (ev.play_at_iso || ev.play_at || "").slice(11,16);
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Legend() {
  return (
    <div style={{display:"flex",alignItems:"center",gap:"12px",fontSize:"12px",color:"var(--color-text-secondary)"}}>
      {[
        ["var(--color-background-danger)","var(--color-border-danger)","Holiday"],
        ["var(--color-background-info)","var(--color-border-info)","Upcoming"],
        ["var(--color-background-success)","var(--color-border-success)","Played"],
      ].map(([bg,border,label]) => (
        <span key={label} style={{display:"flex",alignItems:"center",gap:"4px"}}>
          <span style={{width:"10px",height:"10px",borderRadius:"2px",
            background:bg,border:`0.5px solid ${border}`,display:"inline-block",flexShrink:0}}/>
          {label}
        </span>
      ))}
    </div>
  );
}

function EventChip({ ev }) {
  const played = ev.played;
  return (
    <div
      title={`${ev.stream_name} — ${ev.file_name || ev.file_path}`}
      style={{
        borderRadius:"3px", padding:"2px 5px", marginBottom:"2px",
        fontSize:"10px", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
        background: played ? "var(--color-background-success)" : "var(--color-background-info)",
        border:`0.5px solid ${played ? "var(--color-border-success)" : "var(--color-border-info)"}`,
        color: played ? "var(--color-text-success)" : "var(--color-text-info)",
      }}
    >
      <span style={{fontWeight:"500"}}>{getEventTime(ev)}</span>
      {" "}{ev.stream_name}
    </div>
  );
}

function DayCell({ day, year, month, todayStr, holidays, eventsByDate, onOpen }) {
  if (!day) return (
    <div style={{
      minHeight:"88px",
      borderRight:"0.5px solid var(--color-border-tertiary)",
      borderBottom:"0.5px solid var(--color-border-tertiary)",
    }}/>
  );

  const ds = `${year}-${String(month+1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
  const isToday = ds === todayStr;
  const isPast  = ds < todayStr;
  const holiday = holidays[ds];
  const dayEvts = eventsByDate[ds] || [];

  const baseBg = isToday
    ? "var(--color-background-info)"
    : holiday
      ? "var(--color-background-danger)"
      : "transparent";

  return (
    <div
      onClick={() => onOpen(day)}
      tabIndex={0}
      role="button"
      aria-label={`${MONTHS[month]} ${day}, ${year}${holiday ? `, ${holiday}` : ""}`}
      onKeyDown={e => e.key === "Enter" && onOpen(day)}
      style={{
        minHeight:"88px", padding:"7px 8px",
        borderRight:"0.5px solid var(--color-border-tertiary)",
        borderBottom:"0.5px solid var(--color-border-tertiary)",
        background: baseBg,
        cursor:"pointer",
        opacity: isPast && !isToday ? 0.55 : 1,
        transition:"background 0.1s",
        outline:"none",
      }}
      onMouseEnter={e => { e.currentTarget.style.background = "var(--color-background-secondary)"; }}
      onMouseLeave={e => { e.currentTarget.style.background = baseBg; }}
    >
      {/* Day number */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:"3px"}}>
        <span style={{
          fontSize:"13px",
          fontWeight: isToday ? "500" : "400",
          width:"22px", height:"22px",
          borderRadius:"50%",
          display:"flex", alignItems:"center", justifyContent:"center",
          background: isToday ? "var(--color-text-info)" : "transparent",
          color: isToday ? "#fff" : "var(--color-text-primary)",
          flexShrink:0,
        }}>{day}</span>
        {holiday && (
          <i className="ti ti-star-filled" aria-hidden="true"
             style={{fontSize:"11px",color:"var(--color-text-danger)",marginTop:"3px"}}/>
        )}
      </div>

      {/* Holiday label */}
      {holiday && (
        <div style={{fontSize:"10px",color:"var(--color-text-danger)",marginBottom:"3px",
          lineHeight:"1.3",overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}
          title={holiday}>{holiday}</div>
      )}

      {/* Event chips (max 3 + overflow label) */}
      {dayEvts.slice(0,3).map((ev,i) => <EventChip key={i} ev={ev}/>)}
      {dayEvts.length > 3 && (
        <div style={{fontSize:"10px",color:"var(--color-text-tertiary)"}}>
          +{dayEvts.length - 3} more
        </div>
      )}
    </div>
  );
}

function Sidebar({ month, year, events, holidays }) {
  const monthPfx = `${year}-${String(month+1).padStart(2,"0")}`;
  const evts = events
    .filter(e => getEventDate(e).startsWith(monthPfx))
    .sort((a,b) => getEventDate(a).localeCompare(getEventDate(b)) ||
                   getEventTime(a).localeCompare(getEventTime(b)));

  return (
    <aside style={{width:"220px",borderLeft:"0.5px solid var(--color-border-tertiary)",flexShrink:0,overflowY:"auto"}}>
      <div style={{padding:"10px 14px",borderBottom:"0.5px solid var(--color-border-tertiary)",
        display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <span style={{fontSize:"12px",fontWeight:"500",color:"var(--color-text-secondary)"}}>
          {MONTHS[month]} events
        </span>
        <span style={{fontSize:"12px",color:"var(--color-text-tertiary)"}}>{evts.length}</span>
      </div>

      {evts.length === 0 ? (
        <p style={{padding:"20px 14px",fontSize:"12px",color:"var(--color-text-tertiary)",
          textAlign:"center",lineHeight:"1.6",margin:0}}>
          No events this month.<br/>Click any date to schedule one.
        </p>
      ) : (
        evts.map((ev,i) => {
          const ds  = getEventDate(ev);
          const ts  = getEventTime(ev);
          const hol = holidays[ds];
          return (
            <div key={i} style={{padding:"9px 14px",borderBottom:"0.5px solid var(--color-border-tertiary)",fontSize:"12px"}}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:"2px"}}>
                <span style={{color:"var(--color-text-secondary)",fontWeight:"500"}}>
                  {ds.slice(5).replace("-","/")} {ts}
                </span>
                <span style={{
                  fontSize:"10px",padding:"1px 6px",borderRadius:"999px",
                  background: ev.played ? "var(--color-background-success)" : "var(--color-background-info)",
                  color:      ev.played ? "var(--color-text-success)" : "var(--color-text-info)",
                  border:`0.5px solid ${ev.played ? "var(--color-border-success)" : "var(--color-border-info)"}`,
                }}>{ev.played ? "played" : "upcoming"}</span>
              </div>
              <div style={{fontWeight:"500",color:"var(--color-text-primary)",
                overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                {ev.stream_name}
              </div>
              <div style={{color:"var(--color-text-tertiary)",overflow:"hidden",
                textOverflow:"ellipsis",whiteSpace:"nowrap",marginTop:"1px"}}
                title={ev.file_name || ev.file_path}>
                {ev.file_name || (ev.file_path||"").split("/").pop()}
              </div>
              {hol && (
                <div style={{fontSize:"10px",color:"var(--color-text-danger)",marginTop:"3px",
                  display:"flex",alignItems:"center",gap:"3px"}}>
                  <i className="ti ti-star-filled" aria-hidden="true" style={{fontSize:"9px"}}/> {hol}
                </div>
              )}
              <div style={{fontSize:"10px",color:"var(--color-text-tertiary)",marginTop:"2px",
                display:"flex",alignItems:"center",gap:"3px"}}>
                <i className="ti ti-rotate-clockwise" aria-hidden="true" style={{fontSize:"11px"}}/>
                {ev.post_action || "compliance"}
              </div>
            </div>
          );
        })
      )}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Create-event modal
// ---------------------------------------------------------------------------
function CreateModal({ date, holidays, streams, library, libraryLoading, onClose, onCreate }) {
  const [time,       setTime]       = useState("12:00");
  const [selStreams,  setSelStreams] = useState({});   // name -> true
  const [files,      setFiles]      = useState({});   // name -> file_path
  const [submitting, setSubmitting] = useState(false);
  const [err,        setErr]        = useState("");

  const holiday = holidays[fmtDate(date)];

  const toggle = name => setSelStreams(p => { const n={...p}; n[name] ? delete n[name] : (n[name]=true); return n; });

  const submit = async () => {
    const sel = Object.keys(selStreams);
    if (!sel.length) { setErr("Select at least one stream."); return; }
    for (const s of sel) {
      if (!files[s]) { setErr(`Select a file for "${s}".`); return; }
    }
    const [hh,mm] = time.split(":").map(Number);
    const dt = new Date(date);
    dt.setHours(hh, mm, 0, 0);
    const iso = fmtDate(dt) + `T${String(hh).padStart(2,"0")}:${String(mm).padStart(2,"0")}:00`;

    setSubmitting(true);
    setErr("");
    try {
      await onCreate({
        play_at: iso,
        streams: sel.map(name => ({ stream_name: name, file_path: files[name] })),
        post_action: "compliance",
      });
      onClose();
    } catch(e) {
      setErr(e.message || "Failed to schedule events.");
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      background:"var(--color-background-primary)",
      border:"0.5px solid var(--color-border-primary)",
      borderRadius:"var(--border-radius-lg)",
      width:"520px",maxHeight:"78vh",overflowY:"auto",
      boxShadow:"0 8px 32px rgba(0,0,0,0.18)",
    }}>
      {/* Header */}
      <div style={{padding:"16px 20px",borderBottom:"0.5px solid var(--color-border-tertiary)",
        display:"flex",justifyContent:"space-between",alignItems:"flex-start"}}>
        <div>
          <p style={{margin:0,fontSize:"15px",fontWeight:"500",color:"var(--color-text-primary)"}}>
            Schedule event
          </p>
          <p style={{margin:"3px 0 0",fontSize:"13px",color:"var(--color-text-secondary)"}}>
            {date.toLocaleDateString("en-GB",{weekday:"long",day:"numeric",month:"long",year:"numeric"})}
            {holiday && (
              <span style={{marginLeft:"8px",color:"var(--color-text-danger)",fontSize:"12px"}}>
                <i className="ti ti-star-filled" aria-hidden="true" style={{fontSize:"11px",verticalAlign:"-1px",marginRight:"3px"}}/>
                {holiday}
              </span>
            )}
          </p>
        </div>
        <button onClick={onClose} aria-label="Close"
          style={{background:"none",border:"none",cursor:"pointer",
            color:"var(--color-text-secondary)",fontSize:"20px",lineHeight:1,padding:"2px 6px"}}>
          ×
        </button>
      </div>

      <div style={{padding:"18px 20px"}}>
        {/* Time */}
        <div style={{marginBottom:"16px"}}>
          <label style={lbl}>Broadcast time</label>
          <input type="time" value={time} onChange={e=>setTime(e.target.value)} style={{width:"160px"}}/>
        </div>

        {/* Streams */}
        <div style={{marginBottom:"16px"}}>
          <label style={lbl}>
            Streams
            {Object.keys(selStreams).length > 0 &&
              <span style={{fontWeight:"400",color:"var(--color-text-tertiary)",marginLeft:"6px"}}>
                — {Object.keys(selStreams).length} selected
              </span>
            }
          </label>
          {streams.length === 0 ? (
            <p style={{fontSize:"12px",color:"var(--color-text-tertiary)",margin:0}}>No streams configured.</p>
          ) : (
            <div style={{display:"flex",flexDirection:"column",gap:"6px"}}>
              {streams.map(st => {
                const sel = !!selStreams[st.name];
                return (
                  <div key={st.name} style={{
                    border:`0.5px solid ${sel ? "var(--color-border-info)" : "var(--color-border-tertiary)"}`,
                    borderRadius:"var(--border-radius-md)",overflow:"hidden",
                    background: sel ? "var(--color-background-info)" : "var(--color-background-secondary)",
                    transition:"border-color 0.12s",
                  }}>
                    {/* Stream row */}
                    <div onClick={()=>toggle(st.name)}
                      style={{display:"flex",alignItems:"center",gap:"10px",padding:"10px 12px",cursor:"pointer"}}>
                      <div style={{
                        width:"16px",height:"16px",borderRadius:"3px",flexShrink:0,
                        border:`0.5px solid ${sel ? "var(--color-border-info)" : "var(--color-border-secondary)"}`,
                        background: sel ? "var(--color-text-info)" : "transparent",
                        display:"flex",alignItems:"center",justifyContent:"center",
                      }}>
                        {sel && <i className="ti ti-check" aria-hidden="true" style={{fontSize:"11px",color:"#fff"}}/>}
                      </div>
                      <div style={{flex:1}}>
                        <p style={{margin:0,fontSize:"13px",fontWeight:"500",color:"var(--color-text-primary)"}}>{st.name}</p>
                        <p style={{margin:0,fontSize:"11px",color:"var(--color-text-secondary)"}}>:{st.port}</p>
                      </div>
                      <span style={{
                        fontSize:"11px",padding:"2px 8px",borderRadius:"999px",
                        background: st.status==="running" ? "var(--color-background-success)" : "var(--color-background-secondary)",
                        color:      st.status==="running" ? "var(--color-text-success)" : "var(--color-text-secondary)",
                        border:`0.5px solid ${st.status==="running" ? "var(--color-border-success)" : "var(--color-border-tertiary)"}`,
                      }}>{st.status}</span>
                    </div>

                    {/* File picker (shown when stream selected) */}
                    {sel && (
                      <div style={{padding:"0 12px 12px",borderTop:"0.5px solid var(--color-border-tertiary)"}}>
                        <label style={{...lbl,paddingTop:"10px",display:"block"}}>
                          File for {st.name}
                        </label>
                        {libraryLoading ? (
                          <p style={{fontSize:"12px",color:"var(--color-text-tertiary)",margin:0}}>Loading library…</p>
                        ) : (
                          <select
                            value={files[st.name]||""}
                            onChange={e=>setFiles(f=>({...f,[st.name]:e.target.value}))}
                            style={{width:"100%"}}
                          >
                            <option value="">— select a file —</option>
                            {library.map((f,i) => (
                              <option key={i} value={f.full_path}>{f.path}</option>
                            ))}
                          </select>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Post-action note */}
        <div style={{padding:"10px 12px",borderRadius:"var(--border-radius-md)",
          background:"var(--color-background-secondary)",border:"0.5px solid var(--color-border-tertiary)",
          marginBottom:"16px",fontSize:"12px",color:"var(--color-text-secondary)",
          display:"flex",alignItems:"center",gap:"7px"}}>
          <i className="ti ti-rotate-clockwise" aria-hidden="true" style={{fontSize:"14px",flexShrink:0}}/>
          After playback: return to compliance / normal schedule
        </div>

        {/* Error */}
        {err && (
          <div style={{padding:"8px 12px",borderRadius:"var(--border-radius-md)",
            background:"var(--color-background-danger)",border:"0.5px solid var(--color-border-danger)",
            fontSize:"12px",color:"var(--color-text-danger)",marginBottom:"14px"}}>
            {err}
          </div>
        )}

        {/* Actions */}
        <div style={{display:"flex",gap:"8px",justifyContent:"flex-end"}}>
          <button onClick={onClose}>Cancel</button>
          <button onClick={submit} disabled={submitting}
            style={{background:"var(--color-text-info)",color:"#fff",border:"none",opacity:submitting?0.65:1}}>
            {submitting ? "Scheduling…" : "Schedule event"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings modal
// ---------------------------------------------------------------------------
function SettingsModal({ settings, onSave, onClose }) {
  const [form,    setForm]    = useState({ country: settings.holiday_country||"US", subdiv: settings.holiday_subdiv||"" });
  const [query,   setQuery]   = useState("");
  const [saving,  setSaving]  = useState(false);

  const filtered = COUNTRIES.filter(c =>
    c.name.toLowerCase().includes(query.toLowerCase()) ||
    c.code.toLowerCase().includes(query.toLowerCase())
  );

  const save = async () => {
    setSaving(true);
    try { await onSave(form); } finally { setSaving(false); }
  };

  return (
    <div style={{
      background:"var(--color-background-primary)",
      border:"0.5px solid var(--color-border-primary)",
      borderRadius:"var(--border-radius-lg)",
      width:"380px",
      boxShadow:"0 8px 32px rgba(0,0,0,0.18)",
    }}>
      <div style={{padding:"16px 20px",borderBottom:"0.5px solid var(--color-border-tertiary)",
        display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <p style={{margin:0,fontSize:"15px",fontWeight:"500"}}>Holiday settings</p>
        <button onClick={onClose} aria-label="Close"
          style={{background:"none",border:"none",cursor:"pointer",
            color:"var(--color-text-secondary)",fontSize:"20px",lineHeight:1,padding:"2px 6px"}}>×</button>
      </div>
      <div style={{padding:"18px 20px"}}>
        <div style={{marginBottom:"14px"}}>
          <label style={lbl}>Country</label>
          <input placeholder="Search…" value={query} onChange={e=>setQuery(e.target.value)}
            style={{width:"100%",marginBottom:"8px"}} autoFocus/>
          <select value={form.country} onChange={e=>setForm(f=>({...f,country:e.target.value}))}
            style={{width:"100%"}} size={6}>
            {filtered.map(c => <option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}
          </select>
        </div>
        <div style={{marginBottom:"18px"}}>
          <label style={lbl}>
            State / province
            <span style={{fontWeight:"400",color:"var(--color-text-tertiary)",marginLeft:"6px"}}>optional</span>
          </label>
          <input value={form.subdiv} onChange={e=>setForm(f=>({...f,subdiv:e.target.value}))}
            placeholder="e.g. CA, NSW, ON…" style={{width:"100%"}}/>
          <p style={{fontSize:"12px",color:"var(--color-text-tertiary)",margin:"6px 0 0"}}>
            Leave blank for national holidays only.
          </p>
        </div>
        <div style={{display:"flex",gap:"8px",justifyContent:"flex-end"}}>
          <button onClick={onClose}>Cancel</button>
          <button onClick={save} disabled={saving}
            style={{background:"var(--color-text-info)",color:"#fff",border:"none",opacity:saving?0.65:1}}>
            {saving ? "Saving…" : "Save settings"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export default function EventsCalendar() {
  const TODAY = new Date();

  const [month,    setMonth]    = useState(TODAY.getMonth());
  const [year,     setYear]     = useState(TODAY.getFullYear());
  const [events,   setEvents]   = useState([]);
  const [streams,  setStreams]  = useState([]);
  const [library,  setLibrary]  = useState([]);
  const [libLoading, setLibLoading] = useState(false);
  const [settings, setSettings] = useState({ holiday_country:"US", holiday_subdiv:null });
  const [holidays, setHolidays] = useState({});
  const [holKey,   setHolKey]   = useState("");   // cache buster
  const [loading,  setLoading]  = useState(true);
  const [modal,    setModal]    = useState(null);  // null | "create" | "settings"
  const [selDate,  setSelDate]  = useState(null);
  const [toast,    setToast]    = useState(null);
  const libLoaded = useRef(false);
  const toastRef  = useRef(null);

  // ---- toast helper ----
  const showToast = (msg, type="success") => {
    if (toastRef.current) clearTimeout(toastRef.current);
    setToast({ msg, type });
    toastRef.current = setTimeout(() => setToast(null), 3500);
  };

  // ---- initial data load ----
  useEffect(() => {
    Promise.all([
      fetch("/api/streams").then(r=>r.json()).catch(()=>[]),
      fetch("/api/events").then(r=>r.json()).catch(()=>[]),
      fetch("/api/settings").then(r=>r.json()).catch(()=>({holiday_country:"US"})),
    ]).then(([str, evts, sett]) => {
      setStreams(Array.isArray(str) ? str : []);
      setEvents(Array.isArray(evts) ? evts : []);
      setSettings(sett || {});
      setLoading(false);
    });
  }, []);

  // ---- holiday reload when year / country changes ----
  useEffect(() => {
    if (loading) return;
    const country = settings.holiday_country || "US";
    const subdiv  = settings.holiday_subdiv  || "";
    const key = `${year}:${country}:${subdiv}`;
    if (key === holKey) return;
    const qs = new URLSearchParams({ year, country });
    if (subdiv) qs.set("subdiv", subdiv);
    fetch(`/api/holidays?${qs}`)
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) {
          const map = {};
          data.forEach(h => { map[h.date] = h.name; });
          setHolidays(map);
          setHolKey(key);
        }
      })
      .catch(() => {});
  }, [year, settings, loading, holKey]);

  // ---- lazy-load library when create modal opens ----
  useEffect(() => {
    if (modal === "create" && !libLoaded.current) {
      setLibLoading(true);
      fetch("/api/library")
        .then(r => r.json())
        .then(data => { setLibrary(Array.isArray(data) ? data : []); libLoaded.current = true; })
        .catch(() => {})
        .finally(() => setLibLoading(false));
    }
  }, [modal]);

  // ---- poll events every 15s ----
  useEffect(() => {
    const t = setInterval(() => {
      fetch("/api/events").then(r=>r.json()).then(d => {
        if (Array.isArray(d)) setEvents(d);
      }).catch(()=>{});
    }, 15_000);
    return () => clearInterval(t);
  }, []);

  // ---- calendar grid ----
  const firstDay    = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month+1, 0).getDate();
  const cells = [];
  for (let i=0; i<firstDay; i++) cells.push(null);
  for (let d=1; d<=daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const eventsByDate = {};
  events.forEach(ev => {
    const d = getEventDate(ev);
    if (d) (eventsByDate[d] = eventsByDate[d] || []).push(ev);
  });

  const todayStr = fmtDate(TODAY);

  // ---- handlers ----
  const prevMonth = () => month===0 ? (setMonth(11),setYear(y=>y-1)) : setMonth(m=>m-1);
  const nextMonth = () => month===11 ? (setMonth(0), setYear(y=>y+1)) : setMonth(m=>m+1);
  const goToday   = () => { setMonth(TODAY.getMonth()); setYear(TODAY.getFullYear()); };

  const openCreateModal = (day) => {
    setSelDate(new Date(year, month, day));
    setModal("create");
  };

  const handleCreate = async (payload) => {
    const res  = await fetch("/api/events/bulk", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.created?.length) throw new Error(data.errors?.[0]?.error || "Failed.");
    // Optimistically append new events
    const added = data.created.map(ev => ({
      ...ev,
      play_at_iso: ev.play_at,
      file_name:   payload.streams.find(s=>s.stream_name===ev.stream_name)?.file_path.split("/").pop()||"",
      played:      false,
      post_action: "compliance",
    }));
    setEvents(prev => [...prev, ...added]);
    showToast(`${added.length} event${added.length>1?"s":""} scheduled`);
  };

  const handleSaveSettings = async ({ country, subdiv }) => {
    const res = await fetch("/api/settings", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ holiday_country: country, holiday_subdiv: subdiv||null }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    setSettings(data);
    setHolKey(""); // force reload
    setModal(null);
    showToast("Holiday settings saved");
  };

  if (loading) {
    return (
      <div style={{display:"flex",alignItems:"center",justifyContent:"center",minHeight:"300px",
        fontSize:"14px",color:"var(--color-text-secondary)"}}>
        <i className="ti ti-loader-2" aria-hidden="true" style={{fontSize:"20px",marginRight:"8px"}}/>
        Loading calendar…
      </div>
    );
  }

  return (
    <div style={{position:"relative",minHeight:"680px"}}>
      {/* --- Toast --- */}
      {toast && (
        <div style={{
          position:"absolute",top:"12px",right:"12px",zIndex:200,
          padding:"9px 16px",borderRadius:"var(--border-radius-md)",
          background: toast.type==="error" ? "var(--color-background-danger)" : "var(--color-background-success)",
          color:      toast.type==="error" ? "var(--color-text-danger)"      : "var(--color-text-success)",
          border:`0.5px solid ${toast.type==="error" ? "var(--color-border-danger)" : "var(--color-border-success)"}`,
          fontSize:"13px",fontWeight:"500",
        }}>{toast.msg}</div>
      )}

      {/* --- Modal overlay (absolute, not fixed) --- */}
      {modal && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={e => { if(e.target===e.currentTarget) setModal(null); }}
          style={{
            position:"absolute",inset:0,zIndex:100,
            background:"rgba(0,0,0,0.32)",
            display:"flex",alignItems:"flex-start",justifyContent:"center",
            paddingTop:"56px",
          }}
        >
          {modal==="create" && selDate && (
            <CreateModal
              date={selDate}
              holidays={holidays}
              streams={streams}
              library={library}
              libraryLoading={libLoading}
              onClose={()=>setModal(null)}
              onCreate={handleCreate}
            />
          )}
          {modal==="settings" && (
            <SettingsModal
              settings={settings}
              onSave={handleSaveSettings}
              onClose={()=>setModal(null)}
            />
          )}
        </div>
      )}

      {/* --- Calendar header --- */}
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",
        padding:"14px 16px",borderBottom:"0.5px solid var(--color-border-tertiary)"}}>
        <div style={{display:"flex",alignItems:"center",gap:"8px"}}>
          <button onClick={prevMonth} aria-label="Previous month"
            style={{width:"30px",height:"30px",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <i className="ti ti-chevron-left" aria-hidden="true" style={{fontSize:"16px"}}/>
          </button>
          <span style={{fontSize:"16px",fontWeight:"500",minWidth:"190px",textAlign:"center",letterSpacing:"-0.01em"}}>
            {MONTHS[month]} {year}
          </span>
          <button onClick={nextMonth} aria-label="Next month"
            style={{width:"30px",height:"30px",display:"flex",alignItems:"center",justifyContent:"center"}}>
            <i className="ti ti-chevron-right" aria-hidden="true" style={{fontSize:"16px"}}/>
          </button>
          <button onClick={goToday} style={{fontSize:"12px",padding:"4px 10px",marginLeft:"4px"}}>Today</button>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:"12px"}}>
          <Legend/>
          <button onClick={()=>setModal("settings")}
            style={{display:"flex",alignItems:"center",gap:"5px",fontSize:"12px",padding:"4px 10px"}}>
            <i className="ti ti-world" aria-hidden="true" style={{fontSize:"14px"}}/>
            {settings.holiday_country || "—"}
          </button>
        </div>
      </div>

      {/* --- Main grid + sidebar --- */}
      <div style={{display:"flex"}}>
        <div style={{flex:"1 1 0",minWidth:0}}>
          {/* Weekday headers */}
          <div style={{display:"grid",gridTemplateColumns:"repeat(7,minmax(0,1fr))",
            borderBottom:"0.5px solid var(--color-border-tertiary)"}}>
            {DAYS_SHORT.map(d => (
              <div key={d} style={{padding:"8px 0",textAlign:"center",fontSize:"12px",
                color:"var(--color-text-secondary)",borderRight:"0.5px solid var(--color-border-tertiary)"}}>
                {d}
              </div>
            ))}
          </div>
          {/* Day cells */}
          <div style={{display:"grid",gridTemplateColumns:"repeat(7,minmax(0,1fr))"}}>
            {cells.map((day,idx) => (
              <DayCell
                key={idx}
                day={day}
                year={year}
                month={month}
                todayStr={todayStr}
                holidays={holidays}
                eventsByDate={eventsByDate}
                onOpen={openCreateModal}
              />
            ))}
          </div>
        </div>

        <Sidebar month={month} year={year} events={events} holidays={holidays}/>
      </div>
    </div>
  );
}

// Shared label style
const lbl = {
  display:"block",
  fontSize:"11px",
  fontWeight:"500",
  color:"var(--color-text-secondary)",
  marginBottom:"6px",
};
