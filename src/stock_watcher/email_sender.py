"""Email notification sender for stock alerts and daily summaries."""

from __future__ import annotations

import asyncio
import datetime as dt
import html
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from stock_watcher.config import EmailConfig
from stock_watcher.models import StockQuote


def _build_alert_html(code: str, name: str, rule_desc: str, price: float) -> str:
    """Build a simple HTML email body for a single alert."""
    return textwrap.dedent(f"""\
    <html><body style="font-family:sans-serif">
      <h2 style="color:#e74c3c">⚠️ 股票告警触发</h2>
      <table style="border-collapse:collapse;width:100%">
        <tr><td><b>代码</b></td><td>{html.escape(code)}</td></tr>
        <tr><td><b>名称</b></td><td>{html.escape(name)}</td></tr>
        <tr><td><b>现价</b></td><td>{price:.2f}</td></tr>
        <tr><td><b>条件</b></td><td>{html.escape(rule_desc)}</td></tr>
      </table>
      <p style="color:#888;font-size:small">— Stock Watcher</p>
    </body></html>
    """)


def _build_summary_html(quotes: dict[str, StockQuote]) -> str:
    """Build HTML daily summary of all monitored stocks."""
    rows = ""
    for code, q in sorted(quotes.items()):
        pct = f"{q.change_pct:+.2f}%" if q.change_pct is not None else "—"
        price = f"{q.price:.2f}" if q.price is not None else "—"
        color = "#27ae60" if q.change_pct is not None and q.change_pct >= 0 else "#e74c3c"
        rows += f"""<tr>
            <td>{html.escape(code)}</td><td>{html.escape(q.name or "—")}</td>
            <td>{price}</td>
            <td style="color:{color}">{html.escape(pct)}</td>
        </tr>\n"""

    return textwrap.dedent(f"""\
    <html><body style="font-family:sans-serif">
      <h2>📊 每日持仓汇总</h2>
      <p>{dt.datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
      <table style="border-collapse:collapse;width:100%" border="1" cellpadding="4">
        <tr style="background:#f0f0f0">
          <th>代码</th><th>名称</th><th>现价</th><th>涨跌幅</th>
        </tr>
        {rows}
      </table>
      <p style="color:#888;font-size:small">— Stock Watcher</p>
    </body></html>
    """)


async def send_email(
    cfg: EmailConfig,
    subject: str,
    body_html: str,
) -> bool:
    """Send an email via SMTP.  Returns True on success, False on failure."""
    if not cfg.is_configured:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr or cfg.username
    msg["To"] = cfg.to_addr
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    def _send() -> None:
        if cfg.smtp_port == 465:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
                smtp.login(cfg.username, cfg.password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(cfg.username, cfg.password)
                smtp.send_message(msg)

    try:
        await asyncio.to_thread(_send)
        return True
    except Exception:
        return False


def send_email_sync(
    cfg: EmailConfig,
    subject: str,
    body_html: str,
) -> bool:
    """Synchronous version for use outside async loops."""
    if not cfg.is_configured:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr or cfg.username
    msg["To"] = cfg.to_addr
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if cfg.smtp_port == 465:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
                smtp.login(cfg.username, cfg.password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(cfg.username, cfg.password)
                smtp.send_message(msg)
        return True
    except Exception:
        return False


def build_alert_email(
    code: str,
    name: str,
    rule_desc: str,
    price: float,
) -> tuple[str, str]:
    """Return (subject, html_body) for an alert email."""
    subject = f"🚨 告警：{name}（{code}）价格触发"
    body = _build_alert_html(code, name, rule_desc, price)
    return subject, body


def build_summary_email(
    quotes: dict[str, StockQuote],
) -> tuple[str, str]:
    """Return (subject, html_body) for a daily summary email."""
    date_str = dt.datetime.now().strftime("%Y-%m-%d")
    subject = f"📊 股票监控日报 — {date_str}"
    body = _build_summary_html(quotes)
    return subject, body
