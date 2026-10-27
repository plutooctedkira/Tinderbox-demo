"""手搓一个最小 PDF（不依赖任何库），用来验证 pdf 提取。"""
from pathlib import Path

OUT = Path(r"E:\记忆库\.tmp")
OUT.mkdir(exist_ok=True)
target = OUT / "sample.pdf"

lines = [
    "Decision: shipping moves to Tuesday.",
    "Reason: the warehouse is closed on Monday.",
    "Courier: SF Express, stable but expensive.",
]

stream = "BT /F1 12 Tf 72 720 Td 14 TL\n"
for ln in lines:
    stream += f"({ln}) Tj T*\n"
stream += "ET"

objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
]

out = bytearray(b"%PDF-1.4\n")
offsets = []
for i, body in enumerate(objs, 1):
    offsets.append(len(out))
    out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")

xref_at = len(out)
out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
for off in offsets:
    out += f"{off:010d} 00000 n \n".encode()
out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n").encode()

target.write_bytes(bytes(out))
print(f"生成 {target}（{len(out)} 字节）")
