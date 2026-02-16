"""
Minimal server-side PDF generator without external dependencies.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime


class SimplePdfService:
    @staticmethod
    def _ascii_safe(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    @staticmethod
    def build_text_pdf(
        title: str,
        lines: list[str],
        footer: str | None = None,
    ) -> bytes:
        """
        Build a simple one-page text PDF.
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        safe_title = SimplePdfService._ascii_safe(title)[:110]
        safe_footer = SimplePdfService._ascii_safe(footer or "")[:110]

        printable_lines = [line.strip() for line in lines if line and line.strip()]
        printable_lines = printable_lines[:52]

        stream_chunks: list[str] = [
            "BT",
            "/F1 16 Tf",
            "50 800 Td",
            f"({safe_title}) Tj",
            "0 -24 Td",
            "/F1 10 Tf",
            f"(Generated: {SimplePdfService._ascii_safe(timestamp)}) Tj",
            "0 -20 Td",
            "/F1 11 Tf",
        ]

        for line in printable_lines:
            safe_line = SimplePdfService._ascii_safe(line)[:120]
            stream_chunks.append(f"({safe_line}) Tj")
            stream_chunks.append("0 -14 Td")

        if safe_footer:
            stream_chunks.extend([
                "0 -8 Td",
                "/F1 10 Tf",
                f"({safe_footer}) Tj",
            ])

        stream_chunks.append("ET")
        stream = "\n".join(stream_chunks).encode("latin-1", errors="ignore")

        objects: list[bytes] = []
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        )
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

        pdf = b"%PDF-1.4\n"
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf += f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"

        xref_pos = len(pdf)
        pdf += f"xref\n0 {len(offsets)}\n".encode("ascii")
        pdf += b"0000000000 65535 f \n"
        for offset in offsets[1:]:
            pdf += f"{offset:010d} 00000 n \n".encode("ascii")

        pdf += (
            b"trailer\n<< /Size "
            + str(len(offsets)).encode("ascii")
            + b" /Root 1 0 R >>\nstartxref\n"
            + str(xref_pos).encode("ascii")
            + b"\n%%EOF\n"
        )
        return pdf
