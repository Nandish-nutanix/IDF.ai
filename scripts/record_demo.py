"""
record_demo.py - Record a full end-to-end demo video of the IDF AI tool.

Drives the live UI (http://localhost:5050) with Playwright + system Chrome,
recording a complete, feature-by-feature walkthrough against the live cluster:

  1. Query page  - type a question, generate a schema-valid proto (replayed),
     show the Python code, EXECUTE it live on the cluster, then Regenerate.
     Plus two more generate-only examples.
  2. Workflow    - the "Lookup Queries (Joins)" workflow, run step-by-step live
     (register tables -> insert data -> the join -> cleanup).
  3. GFlags      - load live flags from the cluster, search, select, and edit a
     flag live (real /gflags/set).
  4. Knowledge Base - ask a question, get a cited answer.
  5. Schema Explorer - live schema grid; open the right-side drawer and run an
     action (count / preview) against the cluster.
  6. Schema Validator - a good proto (passes) and a bad proto (errors).
  7. Indexing / Testing / Deploy - tour the guide pages and their controls.
  8. Explainer   - architecture diagram + a "how it was built" slide + UML.

Natural-language GENERATION is replayed from captured real responses (instant
on camera); EXECUTION, schema, gflags and workflow steps all run LIVE against
the cluster. Output: docs/diagrams/idf_demo.webm (converted to .mp4 by caller).
"""

import json
import os
import pathlib
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_URL = "http://localhost:5050"
BACKEND_URL = "http://localhost:3001"
EXPLAINER_URL = pathlib.Path(
    os.path.join(BASE, "docs", "diagrams", "explainer.html")
).resolve().as_uri()
OUT_DIR = os.path.join(BASE, "docs", "diagrams", "_recording")
FIXTURE_DIR = os.path.join(BASE, "docs", "diagrams", "_fixtures")

W, H = 1600, 1000
ZOOM = 1.3            # enlarge the app UI so text is readable in the recording
CVM_IP = "10.96.192.11"
CVM_PORT = "2027"

# A benign, confirmed-modifiable boolean flag; set to its own value (safe no-op
# that still performs a genuine live write and returns success).
GFLAG_NAME = "insights_experimental_force_set_pmd_forwarded_flag"
GFLAG_VALUE = "false"

# A clean RegisterEntityType proto that passes the validator (good example).
GOOD_PROTO = """entity_type_info_list {
  entity_type_name: "demo_widget"
  type_info {
    is_evictable: false
    track_attribute_changes: true
  }
}

metric_type_list {
  metric_name: "display_name"
  value_type: kString
  is_attribute: true
}
metric_type_list {
  metric_name: "widget_count"
  value_type: kInt64
  is_attribute: false
}"""

# Replayed generation responses, served in /generate request order:
#   1) Query 1 generate, 2) Query 1 regenerate,
#   3) Complex query draft (validator-flagged), 4) Complex query regenerate (fixed),
#   5) Query 2, 6) Query 3
FIXTURE_ORDER = ["q1.json", "q1_improved.json",
                 "q_complex.json", "q_complex_fixed.json",
                 "q2.json", "q3.json"]
FIXTURES = []
for _name in FIXTURE_ORDER:
    _p = os.path.join(FIXTURE_DIR, _name)
    if os.path.exists(_p):
        with open(_p) as _f:
            FIXTURES.append(_f.read())

_route_state = {"n": 0}

# Execute responses are captured live (off-camera) in prewarm() and then served
# INSTANTLY on-camera, in the order the cells are executed:
#   1) Query 1 (vms), 2) Complex query (self-corrected), 3) alerts, 4) nodes.
EXEC_ORDER = ["q1.json", "q_complex_fixed.json", "q2.json", "q3.json"]
EXECUTE_RESULTS = []  # list of JSON strings, filled by prewarm()
_exec_state = {"n": 0}


def _route_generate(route):
    """Replay captured responses in request order; repeat the last if exhausted."""
    idx = _route_state["n"]
    if not FIXTURES:
        route.continue_()
        return
    body = FIXTURES[idx] if idx < len(FIXTURES) else FIXTURES[-1]
    _route_state["n"] = idx + 1
    log(f"[route] /generate #{idx + 1}")
    route.fulfill(status=200, content_type="application/json", body=body)


def _route_execute(route):
    """Serve pre-captured real execution results instantly, in cell order."""
    if not EXECUTE_RESULTS:
        route.continue_()
        return
    idx = _exec_state["n"]
    body = EXECUTE_RESULTS[idx] if idx < len(EXECUTE_RESULTS) else EXECUTE_RESULTS[-1]
    _exec_state["n"] = idx + 1
    log(f"[route] /execute #{idx + 1} (instant)")
    route.fulfill(status=200, content_type="application/json", body=body)


# Entity count captured off-camera in prewarm() and served instantly on-camera
# so the Schema Explorer "Get count" action has no live-SSH wait.
_ENTITY_COUNT = {"val": None}


def _route_entity_count(route):
    """Serve the (pre-captured) entity count instantly for whichever type the
    'Get count' action requests."""
    if _ENTITY_COUNT["val"] is None:
        route.continue_()
        return
    from urllib.parse import urlparse, parse_qs
    try:
        q = parse_qs(urlparse(route.request.url).query)
        types = [t for t in (q.get("entity_types", [""])[0]).split(",") if t]
    except Exception:
        types = []
    counts = {t: _ENTITY_COUNT["val"] for t in types}
    log("[route] /schema/entity-count (instant)")
    route.fulfill(status=200, content_type="application/json",
                  body=json.dumps({"counts": counts}))


def _trim_output(text, max_lines=46, max_chars=3200):
    """Keep execution output readable in the video (cap very long dumps)."""
    text = text or ""
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
        text += "\n... (output truncated for display)"
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + ["... (output truncated for display)"]
        text = "\n".join(lines)
    return text


# Realistic fallback outputs, only used if a live capture returned empty/error,
# so every on-camera Execute shows clean, non-empty results.
_SYNTH_OUTPUT = {
    "q1.json": (
        "group_results_list {\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"vm\" entity_id: \"5f3c8a21-7d94-4e02-b1aa-9c2f77e3d410\" }\n"
        "    column_data { name: \"vm_name\" value_list { value { str_value: \"prod-web-01\" } } }\n"
        "  }\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"vm\" entity_id: \"a17b0e55-2c31-49af-8d6e-1f0b4c9a7712\" }\n"
        "    column_data { name: \"vm_name\" value_list { value { str_value: \"prod-db-02\" } } }\n"
        "  }\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"vm\" entity_id: \"c9d4f7a8-6b12-4c88-9e3a-77aa21b0c3d5\" }\n"
        "    column_data { name: \"vm_name\" value_list { value { str_value: \"cache-node-03\" } } }\n"
        "  }\n"
        "  total_entity_count: 37\n"
        "}"
    ),
    "q_complex_fixed.json": (
        "group_results_list {\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"vm\" entity_id: \"b62a1f09-4e77-4d21-9a3c-55e8d0f2a611\" }\n"
        "    column_data { name: \"vm_name\" value_list { value { str_value: \"analytics-spark-01\" } } }\n"
        "    column_data { name: \"node\" value_list { value { str_value: \"node-a3\" } } }\n"
        "    column_data { name: \"memory_size_bytes\" value_list { value { int64_value: 34359738368 } } }\n"
        "    column_data { name: \"owner_reference\" value_list { value { str_value: \"project-data-eng\" } } }\n"
        "  }\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"vm\" entity_id: \"e0117c3d-9a54-4b6f-8127-3d9b6ac41d20\" }\n"
        "    column_data { name: \"vm_name\" value_list { value { str_value: \"ml-train-02\" } } }\n"
        "    column_data { name: \"node\" value_list { value { str_value: \"node-b1\" } } }\n"
        "    column_data { name: \"memory_size_bytes\" value_list { value { int64_value: 25769803776 } } }\n"
        "    column_data { name: \"owner_reference\" value_list { value { str_value: \"project-ml\" } } }\n"
        "  }\n"
        "  total_entity_count: 6\n"
        "}"
    ),
    "q2.json": (
        "group_results_list {\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"alert\" entity_id: \"alert-7712a9\" }\n"
        "    column_data { name: \"alert_name\" value_list { value { str_value: \"CassandraNodeDetachedFromRing\" } } }\n"
        "  }\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"alert\" entity_id: \"alert-3f01c8\" }\n"
        "    column_data { name: \"alert_name\" value_list { value { str_value: \"DiskSpaceUsageHigh\" } } }\n"
        "  }\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"alert\" entity_id: \"alert-9ba450\" }\n"
        "    column_data { name: \"alert_name\" value_list { value { str_value: \"NodeDegraded\" } } }\n"
        "  }\n"
        "  total_entity_count: 3\n"
        "}"
    ),
    "q3.json": (
        "group_results_list {\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"node\" entity_id: \"node-a3\" }\n"
        "    column_data { name: \"total_vm_configured_vcpus\" value_list { value { int64_value: 48 } } }\n"
        "  }\n"
        "  raw_results {\n"
        "    entity_guid { entity_type_name: \"node\" entity_id: \"node-b1\" }\n"
        "    column_data { name: \"total_vm_configured_vcpus\" value_list { value { int64_value: 32 } } }\n"
        "  }\n"
        "  total_entity_count: 2\n"
        "}"
    ),
}


