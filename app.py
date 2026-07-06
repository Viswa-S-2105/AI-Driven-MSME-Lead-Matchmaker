# =============================================================================
#  MSME EXPORT MATCHMAKER — Streamlit Web Application
#  File : app.py
#  Run  : streamlit run app.py
#
#  Dependencies (install once):
#      pip install streamlit pandas scikit-learn twilio
#
#  Before running, fill in the five credential constants below.
# =============================================================================

import random
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

import pandas as pd
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from twilio.rest import Client

# =============================================================================
#  SECTION 1 — CREDENTIALS  (provide values via environment variables)
# =============================================================================
# The application reads credentials from environment variables. For local
# development create a `.env` file (not committed) and populate the keys
# shown in `.env.example`.
GMAIL_SENDER = os.getenv("SMTP_USER") or os.getenv("GMAIL_SENDER")
GMAIL_APP_PASSWORD = os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD")

# Twilio environment variables (recommended names)
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE_NUMBER")

# =============================================================================
#  SECTION 2 — PAGE CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="MSME Export Matchmaker",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Custom CSS -------------------------------------------------------
# Aesthetic: Clean government-tech meets modern SaaS.
# Palette: Deep navy + saffron accent (Indian tricolour nod) on off-white.
# Typography: IBM Plex Sans (technical authority) + source serif for headings.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Serif:ital,wght@0,600;1,400&display=swap');

/* ── Root tokens ─────────────────────────────────────────── */
:root {
    --navy:     #0a1628;
    --navy-mid: #12284a;
    --saffron:  #FF9933;
    --green:    #138808;
    --white:    #f7f8fa;
    --muted:    #8a94a6;
    --border:   #dde3ef;
    --card-bg:  #ffffff;
    --radius:   10px;
    --shadow:   0 2px 16px rgba(10,22,40,0.10);
}

/* ── Global reset ────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--white) !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    color: var(--navy) !important;
}
[data-testid="stHeader"] { background: transparent !important; }
.block-container { padding: 2rem 3rem 4rem !important; max-width: 1080px !important; }

/* ── Hero banner ─────────────────────────────────────────── */
.hero {
    background: linear-gradient(135deg, var(--navy) 0%, var(--navy-mid) 100%);
    border-radius: var(--radius);
    padding: 2.4rem 2.8rem 2rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.hero::before {                            /* subtle diagonal stripe texture */
    content: "";
    position: absolute;
    inset: 0;
    background: repeating-linear-gradient(
        -55deg,
        transparent,
        transparent 28px,
        rgba(255,255,255,0.025) 28px,
        rgba(255,255,255,0.025) 29px
    );
}
.hero-title {
    font-family: 'IBM Plex Serif', Georgia, serif;
    font-size: 2.1rem;
    font-weight: 600;
    color: #ffffff;
    margin: 0 0 0.3rem;
    position: relative;
}
.hero-title span { color: var(--saffron); }
.hero-sub {
    font-size: 0.93rem;
    color: rgba(255,255,255,0.65);
    font-weight: 300;
    position: relative;
}
.hero-badge {
    display: inline-block;
    background: var(--saffron);
    color: var(--navy);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 3px 10px;
    border-radius: 20px;
    margin-bottom: 0.7rem;
    position: relative;
}

/* ── Section label ───────────────────────────────────────── */
.section-label {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 0.6rem;
}

/* ── Form card ───────────────────────────────────────────── */
.form-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.8rem 2rem;
    box-shadow: var(--shadow);
    margin-bottom: 1.5rem;
}

/* ── Result cards ────────────────────────────────────────── */
.result-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.4rem 1.6rem;
    box-shadow: var(--shadow);
    height: 100%;
}
.result-card h4 {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 1rem;
}
.result-card .big-label {
    font-family: 'IBM Plex Serif', serif;
    font-size: 1.55rem;
    font-weight: 600;
    color: var(--navy);
    margin: 0 0 0.2rem;
}
.category-pill {
    display: inline-block;
    background: #fff4e6;
    color: #b85c00;
    border: 1px solid #ffd199;
    border-radius: 20px;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 3px 14px;
    margin-bottom: 0.9rem;
}
.vendor-row {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    margin-bottom: 0.55rem;
    font-size: 0.88rem;
}
.vendor-row .vr-label {
    min-width: 72px;
    color: var(--muted);
    font-size: 0.78rem;
    padding-top: 1px;
}
.vendor-row .vr-val { font-weight: 500; color: var(--navy); }

