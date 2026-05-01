"""Shared AI 10-day SPY forecast view — used by spy_dashboard and spy_gap_table."""

from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

from stockiq.backend.services.ai_forecast_service import (
    get_ai_forecast,
    get_app_key,
    get_market_status,
    get_providers,
)


def _share_url(path: str) -> str:
    try:
        import urllib.parse
        parsed = urllib.parse.urlparse(st.context.url)
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    except Exception:
        return path


def _personal_key_input(provider: str) -> str:
    """Render a personal API key input. Returns the key if entered, else empty string."""
    prov_info   = get_providers()[provider]
    session_key = f"personal_api_key_{provider}"
    input_key   = f"personal_key_input_{provider}"

    with st.expander("🔑 Use your own API key (optional — your key stays private)", expanded=False):
        st.markdown("""
<div style="
    background:#0F2A1A;
    border:1px solid #16A34A;
    border-radius:8px;
    padding:12px 16px;
    margin-bottom:14px;
    font-size:0.875rem;
    color:#86EFAC;
    line-height:1.6;
">
🛡️ <strong>Your key is 100% private to your session</strong><br>
It is stored only in your browser's session memory, <em>never</em> sent to our servers,
never logged, and is automatically deleted the moment you close or refresh this tab.
No other user can see or use your key.
</div>
""", unsafe_allow_html=True)

        user_key = st.text_input(
            label=prov_info["env_var"],
            type="password",
            placeholder=f"Paste your {prov_info['label']} key here…",
            key=input_key,
            help=f"Get a free key at: {_key_signup_url(provider)}",
        )

        if user_key:
            st.session_state[session_key] = user_key
            st.success(
                "✓ Your personal key is active for this session only. "
                "It will be removed when you close this tab.",
                icon="🔒",
            )
        else:
            st.session_state.pop(session_key, None)

        st.caption(
            "Using your own key gives you a dedicated free quota and keeps shared app limits "
            "available for other users."
        )

    return st.session_state.get(session_key, "")


def _key_signup_url(provider: str) -> str:
    return {
        "groq":      "https://console.groq.com/keys",
        "deepseek":  "https://platform.deepseek.com/api_keys",
        "openai":    "https://platform.openai.com/api-keys",
        "gemini":    "https://aistudio.google.com/apikey",
        "anthropic": "https://console.anthropic.com/settings/keys",
    }.get(provider, "")


def _provider_selector() -> str:
    """Render a compact provider selector; returns the chosen provider key."""
    providers = get_providers()
    options = list(providers.keys())
    labels  = [providers[k]["label"] for k in options]

    st.markdown("**AI Provider**")
    chosen_label = st.radio(
        "AI Provider",
        labels,
        index=0,
        horizontal=True,
        label_visibility="collapsed",
        help=(
            "Free providers need their own API key — sign up takes < 1 minute.\n\n"
            "• **Groq** → groq.com/keys → set `GROQ_API_KEY`\n"
            "• **DeepSeek** → platform.deepseek.com → set `DEEPSEEK_API_KEY`\n"
            "• **Gemini** → aistudio.google.com → set `GOOGLE_API_KEY`\n"
            "• **OpenAI** → platform.openai.com → set `OPENAI_API_KEY`\n"
            "• **Claude** → console.anthropic.com → set `ANTHROPIC_API_KEY`"
        ),
    )
    idx = labels.index(chosen_label)
    return options[idx]