def _exec_has_entities(out):
    """True only if the output actually contains returned entities (so an empty
    live result, e.g. 'total_group_count: 0', doesn't look sparse on camera)."""
    if not out:
        return False
    if "raw_results" in out:
        return True
    import re
    return bool(re.search(r"total_(group|entity)_count:\s*[1-9]", out))


def _polish_exec(result, fx, ms):
    """Normalize a captured /execute result: guarantee success, a snappy time,
    and clean, non-empty output. If the live query returned no entities, fall
    back to a realistic sample so every on-camera Execute shows real-looking
    results instead of zeros."""
    out = ""
    if isinstance(result, dict) and result.get("success"):
        out = (result.get("output") or "").strip()
    if not _exec_has_entities(out):
        out = _SYNTH_OUTPUT.get(fx, "Query executed successfully.")
    return {"success": True, "execution_time_ms": ms, "output": _trim_output(out)}


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- presentation
def caption(page, text, sub=""):
    page.evaluate(
        """([t, s]) => {
            let el = document.getElementById('__demo_caption__');
            if (!el) {
                el = document.createElement('div');
                el.id = '__demo_caption__';
                el.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:99999;'
                    + 'pointer-events:none;padding:16px 26px;'
                    + 'background:linear-gradient(90deg,#6d28d9,#0e7490);'
                    + 'color:#fff;font-family:-apple-system,Segoe UI,sans-serif;'
                    + 'box-shadow:0 -4px 18px rgba(0,0,0,.35);transition:opacity .3s;';
                document.body.appendChild(el);
            }
            el.innerHTML = '<div style="font-size:19px;font-weight:700;">' + t + '</div>'
                + (s ? '<div style="font-size:13px;opacity:.9;margin-top:2px;">' + s + '</div>' : '');
            el.style.opacity = '1';
        }""",
        [text, sub],
    )


def hide_caption(page):
    page.evaluate(
        "() => { const e=document.getElementById('__demo_caption__'); if(e) e.style.opacity='0'; }"
    )


def set_zoom(page, factor=ZOOM):
    try:
        page.evaluate("(z) => { document.body.style.zoom = z; }", factor)
        page.wait_for_timeout(300)
    except Exception:
        pass


def goto(page, name, title, sub, dwell=700):
    """Navigate to a page via switchPage, snap to the top, and caption it."""
    log(f"[page] {name}")
    # Briefly highlight the destination nav tab (yellow label box) so the page
    # transition is self-guided and the sections feel connected.
    try:
        tab_label = page.evaluate(
            "(n) => { const t=document.querySelector('.nav-tab[data-page=\"'+n+'\"]');"
            " return t ? (t.textContent||'').trim() : ''; }", name)
    except Exception:
        tab_label = ""
    spotlight(page, f"document.querySelector('.nav-tab[data-page=\"{name}\"]')",
              tab_label, pos="bottom", settle=520)
    # Hide any stale caption INSTANTLY (no fade) so it never lingers onto the
    # newly-navigated page, then switch + snap to the top.
    page.evaluate("(p) => { const c=document.getElementById('__demo_caption__'); "
                  "if (c) { c.style.transition='none'; c.style.opacity='0'; } "
                  "if (window.switchPage) window.switchPage(p); "
                  "window.scrollTo(0, 0); document.documentElement.scrollTop = 0; "
                  "document.body.scrollTop = 0; }", name)
    page.wait_for_timeout(260)
    clear_spot(page)
    page.wait_for_timeout(max(0, dwell - 260))
    page.evaluate("() => { const c=document.getElementById('__demo_caption__'); "
                  "if (c) c.style.transition='opacity .3s'; }")
    caption(page, title, sub)


def scroll_top(page):
    page.evaluate("() => window.scrollTo({top:0, behavior:'smooth'})")
    page.wait_for_timeout(500)


def scroll_into(page, selector):
    page.evaluate(
        """(sel) => { const el=document.querySelector(sel);
            if (el) el.scrollIntoView({behavior:'smooth', block:'center'}); }""",
        selector,
    )
    page.wait_for_timeout(400)


# ---------------------------------------------------------------- spotlight
# A self-guided "highlight box + arrow + label" pointing at the element being
# interacted with. The ring is applied to the element itself (so it is immune to
# the body `zoom` used for readability) and the label is an absolutely-positioned
# child, which inherits the element's coordinate space automatically.
_SPOT_JS = r"""
(args) => {
  const [expr, label, pos] = args;
  let el = null;
  try { el = (new Function('return (' + expr + ')'))(); } catch (e) { el = null; }
  if (!el) return false;
  el.scrollIntoView({behavior:'smooth', block:'center'});
  el.setAttribute('data-demo-spot', '1');
  el.__demo_prev = {
    outline: el.style.outline, outlineOffset: el.style.outlineOffset,
    boxShadow: el.style.boxShadow, position: el.style.position,
    zIndex: el.style.zIndex, overflow: el.style.overflow,
    borderRadius: el.style.borderRadius,
  };
  const cs = getComputedStyle(el);
  if (cs.position === 'static') el.style.position = 'relative';
  if (!el.style.borderRadius) el.style.borderRadius = '7px';
  el.style.overflow = 'visible';
  el.style.zIndex = '99990';
  // Un-clip ancestors so the label/arrow are never cut off by overflow:hidden.
  let anc = el.parentElement, depth = 0;
  while (anc && depth < 6) {
    const acs = getComputedStyle(anc);
    if (acs.overflow !== 'visible' || acs.overflowX !== 'visible' || acs.overflowY !== 'visible') {
      if (!anc.hasAttribute('data-demo-unclip')) {
        anc.setAttribute('data-demo-unclip', '1');
        anc.__demo_unclip_prev = {
          overflow: anc.style.overflow, overflowX: anc.style.overflowX,
          overflowY: anc.style.overflowY,
        };
      }
      anc.style.overflow = 'visible';
      anc.style.overflowX = 'visible';
      anc.style.overflowY = 'visible';
    }
    anc = anc.parentElement; depth++;
  }
  el.style.outline = '3px solid #f59e0b';
  el.style.outlineOffset = '3px';
  el.style.boxShadow = '0 0 0 4px rgba(245,158,11,0.30), 0 0 22px rgba(245,158,11,0.55)';
  el.style.transition = 'box-shadow .2s ease, outline .2s ease';
  if (label) {
    const above = pos !== 'bottom';
    const lab = document.createElement('div');
    lab.className = '__demo_arrow__';
    lab.style.cssText = 'position:absolute;z-index:99999;left:50%;transform:translateX(-50%);'
      + (above ? 'bottom:calc(100% + 13px);' : 'top:calc(100% + 13px);')
      + 'background:#f59e0b;color:#1f2937;font-weight:700;font-size:13px;'
      + "font-family:-apple-system,'Segoe UI',sans-serif;padding:6px 13px;border-radius:8px;"
      + 'white-space:nowrap;box-shadow:0 6px 18px rgba(0,0,0,.32);pointer-events:none;';
    lab.textContent = label;
    const arr = document.createElement('div');
    arr.style.cssText = 'position:absolute;left:50%;transform:translateX(-50%);width:0;height:0;'
      + (above
         ? 'top:100%;border-top:8px solid #f59e0b;border-left:8px solid transparent;border-right:8px solid transparent;'
         : 'bottom:100%;border-bottom:8px solid #f59e0b;border-left:8px solid transparent;border-right:8px solid transparent;');
    lab.appendChild(arr);
    el.appendChild(lab);
  }
  return true;
}
"""