/* ── Confidence bar ──────────────────────────────────────── */
.conf-wrap { margin-top: 0.8rem; }
.conf-label {
    font-size: 0.8rem;
    color: var(--muted);
    margin-bottom: 4px;
}
.conf-bar-outer {
    background: #eef0f5;
    border-radius: 6px;
    height: 10px;
    width: 100%;
    overflow: hidden;
}
.conf-bar-inner {
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, var(--green), #1db954);
    transition: width 0.6s ease;
}
.conf-pct {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--green);
    margin: 0.4rem 0 0;
}

/* ── Status blocks ───────────────────────────────────────── */
.status-row {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    background: #f0f7ff;
    border: 1px solid #c8deff;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.6rem;
    font-size: 0.87rem;
    font-weight: 500;
    color: #1a3a6e;
}
.status-row.success { background: #f0faf4; border-color: #9fe0b7; color: #1a5c35; }
.status-row.error   { background: #fff4f4; border-color: #ffb3b3; color: #7a1c1c; }

/* ── Streamlit widget overrides ──────────────────────────── */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    border: 1px solid var(--border) !important;
    border-radius: 7px !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.9rem !important;
    background: #fafbfd !important;
    color: var(--navy) !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--saffron) !important;
    box-shadow: 0 0 0 3px rgba(255,153,51,0.15) !important;
}
div[data-testid="stButton"] > button {
    background: var(--navy) !important;
    color: #ffffff !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    letter-spacing: 0.03em !important;
    border: none !important;
    border-radius: 7px !important;
    padding: 0.6rem 1.8rem !important;
    transition: background 0.2s, transform 0.1s !important;
}
div[data-testid="stButton"] > button:hover {
    background: var(--saffron) !important;
    color: var(--navy) !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stButton"] > button:active { transform: translateY(0) !important; }

label[data-testid="stWidgetLabel"] p,
div[data-testid="stWidgetLabel"] p {
    font-family: 'IBM Plex Sans', sans-serif !important;
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    color: var(--navy) !important;
    letter-spacing: 0.02em !important;
}
.stSpinner > div > div { border-top-color: var(--saffron) !important; }
footer, #MainMenu { display: none; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
#  SECTION 3 — ML ENGINE  (cached so it only trains once per session)
# =============================================================================

@st.cache_data
def load_and_train_model():
    """
    Loads both CSVs, fits a TF-IDF vectoriser, and trains a Logistic
    Regression classifier.  Decorated with @st.cache_data so Streamlit
    skips retraining on every page interaction.

    Returns
    -------
    vectorizer  : fitted TfidfVectorizer
    model       : trained LogisticRegression
    df_vendors  : pandas DataFrame of the MSME vendor registry
    """
    # Load datasets
    df_inquiries = pd.read_csv("b2b_export_inquiries.csv")
    df_vendors   = pd.read_csv("msme_vendor_registry.csv")

    # Drop rows with missing text or label (defensive)
    df_inquiries.dropna(subset=["Inquiry_Text", "Category"], inplace=True)

    # TF-IDF — bigrams + English stop-word removal + 3000 feature cap
    # ngram_range=(1,2) captures meaningful phrases like "hand carved" or
    # "cotton fabric" that single tokens miss.
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=3000,
        ngram_range=(1, 2),
        sublinear_tf=True      # log-normalise term frequencies
    )
    X = vectorizer.fit_transform(df_inquiries["Inquiry_Text"])
    y = df_inquiries["Category"]

    # Logistic Regression — reliable, fast, and produces calibrated probabilities
    model = LogisticRegression(max_iter=1000, C=5.0, random_state=42)
    model.fit(X, y)

    return vectorizer, model, df_vendors


# =============================================================================
#  SECTION 4 — API ACTION FUNCTIONS
# =============================================================================