def render_ai_forecast(gaps_df: pd.DataFrame, quote: dict, show_share_btn: bool = True) -> None:
    """Render the AI 10-day SPY forecast table."""
    current_price = quote.get("price", 0)

    head_col, btn_col = st.columns([8, 1])
    head_col.markdown("### 🤖 SPY AI Outlook")
    if show_share_btn:
        with btn_col:
            with st.popover("🔗 Share", use_container_width=True):
                st.code(_share_url("/spy-ai-forecast"), language=None)
                st.caption("Copy the link above to share this forecast.")

    # ── Provider selector ─────────────────────────────────────────────────────
    provider  = _provider_selector()
    prov_info = get_providers()[provider]

    # ── Personal key input (always shown so users can bypass quota limits) ────
    user_key   = _personal_key_input(provider)
    active_key = user_key or get_app_key(provider)

    if not active_key:
        st.warning(
            f"No API key found for **{prov_info['label']}**. "
            f"Set `{prov_info['env_var']}` or paste your own key above.",
            icon="🔑",
        )
        st.caption(
            f"Get a free key at: [{_key_signup_url(provider)}]({_key_signup_url(provider)})"
            if prov_info["free"] else
            f"Get a key at: [{_key_signup_url(provider)}]({_key_signup_url(provider)})"
        )
        return

    et     = timezone(timedelta(hours=-4))
    now_et = datetime.now(et)

    # ── Gate: only call the API when the user explicitly requests it ──────────
    cache_key = f"{now_et.strftime('%Y-%m-%d-%H')}-{provider}"
    state_key = f"ai_forecast_{cache_key}"

    if state_key not in st.session_state:
        status = get_market_status()
        if not status["is_open"] and now_et.weekday() >= 5:
            st.info(f"Market closed (weekend). Next update at {status['next_open_str']}.", icon="🗓️")
        st.button(
            f"🤖 Generate SPY AI Outlook  ·  {prov_info['label']}",
            key="ai_forecast_btn",
            type="primary",
            help="Calls the selected AI provider — cached for 1 hour after first load",
            on_click=lambda: st.session_state.update({state_key: True}),
        )
        st.caption("Forecast is generated on demand to save API costs · cached for 1 hour once loaded")
        return

    status = get_market_status()
    market_open = status["is_open"]
    if not market_open and now_et.weekday() >= 5:
        st.info(f"Market closed (weekend). Next update at {status['next_open_str']}.", icon="🗓️")

    with st.spinner(f"Generating AI forecast via {prov_info['label']}…"):
        try:
            predictions = get_ai_forecast(gaps_df, provider=provider, user_key=user_key, cache_key=cache_key)
        except Exception as e:
            err = str(e)
            if "429" in err or "402" in err or "Payment Required" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower() or "rate" in err.lower():
                st.markdown("""
<div style="
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border: 1px solid #F59E0B;
    border-radius: 12px;
    padding: 24px 28px;
    margin: 8px 0;
    font-family: sans-serif;
">
    <div style="font-size:1.5rem; margin-bottom:8px;">⚠️ Free Tier Quota Reached</div>
    <div style="color:#CBD5E1; font-size:0.95rem; line-height:1.6; margin-bottom:16px;">
        The <strong style="color:#F8FAFC;">free API quota</strong> for this AI provider has been exhausted
        for today. StockIQ is a free, open-source tool — shared API quotas run out quickly with many users.
    </div>
    <div style="color:#94A3B8; font-size:0.9rem; line-height:1.6; margin-bottom:20px;">
        💡 <strong style="color:#F8FAFC;">Quick fix:</strong> Switch to a different provider above,
        or add your own API key to get a dedicated free quota.
    </div>
    <div style="
        background: #0F172A;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px 20px;
    ">
        <div style="font-size:1rem; font-weight:700; color:#F1C40F; margin-bottom:6px;">
            ❤️ Help keep StockIQ free for everyone
        </div>
        <div style="color:#CBD5E1; font-size:0.875rem; line-height:1.6; margin-bottom:14px;">
            Your sponsorship directly funds API costs, server capacity, and new features —
            so more traders can access professional-grade analysis without paying a subscription.
        </div>
        <a href="https://buymeacoffee.com/mamuninfo" target="_blank" rel="noopener noreferrer"
           style="
               display: inline-block;
               background: #FFDD00;
               color: #0F172A;
               font-weight: 700;
               font-size: 0.9rem;
               padding: 10px 24px;
               border-radius: 6px;
               text-decoration: none;
           ">
            ☕ Buy Me a Coffee
        </a>
    </div>
</div>
""", unsafe_allow_html=True)
            elif "401" in err or "invalid_api_key" in err or "Invalid API Key" in err or "authentication" in err.lower() or "unauthorized" in err.lower() or "API_KEY_INVALID" in err:
                # Clear the bad key from session state so the input resets
                st.session_state.pop(f"personal_api_key_{provider}", None)
                st.session_state.pop(f"personal_key_input_{provider}", None)
                source = "personal key you entered" if user_key else "app's API key"
                st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #2D1B1B 0%, #1A0F0F 100%);
    border: 1px solid #EF4444;
    border-radius: 12px;
    padding: 24px 28px;
    margin: 8px 0;
    font-family: sans-serif;