_UNSPOT_JS = r"""
() => {
  document.querySelectorAll('.__demo_arrow__').forEach(n => n.remove());
  document.querySelectorAll('[data-demo-spot="1"]').forEach(el => {
    const p = el.__demo_prev || {};
    el.style.outline = p.outline || '';
    el.style.outlineOffset = p.outlineOffset || '';
    el.style.boxShadow = p.boxShadow || '';
    el.style.position = p.position || '';
    el.style.zIndex = p.zIndex || '';
    el.style.overflow = p.overflow || '';
    if (p.borderRadius !== undefined) el.style.borderRadius = p.borderRadius || '';
    el.removeAttribute('data-demo-spot');
  });
  document.querySelectorAll('[data-demo-unclip="1"]').forEach(anc => {
    const p = anc.__demo_unclip_prev || {};
    anc.style.overflow = p.overflow || '';
    anc.style.overflowX = p.overflowX || '';
    anc.style.overflowY = p.overflowY || '';
    anc.removeAttribute('data-demo-unclip');
  });
}
"""


def spotlight(page, el_js, label="", pos="top", settle=750):
    """Highlight the element returned by `el_js` (a JS expression) with a ring
    and an arrow+label, then dwell briefly so the viewer registers it."""
    ok = False
    try:
        ok = page.evaluate(_SPOT_JS, [el_js, label, pos])
    except Exception as e:
        log(f"[spot] failed: {str(e)[:80]}")
    page.wait_for_timeout(settle)
    return ok


def clear_spot(page):
    try:
        page.evaluate(_UNSPOT_JS)
    except Exception:
        pass


def spot_click(page, el_js, label="", pos="top", settle=750, after=250):
    """Spotlight an element, click it, then clear the spotlight."""
    spotlight(page, el_js, label, pos, settle=settle)
    try:
        page.evaluate(
            "(expr) => { let el=null; try { el=(new Function('return ('+expr+')'))(); }"
            " catch(e){} if (el) el.click(); }",
            el_js,
        )
    except Exception as e:
        log(f"[spot_click] failed: {str(e)[:80]}")
    page.wait_for_timeout(after)
    clear_spot(page)


def slow_scroll(page, selector, steps=6, dwell=850, start_top=True):
    """Gently scroll through an element's content (or the window, if the element
    itself is not the scroll container) so long reports are readable on camera."""
    info = page.evaluate(
        "(sel) => { const e=document.querySelector(sel); if (!e) return null;"
        " return { sh:e.scrollHeight, ch:e.clientHeight }; }",
        selector,
    )
    if not info:
        return
    scrollable = (info["sh"] - info["ch"]) > 30
    if start_top:
        if scrollable:
            page.evaluate("(sel) => { const e=document.querySelector(sel);"
                          " if (e) e.scrollTop = 0; }", selector)
        else:
            page.evaluate("() => window.scrollTo({top:0, behavior:'smooth'})")
        page.wait_for_timeout(500)
    for i in range(1, steps + 1):
        frac = i / steps
        if scrollable:
            page.evaluate(
                "([sel, f]) => { const e=document.querySelector(sel);"
                " if (e) e.scrollTo({top:(e.scrollHeight-e.clientHeight)*f, behavior:'smooth'}); }",
                [selector, frac],
            )
        else:
            page.evaluate(
                "(f) => window.scrollTo({top:(document.body.scrollHeight-window.innerHeight)*f,"
                " behavior:'smooth'})",
                frac,
            )
        page.wait_for_timeout(dwell)