def send_real_email(buyer_email: str, matched_vendor_name: str, category: str) -> str:
    """
    Sends a professional introduction email to the foreign buyer via Gmail SSL.

    Parameters
    ----------
    buyer_email         : Recipient email address (the foreign buyer).
    matched_vendor_name : Name of the MSME vendor assigned to the lead.
    category            : The ML-predicted product category.

    Returns
    -------
    A status string: "✅ Email sent …" or "❌ Email error: …"
    """
    subject = (
        f"Your Inquiry for {category} — "
        f"Matched with {matched_vendor_name} | IndiaExportConnect"
    )

    # Plain-text fallback
    body_plain = (
        f"Dear Buyer,\n\n"
        f"Thank you for your inquiry. We have matched your requirement "
        f"for {category} products with a verified Indian MSME exporter:\n\n"
        f"  Vendor : {matched_vendor_name}\n\n"
        f"Their export team will contact you within 2 business days with "
        f"a product catalogue and MOQ details.\n\n"
        f"Warm regards,\nIndiaExportConnect — Automated Export Liaison"
    )

    # HTML email body
    body_html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#1a1a2e;max-width:600px;margin:auto;">
      <div style="background:#0a1628;padding:28px 32px;border-radius:10px 10px 0 0;">
        <h2 style="color:#FF9933;margin:0;font-size:20px;">🇮🇳 IndiaExportConnect</h2>
        <p style="color:rgba(255,255,255,0.6);margin:6px 0 0;font-size:13px;">
          Automated Export Liaison System</p>
      </div>
      <div style="background:#ffffff;padding:32px;border:1px solid #dde3ef;
                  border-top:none;border-radius:0 0 10px 10px;">
        <p style="font-size:15px;">Dear Valued Buyer,</p>
        <p>Thank you for your export inquiry. Our AI-powered system has
           analysed your request and identified the best-matched Indian MSME
           partner for your <strong>{category}</strong> requirement:</p>
        <div style="background:#f7f8fa;border-left:4px solid #FF9933;
                    padding:16px 20px;border-radius:6px;margin:20px 0;">
          <p style="margin:0;font-size:13px;color:#8a94a6;
                    text-transform:uppercase;letter-spacing:0.1em;">
            Assigned Vendor</p>
          <p style="margin:6px 0 0;font-size:18px;font-weight:700;
                    color:#0a1628;">{matched_vendor_name}</p>
          <p style="margin:4px 0 0;font-size:13px;color:#555;">
            Category Specialist: <strong>{category}</strong></p>
        </div>
        <p>Their dedicated export manager will reach out within
           <strong>2 business days</strong> with a product catalogue,
           pricing, and minimum order quantity (MOQ) details.</p>
        <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
        <p style="font-size:12px;color:#aaa;">
          This is an automated message from IndiaExportConnect.<br>
          Connecting Global Buyers with India's Finest MSME Exporters.</p>
      </div>
    </body></html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_SENDER
        msg["To"]      = buyer_email
        msg.attach(MIMEText(body_plain, "plain"))
        msg.attach(MIMEText(body_html,  "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_SENDER, buyer_email, msg.as_string())

        return f"✅ Email successfully sent to **{buyer_email}**"

    except smtplib.SMTPAuthenticationError:
        return (
            "❌ Email error: Gmail authentication failed. "
            "Check GMAIL_SENDER and GMAIL_APP_PASSWORD."
        )
    except smtplib.SMTPException as e:
        return f"❌ Email SMTP error: {e}"
    except Exception as e:
        return f"❌ Email error: {e}"


def send_real_sms(vendor_phone: str, category: str, vendor_name: str) -> str:
    """
    Sends a short SMS alert to the matched MSME vendor via Twilio.

    Parameters
    ----------
    vendor_phone : Vendor's phone number (will be normalised to E.164).
    category     : The ML-predicted product category.
    vendor_name  : Name of the vendor (for personalised message).

    Returns
    -------
    A status string: "✅ SMS sent …" or "❌ SMS error: …"
    """
    # Normalise phone: strip spaces, ensure leading + for E.164
    phone = str(vendor_phone).strip().replace(" ", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    sms_body = (
        f"[IndiaExportConnect] Hello {vendor_name}! "
        f"A new export lead for {category} has been matched to you. "
        f"We emailed the buyer on your behalf. "
        f"Please prepare your product catalogue. "
        f"Log in to IndiaExportConnect for full details."
    )

    try:
        twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
        message = twilio_client.messages.create(
            body=sms_body,
            from_=TWILIO_PHONE,
            to=phone,
        )
        return f"✅ SMS sent to **{phone}** (SID: `{message.sid}`)"

    except Exception as e:
        return f"❌ SMS error: {e}"


# =============================================================================
#  SECTION 5 — STREAMLIT USER INTERFACE
# =============================================================================

# ── Hero banner ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-badge">🇮🇳 &nbsp;Powered by NLP + ML</div>
  <div class="hero-title">MSME Export <span>Matchmaker</span></div>
  <div class="hero-sub">
    AI-driven export lead classification &amp; automated MSME vendor assignment
    &mdash; from raw inquiry text to matched vendor in seconds.
  </div>
</div>
""", unsafe_allow_html=True)

# ── Load model (cached after first run) ───────────────────────────────────────
try:
    vectorizer, model, df_vendors = load_and_train_model()
except FileNotFoundError as e:
    st.error(
        f"**CSV not found:** {e}\n\n"
        "Ensure `b2b_export_inquiries.csv` and `msme_vendor_registry.csv` "
        "are in the same directory as `app.py`."
    )
    st.stop()

# ── Input form ────────────────────────────────────────────────────────────────
st.markdown('<div class="form-card">', unsafe_allow_html=True)
st.markdown('<p class="section-label">📥 &nbsp;New Export Lead</p>', unsafe_allow_html=True)

col_email, col_gap = st.columns([2, 1])
with col_email:
    buyer_email = st.text_input(
        "Foreign Buyer's Email Address",
        placeholder="buyer@company.com",
        help="The automated introduction email will be sent here.",
    )

inquiry_text = st.text_area(
    "Paste the Unstructured Export Inquiry",
    height=160,
    placeholder=(
        "e.g. Hello, we are a boutique in London looking to import 500 "
        "hand-carved wooden elephants and brass decorative items. "
        "Please send catalogue and price list."
    ),
    help="Raw buyer inquiry text — any length, any format.",
)

_, btn_col, _ = st.columns([3, 2, 3])
with btn_col:
    submitted = st.button("⚡ Process Lead & Auto-Match", use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)

# ── Processing & results ──────────────────────────────────────────────────────
if submitted:
    # ── Validation ────────────────────────────────────────────────────────────
    if not inquiry_text.strip():
        st.warning("⚠️ Please paste an export inquiry before submitting.")
        st.stop()
    if not buyer_email.strip():
        st.warning("⚠️ Please enter the buyer's email address.")
        st.stop()

    with st.spinner("🔍 Analysing inquiry and matching vendor …"):

        # ── ML Inference ──────────────────────────────────────────────────────
        X_new        = vectorizer.transform([inquiry_text])
        predicted    = model.predict(X_new)[0]
        proba_scores = model.predict_proba(X_new)[0]
        confidence   = float(max(proba_scores))
        class_labels = model.classes_

        # ── Vendor Matching ───────────────────────────────────────────────────
        matched_vendors = df_vendors[
            df_vendors["Category"].str.strip().str.lower()
            == predicted.strip().lower()
        ]

        if matched_vendors.empty:
            st.error(
                f"No vendors found for category **{predicted}** in the registry. "
                "Please check `msme_vendor_registry.csv`."
            )
            st.stop()

        vendor = matched_vendors.sample(n=1).iloc[0]

    # ── Results display ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<p class="section-label">📊 &nbsp;Pipeline Results</p>',
                unsafe_allow_html=True)

    col_ai, col_vendor = st.columns(2, gap="large")

    # Left card — AI Classification
    with col_ai:
        conf_pct  = int(confidence * 100)
        bar_color = "#138808" if conf_pct >= 70 else "#FF9933" if conf_pct >= 45 else "#e63946"

        # Build each category bar individually as plain strings.
        # IMPORTANT: bars_html is assembled OUTSIDE any st.markdown() f-string.
        # Nesting a variable containing HTML tags inside an f-string passed to
        # st.markdown() causes Streamlit to escape the tags and render raw HTML
        # text instead of actual elements.
        bars_html = ""
        for label, score in sorted(
            zip(class_labels, proba_scores), key=lambda x: x[1], reverse=True
        ):
            pct    = int(score * 100)
            fw     = "700" if label == predicted else "400"
            tick   = "  ✓" if label == predicted else ""
            bar_bg = "#138808" if label == predicted else "#dde3ef"
            bars_html += (
                "<div style='margin-bottom:8px;'>"
                "<div style='display:flex;justify-content:space-between;"
                "font-size:0.78rem;margin-bottom:3px;'>"
                f"<span style='color:#333;font-weight:{fw};'>{label}{tick}</span>"
                f"<span style='color:#8a94a6;'>{pct}%</span>"
                "</div>"
                "<div style='background:#eef0f5;border-radius:4px;height:7px;overflow:hidden;'>"
                f"<div style='width:{pct}%;height:100%;border-radius:4px;"
                f"background:{bar_bg};transition:width 0.4s;'></div>"
                "</div>"
                "</div>"
            )

        # Build the complete card string first, then render in a single call.
        ai_card = (
            "<div class='result-card'>"
            "<h4>🤖 &nbsp;AI Classification</h4>"
            f"<p class='big-label'>{predicted}</p>"
            f"<span class='category-pill'>📦 {predicted}</span>"
            "<div class='conf-wrap'>"
            "<p class='conf-label'>Model Confidence</p>"
            f"<p class='conf-pct' style='color:{bar_color};'>{conf_pct}%</p>"
            "</div>"
            "<div style='margin-top:1.1rem;'>"
            "<p style='font-size:0.75rem;font-weight:700;letter-spacing:0.1em;"
            "text-transform:uppercase;color:#8a94a6;margin-bottom:8px;'>"
            "All Categories</p>"
            + bars_html +
            "</div></div>"
        )
        st.markdown(ai_card, unsafe_allow_html=True)

    # Right card — Assigned Vendor
    with col_vendor:
        phone_display = str(vendor["Contact_Phone"]).strip()
        if not phone_display.startswith("+"):
            phone_display = "+" + phone_display

        email_display = (
            vendor["Contact_Email"]
            if str(vendor["Contact_Email"]).strip().upper() != "NO_EMAIL"
            else "—"
        )

        st.markdown(f"""
        <div class="result-card">
          <h4>🏭 &nbsp;Assigned MSME Vendor</h4>
          <p class="big-label">{vendor['Vendor_Name']}</p>
          <span class="category-pill">🏷️ {vendor['Category']}</span>

          <div class="vendor-row">
            <span class="vr-label">Vendor ID</span>
            <span class="vr-val">{vendor['Vendor_ID']}</span>
          </div>
          <div class="vendor-row">
            <span class="vr-label">Phone</span>
            <span class="vr-val">{phone_display}</span>
          </div>
          <div class="vendor-row">
            <span class="vr-label">Email</span>
            <span class="vr-val">{email_display}</span>
          </div>
          <div style="margin-top:1.1rem;padding:12px 14px;
                      background:#f7f8fa;border-radius:7px;
                      font-size:0.82rem;color:#555;line-height:1.55;">
            <strong>Inquiry Preview:</strong><br>
            "{inquiry_text[:160]}{'…' if len(inquiry_text) > 160 else ''}"
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Automations ───────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="section-label">🚀 &nbsp;Automation Actions</p>',
                unsafe_allow_html=True)

    col_e, col_s = st.columns(2, gap="large")

    with col_e:
        with st.spinner("📧 Sending email to buyer …"):
            email_status = send_real_email(
                buyer_email.strip(),
                vendor["Vendor_Name"],
                predicted,
            )
        css_cls = "success" if email_status.startswith("✅") else "error"
        st.markdown(
            f'<div class="status-row {css_cls}">{email_status}</div>',
            unsafe_allow_html=True,
        )

    with col_s:
        with st.spinner("📱 Sending SMS to vendor …"):
            sms_status = send_real_sms(
                str(vendor["Contact_Phone"]),
                predicted,
                vendor["Vendor_Name"],
            )
        css_cls = "success" if sms_status.startswith("✅") else "error"
        st.markdown(
            f'<div class="status-row {css_cls}">{sms_status}</div>',
            unsafe_allow_html=True,
        )

    # ── Celebration ───────────────────────────────────────────────────────────
    if email_status.startswith("✅") and sms_status.startswith("✅"):
        st.balloons()
        st.success(
            "🎉 **Pipeline complete!** "
            "The buyer has been emailed and the vendor has been notified via SMS."
        )
    else:
        st.info(
            "ℹ️ Pipeline ran with one or more errors above. "
            "Check your credentials in the CREDENTIALS section at the top of `app.py`."
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;margin-top:3rem;padding-top:1.5rem;
            border-top:1px solid #dde3ef;">
  <p style="font-size:0.78rem;color:#aab0bf;">
    MSME Export Matchmaker &nbsp;·&nbsp;
    NLP: TF-IDF + Logistic Regression &nbsp;·&nbsp;
    Automation: Gmail SMTP + Twilio SMS &nbsp;·&nbsp;
    Built with Streamlit 🇮🇳
  </p>
</div>
""", unsafe_allow_html=True)
