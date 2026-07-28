from src.services.certificate_renderer import (
    CertificateImageRenderer,
    CertificatePayload,
)


def test_renderer_outputs_png_containing_certificate_content():
    payload = CertificatePayload(
        contest_title="Summer Cup",
        rank=1,
        recipient_name="Alice",
        wallet_address="So11111111111111111111111111111111111111112",
        final_equity="12850.42 USDT_TEST",
        roi="28.5042%",
        settlement_date="2026-07-28",
        snapshot_hash="abcdef1234567890",
    )

    png = CertificateImageRenderer().render_png(payload)

    assert png.startswith(b"\x89PNG")
    assert len(png) > 1000