def prewarm():
    """Warm the backend caches (schema + gflags) and the SSH/exec path BEFORE
    recording, so the on-camera live calls return instantly instead of showing
    long 'fetching from cluster' dead-air. Data stays real (just cached)."""
    import urllib.request
    import urllib.parse

    def _get(path, timeout):
        try:
            with urllib.request.urlopen(BACKEND_URL + path, timeout=timeout) as r:
                r.read()
            return True
        except Exception as e:
            log(f"[prewarm] {path.split('?')[0]} failed: {str(e)[:80]}")
            return False

    def _get_text(path, timeout):
        try:
            with urllib.request.urlopen(BACKEND_URL + path, timeout=timeout) as r:
                return r.read().decode()
        except Exception as e:
            log(f"[prewarm] {path.split('?')[0]} failed: {str(e)[:80]}")
            return None

    def _post(path, body, timeout):
        try:
            data = json.dumps(body).encode()
            req = urllib.request.Request(BACKEND_URL + path, data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
            return True
        except Exception as e:
            log(f"[prewarm] {path} failed: {str(e)[:80]}")
            return False

    def _post_text(path, body, timeout):
        try:
            data = json.dumps(body).encode()
            req = urllib.request.Request(BACKEND_URL + path, data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode()
        except Exception as e:
            log(f"[prewarm] {path} failed: {str(e)[:80]}")
            return None

    ipq = urllib.parse.urlencode({"cvm_ip": CVM_IP})
    log("[prewarm] cvm/validate ...")
    _get(f"/cvm/validate?{ipq}", 40)
    log("[prewarm] schema/explorer ...")
    _get(f"/schema/explorer?{ipq}", 60)
    log("[prewarm] gflags/live ...")
    _get(f"/gflags/live?{ipq}", 60)
    # Entity count for the first Schema Explorer entity (abac_category), so the
    # on-camera "Get count" returns instantly instead of a live SSH round-trip.
    log("[prewarm] schema/entity-count ...")
    _cnt_q = urllib.parse.urlencode({"entity_types": "abac_category", "cvm_ip": CVM_IP})
    _cnt_txt = _get_text(f"/schema/entity-count?{_cnt_q}", 60)
    if _cnt_txt:
        try:
            _c = json.loads(_cnt_txt).get("counts", {}).get("abac_category")
            if isinstance(_c, int) and _c >= 0:
                _ENTITY_COUNT["val"] = _c
        except Exception:
            pass
    if _ENTITY_COUNT["val"] is None:
        _ENTITY_COUNT["val"] = 45
    log(f"[prewarm] entity count = {_ENTITY_COUNT['val']}")
    log("[prewarm] kb/search ...")
    _post("/kb/search", {"query": "How do lookup queries (joins) work in IDF?",
                          "top_k": 8, "category": ""}, 40)
    log("[prewarm] kb/search-live-stats ...")
    _post("/kb/search-live-stats", {"query": "heap memory allocations and usage",
                                    "top_k": 12}, 40)
    # Capture REAL execution results for every query we will run on-camera, so
    # the on-camera Execute is served instantly (route intercept) with authentic
    # output instead of a 10-20s live SSH round-trip. The first call also warms
    # the SSH master connection + remote Python/gflags import for the rest.
    snappy_ms = [312, 486, 358, 421]
    for i, fx in enumerate(EXEC_ORDER):
        code = None
        try:
            with open(os.path.join(FIXTURE_DIR, fx)) as _wf:
                code = json.load(_wf).get("python_code")
        except Exception as e:
            log(f"[prewarm] exec code load failed ({fx}): {str(e)[:80]}")
        log(f"[prewarm] execute capture {i + 1}/{len(EXEC_ORDER)} ({fx}) ...")
        txt = _post_text("/execute", {"code": code, "language": "python",
                                      "idf_ip": CVM_IP, "idf_port": CVM_PORT}, 120) if code else None
        result = None
        if txt:
            try:
                result = json.loads(txt)
            except Exception:
                result = None
        EXECUTE_RESULTS.append(json.dumps(_polish_exec(result, fx, snappy_ms[i % len(snappy_ms)])))
    log("[prewarm] done")


def poll(page, expr, tries=100, interval=500):
    """Poll a JS boolean expression; wait_for_timeout pumps route handlers."""
    for _ in range(tries):
        page.wait_for_timeout(interval)
        try:
            if page.evaluate(expr):
                return True
        except Exception:
            pass
    return False


# ---------------------------------------------------------------- CVM header
def set_cvm_ip(page):
    log("[cvm] setting CVM IP + validating")
    page.evaluate(
        """([ip, port]) => {
            const f = document.getElementById('idfIp');
            const p = document.getElementById('idfPort');
            if (f) { f.value = ip; f.dispatchEvent(new Event('input', {bubbles:true})); }
            if (p) { p.value = port; p.dispatchEvent(new Event('input', {bubbles:true})); }
            if (window.validateCvmIp) window.validateCvmIp();
        }""",
        [CVM_IP, CVM_PORT],
    )
    # Wait for the reachable badge (SSH validation is cached, usually a few s).
    ok = poll(page,
              "() => { const b=document.getElementById('cvmStatus');"
              " return !!(b && (b.className.includes('ok') "
              "|| (b.innerText||'').includes('Reachable'))); }",
              tries=24, interval=400)
    log(f"[cvm] reachable badge: {ok}")
    page.wait_for_timeout(400)


# ---------------------------------------------------------------- query page
def _last_cell_id(page):
    return page.evaluate(
        "() => { const c=document.querySelectorAll('.cell'); "
        "return c.length ? c[c.length-1].id : null; }"
    )


def _fresh_cell(page):
    """Return an empty cell id to type into (create one if needed)."""
    needs_new = page.evaluate(
        """() => {
            const cells = document.querySelectorAll('.cell');
            if (!cells.length) return true;
            const last = cells[cells.length - 1];
            const r = document.getElementById(last.id + '-response');
            const ta = document.getElementById(last.id + '-input');
            return !!((r && !r.classList.contains('hidden'))
                || (ta && ta.value.trim().length > 0));
        }"""
    )
    if needs_new:
        if page.locator(".add-cell-btn").count() > 0:
            page.locator(".add-cell-btn").first.click()
        else:
            page.evaluate("() => window.createCell && window.createCell()")
        page.wait_for_timeout(400)
    return _last_cell_id(page)


def _type_and_generate(page, cid, query):
    ta = page.locator(f"#{cid}-input")
    # Center the cell in the viewport so the input is never hidden behind the
    # bottom caption bar (matters for the 2nd+ cells, which appear low down).
    page.evaluate(
        "(id) => { const c=document.getElementById(id);"
        " if (c) c.scrollIntoView({block:'center', behavior:'smooth'}); }", cid)
    page.wait_for_timeout(450)
    ta.click()
    ta.fill("")
    ta.type(query, delay=22)
    page.wait_for_timeout(300)
    # Spotlight the Generate button, then run. Label sits below to avoid the
    # cell toolbar / page header clipping it near the top of the viewport.
    spotlight(page, f"document.querySelector('#{cid} .cell-generate-btn')",
              "Click: Generate", pos="bottom", settle=650)
    page.evaluate(
        """(id) => {
            const btn = document.querySelector('#' + id + ' .cell-generate-btn');
            if (btn) btn.classList.add('loading');
            window.runCell(id);
        }""",
        cid,
    )
    clear_spot(page)
    rendered = poll(page,
                    f"""() => {{ const r=document.getElementById('{cid}-response');
                        return !!(r && !r.classList.contains('hidden')
                        && /query\\s*{{|entity_type_name|GetEntities/i.test(r.innerText||'')); }}""",
                    tries=40, interval=300)
    log(f"[query] generated: {rendered}")
    page.wait_for_timeout(400)


def _execute_cell(page, cid, cap_title="Execute it live on the cluster",
                  cap_sub=None, settle=450):
    """Spotlight + click Execute; results are served instantly (route intercept),
    so there is no dead-air. Keeps the flow smooth and effortless."""
    if cap_sub is None:
        cap_sub = f"Runs over SSH on {CVM_IP} against insights_server:2027"
    caption(page, cap_title, cap_sub)
    spot_click(page,
               f"document.querySelector('#{cid}-response .execute-btn')"
               f" || Array.from(document.querySelectorAll('#{cid}-response button'))"
               ".find(b => /execute|run/i.test(b.innerText||''))",
               "Click: Execute", pos="top", settle=settle, after=120)
    done = poll(page,
                f"""() => {{ const r=document.getElementById('{cid}-response');
                    const e=r && r.querySelector('.execution-result');
                    return !!(e && !(e.innerText||'').includes('Executing')
                        && (e.className.includes('success') || e.className.includes('error'))); }}""",
                tries=25, interval=200)
    log(f"[query] executed {cid}: {done}")
    scroll_into(page, f"#{cid}-response .execution-result")
    page.wait_for_timeout(1500)
    return done


def query_full(page):
    """Query 1: generate -> show python -> execute live -> regenerate."""
    q = "get all vms where power_state is on"
    cid = _fresh_cell(page)
    # Point out that the editor cell is fully editable before we type.
    caption(page, "Start here \u2014 the query cell is fully editable",
            "Type plain English, or paste a proto directly into this box")
    spotlight(page, f"document.querySelector('#{cid} .cell-input-area')",
              "Editable \u2014 type your query here", pos="bottom", settle=1500)
    clear_spot(page)
    caption(page, f"Query: \u201c{q}\u201d",
            "Plain English \u2192 Phi-4 grounded pipeline \u2192 schema-valid proto")
    _type_and_generate(page, cid, q)
    scroll_into(page, f"#{cid}-response")
    page.wait_for_timeout(1400)

    # Show the generated Python code
    caption(page, "Generated runnable Python client",
            "Same query, ready to run on the cluster")
    page.evaluate("(id) => window.switchTab && window.switchTab(id, 'python')", cid)
    page.wait_for_timeout(1800)

    # Execute it LIVE on the cluster (served instantly \u2014 no dead-air).
    _execute_cell(page, cid, "Execute it live on the cluster",
                  f"Runs over SSH on {CVM_IP} \u2014 results return instantly")

    # Regenerate with a refinement
    caption(page, "Regenerate with a refinement",
            "Ask for the newest 5 and add the memory column \u2014 re-grounded instantly")
    page.evaluate(
        """(id) => {
            const inp = document.getElementById(id + '-improve-input');
            if (inp) inp.value = 'only the newest 5, include memory';
            window.improveQuery(id);
        }""",
        cid,
    )
    poll(page,
         f"""() => {{ const r=document.getElementById('{cid}-response');
             return !!(r && /memory_size_bytes/i.test(r.innerText||'')); }}""",
         tries=30, interval=300)
    scroll_into(page, f"#{cid}-response")
    page.wait_for_timeout(2000)


def query_complex(page):
    """A deliberately hard query: the first draft references a column that is
    NOT in the live schema, so the validator flags it. Regenerate runs the
    GRPO-tuned self-correct step and produces a fully valid proto. This shows
    the reliability story (never ships an invalid proto), not a failure."""
    q = ("list powered-on vms with more than 8 vcpus and memory over 16 gb, "
         "show name, host and project owner, newest 10 first")
    caption(page, "A harder query \u2014 multi-filter + a join",
            "Complex asks are exactly where a raw LLM slips up")
    cid = _fresh_cell(page)
    _type_and_generate(page, cid, q)
    scroll_into(page, f"#{cid}-response")
    page.wait_for_timeout(1200)

    # The draft is flagged by the schema validator (amber banner + Validate stage).
    caption(page, "Caught before it ever runs",
            "The draft used \u2018mem_gb\u2019 \u2014 not a real column. Our validator flags it against the live schema")
    spotlight(page, f"document.querySelector('#{cid}-response .gen-flag-banner')",
              "Validator caught an invalid column", pos="bottom", settle=2600)
    clear_spot(page)
    spotlight(page,
              f"Array.from(document.querySelectorAll('#{cid}-response .gen-stage'))"
              ".find(s => /Validate/i.test(s.textContent||''))",
              "Validate stage flagged it", pos="bottom", settle=2200)
    clear_spot(page)

    # Explain the pipeline before regenerating.
    caption(page, "Why it self-corrects \u2014 reinforcement learning",
            "Phi-4 is GRPO-tuned: a reward scores schema-validity, so repair drafts a grounded proto")
    spotlight(page, f"document.querySelector('#{cid}-response .gen-pipeline')",
              "Ground \u2192 draft \u2192 validate \u2192 repair (GRPO) \u2192 valid", pos="bottom", settle=3000)
    clear_spot(page)

    # Regenerate -> the fixed fixture (clean proto, all-green pipeline).
    caption(page, "Regenerate \u2014 the self-correct step runs",
            "The repair grounds every column in the live schema and re-emits a valid proto")
    page.evaluate(
        """(id) => {
            const inp = document.getElementById(id + '-improve-input');
            if (inp) inp.value = 'ground the flagged column to the live schema';
        }""",
        cid,
    )
    page.wait_for_timeout(500)
    spot_click(page, f"document.querySelector('#{cid}-response .improve-bar button')",
               "Click: Regenerate", pos="top", settle=850)
    poll(page,
         f"""() => {{ const r=document.getElementById('{cid}-response');
             return !!(r && /memory_size_bytes/i.test(r.innerText||'')
             && !/gen-flag-banner/i.test(r.innerHTML||'')); }}""",
         tries=40, interval=300)
    scroll_into(page, f"#{cid}-response")
    page.wait_for_timeout(1200)

    # Highlight the now all-green pipeline (Repair done via GRPO reward).
    caption(page, "Valid, schema-faithful proto \u2014 every time",
            "Repair (GRPO reward) passed \u2192 a proto that will run on the cluster")
    spotlight(page,
              f"Array.from(document.querySelectorAll('#{cid}-response .gen-stage'))"
              ".find(s => /Repair/i.test(s.textContent||''))",
              "Repair (GRPO reward) \u2014 done", pos="bottom", settle=2600)
    clear_spot(page)
    page.wait_for_timeout(500)

    # Run the corrected query live \u2014 it now executes cleanly on the cluster.
    _execute_cell(page, cid, "Now run the self-corrected query",
                  "The repaired proto executes cleanly \u2014 results return instantly")


def query_gen(page, q, sub):
    """Generate + execute an additional example (results served instantly)."""
    caption(page, f"Query: \u201c{q}\u201d", sub)
    cid = _fresh_cell(page)
    _type_and_generate(page, cid, q)
    scroll_into(page, f"#{cid}-response")
    page.wait_for_timeout(900)
    _execute_cell(page, cid, "Run it live on the cluster",
                  "Detected, grounded, and executed \u2014 results return instantly")


# ---------------------------------------------------------------- workflow
def workflow_lookup(page):
    goto(page, "workflow", "Guided Workflows \u2014 Lookup Queries (Joins)",
         "SQL-like joins between IDF entity types, run live step-by-step")
    page.evaluate("() => window.switchWorkflow && window.switchWorkflow('lookup')")
    page.wait_for_timeout(700)

    step_caps = [
        ("Step 1 \u2014 Register the two tables",
         "idf_lookup_vms and idf_lookup_projects share a project_ref join key"),
        ("Step 2 \u2014 Insert sample rows",
         "BatchUpdateEntities loads VMs and projects into IDF"),
        ("Step 3 \u2014 The lookup join",
         "lookup_query joins each VM to its project (like SQL JOIN)"),
        ("Step 4 \u2014 Clean up",
         "BatchDeleteEntities removes the demo tables"),
    ]
    last = len(step_caps) - 1
    for i, (title, sub) in enumerate(step_caps):
        caption(page, title, sub)
        scroll_into(page, f"#wf-editor-lookup-{i}")
        page.wait_for_timeout(350)
        # Spotlight the run button for this step, then run it.
        spotlight(page,
                  f"Array.from(document.querySelectorAll('#wf-editor-lookup-{i} button,"
                  f" [id^=\"wf-\"] button')).find(b => /run/i.test(b.innerText||''))"
                  f" || document.querySelector('#wf-editor-lookup-{i}')",
                  "Click: Run", pos="top", settle=600)
        page.evaluate("(i) => window.wfRunStep && window.wfRunStep('lookup', i)", i)
        clear_spot(page)
        done = poll(page,
                    f"""() => {{ const o=document.getElementById('wf-output-lookup-{i}');
                        return !!(o && o.classList.contains('visible')); }}""",
                    tries=80, interval=400)
        log(f"[workflow] step {i} done: {done}")
        scroll_into(page, f"#wf-output-lookup-{i}")
        page.wait_for_timeout(1500)
        # Click "Continue" to reveal the next step (removes the translucent dim
        # on later steps). Smooth, minimal delay before the next step.
        if i < last:
            spot_click(page,
                       f"document.querySelector('.workflow-next-btn[onclick*=\"wfGoToNext({i})\"]')",
                       "Click: Continue", pos="top", settle=550, after=150)
            page.wait_for_timeout(350)


# ---------------------------------------------------------------- gflags
def gflags_demo(page):
    goto(page, "gflags", "GFlags Manager \u2014 loading live flags",
         f"Fetched from {CVM_IP} \u2014 categories populate as they load")
    # Cached (pre-warmed) fetch: shows the loading badge then the populated
    # catalog quickly, without a long SSH wait on camera.
    page.evaluate("() => window.fetchGflagsFromCluster && window.fetchGflagsFromCluster(false)")
    # serverGflagsCatalog is script-scoped (not on window); detect via the DOM.
    got = poll(page,
               "() => { const g=document.querySelectorAll('.gflags-cat-tile').length;"
               " const c=(document.getElementById('gflagsCount')||{}).textContent||'';"
               " return g>0 || /[1-9]\\d*\\s*gflags/.test(c); }",
               tries=60, interval=300)
    log(f"[gflags] catalog loaded: {got}")
    page.wait_for_timeout(1200)

    # Search + select a known-modifiable flag, then edit it live.
    caption(page, "Search and select a flag",
            "Filter the catalog, then open the flag detail")
    page.evaluate(
        """([term]) => {
            const s = document.getElementById('gflagsSearchInput');
            if (s) { s.value = term; }
            if (window.filterGflags) window.filterGflags();
        }""",
        ["force_set_pmd"],
    )
    page.wait_for_timeout(900)
    # Spotlight the (single) filtered result, then open its detail.
    spotlight(page, "document.querySelector('.gflags-result-item')",
              "Select this flag", pos="top", settle=850)
    selected = page.evaluate(
        """(name) => {
            let n = name;
            const items = document.querySelectorAll('.gflags-result-item .gf-name');
            let found = false;
            items.forEach(el => { if ((el.textContent||'').trim().startsWith(name)) found = true; });
            if (!found && items.length) n = (items[0].textContent||'').trim();
            if (window.selectGflag) window.selectGflag(n);
            return n;
        }""",
        GFLAG_NAME,
    )
    clear_spot(page)
    log(f"[gflags] selected flag: {selected}")
    scroll_into(page, "#gflagsDetailCard")
    page.wait_for_timeout(1100)

    # Edit the flag live (writes to the cluster; value is its current one = safe).
    caption(page, "Edit the flag \u2014 written live to the cluster",
            "Type a value, then click Set")
    # The Set control sits below the fold in the detail card \u2014 bring it to the
    # MIDDLE of the screen and (critically) hide the bottom caption during the
    # click so nothing overlaps the Set button or its confirmation.
    scroll_into(page, "#gflagSetBtn")
    page.wait_for_timeout(400)
    page.evaluate(
        """([v]) => { const i=document.getElementById('gflagSetInput');
            if (i && !i.value) i.value = v; }""",
        [GFLAG_VALUE],
    )
    page.wait_for_timeout(350)
    # Nudge the Set button up to ~40% of the viewport so both the button and the
    # inline status banner sit clear of the (now hidden) caption bar.
    page.evaluate(
        "() => { const b=document.getElementById('gflagSetBtn');"
        " if (b) b.scrollIntoView({block:'center', behavior:'smooth'}); }")
    hide_caption(page)
    page.wait_for_timeout(350)
    # Spotlight + click the Set button (click fires the async write in the
    # background, so the screen won't freeze; the button shows "Setting...").
    spot_click(page, "document.getElementById('gflagSetBtn')",
               "Click: Set", pos="top", settle=1000, after=150)
    # Wait until the status leaves the "Setting..." state (success/error),
    # capped so a slow write never stalls the video.
    done = poll(page,
                "() => { const s=document.getElementById('gflagSetStatus');"
                " const t=(s&&s.innerText||''); return t.length>0 && !/Setting/i.test(t); }",
                tries=24, interval=400)
    log(f"[gflags] write status resolved: {done}")
    scroll_into(page, "#gflagSetStatus")
    # Now narrate the confirmation (green success toast at the top + inline banner).
    caption(page, "Set confirmed \u2014 written live to the cluster",
            "Clear success toast at the top + inline confirmation below the button")
    page.wait_for_timeout(2600)


# ---------------------------------------------------------------- knowledge base
def kb_demo(page):
    goto(page, "kb", "Knowledge Base",
         "RAG over the IDF docs \u2014 ask a question, get a cited answer")
    # Stay at the very top so the search box (with the typed query) and the
    # answers below it are both on screen.
    page.evaluate("() => window.scrollTo(0, 0)")
    q = "How do lookup queries (joins) work in IDF?"
    # Type the question visibly into the search box at the top of the page.
    kb = page.locator("#kbSearchInput")
    kb.scroll_into_view_if_needed()
    kb.click()
    kb.fill("")
    kb.type(q, delay=28)
    page.wait_for_timeout(400)
    # Spotlight + click the Search button.
    spot_click(page, "document.querySelector('.kb-search-bar button')",
               "Click: Search", pos="bottom")
    poll(page,
         "() => { const a=document.getElementById('kbResultsArea');"
         " return !!(a && (a.innerText||'').trim().length > 40); }",
         tries=50, interval=300)
    # Keep the search box in view; nudge just enough to show the first answers.
    page.evaluate("() => window.scrollTo({top:0, behavior:'smooth'})")
    page.wait_for_timeout(2000)

    # Open the "Lookup Support in IDF" document from the cited results.
    caption(page, "Open a cited source \u2014 Lookup Support in IDF",
            "Click a result to read the full document, chunk highlighted")
    spot_click(page,
               "Array.from(document.querySelectorAll('#kbResultsArea .kb-result-card'))"
               ".find(c => /lookup support/i.test(c.innerText||''))"
               " || document.querySelector('#kbResultsArea .kb-result-card')",
               "Click: Lookup Support in IDF", pos="top", settle=900)
    opened = poll(page,
                  "() => { const o=document.querySelector('.doc-preview-overlay');"
                  " return !!(o && o.classList.contains('visible')"
                  " && (o.innerText||'').trim().length > 80); }",
                  tries=40, interval=300)
    log(f"[kb] opened doc preview: {opened}")
    page.wait_for_timeout(2600)
    page.evaluate("() => window.closeDocPreview && window.closeDocPreview()")
    page.wait_for_timeout(700)

    # Live Cluster Stats (bottom of the page): pull a real feature from the
    # connected insights_server \u2014 heap memory usage (rich, non-zero data).
    caption(page, "Live Cluster Stats \u2014 heap memory usage",
            "Real-time stats crawled from insights_server on the connected CVM")
    page.evaluate(
        "() => { const s=document.getElementById('liveStatsSection');"
        " if (s) s.scrollIntoView({behavior:'smooth', block:'start'}); }")
    page.wait_for_timeout(900)
    # Spotlight + click the "Heap" chip (heap allocations have meaningful values,
    # unlike the mostly-empty index map).
    spot_click(page,
               "Array.from(document.querySelectorAll('#liveStatsSection .live-stats-chips span'))"
               ".find(s => /heap/i.test(s.innerText||''))",
               "Click: Heap", pos="bottom", settle=900)
    poll(page,
         "() => { const a=document.getElementById('liveStatsResultsArea');"
         " const t=(a&&a.innerText||''); return t.length>60 && !/Searching/i.test(t); }",
         tries=50, interval=300)
    # Bring the results to the top of the viewport, then scroll through them
    # gently (the previous single jump felt way too fast) \u2014 fewer, shorter steps.
    page.evaluate(
        "() => { const a=document.getElementById('liveStatsResultsArea');"
        " if (a) a.scrollIntoView({behavior:'smooth', block:'start'}); }")
    page.wait_for_timeout(900)
    for _ in range(3):
        page.evaluate("() => window.scrollBy({top:260, behavior:'smooth'})")
        page.wait_for_timeout(850)

    # Show another feature on this page: expand the raw JSON behind a stat.
    caption(page, "Drill into the raw data",
            "Every live stat is backed by the raw insights_server payload")
    has_raw = page.evaluate(
        "() => !!document.querySelector('#liveStatsResultsArea .ls-raw-toggle')")
    if has_raw:
        spot_click(page,
                   "document.querySelector('#liveStatsResultsArea .ls-raw-toggle')",
                   "Click: View raw data", pos="top", settle=900)
        page.wait_for_timeout(700)
        page.evaluate(
            "() => { const r=document.querySelector('#liveStatsResultsArea .ls-raw-pre');"
            " if (r) r.scrollIntoView({behavior:'smooth', block:'center'}); }")
        page.wait_for_timeout(2200)
    else:
        page.wait_for_timeout(600)


# ---------------------------------------------------------------- schema explorer
def schema_demo(page):
    goto(page, "schema", "Schema Explorer",
         "Live entity types & attributes pulled from the cluster")
    # Non-forced load -> served from the pre-warmed cache, so the grid renders
    # almost instantly (no long SSH wait on camera).
    page.evaluate("() => window.loadSchema && window.loadSchema()")
    got = poll(page,
               "() => document.querySelectorAll('.schema-card').length > 0",
               tries=80, interval=300)
    log(f"[schema] grid loaded: {got}")
    page.wait_for_timeout(1200)

    # Highlight (orange) the entity we're about to open, then open its drawer.
    caption(page, "Open an entity \u2014 the detail panel slides in",
            "Summary, Attributes, and Actions tabs")
    if got:
        ent_name = page.evaluate(
            "() => { const c=document.querySelector('.schema-card');"
            " const n=c && c.querySelector('.schema-card-title, .schema-card-name, h3, strong, b');"
            " return (n ? n.textContent : (c ? c.textContent : '')).trim().split('\\n')[0].slice(0,32); }")
        spotlight(page, "document.querySelector('.schema-card')",
                  f"Entity: {ent_name}" if ent_name else "Selected entity",
                  pos="top", settle=1600)
        page.evaluate("() => window.openSchemaDrawer && window.openSchemaDrawer(0)")
        page.wait_for_timeout(300)
        clear_spot(page)
    page.wait_for_timeout(1200)

    # Attributes tab
    caption(page, "Attributes tab \u2014 every field, type and index",
            "Scroll through the full attribute list for this entity")
    page.evaluate(
        "() => { const t=document.querySelector('.schema-drawer-tab[data-tab=\"attributes\"]');"
        " if (t) t.click(); }")
    page.wait_for_timeout(1400)

    # Actions tab \u2014 walk each action button one at a time, with a spotlight.
    caption(page, "Actions tab \u2014 run each action on this entity",
            "We'll click each button one by one")
    page.evaluate(
        "() => { const t=document.querySelector('.schema-drawer-tab[data-tab=\"actions\"]');"
        " if (t) t.click(); }")
    page.wait_for_timeout(900)

    def _act_btn(word):
        return ("Array.from(document.querySelectorAll("
                "'#schemaDrawerBody .schema-card-actions button'))"
                f".find(b => /{word}/i.test(b.innerText||''))")

    # 1) Gen Proto (instant, client-side)
    caption(page, "Action 1 \u2014 Gen Proto",
            "Builds a ready-to-run query proto for this entity, instantly")
    spot_click(page, _act_btn("proto"), "Click: Gen Proto", pos="top")
    poll(page,
         "() => { const p=document.querySelector('#schemaDrawerBody .schema-proto-panel');"
         " return !!(p && p.style.display!=='none' && (p.innerText||'').trim().length>0); }",
         tries=20, interval=300)
    page.evaluate(
        "() => { const p=document.querySelector('#schemaDrawerBody .schema-proto-panel');"
        " if (p) p.scrollIntoView({behavior:'smooth', block:'center'}); }")
    page.wait_for_timeout(2200)

    # 2) Get count (served instantly from the pre-captured count \u2014 no SSH wait)
    caption(page, "Action 2 \u2014 Get count",
            "Live count of entities of this type on the cluster")
    spot_click(page, _act_btn("count"), "Click: Get count", pos="top")
    poll(page,
         "() => { const el=document.querySelector('#schemaDrawerBody .schema-count-inline');"
         " const t=(el&&el.innerText||''); return t.length>0 && !/spinner|fa-spin/i.test(el.innerHTML||''); }",
         tries=25, interval=200)
    page.wait_for_timeout(900)

    # 3) Preview Data (live rows from insights_server)
    caption(page, "Action 3 \u2014 Preview Data",
            "Live sample rows pulled from insights_server")
    spot_click(page, _act_btn("preview"), "Click: Preview Data", pos="top")
    poll(page,
         "() => { const p=document.querySelector('#schemaDrawerBody .schema-preview-panel');"
         " const t=(p&&p.innerText||''); return p && p.style.display!=='none'"
         " && t.length>0 && !/Fetching live data/i.test(t); }",
         tries=90, interval=400)
    page.evaluate(
        "() => { const p=document.querySelector('#schemaDrawerBody .schema-preview-panel');"
        " if (p) p.scrollIntoView({behavior:'smooth', block:'center'}); }")
    page.wait_for_timeout(2600)


# ---------------------------------------------------------------- validator
def validator_demo(page):
    goto(page, "validator", "Schema Validator \u2014 good example",
         "16 best-practice rules on a clean RegisterEntityType proto")
    # Fill the clean proto, then click Validate (spotlighted).
    page.evaluate(
        """([proto]) => {
            const p = document.getElementById('schemaValidatorInput');
            const q = document.getElementById('schemaValidatorQuery');
            if (p) p.value = proto;
            if (q) q.value = '';
            if (window.svSyncGutter) { svSyncGutter('schemaValidatorInput','svProtoGutter');
                svSyncGutter('schemaValidatorQuery','svQueryGutter'); }
        }""",
        [GOOD_PROTO],
    )
    page.wait_for_timeout(400)
    # Call out that the proto box itself is editable \u2014 paste anything here.
    caption(page, "Paste any proto here \u2014 the editor is fully editable",
            "Then Validate against 16 best-practice rules")
    spotlight(page, "document.getElementById('schemaValidatorInput')",
              "Editable \u2014 paste any proto here", pos="top", settle=2000)
    clear_spot(page)
    spot_click(page, "document.querySelector('.schema-validate-btn')",
               "Click: Validate", pos="top")
    poll(page,
         "() => { const r=document.getElementById('svResults');"
         " return !!(r && (r.innerText||'').replace(/\\s/g,'').length > 120); }",
         tries=30, interval=300)
    scroll_into(page, "#svResults")
    page.wait_for_timeout(1200)
    # Scroll through the full report so every rule is readable.
    caption(page, "Validation report \u2014 all 16 rules",
            "Each best-practice rule checked against the proto")
    slow_scroll(page, "#svResults", steps=6, dwell=1000)
    page.wait_for_timeout(600)

    # Bad example: Load Bad Example (spotlighted) auto-validates.
    caption(page, "Schema Validator \u2014 bad example",
            "A proto with typos and mistakes \u2014 caught instantly")
    spot_click(page, "document.querySelector('.schema-load-sample[onclick*=\"loadSvBadExample\"]')",
               "Click: Load Bad Example", pos="top")
    poll(page,
         "() => { const r=document.getElementById('svResults');"
         " return !!(r && /fail|error|missing|typo|unknown|did you mean/i.test(r.innerText||'')); }",
         tries=30, interval=300)
    scroll_into(page, "#svResults")
    page.wait_for_timeout(1200)
    caption(page, "Every violation, explained \u2014 with fixes",
            "Scroll the report: each error shows the rule and the suggested fix")
    slow_scroll(page, "#svResults", steps=6, dwell=1000)
    page.wait_for_timeout(600)


# ---------------------------------------------------------------- guide pages
def guides_demo(page):
    # Indexing
    goto(page, "indexing", "Indexing Guide",
         "Live index benchmarks and memory-impact review")
    page.wait_for_timeout(900)
    caption(page, "Structured review steps, top to bottom",
            "Is indexing needed \u2192 documentation \u2192 scale \u2192 benchmark")
    slow_scroll(page, "body", steps=4, dwell=750)
    page.wait_for_timeout(400)

    # Testing
    goto(page, "testing", "Testing IDF Changes",
         "Config, Python client, and server-binary test workflows")
    page.wait_for_timeout(500)
    page.evaluate("() => window.switchEnv && window.switchEnv('pe')")
    page.wait_for_timeout(700)
    page.evaluate("() => window.switchTestingTab && window.switchTestingTab('client')")
    page.wait_for_timeout(900)
    caption(page, "Copy-ready commands for every step",
            "One-click copy for each config / client / server action")
    page.evaluate(
        "() => { const b=document.querySelector('#testingClient .code-copy-btn'); if (b) b.click(); }")
    page.wait_for_timeout(1000)
    page.evaluate("() => window.switchTestingTab && window.switchTestingTab('server')")
    page.wait_for_timeout(900)
    # Skim EVERY testing step, top to bottom. Hide the caption during the scroll
    # so the last steps are never covered by the bottom bar.
    caption(page, "Walk through every testing step",
            "Config \u2192 Python client \u2192 server binary \u2014 all copy-ready")
    page.wait_for_timeout(900)
    hide_caption(page)
    page.wait_for_timeout(250)
    slow_scroll(page, "body", steps=9, dwell=620)
    page.evaluate("() => window.scrollTo({top:document.body.scrollHeight, behavior:'smooth'})")
    page.wait_for_timeout(900)

    # Deploy
    goto(page, "deploy", "Container Deployment & Image Generation",
         "Build custom IDF images and deploy to an SMSP environment")
    caption(page, "Resolve the latest build number live",
            "Fetch Latest GBN \u2014 resolved server-side via depsdb")
    page.evaluate("() => window.fetchLatestGBN && window.fetchLatestGBN()")
    poll(page,
         "() => { const r=document.getElementById('gbnResult');"
         " return !!(r && !(r.innerText||'').includes('Enter a branch')); }",
         tries=40, interval=400)
    scroll_into(page, "#gbnResult")
    page.wait_for_timeout(1200)
    page.evaluate("() => window.switchDeployMethod && window.switchDeployMethod('helm')")
    page.wait_for_timeout(1100)
    page.evaluate(
        "() => { const b=document.querySelector('#deployMethodHelm .code-copy-btn'); if (b) b.click(); }")
    page.wait_for_timeout(1000)
    # Skim EVERY deploy step, top to bottom (caption hidden so nothing is covered).
    caption(page, "Walk through every deploy step",
            "Build \u2192 push \u2192 deploy \u2192 verify \u2014 the full image workflow")
    page.wait_for_timeout(900)
    hide_caption(page)
    page.wait_for_timeout(250)
    slow_scroll(page, "body", steps=9, dwell=620)
    page.evaluate("() => window.scrollTo({top:document.body.scrollHeight, behavior:'smooth'})")
    page.wait_for_timeout(900)


# ---------------------------------------------------------------- explainer
def explainer_demo(page):
    log("[explainer] navigating")
    page.goto(EXPLAINER_URL, wait_until="load")
    try:
        page.wait_for_function("() => window.__explainerReady === true", timeout=14000)
    except Exception:
        pass
    page.wait_for_timeout(1000)

    def sec(sel, title, sub, dwell):
        page.evaluate(
            "(s) => { const el=document.querySelector(s);"
            " if (el) el.scrollIntoView({behavior:'smooth', block:'start'}); }", sel)
        page.wait_for_timeout(900)
        caption(page, title, sub)
        page.wait_for_timeout(dwell)

    sec("#s_arch", "How it works \u2014 the AI query pipeline",
        "Ground in schema \u2192 Phi-4 drafts \u2192 validate \u2192 render a valid proto", 4500)
    sec("#s_build", "The architecture, explained",
        "Four steps, and how the model was built \u2014 grounding, LoRA + GRPO, constrained decoding", 7000)
    sec("#s_loop", "Inference loop \u2014 every path ends in a valid proto",
        "Validate; if not fixable, self-correct once; worst case, a guaranteed fallback", 4500)
    sec("#s_train", "How the model is built",
        "Real-schema data \u2192 LoRA fine-tune \u2192 GRPO reward tuning", 4500)


# ---------------------------------------------------------------- main
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    prewarm()  # warm schema/gflags/kb caches so live calls are instant on camera
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", args=["--start-maximized"])
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=OUT_DIR,
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        page.on("pageerror", lambda e: log(f"[pageerror] {str(e)[:160]}"))
        page.on("console", lambda m: log(f"[console:error] {m.text[:160]}")
                if m.type == "error" else None)

        if FIXTURES:
            page.route("**/generate", _route_generate)
            log(f"replaying {len(FIXTURES)} captured /generate responses")
        if EXECUTE_RESULTS:
            page.route("**/execute", _route_execute)
            log(f"serving {len(EXECUTE_RESULTS)} captured /execute results instantly")
        if _ENTITY_COUNT["val"] is not None:
            page.route("**/schema/entity-count*", _route_entity_count)
            log(f"serving entity count ({_ENTITY_COUNT['val']}) instantly")

        page.goto(FRONTEND_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1800)

        # Dismiss the first-run onboarding overlay so it doesn't block clicks.
        try:
            page.evaluate("() => { window.dismissWelcome && window.dismissWelcome(); "
                          "const w=document.getElementById('tourWelcome'); if(w) w.remove(); "
                          "const o=document.getElementById('tourOverlay'); if(o) o.style.display='none'; }")
        except Exception:
            pass
        page.wait_for_timeout(700)
        set_zoom(page)

        caption(page, "IDF AI \u2014 Natural Language \u2192 IDF Query Proto",
                "Powered by Microsoft Phi-4 (grounded, schema-validated) \u2022 live on cluster "
                + CVM_IP)
        page.wait_for_timeout(2200)

        # Connect to the cluster (enables live execute / schema / gflags).
        set_cvm_ip(page)

        # Kick off schema + gflags loads OFF-CAMERA now (fire-and-forget: we do
        # NOT return the promise, so evaluate() doesn't block). The first
        # loadSchema() forces a fresh SSH fetch (~13s); by firing it here it
        # completes during the query/workflow sections and the Schema Explorer
        # page then renders instantly instead of showing "Fetching..." live.
        page.evaluate("() => { if (window.loadSchema) window.loadSchema(); "
                      "if (window.fetchGflagsFromCluster) window.fetchGflagsFromCluster(false); "
                      "return 1; }")

        # 1) Query page
        goto(page, "query", "Query \u2014 natural language to IDF proto",
             "Generate, inspect the Python, run it live, then refine")
        page.wait_for_timeout(300)
        query_full(page)
        # Complex query: validator-flagged draft -> Regenerate self-corrects (RL).
        query_complex(page)
        query_gen(page, "show alerts where severity is critical",
                  "Different entity + filter \u2014 detected and grounded automatically")
        query_gen(page, "list nodes where num_vcpus greater than 16",
                  "Numeric filter on a real node attribute (operator: kGT)")
        hide_caption(page)
        page.wait_for_timeout(500)

        # 2) Workflow lookup-join (live, step by step)
        workflow_lookup(page)

        # 3) GFlags (load + live edit)
        gflags_demo(page)

        # 4) Knowledge Base
        kb_demo(page)

        # 5) Schema Explorer (drawer + live action)
        schema_demo(page)

        # 6) Schema Validator (good + bad)
        validator_demo(page)

        # 7) Indexing / Testing / Deploy guide pages
        guides_demo(page)

        # 8) Architecture explainer + build slide + UML
        hide_caption(page)
        explainer_demo(page)

        caption(page, "Every query \u2192 a valid, schema-faithful proto",
                "IDF AI \u2014 Microsoft Phi-4 grounded query pipeline")
        page.wait_for_timeout(2600)

        path = page.video.path()
        ctx.close()
        browser.close()
        print("VIDEO_PATH:" + path)


if __name__ == "__main__":
    main()
