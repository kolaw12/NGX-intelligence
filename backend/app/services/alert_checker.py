"""Background price alert checking and email delivery service.

Runs as an asyncio loop inside the FastAPI process. Every CHECK_INTERVAL_SECONDS
it loads all active alerts from the database, compares them against the latest
market data, and fires email notifications for any that have crossed their
threshold.

Email delivery requires SMTP env vars (see _send_email). When SMTP is not
configured the alert is still marked triggered — just without an email.

Environment variables:
    SMTP_HOST       — e.g. smtp.gmail.com (required for email)
    SMTP_PORT       — default 587
    SMTP_USER       — sender address / login
    SMTP_PASSWORD   — app password or SMTP password
    SMTP_FROM       — display name + address, e.g. "NGX Intelligence <noreply@example.com>"
    APP_BASE_URL    — frontend URL for deep-links in emails
    ALERT_CHECK_INTERVAL_SECONDS — how often to run (default 900 = 15 min)
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from textwrap import dedent
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = int(os.getenv("ALERT_CHECK_INTERVAL_SECONDS", "900"))


# ── price lookup ─────────────────────────────────────────────────────────────

def _latest_prices() -> dict[str, float]:
    """Return {canonical_ticker: latest_close} from the parquet layer."""
    try:
        from app.db.crud import get_latest_by_ticker
        df = get_latest_by_ticker()
        if df.empty or "close" not in df.columns:
            return {}
        return {
            str(row["ticker"]).upper().strip(): float(row["close"])
            for _, row in df.iterrows()
            if row.get("close") is not None
        }
    except Exception as exc:
        logger.warning("alert_checker: failed to load prices: %s", exc)
        return {}


# ── condition evaluation ─────────────────────────────────────────────────────

def _is_triggered(condition: str, current_price: float, threshold: float) -> bool:
    """Return True when an alert's condition is met."""
    c = condition.lower().strip()
    if c in {"above", "price_above", ">"}:
        return current_price >= threshold
    if c in {"below", "price_below", "<"}:
        return current_price <= threshold
    if c in {"percent_change", "change_pct"}:
        return abs(current_price - threshold) / max(threshold, 0.01) * 100 >= abs(threshold)
    logger.warning("alert_checker: unknown condition %r; treating as above", condition)
    return current_price >= threshold


# ── email delivery ────────────────────────────────────────────────────────────

def _smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def _send_email(to_email: str, to_name: str | None, subject: str, body_html: str, body_text: str) -> bool:
    """Send a transactional email via SMTP TLS. Returns True on success."""
    if not _smtp_configured():
        logger.info("alert_checker: SMTP not configured — alert logged only (no email sent)")
        return False

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", f"NGX Intelligence <{smtp_user}>")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, [to_email], msg.as_string())
        logger.info("alert_checker: email sent to %s — %s", to_email, subject)
        return True
    except Exception as exc:
        logger.warning("alert_checker: failed to send email to %s: %s", to_email, exc)
        return False