">
    <div style="font-size:1.5rem; margin-bottom:8px;">🔑 Invalid API Key</div>
    <div style="color:#FCA5A5; font-size:0.95rem; line-height:1.6; margin-bottom:16px;">
        The <strong>{source}</strong> was rejected by <strong style="color:#F8FAFC;">{prov_info['label']}</strong>.
        The key has been cleared — please double-check and try again.
    </div>
    <div style="color:#94A3B8; font-size:0.875rem; line-height:1.7;">
        Common reasons:<br>
        &nbsp;• You copied extra spaces or characters around the key<br>
        &nbsp;• The key was revoked or has not been activated yet<br>
        &nbsp;• The key belongs to a different provider than selected<br>
        &nbsp;• A free-tier key was used but billing was never enabled
    </div>
    {"" if not prov_info["free"] else f'''
    <div style="margin-top:16px;">
        <a href="{_key_signup_url(provider)}" target="_blank" rel="noopener noreferrer"
           style="
               display:inline-block;
               background:#1E40AF;
               color:#BFDBFE;
               font-weight:600;
               font-size:0.875rem;
               padding:8px 20px;
               border-radius:6px;
               text-decoration:none;
           ">
            Get a valid free key →
        </a>
    </div>
    '''}
</div>
""", unsafe_allow_html=True)
            else:
                st.error(f"AI forecast unavailable: {e}")
            return

    if not predictions:
        st.error("AI forecast returned no data.")
        return

    rows = []
    for p in predictions:
        direction = p.get("direction", "Neutral")
        dir_icon  = "▲" if direction == "Bullish" else ("▼" if direction == "Bearish" else "—")
        conf      = p.get("confidence", "Low")
        conf_icon = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(conf, "🔴")
        est       = float(p.get("est_close", current_price))
        chg       = est - current_price
        chg_p     = (chg / current_price * 100) if current_price else 0
        raw_date  = p.get("date", "")
        try:
            fmt_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%m-%d")
        except ValueError:
            fmt_date = raw_date
        rows.append({
            "Date":       fmt_date,
            "Direction":  dir_icon,
            "Est. Close": est,
            "Change":     chg,
            "Change %":   chg_p,
            "Low":        float(p.get("range_low",  est)),
            "High":       float(p.get("range_high", est)),
            "Confidence": f"{conf_icon} {conf}",
            "Signal":     p.get("reason", ""),
        })

    pred_df = pd.DataFrame(rows)

    def _color_direction(val):
        if val == "▲":
            return "color:#22C55E; font-weight:700"
        if val == "▼":
            return "color:#EF4444; font-weight:700"
        return "color:#94A3B8"

    def _color_change(val):
        if val > 0:
            return "color:#22C55E; font-weight:600"
        if val < 0:
            return "color:#EF4444; font-weight:600"
        return ""

    fmt = {
        "Est. Close": "${:.2f}",
        "Change":     lambda v: f"+${v:.2f}" if v >= 0 else f"-${abs(v):.2f}",
        "Change %":   lambda v: f"+{v:.2f}%" if v >= 0 else f"{v:.2f}%",
        "Low":        "${:.2f}",
        "High":       "${:.2f}",
    }

    st.dataframe(
        pred_df.style
            .map(_color_direction, subset=["Direction"])
            .map(_color_change,    subset=["Change", "Change %"])
            .format(fmt),
        hide_index=True,
        width="stretch",
        height=(len(pred_df) + 1) * 35 + 4,
    )

    updated_at  = now_et.strftime("%I:%M %p ET")
    next_update = (now_et + timedelta(hours=1)).strftime("%I:%M %p ET")
    model_name  = prov_info["model"]
    if market_open:
        st.caption(
            f"Model: {model_name} · Last updated: {updated_at} · "
            f"Next refresh: {next_update} · Anchor: ${current_price:.2f}"
        )
    else:
        st.caption(f"Model: {model_name} · Last updated: {updated_at} · Market closed — refreshes at next open")
