"""
MSME Export Lead Matchmaker — FastAPI Admin API
Train TF-IDF + Logistic Regression on inquiries; match vendors; stream logs via SSE.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import inspect
from io import StringIO
from pathlib import Path
from typing import AsyncGenerator

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from twilio.rest import Client

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

VENDOR_FILENAME = "msme_vendor_registry.csv"
INQUIRIES_FILENAME = "b2b_export_inquiries.csv"

DEFAULT_VENDOR_PATH = BASE_DIR / "msme_vendor_registry.csv"
DEFAULT_INQUIRIES_PATH = BASE_DIR / "b2b_export_inquiries.csv"
EXPANDED_INQUIRIES_PATH = BASE_DIR / "expanded_inquiries.csv"
MASTER_VENDOR_DB_PATH = BASE_DIR / "master_vendors_db.csv"
MASTER_BUYER_DB_PATH = BASE_DIR / "master_buyers_db.csv"

MASTER_BUYER_COLUMNS = [
    "Buyer_Email",
    "Company_Name",
    "Buyer_Rating",
    "Total_Reviews",
    "Payment_Delay_Flags",
    "Entity_Type",
]


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


def _is_placeholder(val: str | None) -> bool:
    if val is None or not str(val).strip():
        return True
    v = str(val).strip().lower()
    return v.startswith("your_") or v in ("dummy", "changeme", "xxx")


def train_classifier(df_inquiries: pd.DataFrame) -> tuple[TfidfVectorizer, LogisticRegression]:
    if "Inquiry_Text" not in df_inquiries.columns or "Category" not in df_inquiries.columns:
        raise ValueError("Inquiries CSV must include Inquiry_Text and Category columns.")
    df = df_inquiries.dropna(subset=["Inquiry_Text", "Category"]).copy()
    if df.empty:
        raise ValueError("No labeled rows after dropping missing Inquiry_Text or Category.")

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=5000,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(df["Inquiry_Text"].astype(str))
    y = df["Category"].astype(str)

    model = LogisticRegression(max_iter=1000, C=5.0, random_state=42)
    model.fit(X, y)
    return vectorizer, model


def send_vendor_sms_simulated(
    vendor_phone: str, category: str, vendor_name: str, buyer_country: str
) -> str:
    phone = str(vendor_phone).strip().replace(" ", "")
    if not phone.startswith("+"):
        phone = "+" + phone.lstrip("+")
    return (
        f"[SIMULATED SMS] → {phone} | {vendor_name}: "
        f"New {category} export lead from {buyer_country}. Check email for buyer intro."
    )


def send_vendor_sms_twilio(
    vendor_phone: str, category: str, vendor_name: str, buyer_country: str
) -> str:
    phone = str(vendor_phone).strip().replace(" ", "")
    if not phone.startswith("+"):
        phone = "+" + phone.lstrip("+")
        
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_num = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    # Safe English SMS (Under 122 chars) - No email mention
    body = (
        f"Hi {vendor_name}! New {category} lead "
        f"from {buyer_country}. Prepare your catalogue, "
        f"our Admin team will call you soon."
    )
    
    try:
        client = Client(sid, token)
        msg = client.messages.create(body=body, from_=from_num, to=phone)
        return f"[Twilio SMS] SID={msg.sid} → {phone}"
    except Exception as e:
        return f"⚠️ SMS Error: {str(e)}"

def send_buyer_email_simulated(
    to_email: str, vendor_name: str, category: str, buyer_country: str
) -> str:
    return (
        f"[SIMULATED EMAIL] To: {to_email} | Subject: {category} match — {vendor_name} "
        f"({buyer_country})"
    )


def send_buyer_email_smtp(
    to_email: str, vendor_name: str, category: str, buyer_country: str
) -> str:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", user)

    subject = f"Match Confirmed: Your Export Inquiry for {category} from IndiaExportConnect"
    
    # 1. Plain text fallback (for older email clients)
    plain = (
        f"Dear Buyer,\n\n"
        f"Thank you for your inquiry from {buyer_country}. "
        f"We matched your {category} requirement with verified Indian MSME: {vendor_name}.\n\n"
        f"Their team will follow up within 2 business days.\n\n"
        f"— IndiaExportConnect Team"
    )

    # 2. The Beautiful HTML Version
    html_body = f"""
    <div style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
        <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-bottom: 3px solid #ff9933;">
            <h2 style="margin: 0; color: #1a365d;">IndiaExportConnect</h2>
            <p style="margin: 5px 0 0; font-size: 14px; color: #666;">Connecting Global Buyers with Verified Indian MSMEs</p>
        </div>
        <div style="padding: 30px;">
            <p>Dear Valued Buyer,</p>
            <p>Thank you for submitting your trade inquiry from <strong>{buyer_country}</strong> through our platform. We have successfully processed your request for <strong>{category}</strong>.</p>
            
            <p>We are pleased to inform you that we have matched your requirements with a verified Indian MSME exporter. They have been notified of your interest and will be reaching out shortly.</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background-color: #ffffff;">
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #eee; width: 40%;"><strong>Matched Vendor:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">{vendor_name}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>Verified Category:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">{category}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>Buyer Location:</strong></td>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">{buyer_country}</td>
                </tr>
            </table>
            
            <p>The vendor's export manager will contact you directly within 1 to 2 business days with a detailed product catalogue, pricing, and Minimum Order Quantity (MOQ) details.</p>
            <p>If you require any specific certifications (e.g., ISO, OEKO-TEX, APEDA), please feel free to request them when the vendor connects with you.</p>
            <br>
            <p>Warm regards,</p>
            <p><strong>The IndiaExportConnect Team</strong><br>
            <a href="mailto:{from_email}" style="color: #1a365d;">{from_email}</a></p>
        </div>
        <div style="background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #888;">
            This is an automated message generated by the IndiaExportConnect Matchmaking System. Please do not reply directly to this email.
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    
    # Attach both (HTML goes last so the email client prioritizes it)
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    use_tls = os.getenv("SMTP_USE_TLS", "false").lower() in ("1", "true", "yes")
    if port == 465 and not use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.login(user, password)
            server.sendmail(from_email, to_email, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(user, password)
            server.sendmail(from_email, to_email, msg.as_string())

    return f"[SMTP] Sent intro email to {to_email}"


def notify_vendor_sms(vendor_phone: str, category: str, vendor_name: str, buyer_country: str) -> str:
    if _is_placeholder(os.getenv("TWILIO_ACCOUNT_SID")) or _is_placeholder(
        os.getenv("TWILIO_AUTH_TOKEN")
    ):
        return send_vendor_sms_simulated(vendor_phone, category, vendor_name, buyer_country)
    return send_vendor_sms_twilio(vendor_phone, category, vendor_name, buyer_country)


def notify_buyer_email(
    to_email: str, vendor_name: str, category: str, buyer_country: str
) -> str:
    if _is_placeholder(os.getenv("SMTP_USER")) or _is_placeholder(os.getenv("SMTP_PASSWORD")):
        return send_buyer_email_simulated(to_email, vendor_name, category, buyer_country)
    return send_buyer_email_smtp(to_email, vendor_name, category, buyer_country)


def resolve_data_paths() -> tuple[Path, Path]:
    v_upload = UPLOAD_DIR / VENDOR_FILENAME
    i_upload = UPLOAD_DIR / INQUIRIES_FILENAME
    vendors_path = v_upload if v_upload.exists() else DEFAULT_VENDOR_PATH
    inquiries_path = i_upload if i_upload.exists() else DEFAULT_INQUIRIES_PATH
    return vendors_path, inquiries_path


def load_training_inquiries_df() -> pd.DataFrame:
    """Prefer uploaded inquiries with Category; else fall back to bundled labeled CSV."""
    up = UPLOAD_DIR / INQUIRIES_FILENAME
    if up.exists():
        df = pd.read_csv(up)
        if "Category" in df.columns and df["Category"].notna().any():
            return df
    if DEFAULT_INQUIRIES_PATH.exists():
        return pd.read_csv(DEFAULT_INQUIRIES_PATH)
    raise FileNotFoundError(
        "No labeled inquiries for training. Upload a CSV with Inquiry_Text and Category, "
        "or keep b2b_export_inquiries.csv in the project root."
    )


def load_batch_inquiries_df() -> pd.DataFrame:
    """Rows to score and match; defaults to project CSV if none uploaded."""
    _, inquiries_path = resolve_data_paths()
    return pd.read_csv(inquiries_path)


def _normalize_vendor_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize vendor rows: inject trust columns for raw CSVs, canonicalize V-IDs, dedupe."""
    required = {"Vendor_ID", "Vendor_Name", "Category", "Contact_Email", "Contact_Phone"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"CSV must include columns: {sorted(required)}")

    had_vendor_rating_col = "Vendor_Rating" in df.columns

    normalized = df.copy()
    if "Gov_Order_Badge" in normalized.columns and "Govt_Order_Badge" not in normalized.columns:
        normalized = normalized.rename(columns={"Gov_Order_Badge": "Govt_Order_Badge"})
    if "Vendor_Rating" not in normalized.columns:
        normalized["Vendor_Rating"] = 5.0
    if "Total_Reviews" not in normalized.columns:
        normalized["Total_Reviews"] = 0
    if "Defect_Rate_Pct" not in normalized.columns:
        normalized["Defect_Rate_Pct"] = 0.0
    if "Leads_Received" not in normalized.columns:
        normalized["Leads_Received"] = 0
    if "Govt_Order_Badge" not in normalized.columns:
        normalized["Govt_Order_Badge"] = False

    normalized["Vendor_ID"] = normalized["Vendor_ID"].astype(str).str.strip()
    normalized = normalized[normalized["Vendor_ID"] != ""]
    normalized = normalized[normalized["Vendor_ID"].str.upper() != "NAN"]
    normalized["Vendor_ID"] = normalized["Vendor_ID"].map(_canonicalize_vendor_id_for_storage)
    normalized = normalized.drop_duplicates(subset=["Vendor_ID"], keep="first")

    normalized["Leads_Received"] = (
        pd.to_numeric(normalized["Leads_Received"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    normalized["Vendor_Rating"] = pd.to_numeric(normalized["Vendor_Rating"], errors="coerce")
    if not had_vendor_rating_col:
        normalized["Vendor_Rating"] = normalized["Vendor_Rating"].fillna(5.0)
    normalized["Vendor_Rating"] = normalized["Vendor_Rating"].astype(float).clip(lower=0.0, upper=5.0)

    normalized["Total_Reviews"] = (
        pd.to_numeric(normalized["Total_Reviews"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    normalized["Govt_Order_Badge"] = (
        normalized["Govt_Order_Badge"]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["1", "true", "yes", "y"])
    )

    normalized["Defect_Rate_Pct"] = (
        pd.to_numeric(normalized["Defect_Rate_Pct"], errors="coerce")
        .fillna(0.0)
        .astype(float)
        .clip(lower=0.0, upper=100.0)
    )
    return normalized


def _normalize_buyer_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    if "Buyer_Email" not in normalized.columns and "Buyer_ID" in normalized.columns:
        normalized = normalized.rename(columns={"Buyer_ID": "Buyer_Email"})

    required = {"Buyer_Email", "Company_Name"}
    if not required.issubset(set(normalized.columns)):
        raise ValueError(f"Buyer DB must include columns: {sorted(required)}")

    had_buyer_rating_col = "Buyer_Rating" in normalized.columns

    normalized["Buyer_Email"] = normalized["Buyer_Email"].astype(str).str.strip()
    normalized = normalized[normalized["Buyer_Email"] != ""]
    normalized["Company_Name"] = normalized["Company_Name"].astype(str).str.strip()

    if "Buyer_Rating" not in normalized.columns:
        normalized["Buyer_Rating"] = 5.0
    if "Total_Reviews" not in normalized.columns:
        normalized["Total_Reviews"] = 0
    if "Payment_Delay_Flags" not in normalized.columns:
        normalized["Payment_Delay_Flags"] = 0

    normalized["Buyer_Rating"] = pd.to_numeric(normalized["Buyer_Rating"], errors="coerce")
    if not had_buyer_rating_col:
        normalized["Buyer_Rating"] = normalized["Buyer_Rating"].fillna(5.0)
    normalized["Buyer_Rating"] = normalized["Buyer_Rating"].astype(float)

    normalized["Total_Reviews"] = (
        pd.to_numeric(normalized["Total_Reviews"], errors="coerce")
        .fillna(0)
        .astype(int)
    )

    normalized["Payment_Delay_Flags"] = (
        pd.to_numeric(normalized["Payment_Delay_Flags"], errors="coerce")
        .fillna(0)
        .astype(int)
        .clip(lower=0)
    )

    if "Entity_Type" not in normalized.columns:
        normalized["Entity_Type"] = "Private"
    et = normalized["Entity_Type"].astype(str).str.strip()
    et = et.mask(et.str.len() == 0, "Private")
    et = et.mask(et.str.lower().isin(["nan", "none", "nat"]), "Private")
    normalized["Entity_Type"] = et

    normalized = normalized[MASTER_BUYER_COLUMNS]
    return normalized


def ensure_master_buyer_db() -> None:
    if MASTER_BUYER_DB_PATH.exists():
        return
    pd.DataFrame(columns=MASTER_BUYER_COLUMNS).to_csv(MASTER_BUYER_DB_PATH, index=False)


def save_master_buyer_db(df: pd.DataFrame) -> None:
    tmp_path = MASTER_BUYER_DB_PATH.with_suffix(".csv.tmp")
    try:
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, MASTER_BUYER_DB_PATH)
    except PermissionError as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise PermissionError(
            "master_buyers_db.csv is locked by another app. "
            "Close Excel/Sheets/file viewer and try again."
        ) from e
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise


def read_expanded_inquiries_entity_map() -> dict[str, str]:
    """
    Load Buyer_Email -> Entity_Type from expanded_inquiries.csv (lowercase email keys).
    Returns {} if file missing or required columns absent.
    """
    if not EXPANDED_INQUIRIES_PATH.exists() or os.path.getsize(EXPANDED_INQUIRIES_PATH) == 0:
        return {}
    try:
        exp = pd.read_csv(EXPANDED_INQUIRIES_PATH)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, Exception):
        return {}
    exp.columns = [str(c).replace("\ufeff", "").strip() for c in exp.columns]
    key_map = {_normalize_header_key(c): c for c in exp.columns}
    em_col = (
        key_map.get("buyer_email")
        or key_map.get("email")
        or key_map.get("email_address")
        or key_map.get("buyer_e_mail")
    )
    et_col = key_map.get("entity_type") or key_map.get("entity") or key_map.get("buyer_entity_type")
    if not em_col or not et_col:
        return {}
    out: dict[str, str] = {}
    for _, row in exp.iterrows():
        raw_em = row.get(em_col, "")
        if raw_em is None or (isinstance(raw_em, float) and pd.isna(raw_em)):
            continue
        em = str(raw_em).strip().lower()
        if not em or "@" not in em:
            continue
        et_raw = row.get(et_col, "")
        et = str(et_raw).strip() if pd.notna(et_raw) else ""
        if et.lower() in ("nan", "none", ""):
            et = "Private"
        out[em] = et
    return out


def merge_buyer_entity_types_from_expanded_inquiries(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Entity_Type from expanded_inquiries.csv onto a buyer dataframe (by email)."""
    mapping = read_expanded_inquiries_entity_map()
    if not mapping or df is None or df.empty:
        return df
    out = df.copy()
    if "Entity_Type" not in out.columns:
        out["Entity_Type"] = "Private"
    em_lower = out["Buyer_Email"].astype(str).str.strip().str.lower()
    mapped = em_lower.map(lambda e: mapping.get(e))
    out["Entity_Type"] = mapped.where(mapped.notna(), out["Entity_Type"])
    out["Entity_Type"] = out["Entity_Type"].astype(str).str.strip()
    out["Entity_Type"] = out["Entity_Type"].mask(out["Entity_Type"].str.len() == 0, "Private")
    return out


def buyer_entity_is_government_buyer(entity_type: str) -> bool:
    """True when buyer is treated as government/public-sector for vendor badge rules."""
    et = str(entity_type or "").strip().lower()
    return et in ("government", "public")


def buyer_entity_is_government_audit(entity_type: str) -> bool:
    """Alias for JSON / audit flags (Government or Public)."""
    return buyer_entity_is_government_buyer(entity_type)


def _gov_badge_transaction_success(extracted: dict) -> bool:
    """Success for Gov badge: defect rate under 2% and no payment delay."""
    defect = float(extracted.get("Defect_Rate") or 0)
    if defect >= 2.0:
        return False
    dd = extracted.get("Delay_Days")
    if dd is not None and int(float(dd)) != 0:
        return False
    if bool(extracted.get("Payment_Delayed")):
        return False
    return True


def _award_vendor_govt_order_badge_if_eligible(
    vendors_df: pd.DataFrame,
    extracted: dict,
    *,
    is_government_buyer: bool,
) -> bool:
    """
    If buyer is Government/Public and transaction meets success criteria, set Govt_Order_Badge on vendor.
    Returns True if the vendor newly received the badge (was False before).
    """
    if not is_government_buyer or not _gov_badge_transaction_success(extracted):
        return False
    v_ser = _vendor_serial(str(extracted.get("Vendor_ID", "")))
    if v_ser is None:
        return False
    vmask = vendors_df["Vendor_ID"].astype(str).map(_vendor_serial) == v_ser
    if not vmask.any():
        return False
    if "Govt_Order_Badge" not in vendors_df.columns:
        vendors_df["Govt_Order_Badge"] = False
    prev = bool(vendors_df.loc[vmask, "Govt_Order_Badge"].iloc[0])
    vendors_df.loc[vmask, "Govt_Order_Badge"] = True
    return not prev


def buyer_entity_shows_directory_government_badge(entity_type: str) -> bool:
    """Directory badge: any entity except Private (empty treated as Private)."""
    et = str(entity_type or "").strip()
    if not et or et.lower() in ("nan", "none"):
        return False
    return et.strip().lower() != "private"


def upsert_master_buyer_db_from_inquiries(df_inquiries: pd.DataFrame) -> tuple[int, int]:
    required = {"Buyer_Email", "Company_Name"}
    if not required.issubset(set(df_inquiries.columns)):
        raise ValueError(
            "Inquiries CSV must include Buyer_Email and Company_Name columns for buyer-profile ETL."
        )

    ensure_master_buyer_db()
    try:
        if MASTER_BUYER_DB_PATH.exists() and os.path.getsize(MASTER_BUYER_DB_PATH) > 0:
            master_df = pd.read_csv(MASTER_BUYER_DB_PATH)
        else:
            master_df = pd.DataFrame(columns=MASTER_BUYER_COLUMNS)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        master_df = pd.DataFrame(columns=MASTER_BUYER_COLUMNS)

    master_df = _normalize_buyer_df(master_df)

    incoming = df_inquiries[["Buyer_Email", "Company_Name"]].copy()
    incoming["Buyer_Email"] = incoming["Buyer_Email"].astype(str).str.strip()
    incoming["Company_Name"] = incoming["Company_Name"].astype(str).str.strip()
    incoming = incoming[incoming["Buyer_Email"] != ""]
    incoming = incoming.drop_duplicates(subset=["Buyer_Email"], keep="first")

    existing_emails = set(master_df["Buyer_Email"].astype(str).str.strip().str.lower())
    new_buyers = incoming[~incoming["Buyer_Email"].str.lower().isin(existing_emails)].copy()

    if not new_buyers.empty:
        new_buyers["Buyer_Rating"] = pd.NA
        new_buyers["Total_Reviews"] = 0
        new_buyers["Payment_Delay_Flags"] = 0
        new_buyers["Entity_Type"] = "Private"
        new_buyers = new_buyers[MASTER_BUYER_COLUMNS]
        updated = pd.concat([master_df, new_buyers], ignore_index=True)
    else:
        updated = master_df

    updated = updated.drop_duplicates(subset=["Buyer_Email"], keep="first")
    updated = merge_buyer_entity_types_from_expanded_inquiries(updated)
    updated = _normalize_buyer_df(updated)
    save_master_buyer_db(updated)
    return len(new_buyers), len(updated)


def upsert_master_vendor_db(new_vendors_df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Merge uploaded vendors into master DB, keep existing rows on Vendor_ID clash."""
    incoming = _normalize_vendor_df(new_vendors_df)
    master_exists = os.path.exists(MASTER_VENDOR_DB_PATH)

    if master_exists:
        try:
            # If file exists but is blank/corrupt, treat as empty master DB.
            if os.path.getsize(MASTER_VENDOR_DB_PATH) == 0:
                existing = pd.DataFrame(columns=incoming.columns)
            else:
                existing = pd.read_csv(MASTER_VENDOR_DB_PATH)
            existing = _normalize_vendor_df(existing)
            merged = pd.concat([existing, incoming], ignore_index=True)
            merged = merged.drop_duplicates(subset=["Vendor_ID"], keep="first")
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            merged = incoming.drop_duplicates(subset=["Vendor_ID"], keep="first")
    else:
        merged = incoming.drop_duplicates(subset=["Vendor_ID"], keep="first")

    save_master_vendor_db(merged, sync_registry=True)
    return merged, master_exists


def _save_vendor_csv_atomic(path: Path, df: pd.DataFrame) -> None:
    """Write any vendor CSV (registry or master) via temp file + replace."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, path)
    except PermissionError as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise PermissionError(
            f"{path.name} is locked by another app. Close Excel/Sheets/file viewer and try again."
        ) from e
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise


def _export_master_vendors_to_registry_files(df: pd.DataFrame | None = None) -> None:
    """Mirror normalized master vendors to msme_vendor_registry.csv (and upload copy if present)."""
    try:
        out = df if df is not None else pd.read_csv(MASTER_VENDOR_DB_PATH)
        out = _normalize_vendor_df(out)
    except Exception as e:
        print(f"[registry-sync] skipped: {e}")
        return
    for target in (DEFAULT_VENDOR_PATH, UPLOAD_DIR / VENDOR_FILENAME):
        try:
            if target is DEFAULT_VENDOR_PATH or target.exists():
                _save_vendor_csv_atomic(target, out)
        except Exception as e:
            print(f"[registry-sync] failed writing {target}: {e}")


def save_master_vendor_db(df: pd.DataFrame, *, sync_registry: bool = False) -> None:
    """Persist master DB safely and surface file-lock errors clearly."""
    tmp_path = MASTER_VENDOR_DB_PATH.with_suffix(".csv.tmp")
    try:
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, MASTER_VENDOR_DB_PATH)
    except PermissionError as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise PermissionError(
            "master_vendors_db.csv is locked by another app. "
            "Close Excel/Sheets/file viewer and try again."
        ) from e
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise
    if sync_registry:
        try:
            _export_master_vendors_to_registry_files(df)
        except Exception as e:
            print(f"[registry-sync] after master save: {e}")


def _dev_reset_master_trust_scores() -> tuple[int, int]:
    """
    Reset trust-related columns on master buyer/vendor CSVs (local testing only).
    Reads and validates both files before saving either.
    Returns (buyer_row_count, vendor_row_count).
    """
    if not MASTER_BUYER_DB_PATH.exists():
        raise HTTPException(404, "master_buyers_db.csv not found.")
    if not MASTER_VENDOR_DB_PATH.exists():
        raise HTTPException(404, "master_vendors_db.csv not found.")
    if os.path.getsize(MASTER_BUYER_DB_PATH) == 0:
        raise HTTPException(404, "master_buyers_db.csv is empty.")
    if os.path.getsize(MASTER_VENDOR_DB_PATH) == 0:
        raise HTTPException(404, "master_vendors_db.csv is empty.")

    try:
        buyers_df = pd.read_csv(MASTER_BUYER_DB_PATH)
        buyers_df = _normalize_buyer_df(buyers_df)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        raise HTTPException(400, f"Could not parse master_buyers_db.csv: {e}") from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Failed to read master_buyers_db.csv: {e}") from e

    try:
        vendors_df = pd.read_csv(MASTER_VENDOR_DB_PATH)
        vendors_df = _normalize_vendor_df(vendors_df)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        raise HTTPException(400, f"Could not parse master_vendors_db.csv: {e}") from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Failed to read master_vendors_db.csv: {e}") from e

    n_buyers = len(buyers_df)
    n_vendors = len(vendors_df)
    if n_buyers == 0 and n_vendors == 0:
        raise HTTPException(404, "Both master databases have no data rows to reset.")

    buyers_df = buyers_df.copy()
    vendors_df = vendors_df.copy()
    buyers_df["Buyer_Rating"] = 5.0
    buyers_df["Total_Reviews"] = 0
    buyers_df["Payment_Delay_Flags"] = 0
    vendors_df["Vendor_Rating"] = 5.0
    vendors_df["Total_Reviews"] = 0
    vendors_df["Defect_Rate_Pct"] = 0.0

    try:
        save_master_buyer_db(buyers_df)
    except PermissionError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Failed to save master_buyers_db.csv: {e}") from e

    try:
        save_master_vendor_db(vendors_df, sync_registry=True)
    except PermissionError as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Failed to save master_vendors_db.csv: {e}") from e

    return n_buyers, n_vendors


# High-accuracy email (no \\b: works with "Email:john@x.com", quoted cells, etc.)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Vendor: V-101, V101, (V-001) — optional hyphen (master DB uses V001, V100, etc.)
_VENDOR_TOKEN = re.compile(r"\bV-?\d+\b", re.IGNORECASE)

# Fallback when summary uses "Vendor 101" without V-
_VENDOR_DIGITS = re.compile(
    r"\bVendor\s*(?:ID|No\.?|#)?\s*:?\s*(\d{1,6})\b", re.IGNORECASE
)

_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)