def _build_email(
    ticker: str,
    condition: str,
    threshold: float,
    current_price: float,
    user_name: str | None,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for a triggered alert."""

    direction = "risen above" if condition.lower() in {"above", "price_above", ">"} else "fallen below"
    app_url = os.getenv("APP_BASE_URL", "https://ngx-intelligence.vercel.app")
    name = user_name or "Investor"
    subject = f"NGX Alert: {ticker} has {direction} ₦{threshold:,.2f}"

    html = dedent(f"""\
        <!DOCTYPE html>
        <html>
        <body style="font-family: Arial, sans-serif; background: #f9f9f9; padding: 24px;">
          <div style="max-width: 520px; margin: 0 auto; background: #fff; border-radius: 8px;
                      padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <h2 style="color: #1a1a2e; margin-top: 0;">Price Alert Triggered</h2>
            <p style="color: #444;">Hi {name},</p>
            <p style="color: #444;">
              Your alert for <strong>{ticker}</strong> has been triggered.
            </p>
            <div style="background: #f0f4ff; border-left: 4px solid #3b5bdb;
                        padding: 16px; border-radius: 4px; margin: 20px 0;">
              <p style="margin: 0; font-size: 14px; color: #555;">Price alert condition</p>
              <p style="margin: 4px 0 0; font-size: 22px; font-weight: bold; color: #1a1a2e;">
                {ticker} {direction} ₦{threshold:,.2f}
              </p>
              <p style="margin: 6px 0 0; font-size: 14px; color: #555;">
                Current price: <strong>₦{current_price:,.2f}</strong>
              </p>
            </div>
            <a href="{app_url}/app/stocks/{ticker}"
               style="display: inline-block; background: #3b5bdb; color: #fff;
                      padding: 12px 24px; border-radius: 6px; text-decoration: none;
                      font-weight: bold; margin-top: 8px;">
              View {ticker} Analysis
            </a>
            <hr style="margin: 28px 0; border: none; border-top: 1px solid #eee;" />
            <p style="font-size: 11px; color: #999;">
              This alert was triggered automatically by NGX Intelligence.<br/>
              AI signals are for informational purposes only and do not constitute
              financial advice. Past performance does not guarantee future results.
            </p>
          </div>
        </body>
        </html>
    """)

    text = dedent(f"""\
        NGX Intelligence — Price Alert Triggered

        Hi {name},

        Your alert for {ticker} has been triggered.

        {ticker} has {direction} ₦{threshold:,.2f}
        Current price: ₦{current_price:,.2f}

        View analysis: {app_url}/app/stocks/{ticker}

        This is an automated alert. AI signals are informational only and do
        not constitute financial advice.
    """)

    return subject, html, text


# ── core check ────────────────────────────────────────────────────────────────

def check_and_fire_alerts() -> dict[str, int]:
    """Synchronous core: check all active alerts against current prices.

    Returns a summary dict: {checked, triggered, emailed, errors}.
    Safe to call from a script, test, or admin endpoint.
    """
    from app.db.database import SessionLocal
    from app.db.models import Alert, User

    summary = {"checked": 0, "triggered": 0, "emailed": 0, "errors": 0}
    prices = _latest_prices()
    if not prices:
        logger.warning("alert_checker: no price data available — skipping check")
        return summary

    db: Session = SessionLocal()
    try:
        active_alerts = (
            db.query(Alert)
            .filter(Alert.status == "active")
            .all()
        )
        summary["checked"] = len(active_alerts)

        for alert in active_alerts:
            try:
                ticker = str(alert.ticker).upper().strip()
                current_price = prices.get(ticker)
                if current_price is None:
                    continue

                if not _is_triggered(alert.condition, current_price, alert.threshold):
                    continue

                alert.status = "triggered"
                alert.triggered_at = datetime.now(timezone.utc)
                alert.message = (
                    f"{ticker} {'rose above' if alert.condition.lower() in ('above','price_above','>') else 'fell below'} "
                    f"₦{alert.threshold:,.2f} — current price ₦{current_price:,.2f}"
                )
                db.flush()
                summary["triggered"] += 1

                user = db.query(User).filter(User.id == alert.user_id).one_or_none()
                if user and user.email:
                    subject, html, text = _build_email(
                        ticker=ticker,
                        condition=alert.condition,
                        threshold=alert.threshold,
                        current_price=current_price,
                        user_name=user.full_name,
                    )
                    if _send_email(user.email, user.full_name, subject, html, text):
                        summary["emailed"] += 1

                logger.info(
                    "alert_checker: fired alert %s for user %s — %s @ ₦%.2f (threshold ₦%.2f)",
                    alert.id,
                    alert.user_id,
                    ticker,
                    current_price,
                    alert.threshold,
                )

            except Exception as exc:
                logger.warning("alert_checker: error processing alert %s: %s", alert.id, exc)
                summary["errors"] += 1

        db.commit()
    except Exception as exc:
        logger.error("alert_checker: DB error during alert check: %s", exc)
        db.rollback()
        summary["errors"] += 1
    finally:
        db.close()

    logger.info(
        "alert_checker: checked=%d triggered=%d emailed=%d errors=%d",
        summary["checked"],
        summary["triggered"],
        summary["emailed"],
        summary["errors"],
    )
    return summary


# ── async loop ────────────────────────────────────────────────────────────────

async def alert_checker_loop() -> None:
    """Asyncio background task: run check_and_fire_alerts every CHECK_INTERVAL_SECONDS."""
    logger.info("alert_checker: background loop started (interval=%ds)", CHECK_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.get_event_loop().run_in_executor(None, check_and_fire_alerts)
        except asyncio.CancelledError:
            logger.info("alert_checker: background loop cancelled")
            break
        except Exception as exc:
            logger.error("alert_checker: unexpected error in loop: %s", exc)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
