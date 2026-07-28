from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class CertificatePayload:
    contest_title: str
    rank: int
    recipient_name: str
    wallet_address: str
    final_equity: str
    roi: str
    settlement_date: str
    snapshot_hash: str


class CertificateImageRenderer:
    width = 1600
    height = 1000

    def render_png(self, payload: CertificatePayload | dict) -> bytes:
        data = self._payload_dict(payload)
        image = Image.new("RGB", (self.width, self.height), "#0f172a")
        draw = ImageDraw.Draw(image)

        draw.rounded_rectangle((80, 80, 1520, 920), radius=32, fill="#f8fafc")
        draw.rectangle((80, 80, 1520, 150), fill="#111827")
        draw.text(
            (800, 118),
            "Crypto DEX Trading Contest",
            anchor="mm",
            font=_font(46, bold=True),
            fill="#ffffff",
        )
        draw.text(
            (800, 250),
            _fit_text(draw, data["contest_title"], _font(48, bold=True), 1280),
            anchor="mm",
            font=_font(48, bold=True),
            fill="#0f172a",
        )
        draw.text(
            (800, 385),
            f"Top {data['rank']}",
            anchor="mm",
            font=_font(98, bold=True),
            fill="#2563eb",
        )
        draw.text(
            (800, 510),
            _fit_text(draw, data["recipient_name"], _font(58, bold=True), 1200),
            anchor="mm",
            font=_font(58, bold=True),
            fill="#111827",
        )
        draw.text(
            (800, 595),
            _short_wallet(data["wallet_address"]),
            anchor="mm",
            font=_font(32),
            fill="#475569",
        )
        draw.text(
            (800, 700),
            f"{data['final_equity']}  |  ROI {data['roi']}",
            anchor="mm",
            font=_font(38, bold=True),
            fill="#111827",
        )
        draw.text(
            (800, 790),
            f"Settled {data['settlement_date']}  |  Snapshot {_short_hash(data['snapshot_hash'])}",
            anchor="mm",
            font=_font(28),
            fill="#64748b",
        )

        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    @staticmethod
    def _payload_dict(payload: CertificatePayload | dict) -> dict:
        if isinstance(payload, CertificatePayload):
            return {
                "contest_title": payload.contest_title,
                "rank": payload.rank,
                "recipient_name": payload.recipient_name,
                "wallet_address": payload.wallet_address,
                "final_equity": payload.final_equity,
                "roi": payload.roi,
                "settlement_date": payload.settlement_date,
                "snapshot_hash": payload.snapshot_hash,
            }
        return dict(payload)


def _font(size: int, bold: bool = False):
    names = (
        ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"]
        if bold
        else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    value = text
    while draw.textlength(value, font=font) > max_width and len(value) > 4:
        value = f"{value[:-4]}..."
    return value


def _short_wallet(wallet: str) -> str:
    if len(wallet) <= 12:
        return wallet
    return f"{wallet[:6]}...{wallet[-6:]}"


def _short_hash(value: str) -> str:
    if len(value) <= 16:
        return value
    return f"{value[:12]}..."