def _deobfuscate_email_text(t: str) -> str:
    """Turn common anti-spam patterns into a normal address before regex."""
    s = t
    s = re.sub(r"\s*\[at\]\s*", "@", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\(at\)\s*", "@", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+at\s+", "@", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\[dot\]\s*", ".", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\(dot\)\s*", ".", s, flags=re.IGNORECASE)
    return s


def _preprocess_summary_text(raw: str) -> str:
    """Strip BOM, zero-width chars, CSV quotes, and normalize punctuation before regex."""
    t = str(raw or "")
    for ch in ("\ufeff", "\u200b", "\u200c", "\u200d", "\xa0"):
        t = t.replace(ch, " ")
    t = t.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    t = t.strip().strip('"').strip("'").strip("`")
    while len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        t = t[1:-1].strip()
    t = t.replace("<", " ").replace(">", " ")
    t = re.sub(r"[\u2013\u2014\u2212]", "-", t)
    t = _deobfuscate_email_text(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _extract_defect_rate(text: str, vendor_id: str) -> float | None:
    """Prefer % near 'defect'; else first percentage in text (handles stray punctuation)."""
    lower = text.lower()
    lower_vid = vendor_id.lower()
    pos = lower.find(lower_vid)
    window = text if pos == -1 else text[max(0, pos - 260) : pos + len(vendor_id) + 260]

    for pat in (
        r"(\d+(?:\.\d+)?)\s*%\s*defect",
        r"defect(?:\s+rate)?\s*[:\s,;()\-]*\s*(\d+(?:\.\d+)?)\s*%",
        r"defect[^0-9]{0,40}(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*%\s*(?:defect|defective|rejection)",
    ):
        m = re.search(pat, window, re.IGNORECASE)
        if m:
            return float(m.group(1))

    best_idx: int | None = None
    best_val: float | None = None
    for m in _PCT_RE.finditer(text):
        start = m.start()
        ctx = text[max(0, start - 40) : start].lower()
        if "defect" in ctx or "rejection" in ctx or "qc" in ctx or "quality" in ctx:
            return float(m.group(1))
        if best_idx is None:
            best_idx = start
            best_val = float(m.group(1))

    if best_val is not None and re.search(
        r"defect|rejection|\bqc\b|quality|inspection", lower
    ):
        return best_val
    return None


def _extract_delay_days(text: str) -> int | None:
    """Numbers adjacent to 'days' / common delay phrasing."""
    lower = text.lower()
    m = re.search(r"delayed\s+by\s+(\d+(?:\.\d+)?)\s*days?", lower)
    if m:
        return int(float(m.group(1)))
    m = re.search(r"(\d+(?:\.\d+)?)\s*days?\s+(?:late|delay|overdue)", lower)
    if m:
        return int(float(m.group(1)))
    m = re.search(r"(\d+(?:\.\d+)?)\s*days?\b", lower)
    if m:
        return int(float(m.group(1)))
    return None


def _extract_payment_delayed(text: str, buyer_email: str, delay_days: int | None) -> bool:
    if delay_days is not None and delay_days > 0:
        return True
    lower = text.lower()
    if re.search(r"delayed\s+by\s+\d+", lower):
        return True
    if re.search(r"\bunpaid\b|\blate\s+payment\b|\bpayment\s+late\b", lower):
        return True
    delay_keywords = ("delayed", "late", "unpaid")
    pos = lower.find(buyer_email.lower())
    if pos == -1:
        return any(k in lower for k in delay_keywords)
    window = lower[max(0, pos - 220) : pos + len(buyer_email) + 220]
    return any(k in window for k in delay_keywords)


def _canonical_vendor_label(n: int) -> str:
    """Human-readable id consistent with extracted summaries (V-101). DB rows may be V101."""
    return f"V-{int(n)}"


def _vendor_serial(vid: str) -> int | None:
    """Numeric vendor index: V001, V-1, V101, 101 -> 1, 1, 101, 101 (for matching master rows)."""
    s0 = str(vid).strip().upper().replace(" ", "").replace("-", "")
    try:
        f = float(s0)
        if f == int(f) and 0 <= int(f) < 10**8:
            return int(f)
    except (ValueError, TypeError, OverflowError):
        pass
    m = re.search(r"V[-\s#/]*(\d{1,8})", s0, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_vendor_id(text: str) -> str:
    m = _VENDOR_TOKEN.search(text)
    if m:
        n = _vendor_serial(m.group(0))
        if n is not None:
            return _canonical_vendor_label(n)
    m2 = _VENDOR_DIGITS.search(text)
    if m2:
        return _canonical_vendor_label(int(m2.group(1)))
    raise ValueError("Could not extract Vendor_ID from transaction summary.")


def _clean_extracted_email(addr: str) -> str:
    e = addr.strip().lower()
    if e.startswith("mailto:"):
        e = e[7:].split("?")[0].strip()
    return e


def extract_transaction_signals(
    report_text: str,
    buyer_email_hint: str | None = None,
    vendor_id_hint: str | None = None,
) -> dict:
    text = _preprocess_summary_text(report_text)
    if not text:
        raise ValueError("Transaction summary text cannot be empty.")

    buyer_email = None
    if buyer_email_hint and str(buyer_email_hint).strip():
        hint = _preprocess_summary_text(buyer_email_hint)
        hm = _EMAIL_RE.search(hint)
        if hm:
            buyer_email = _clean_extracted_email(hm.group(0))
    if not buyer_email:
        em = _EMAIL_RE.search(text)
        if not em:
            raise ValueError("Could not extract Buyer_Email from transaction summary.")
        buyer_email = _clean_extracted_email(em.group(0))

    vendor_id = None
    if vendor_id_hint and str(vendor_id_hint).strip():
        vh = _preprocess_summary_text(str(vendor_id_hint))
        vm = _VENDOR_TOKEN.search(vh)
        if vm:
            sn = _vendor_serial(vm.group(0))
            if sn is not None:
                vendor_id = _canonical_vendor_label(sn)
        if not vendor_id:
            dm = re.search(r"(\d{1,8})", vh)
            if dm:
                vendor_id = _canonical_vendor_label(int(dm.group(1)))
    if not vendor_id:
        vendor_id = _extract_vendor_id(text)

    delay_days = _extract_delay_days(text)
    payment_delayed = _extract_payment_delayed(text, buyer_email, delay_days)
    defect_rate = _extract_defect_rate(text, vendor_id)
    return {
        "Buyer_Email": buyer_email,
        "Vendor_ID": vendor_id,
        "Delay_Days": delay_days,
        "Payment_Delayed": bool(payment_delayed),
        "Defect_Rate": float(defect_rate) if defect_rate is not None else 0.0,
    }


def _normalize_header_key(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def _find_summary_text_column(df: pd.DataFrame) -> str:
    aliases = {
        "summary_text",
        "transaction_summary",
        "summary",
        "report_text",
        "notes",
        "description",
        "transaction_notes",
        "detail",
        "details",
        "text",
        "narrative",
        "transcript",
        "story",
        "dock_notes",
        "remarks",
    }
    for col in df.columns:
        if _normalize_header_key(col) in aliases:
            return str(col)
    raise ValueError(
        "CSV must include a summary column (e.g. Summary_Text, summary_text, transaction_summary)."
    )


def _row_string_ci(row: pd.Series, col_key_norm: dict[str, str], *wanted_norm_keys: str) -> str | None:
    for w in wanted_norm_keys:
        orig = col_key_norm.get(w)
        if orig is None:
            continue
        val = row.get(orig)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        s = str(val).strip()
        if s:
            return s
    return None


def apply_transaction_feedback(
    buyers_df: pd.DataFrame, vendors_df: pd.DataFrame, extracted: dict
) -> tuple[str, str]:
    """
    Apply one extracted transaction feedback record to in-memory DataFrames.
    Returns normalized (buyer_email, vendor_id) on success.
    Raises ValueError when buyer/vendor row is not found.
    """
    buyer_email = str(extracted["Buyer_Email"]).strip().lower()
    want_vendor_serial = _vendor_serial(str(extracted["Vendor_ID"]))
    payment_delayed = bool(extracted["Payment_Delayed"])
    defect_rate = float(extracted["Defect_Rate"])

    buyer_selector = buyers_df["Buyer_Email"].astype(str).str.strip().str.lower() == buyer_email
    if not buyer_selector.any():
        raise ValueError(f"Buyer not found in master_buyers_db.csv: {buyer_email}")

    if want_vendor_serial is None:
        raise ValueError(f"Invalid Vendor_ID in extraction: {extracted['Vendor_ID']!r}")
    vendor_serials = vendors_df["Vendor_ID"].astype(str).map(lambda x: _vendor_serial(x))
    vendor_selector = vendor_serials == want_vendor_serial
    if not vendor_selector.any():
        raise ValueError(
            f"Vendor not found in master_vendors_db.csv (serial {want_vendor_serial}): "
            f"{extracted['Vendor_ID']!r}"
        )

    buyer_idx = buyers_df.index[buyer_selector][0]
    buyer_reviews = int(pd.to_numeric(buyers_df.at[buyer_idx, "Total_Reviews"], errors="coerce") or 0) + 1
    buyer_flags = int(
        pd.to_numeric(buyers_df.at[buyer_idx, "Payment_Delay_Flags"], errors="coerce") or 0
    )
    if payment_delayed:
        buyer_flags += 1
    buyer_rating = max(0.0, 5.0 - (0.5 * buyer_flags))

    buyers_df.at[buyer_idx, "Total_Reviews"] = buyer_reviews
    buyers_df.at[buyer_idx, "Payment_Delay_Flags"] = buyer_flags
    buyers_df.at[buyer_idx, "Buyer_Rating"] = round(buyer_rating, 2)

    vendor_idx = vendors_df.index[vendor_selector][0]
    vendor_reviews = int(
        pd.to_numeric(vendors_df.at[vendor_idx, "Total_Reviews"], errors="coerce") or 0
    ) + 1
    defect_rate = max(0.0, min(100.0, defect_rate))
    vendor_rating = max(0.0, 5.0 - (0.1 * defect_rate))

    vendors_df.at[vendor_idx, "Total_Reviews"] = vendor_reviews
    vendors_df.at[vendor_idx, "Defect_Rate_Pct"] = round(defect_rate, 2)
    vendors_df.at[vendor_idx, "Vendor_Rating"] = round(vendor_rating, 2)

    return buyer_email, str(vendors_df.loc[vendor_selector, "Vendor_ID"].iloc[0]).strip()


def _vendor_id_for_serial(serial: int) -> str:
    """Match existing master style: V001 … V100, V101, … (V + zero-padded to 3 digits when < 1000)."""
    if 0 < serial < 1000:
        return f"V{serial:03d}"
    return f"V{serial}"


def _canonicalize_vendor_id_for_storage(vid: str) -> str:
    """Unify V-001, v001, V001 → V001 (dash/case-insensitive for numeric vendor codes)."""
    raw = str(vid).strip()
    if not raw or raw.lower() in ("nan", "none"):
        return raw
    sn = _vendor_serial(raw)
    if sn is not None:
        return _vendor_id_for_serial(sn)
    return raw


def _extract_vendor_display_name(text: str, serial: int) -> str | None:
    """e.g. 'V-101 (Gujarat Textiles)' -> 'Gujarat Textiles'."""
    m = re.search(rf"V\s*-?\s*{serial}\s*\(([^)]+)\)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:120]
    return None


def _ensure_vendor_in_master(
    vendors_df: pd.DataFrame,
    serial: int,
    name_hint: str | None,
    category_hint: str | None,
) -> pd.DataFrame:
    """Append a minimal vendor row when dock reports reference IDs not yet in master_vendors_db."""
    if serial is None or serial < 0:
        return vendors_df
    vid = _vendor_id_for_serial(serial)
    if vendors_df is not None and not vendors_df.empty and "Vendor_ID" in vendors_df.columns:
        keys = vendors_df["Vendor_ID"].astype(str).map(lambda x: _vendor_serial(x))
        if (keys == serial).any():
            return vendors_df
    name = (name_hint or "").strip() or f"Dock audit vendor {vid}"
    name = name[:120]
    cat = (category_hint or "").strip() or "General"
    cat = cat[:80]
    new_row = {
        "Vendor_ID": vid,
        "Vendor_Name": name,
        "Category": cat,
        "Contact_Email": "NO_EMAIL",
        "Contact_Phone": "919943000000",
        "Leads_Received": 0,
    }
    if vendors_df is None or vendors_df.empty:
        print(f"[batch] auto-added vendor {vid!r} (serial {serial}) to empty master vendor list")
        return _normalize_vendor_df(pd.DataFrame([new_row]))
    print(f"[batch] auto-added vendor {vid!r} (serial {serial}) — not in master_vendors_db.csv")
    out = pd.concat([vendors_df, pd.DataFrame([new_row])], ignore_index=True)
    return _normalize_vendor_df(out)


def _ensure_buyer_in_master(
    buyers_df: pd.DataFrame,
    email: str,
    company_hint: str | None,
    *,
    entity_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Append unrated buyer row if missing so dock audits can still post feedback."""
    el = str(email).strip().lower()
    company = (company_hint or "").strip() or "Dock Audit Buyer"
    company = company[:240]
    emap = entity_map if entity_map is not None else read_expanded_inquiries_entity_map()
    entity_default = emap.get(el, "Private")
    new_row = pd.DataFrame(
        [
            {
                "Buyer_Email": el,
                "Company_Name": company,
                "Buyer_Rating": pd.NA,
                "Total_Reviews": 0,
                "Payment_Delay_Flags": 0,
                "Entity_Type": entity_default,
            }
        ]
    )
    if buyers_df is None or buyers_df.empty:
        return _normalize_buyer_df(new_row)
    if "Buyer_Email" not in buyers_df.columns:
        return _normalize_buyer_df(pd.concat([buyers_df, new_row], ignore_index=True))
    if (buyers_df["Buyer_Email"].astype(str).str.strip().str.lower() == el).any():
        return buyers_df
    out = pd.concat([buyers_df, new_row], ignore_index=True)
    return _normalize_buyer_df(out)


def _bootstrap_vendor_registry_csv_files() -> None:
    """On startup: ensure trust columns + canonical Vendor_ID on registry CSVs."""
    for target in (DEFAULT_VENDOR_PATH, UPLOAD_DIR / VENDOR_FILENAME):
        if not target.exists() or os.path.getsize(target) == 0:
            continue
        try:
            raw = pd.read_csv(target)
            fixed = _normalize_vendor_df(raw)
            _save_vendor_csv_atomic(target, fixed)
        except Exception as e:
            print(f"[init] vendor registry bootstrap ({target}): {e}")


def _bootstrap_master_buyers_csv_schema() -> None:
    """On startup: add missing buyer trust columns, sync Entity_Type from expanded_inquiries, persist."""
    if not MASTER_BUYER_DB_PATH.exists() or os.path.getsize(MASTER_BUYER_DB_PATH) == 0:
        return
    try:
        df = pd.read_csv(MASTER_BUYER_DB_PATH)
        df = merge_buyer_entity_types_from_expanded_inquiries(df)
        save_master_buyer_db(_normalize_buyer_df(df))
    except Exception as e:
        print(f"[init] buyer master bootstrap: {e}")


app = FastAPI(title="MSME Export Matchmaker API", version="1.0.0")
ensure_master_buyer_db()
_bootstrap_master_buyers_csv_schema()
_bootstrap_vendor_registry_csv_files()

# Avoid stale directory UIs after batch trust updates (browser heuristic GET caching).
_PROFILE_JSON_HEADERS = {"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"}


def _json_no_cache(body: list | dict) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(body),
        headers=_PROFILE_JSON_HEADERS,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "msme-matchmaker"}


@app.post("/api/dev/reset-databases")
def dev_reset_databases():
    """Reset trust metrics on master CSVs (developer / demo testing only)."""
    n_buyers, n_vendors = _dev_reset_master_trust_scores()
    return {
        "status": "ok",
        "message": "Buyer and vendor trust columns were reset to demo defaults.",
        "buyer_rows_reset": n_buyers,
        "vendor_rows_reset": n_vendors,
    }


@app.post("/api/upload/vendors")
async def upload_vendors(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")
    dest = UPLOAD_DIR / VENDOR_FILENAME
    content = await file.read()
    dest.write_bytes(content)
    try:
        text = content.decode("utf-8-sig")
        df = pd.read_csv(StringIO(text))
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV: {e}") from e
    try:
        merged_df, merged_into_existing = upsert_master_vendor_db(df)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Failed to update master vendor DB: {e}") from e

    preview = merged_df.head(500).fillna("")
    return {
        "filename": file.filename,
        "rows_uploaded": len(df),
        "rows_master": len(merged_df),
        "merged_into_existing_master": merged_into_existing,
        "saved_as": str(dest),
        "master_db_path": str(MASTER_VENDOR_DB_PATH),
        "columns": list(merged_df.columns),
        "preview_rows": preview.to_dict(orient="records"),
    }


@app.post("/api/upload/inquiries")
async def upload_inquiries(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")
    dest = UPLOAD_DIR / INQUIRIES_FILENAME
    content = await file.read()
    dest.write_bytes(content)
    try:
        text = content.decode("utf-8-sig")
        df = pd.read_csv(StringIO(text))
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV: {e}") from e
    if "Inquiry_Text" not in df.columns:
        raise HTTPException(400, "CSV must include Inquiry_Text column.")
    has_labels = "Category" in df.columns and df["Category"].notna().any()
    return {
        "filename": file.filename,
        "rows": len(df),
        "saved_as": str(dest),
        "has_category_labels": bool(has_labels),
    }


@app.post("/api/admin/reset-leads")
def reset_leads():
    """Reset Leads_Received counter to 0 for all persisted vendors."""
    if not MASTER_VENDOR_DB_PATH.exists():
        raise HTTPException(404, "master_vendors_db.csv not found. Upload vendors first.")
    try:
        if os.path.getsize(MASTER_VENDOR_DB_PATH) == 0:
            raise HTTPException(404, "master_vendors_db.csv is empty. Upload vendors first.")
        df = pd.read_csv(MASTER_VENDOR_DB_PATH)
        df = _normalize_vendor_df(df)
    except HTTPException:
        raise
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        raise HTTPException(404, "master_vendors_db.csv is empty or invalid.")
    except Exception as e:
        raise HTTPException(500, f"Failed to read master DB: {e}") from e

    df["Leads_Received"] = 0
    try:
        save_master_vendor_db(df, sync_registry=True)
    except Exception as e:
        raise HTTPException(500, f"Failed to save master DB: {e}") from e

    return {"status": "ok", "rows_updated": len(df), "message": "Leads_Received reset to 0."}


def _sse_line(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def run_matchmaker_stream() -> AsyncGenerator[str, None]:
    _, inquiries_path = resolve_data_paths()
    yield _sse_line(
        {
            "type": "log",
            "line": f"[init] Using vendors DB: {MASTER_VENDOR_DB_PATH.name} | inquiries: {inquiries_path.name}",
        }
    )
    await asyncio.sleep(0.05)

    if not MASTER_VENDOR_DB_PATH.exists():
        yield _sse_line(
            {
                "type": "error",
                "line": "[error] master_vendors_db.csv missing. Upload vendors first.",
            }
        )
        return
    if not inquiries_path.exists():
        yield _sse_line(
            {"type": "error", "line": f"[error] Inquiries file not found: {inquiries_path}"}
        )
        return

    try:
        df_vendors = pd.read_csv(MASTER_VENDOR_DB_PATH)
        df_vendors = _normalize_vendor_df(df_vendors)
        df_train = load_training_inquiries_df()
        df_batch = load_batch_inquiries_df()
    except Exception as e:
        yield _sse_line({"type": "error", "line": f"[error] Failed to read CSV: {e}"})
        return

    try:
        added, total = upsert_master_buyer_db_from_inquiries(df_batch)
        yield _sse_line(
            {
                "type": "log",
                "line": (
                    "[etl] Buyer profiles synced from inquiries: "
                    f"{added} new, {total} total in {MASTER_BUYER_DB_PATH.name}"
                ),
            }
        )
        await asyncio.sleep(0.03)
    except ValueError as e:
        yield _sse_line({"type": "error", "line": f"[error] Buyer ETL validation failed: {e}"})
        return
    except Exception as e:
        yield _sse_line({"type": "error", "line": f"[error] Buyer ETL failed: {e}"})
        return

    required_v = {"Vendor_ID", "Vendor_Name", "Category", "Contact_Email", "Contact_Phone"}
    if not required_v.issubset(df_vendors.columns):
        yield _sse_line(
            {
                "type": "error",
                "line": f"[error] Vendors CSV missing columns. Need: {sorted(required_v)}",
            }
        )
        return

    try:
        yield _sse_line({"type": "log", "line": "[ml] Training TF-IDF (1–2 grams) + LogisticRegression …"})
        await asyncio.sleep(0.05)
        vectorizer, model = train_classifier(df_train)
        yield _sse_line(
            {
                "type": "log",
                "line": f"[ml] Training complete on labeled set ({len(df_train)} rows). Classes: {list(model.classes_)}",
            }
        )
    except Exception as e:
        yield _sse_line({"type": "error", "line": f"[error] Training failed: {e}"})
        return

    default_buyer = os.getenv("BUYER_NOTIFICATION_EMAIL", "buyer@example.com")

    n = len(df_batch)
    yield _sse_line(
        {
            "type": "log",
            "line": f"[batch] Scoring {n} inquiries from {inquiries_path.name} …",
        }
    )
    await asyncio.sleep(0.05)

    matched_count = 0
    for idx, row in df_batch.iterrows():
        text = str(row.get("Inquiry_Text", "")).strip()
        buyer_country = str(row.get("Buyer_Country", "Unknown")).strip()
        if not text:
            yield _sse_line(
                {"type": "log", "line": f"[row {idx + 1}] SKIP — empty Inquiry_Text"}
            )
            continue

        X = vectorizer.transform([text])
        predicted = model.predict(X)[0]
        proba = float(max(model.predict_proba(X)[0]))

        yield _sse_line(
            {
                "type": "log",
                "line": f"[row {idx + 1}] Predicted category: {predicted} (confidence {proba:.2%}) | {buyer_country}",
            }
        )
        await asyncio.sleep(0.03)

        pool = df_vendors[
            df_vendors["Category"].astype(str).str.strip().str.lower()
            == str(predicted).strip().lower()
        ]
        if pool.empty:
            yield _sse_line(
                {
                    "type": "log",
                    "line": f"  → No vendor for category '{predicted}'. Skipping notifications.",
                }
            )
            continue

        # Least-Leads-First assignment for load balancing (no random allocation).
        pool_sorted = pool.sort_values(by="Leads_Received", ascending=True, kind="stable")
        vendor = pool_sorted.iloc[0]
        vendor_id = str(vendor["Vendor_ID"]).strip()
        current_leads = int(vendor["Leads_Received"])

        v_serial = _vendor_serial(vendor_id)
        if v_serial is not None:
            row_selector = df_vendors["Vendor_ID"].astype(str).map(_vendor_serial) == v_serial
        else:
            row_selector = df_vendors["Vendor_ID"].astype(str).str.strip() == vendor_id
        df_vendors.loc[row_selector, "Leads_Received"] = current_leads + 1
        try:
            save_master_vendor_db(df_vendors)
        except Exception as e:
            yield _sse_line(
                {"type": "error", "line": f"[error] Failed saving lead counters: {e}"}
            )
            return

        vname = str(vendor["Vendor_Name"])
        vphone = str(vendor["Contact_Phone"])
        matched_count += 1

        yield _sse_line(
            {
                "type": "match",
                "line": (
                    f"  → MATCH: {vname} ({vendor_id}) | {predicted} | "
                    f"Leads {current_leads}→{current_leads + 1}"
                ),
            }
        )
        await asyncio.sleep(0.02)

        email_status = notify_buyer_email(default_buyer, vname, predicted, buyer_country)
        yield _sse_line({"type": "email", "line": f"  📧 {email_status}"})
        await asyncio.sleep(0.02)

        sms_status = notify_vendor_sms(vphone, predicted, vname, buyer_country)
        yield _sse_line({"type": "sms", "line": f"  📱 {sms_status}"})
        await asyncio.sleep(0.02)

    yield _sse_line(
        {
            "type": "done",
            "line": f"[done] Batch complete. Leads with vendor match: {matched_count}/{n}",
        }
    )


@app.get("/api/run-matchmaker")
async def run_matchmaker():
    return StreamingResponse(
        run_matchmaker_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Preview persisted master vendors DB
@app.get("/api/vendors/preview")
def preview_vendors():
    if not MASTER_VENDOR_DB_PATH.exists():
        raise HTTPException(404, "No vendor CSV uploaded yet.")
    try:
        if os.path.getsize(MASTER_VENDOR_DB_PATH) == 0:
            raise HTTPException(404, "No vendor CSV uploaded yet.")
        df = pd.read_csv(MASTER_VENDOR_DB_PATH)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        raise HTTPException(404, "No vendor CSV uploaded yet.")
    return {"rows": df.fillna("").to_dict(orient="records"), "columns": list(df.columns)}


@app.get("/api/vendors")
def get_vendors():
    """Return full persisted vendor directory for admin browsing/search."""
    if not MASTER_VENDOR_DB_PATH.exists():
        return _json_no_cache([])
    try:
        if os.path.getsize(MASTER_VENDOR_DB_PATH) == 0:
            return _json_no_cache([])
        df = pd.read_csv(MASTER_VENDOR_DB_PATH)
        df = _normalize_vendor_df(df)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return _json_no_cache([])
    except Exception as e:
        raise HTTPException(
            500,
            f"Unable to read master_vendors_db.csv for /api/vendors: {e}",
        ) from e
    return _json_no_cache(df.fillna("").to_dict(orient="records"))


@app.get("/api/vendor-profiles")
def get_vendor_profiles():
    if not MASTER_VENDOR_DB_PATH.exists():
        return _json_no_cache([])
    try:
        if os.path.getsize(MASTER_VENDOR_DB_PATH) == 0:
            return _json_no_cache([])
        df = pd.read_csv(MASTER_VENDOR_DB_PATH)
        df = _normalize_vendor_df(df)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return _json_no_cache([])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(
            500,
            f"Unable to read master_vendors_db.csv for /api/vendor-profiles: {e}",
        ) from e

    df["Trust_Score"] = (100.0 - df["Defect_Rate_Pct"]).clip(lower=0.0, upper=100.0).round(2)
    return _json_no_cache(df.fillna("").to_dict(orient="records"))


@app.get("/api/buyer-profiles")
def get_buyer_profiles():
    ensure_master_buyer_db()
    try:
        if os.path.getsize(MASTER_BUYER_DB_PATH) == 0:
            df = pd.DataFrame(columns=MASTER_BUYER_COLUMNS)
        else:
            df = pd.read_csv(MASTER_BUYER_DB_PATH)
        df = _normalize_buyer_df(df)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        df = pd.DataFrame(columns=MASTER_BUYER_COLUMNS)
    except Exception:
        return _json_no_cache([])

    rows = []
    for _, row in df.iterrows():
        total_reviews = int(row["Total_Reviews"])
        base_rating_raw = row["Buyer_Rating"]
        has_rating = pd.notna(base_rating_raw)
        base_rating = float(base_rating_raw) if has_rating else None
        delay_flags = int(row["Payment_Delay_Flags"])
        is_new_buyer = total_reviews == 0
        entity_type = str(row.get("Entity_Type", "Private")).strip() or "Private"

        profile = {
            "Buyer_Email": str(row["Buyer_Email"]),
            "Buyer_ID": str(row["Buyer_Email"]),
            "Company_Name": str(row["Company_Name"]),
            "Buyer_Rating": base_rating,
            "Total_Reviews": total_reviews,
            "Payment_Delay_Flags": delay_flags,
            "New_Buyer": is_new_buyer,
            "Entity_Type": entity_type,
            "Government_Directory_Badge": buyer_entity_shows_directory_government_badge(entity_type),
        }
        if is_new_buyer:
            profile["Buyer_Profile_Status"] = "New Buyer"
            profile["Adjusted_Buyer_Rating"] = base_rating
        else:
            if base_rating is None:
                profile["Adjusted_Buyer_Rating"] = None
            else:
                adjusted = max(0.0, base_rating - (0.20 * delay_flags))
                profile["Adjusted_Buyer_Rating"] = round(adjusted, 2)
            profile["Buyer_Profile_Status"] = "Reviewed Buyer"
        rows.append(profile)
    return _json_no_cache(rows)


@app.post("/api/process-transaction-summary")
@app.post("/api/batch-process-transactions")
async def process_transaction_summary(request: Request):
    form = await request.form()
    print(f"DEBUG: Received form keys: {list(form.keys())}")
    file = form.get("file")
    if file is None:
        raise HTTPException(
            status_code=422,
            detail=f"Missing multipart field 'file'. Received keys: {list(form.keys())}",
        )
    # Starlette may supply starlette.datastructures.UploadFile; FastAPI re-exports another
    # reference — isinstance(..., fastapi.UploadFile) can falsely fail. Validate by contract.
    read_fn = getattr(file, "read", None)
    if not callable(read_fn) or not inspect.iscoroutinefunction(read_fn):
        raise HTTPException(
            status_code=422,
            detail=f"Field 'file' must be an async multipart file part; got {type(file).__name__}",
        )

    filename = (getattr(file, "filename", None) or "").strip()
    if not filename or not filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
        df_batch = pd.read_csv(StringIO(text))
    except Exception as e:
        raise HTTPException(400, f"Invalid CSV: {e}") from e

    df_batch.columns = [str(c).replace("\ufeff", "").strip() for c in df_batch.columns]

    try:
        summary_col = _find_summary_text_column(df_batch)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    col_key_norm = {_normalize_header_key(c): c for c in df_batch.columns}
    print(
        f"[batch] Loaded {len(df_batch)} rows from {filename!r}; "
        f"summary column={summary_col!r}; headers={list(df_batch.columns)}"
    )

    ensure_master_buyer_db()
    if not MASTER_VENDOR_DB_PATH.exists():
        raise HTTPException(404, "master_vendors_db.csv not found. Upload vendors first.")

    expanded_entity_map = read_expanded_inquiries_entity_map()
    try:
        if os.path.getsize(MASTER_BUYER_DB_PATH) == 0:
            buyers_df = pd.DataFrame(columns=MASTER_BUYER_COLUMNS)
        else:
            buyers_df = pd.read_csv(MASTER_BUYER_DB_PATH)
        buyers_df = merge_buyer_entity_types_from_expanded_inquiries(buyers_df)
        buyers_df = _normalize_buyer_df(buyers_df)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        buyers_df = pd.DataFrame(columns=MASTER_BUYER_COLUMNS)
    except Exception as e:
        raise HTTPException(500, f"Failed to read buyers DB: {e}") from e

    try:
        if os.path.getsize(MASTER_VENDOR_DB_PATH) == 0:
            raise HTTPException(404, "master_vendors_db.csv is empty. Upload vendors first.")
        vendors_df = pd.read_csv(MASTER_VENDOR_DB_PATH)
        vendors_df = _normalize_vendor_df(vendors_df)
    except HTTPException:
        raise
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        raise HTTPException(404, "master_vendors_db.csv is empty or invalid.")
    except Exception as e:
        raise HTTPException(500, f"Failed to read vendors DB: {e}") from e

    processed_rows = 0
    skipped_rows = 0
    updated_buyers: set[str] = set()
    updated_vendors: set[str] = set()
    sample_extractions: list[dict] = []
    skipped_details: list[dict] = []
    transaction_row_results: list[dict] = []

    for row_num, (_, row) in enumerate(df_batch.iterrows(), start=1):
        summary_raw = row.get(summary_col, "")
        summary_text = str(summary_raw).strip() if pd.notna(summary_raw) else ""
        cleaned_summary = _preprocess_summary_text(summary_text)
        buyer_hint = _row_string_ci(
            row,
            col_key_norm,
            "buyer_email",
            "email",
            "email_address",
            "contact_email",
            "buyer_e_mail",
        )
        vendor_hint = _row_string_ci(
            row,
            col_key_norm,
            "vendor_id",
            "vendor",
            "vendor_no",
            "vendor_number",
            "vid",
        )

        print(
            f"[batch] row {row_num}: summary_preview={cleaned_summary[:220]!r} "
            f"buyer_hint={buyer_hint!r} vendor_hint={vendor_hint!r}"
        )

        if not cleaned_summary:
            skipped_rows += 1
            skipped_details.append({"row": row_num, "reason": f"Empty summary in column {summary_col!r}"})
            print(f"[batch] row {row_num}: SKIP empty summary")
            continue
        try:
            extracted = extract_transaction_signals(
                cleaned_summary,
                buyer_email_hint=buyer_hint,
                vendor_id_hint=vendor_hint,
            )
            delay_days = extracted.get("Delay_Days")
            delay_show = delay_days if delay_days is not None else extracted["Payment_Delayed"]
            print(
                f"Row {row_num} -> Extracted: Email={extracted['Buyer_Email']}, "
                f"Vendor={extracted['Vendor_ID']}, Delay={delay_show}, Defect={extracted['Defect_Rate']}"
            )
            company_hint = _row_string_ci(
                row,
                col_key_norm,
                "company_name",
                "company",
                "buyer_company",
                "organization",
            )
            buyers_df = _ensure_buyer_in_master(
                buyers_df, extracted["Buyer_Email"], company_hint, entity_map=expanded_entity_map
            )
            eml_key = str(extracted["Buyer_Email"]).strip().lower()
            em_sel = buyers_df["Buyer_Email"].astype(str).str.strip().str.lower() == eml_key
            et_from_expanded = expanded_entity_map.get(eml_key)
            if et_from_expanded is not None and str(et_from_expanded).strip():
                et_val = str(et_from_expanded).strip()
            elif em_sel.any() and "Entity_Type" in buyers_df.columns:
                et_raw = buyers_df.loc[em_sel, "Entity_Type"].iloc[0]
                et_val = str(et_raw).strip() if pd.notna(et_raw) else "Private"
            else:
                et_val = "Private"
            if not et_val or et_val.lower() in ("nan", "none"):
                et_val = "Private"
            is_gov_buyer = buyer_entity_is_government_buyer(et_val)
            v_ser = _vendor_serial(str(extracted["Vendor_ID"]))
            if v_ser is not None:
                v_name = _extract_vendor_display_name(cleaned_summary, v_ser)
                if not v_name:
                    v_name = _row_string_ci(
                        row,
                        col_key_norm,
                        "vendor_name",
                        "vendor",
                        "supplier_name",
                        "seller_name",
                    )
                v_cat = _row_string_ci(
                    row,
                    col_key_norm,
                    "category",
                    "vendor_category",
                    "product_category",
                )
                vendors_df = _ensure_vendor_in_master(vendors_df, v_ser, v_name, v_cat)
            buyer_email, vendor_id = apply_transaction_feedback(buyers_df, vendors_df, extracted)
            gov_badge_awarded = _award_vendor_govt_order_badge_if_eligible(
                vendors_df, extracted, is_government_buyer=is_gov_buyer
            )
            processed_rows += 1
            updated_buyers.add(buyer_email)
            updated_vendors.add(vendor_id)
            transaction_row_results.append(
                {
                    "row": row_num,
                    "buyer_email": extracted["Buyer_Email"],
                    "vendor_id": vendor_id,
                    "is_government": buyer_entity_is_government_audit(et_val),
                    "gov_badge_awarded": gov_badge_awarded,
                }
            )
            print(f"[batch] row {row_num}: OK updated buyer={buyer_email} vendor={vendor_id}")
            if len(sample_extractions) < 5:
                sample_extractions.append(extracted)
        except Exception as e:
            skipped_rows += 1
            skipped_details.append({"row": row_num, "reason": str(e)})
            print(f"[batch] row {row_num}: SKIP {type(e).__name__}: {e}")
            continue

    try:
        buyers_df = merge_buyer_entity_types_from_expanded_inquiries(buyers_df)
        buyers_df = _normalize_buyer_df(buyers_df)
        save_master_buyer_db(buyers_df)
        save_master_vendor_db(vendors_df, sync_registry=True)
    except Exception as e:
        raise HTTPException(500, f"Failed to save updated trust databases: {e}") from e

    total_profiles_updated = len(updated_buyers) + len(updated_vendors)
    return {
        "status": "ok",
        "filename": filename,
        "total_rows_in_file": len(df_batch),
        "transactions_processed": processed_rows,
        "transactions_skipped": skipped_rows,
        "buyer_profiles_updated": len(updated_buyers),
        "vendor_profiles_updated": len(updated_vendors),
        "total_profiles_updated": total_profiles_updated,
        "sample_extractions": sample_extractions,
        "skipped_rows_preview": skipped_details[:50],
        "transaction_row_results": transaction_row_results,
    }
