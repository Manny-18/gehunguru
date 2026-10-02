"""Visual layer: CSS + small HTML renderers. Kept separate from app logic."""

from __future__ import annotations

from html import escape

from .crop_stage import CRITICAL_IRRIGATIONS, SEASON_END, STAGES

SHORT = {
    "germination": "Germ.", "seedling": "Seedling", "cri": "CRI", "tillering": "Tillering",
    "jointing": "Jointing", "booting": "Boot", "heading": "Heading", "milk": "Milk",
    "dough": "Dough", "maturity": "Harvest",
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Mukta+Mahee:wght@400;600;800&display=swap');
:root{
  --haze:#F1F4EA; --ink:#1D2B20; --muted:#5B6A5E; --line:#D3DAC4;
  --sprout:#2F6B3A; --grain:#C99A2E; --grain-soft:#F3E6C2;
  --tractor:#B03A2E; --canal:#2E5E86; --paper:#FBFCF7;
}
/* Mukta (Latin + Devanagari) comes from config.toml; Mukta Mahee adds Gurmukhi for Punjabi text.
   Applied only to text containers so Streamlit's icon font is never overridden. */
.stMarkdown, [data-testid="stChatMessageContent"], .stButton p{font-family:'Mukta','Mukta Mahee','Noto Sans Gurmukhi',sans-serif;}
.block-container{max-width:1080px; padding-top:3.2rem;}
.gg-head{display:flex; align-items:baseline; gap:.8rem; flex-wrap:wrap; margin-bottom:.1rem;}
.gg-head h1{font-size:2.05rem; font-weight:800; letter-spacing:-.01em; margin:0; color:var(--ink); padding:0;}
.gg-head .hi{font-size:1.15rem; color:var(--sprout); font-weight:600;}
.gg-sub{color:var(--muted); margin:.15rem 0 .9rem 0; font-size:1rem; line-height:1.45; max-width:70ch;}
.gg-ai{font-size:.86rem; color:var(--muted); border-left:3px solid var(--canal); padding:.25rem .7rem; margin-bottom:1rem; background:var(--paper);}

/* ---- the crop track: the one bold element ---- */
.gg-track{background:var(--paper); border:1px solid var(--line); border-radius:14px; padding:1.1rem 1.2rem 1rem; margin-bottom:1rem;}
.gg-track-top{display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; flex-wrap:wrap;}
.gg-daynum{font-size:2.6rem; font-weight:800; line-height:1; color:var(--ink);}
.gg-dayunit{font-size:1rem; color:var(--muted); margin-left:.35rem;}
.gg-stage{font-size:1.35rem; font-weight:700; color:var(--sprout); line-height:1.2;}
.gg-stage .hi{font-weight:600; color:var(--ink); font-size:1.05rem; margin-left:.4rem;}
.gg-next{color:var(--ink); font-size:.95rem; line-height:1.45; text-align:right;}
.gg-next b{color:var(--canal);}
.gg-bar{position:relative; display:flex; height:26px; margin:1.1rem 0 .35rem; border-radius:6px; overflow:visible;}
.gg-seg{height:100%; border-right:2px solid var(--paper);}
.gg-seg.past{background:#9DB58F;}
.gg-seg.now{background:var(--grain);}
.gg-seg.future{background:#E3E8D8;}
.gg-seg:first-child{border-radius:6px 0 0 6px;} .gg-seg:last-child{border-radius:0 6px 6px 0; border-right:none;}
.gg-marker{position:absolute; top:-9px; width:3px; height:44px; background:var(--ink); border-radius:2px;}
.gg-drop{position:absolute; bottom:-4px; width:9px; height:9px; margin-left:-4px; border-radius:50% 50% 50% 0; transform:rotate(-45deg); background:var(--canal); border:1.5px solid var(--paper);}
.gg-labels{display:flex; font-size:.74rem; color:var(--muted); margin-top:.35rem;}
.gg-labels span{overflow:hidden; white-space:nowrap; text-overflow:clip; padding-left:2px;}
.gg-labels span.now{color:var(--ink); font-weight:700;}
.gg-legend{font-size:.8rem; color:var(--muted); margin-top:.45rem;}
.gg-legend i{display:inline-block; width:8px; height:8px; border-radius:50% 50% 50% 0; transform:rotate(-45deg); background:var(--canal); margin:0 .35rem 0 .1rem;}
.gg-warn{font-size:.85rem; color:#7A5A12; background:var(--grain-soft); border-radius:8px; padding:.35rem .6rem; margin-top:.6rem;}

/* ---- weather ---- */
.gg-wx{display:flex; gap:.4rem; overflow-x:auto; padding-bottom:.2rem;}
.gg-wx-day{flex:1 0 58px; border:1px solid var(--line); border-radius:10px; padding:.4rem .25rem; background:var(--paper); text-align:center;}
.gg-wx-day .d{font-size:.78rem; color:var(--muted);}
.gg-wx-day .i{font-size:1.25rem; line-height:1.5;}
.gg-wx-day .t{font-weight:700; font-size:.95rem;}
.gg-wx-day .t span{font-weight:400; color:var(--muted);}
.gg-wx-day .r{font-size:.7rem; color:var(--canal); line-height:1.25;}
.gg-src{font-size:.78rem; color:var(--muted); margin:.35rem 0 .6rem;}

/* ---- alerts ---- */
.gg-alert{border-left:4px solid var(--canal); background:var(--paper); padding:.45rem .75rem; margin:.4rem 0; border-radius:0 8px 8px 0;}
.gg-alert .t{font-weight:700;}
.gg-alert .m{font-size:.92rem; color:var(--ink); line-height:1.4;}
.gg-alert.high{border-color:var(--tractor);} .gg-alert.high .t{color:var(--tractor);}
.gg-alert.warn{border-color:var(--grain);}  .gg-alert.warn .t{color:#8A6516;}
.gg-alert.good{border-color:var(--sprout);} .gg-alert.good .t{color:var(--sprout);}

/* ---- chat meta + hand-off ---- */
.gg-meta{font-size:.78rem; color:var(--muted); margin-top:.35rem;}
.gg-meta b{color:var(--ink); font-weight:600;}
.gg-handoff{border:1.5px solid var(--tractor); border-radius:12px; padding:.8rem 1rem; background:#FFF8F5; margin:.4rem 0;}
.gg-handoff .h{font-weight:800; color:var(--tractor); font-size:1.05rem;}
.gg-handoff a{color:var(--canal); font-weight:700;}
.gg-handoff .tk{font-family:inherit; background:#F6E1DA; padding:.05rem .45rem; border-radius:5px;}
.gg-dx{border:1px solid var(--line); border-radius:12px; padding:.7rem .9rem; background:var(--paper);}
.gg-dx .cause{display:flex; align-items:center; gap:.6rem; margin:.25rem 0;}
.gg-dx .lk{font-size:.75rem; padding:.05rem .5rem; border-radius:999px; background:#E3E8D8; white-space:nowrap;}
.gg-dx .lk.high{background:var(--grain); color:#2B1F05;} .gg-dx .lk.medium{background:var(--grain-soft);}
.gg-welcome{background:var(--paper); border:1px solid var(--line); border-radius:14px; padding:1.2rem 1.4rem; max-width:720px;}
.gg-welcome h2{margin-top:0; font-weight:800;}
@media (max-width: 640px){
  .gg-next{text-align:left;} .gg-labels span:not(.now){visibility:hidden;} .gg-daynum{font-size:2.1rem;}
}
@media (prefers-reduced-motion: reduce){ *{transition:none !important; animation:none !important;} }
</style>
"""


def header_html() -> str:
    return (
        '<div class="gg-head"><h1>GehunGuru</h1><span class="hi">गेहूं गुरु</span></div>'
        '<div class="gg-sub">Wheat advice for your field, today: based on your sowing date, this week\'s '
        'weather and a checked knowledge base. Ask in English, हिंदी, ਪੰਜਾਬੀ or Hinglish, by text, voice or photo.</div>'
    )


def ai_notice_html() -> str:
    return (
        '<div class="gg-ai">You are chatting with an <b>AI assistant</b>, not a person or a government officer. '
        'Advice is general: confirm with your KVK or Kisan Call Centre (1800-180-1551) before spending on inputs.</div>'
    )


def track_html(info: dict, district: str) -> str:
    st_ = info["stage"]
    status = info["status"]
    total = SEASON_END + 1

    segs, labels = [], []
    for s in STAGES:
        w = s.end - s.start + 1
        if status == "not_sown":
            cls = "future"
        elif info["das"] is not None and info["das"] > s.end:
            cls = "past"
        elif s.key == st_.key:
            cls = "now"
        else:
            cls = "future"
        segs.append(f'<div class="gg-seg {cls}" style="flex:{w}" title="{escape(s.name)} ({s.start}-{s.end} DAS)"></div>')
        labels.append(f'<span class="{"now" if cls == "now" else ""}" style="flex:{w}">{SHORT[s.key]}</span>')

    drops = "".join(
        f'<div class="gg-drop" style="left:{d / total * 100:.2f}%" title="Critical irrigation ~{d} DAS: {escape(l)}"></div>'
        for d, l in CRITICAL_IRRIGATIONS
    )
    marker = ""
    if status in ("growing", "beyond") and info["das"] is not None:
        pos = min(info["das"], SEASON_END) / total * 100
        marker = f'<div class="gg-marker" style="left:calc({pos:.2f}% - 1px)"></div>'

    if status == "not_sown":
        top_left = ('<div><div class="gg-stage">Not sown yet <span class="hi">बुवाई से पहले</span></div>'
                    f'<div class="gg-dayunit" style="margin:0">{escape(district)}</div></div>')
        top_right = ('<div class="gg-next">Best sowing window: <b>25 Oct to 15 Nov</b> (Punjab, Haryana)<br>'
                     '<b>1 to 20 Nov</b> (west UP, Delhi NCR, north Rajasthan)</div>')
    else:
        top_left = (f'<div><span class="gg-daynum">Day {info["das"]}</span><span class="gg-dayunit">after sowing</span>'
                    f'<div class="gg-stage">{escape(st_.name)} <span class="hi">{escape(st_.name_hi)}</span></div></div>')
        bits = []
        if info.get("next_stage") and info.get("days_to_next") is not None:
            bits.append(f'Next stage: <b>{escape(info["next_stage"].name)}</b> in {info["days_to_next"]} days')
        irr = info.get("next_irrigation")
        if irr:
            when = "due now" if irr["in_days"] <= 2 else f'in {irr["in_days"]} days'
            bits.append(f'Critical irrigation: <b>{escape(irr["label"])}</b> ~day {irr["das"]} ({when})')
        if info.get("in_weed_window"):
            bits.append('Weed-control window: <b>30-35 days after sowing</b>')
        top_right = '<div class="gg-next">' + "<br>".join(bits) + "</div>"

    warns = "".join(f'<div class="gg-warn">{escape(w)}</div>' for w in info.get("warnings", []))
    return (
        f'<div class="gg-track"><div class="gg-track-top">{top_left}{top_right}</div>'
        f'<div class="gg-bar">{"".join(segs)}{drops}{marker}</div>'
        f'<div class="gg-labels">{"".join(labels)}</div>'
        '<div class="gg-legend"><i></i>critical irrigation days (approx., timely-sown wheat)</div>'
        f'{warns}</div>'
    )


def _wx_icon(d) -> str:
    if d.rain_mm >= 5 or d.rain_prob >= 60:
        return "🌧️"
    if d.tmin <= 2:
        return "❄️"
    if d.tmax >= 32:
        return "☀️"
    if d.rh_mean >= 85 and d.tmax <= 18:
        return "🌫️"
    return "⛅" if d.rain_prob >= 25 else "🌤️"


def weather_html(days, source_label: str) -> str:
    cells = "".join(
        f'<div class="gg-wx-day"><div class="d">{d.date.strftime("%a %d")}</div><div class="i">{_wx_icon(d)}</div>'
        f'<div class="t">{d.tmax:.0f}° <span>/ {d.tmin:.0f}°</span></div>'
        f'<div class="r">{d.rain_mm:.0f} mm<br>{d.wind_max:.0f} km/h</div></div>'
        for d in days
    )
    return (f'<div class="gg-wx">{cells}</div><div class="gg-src">Rain (mm) and top wind speed per day. '
            f'{escape(source_label)}</div>')


def alerts_html(alerts) -> str:
    return "".join(
        f'<div class="gg-alert {a.level}"><div class="t">{escape(a.title)}</div><div class="m">{escape(a.message)}</div></div>'
        for a in alerts
    )


def handoff_html(ticket: str, reason: str) -> str:
    return (
        '<div class="gg-handoff"><div class="h">Talk to a human expert</div>'
        f'<div>{escape(reason)}</div>'
        '<div style="margin-top:.45rem">📞 Kisan Call Centre (free): <a href="tel:18001801551">1800-180-1551</a>, '
        'local languages, 6 am to 10 pm<br>'
        '🏫 Your district Krishi Vigyan Kendra (KVK): <a href="https://kvk.icar.gov.in" target="_blank">find your KVK</a><br>'
        f'Reference for your call: <span class="tk">{escape(ticket)}</span>. Download the chat summary from the '
        'sidebar and show it to the expert.</div></div>'
    )


def diagnosis_html(dx: dict) -> str:
    if not dx["is_wheat"]:
        return f'<div class="gg-dx"><b>This photo does not look like a wheat plant.</b><br>{escape(dx["summary"])}</div>'
    causes = "".join(
        f'<div class="cause"><span class="lk {c["likelihood"]}">{c["likelihood"]} match</span>'
        f'<div><b>{escape(c["name"])}</b>{" [" + escape(c["kb_id"]) + "]" if c["kb_id"] else ""}'
        f'<br><span style="font-size:.9rem">{escape(c["visible_signs"])}</span></div></div>'
        for c in dx["possible_causes"]
    )
    checks = "".join(f"<li>{escape(x)}</li>" for x in dx["field_checks"])
    acts = "".join(f"<li>{escape(x)}</li>" for x in dx["actions"])
    urg = {"routine": "Routine", "soon": "Act within 2-3 days", "urgent": "Urgent: act today"}[dx["urgency"]]
    return (
        '<div class="gg-dx">'
        f'<div style="font-size:.85rem;color:var(--muted)">Photo check: possible causes, not a confirmed diagnosis. '
        f'Photo quality: {dx["image_quality"]}. Urgency: <b>{urg}</b></div>'
        f'<div style="margin:.4rem 0">{escape(dx["summary"])}</div>{causes}'
        + (f'<div style="margin-top:.5rem"><b>Check in your field</b><ul>{checks}</ul></div>' if checks else "")
        + (f'<div><b>What to do</b><ul>{acts}</ul></div>' if acts else "")
        + "</div>"
    )
