import re
import zlib
from pathlib import Path

def parse_cmap(cmap_text):
    char_map = {}
    for block in re.findall(r"beginbfchar(.*?)endbfchar", cmap_text, re.DOTALL):
        for line in block.strip().splitlines():
            line = line.strip()
            m = re.findall(r"<([0-9a-fA-F]+)>", line)
            if len(m) >= 2:
                src = int(m[0], 16)
                dst = chr(int(m[1], 16))
                char_map[src] = dst

    for block in re.findall(r"beginbfrange(.*?)endbfrange", cmap_text, re.DOTALL):
        for line in block.strip().splitlines():
            line = line.strip()
            m = re.findall(r"<([0-9a-fA-F]+)>", line)
            if len(m) == 3:
                start = int(m[0], 16)
                end = int(m[1], 16)
                dst_start = int(m[2], 16)
                for code in range(start, end + 1):
                    char_map[code] = chr(dst_start + (code - start))
    return char_map

def extract_pdf_text_pure(pdf_bytes):
    all_cmaps = {}
    for m in re.finditer(b"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.DOTALL):
        raw = m.group(1)
        try:
            decomp = zlib.decompress(raw)
        except Exception:
            decomp = raw
        if b"begincmap" in decomp:
            text = decomp.decode("latin1", errors="ignore")
            cm = parse_cmap(text)
            all_cmaps.update(cm)

    extracted_lines = []
    for m in re.finditer(b"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.DOTALL):
        raw = m.group(1)
        try:
            decomp = zlib.decompress(raw)
        except Exception:
            decomp = raw
        if b"BT" in decomp and b"ET" in decomp:
            # Process TJ blocks
            for tj_match in re.finditer(rb"\[(.*?)\]\s*TJ", decomp, re.DOTALL):
                tj_block = tj_match.group(1)
                parts = []
                for sub in re.finditer(rb"\(((?:\\.|[^\)])*)\)|<([0-9a-fA-F]+)>", tj_block):
                    if sub.group(1) is not None:
                        s = sub.group(1)
                        # Handle escaped parens/backslashes
                        s = s.replace(b"\\)", b")").replace(b"\\(", b"(").replace(b"\\\\", b"\\")
                        chars = []
                        for i in range(0, len(s), 2):
                            if i + 1 < len(s):
                                code = (s[i] << 8) | s[i+1]
                                chars.append(all_cmaps.get(code, chr(s[i])))
                            else:
                                chars.append(chr(s[i]))
                        parts.append("".join(chars))
                    elif sub.group(2) is not None:
                        h = sub.group(2).decode("ascii")
                        chars = []
                        for i in range(0, len(h), 4):
                            code = int(h[i:i+4], 16)
                            chars.append(all_cmaps.get(code, "?"))
                        parts.append("".join(chars))
                if parts:
                    line_text = "".join(parts).strip()
                    if line_text:
                        extracted_lines.append(line_text)

            # Process Tj blocks
            for s in re.findall(rb"\(((?:\\.|[^\)])*)\)\s*Tj", decomp, re.DOTALL):
                s = s.replace(b"\\)", b")").replace(b"\\(", b"(").replace(b"\\\\", b"\\")
                chars = []
                for i in range(0, len(s), 2):
                    if i + 1 < len(s):
                        code = (s[i] << 8) | s[i+1]
                        chars.append(all_cmaps.get(code, chr(s[i])))
                    else:
                        chars.append(chr(s[i]))
                line_text = "".join(chars).strip()
                if line_text:
                    extracted_lines.append(line_text)

    return "\n".join(extracted_lines)

if __name__ == "__main__":
    pdf_path = Path("650346192-jio-bill-pdf-1_compress.pdf")
    if pdf_path.exists():
        data = pdf_path.read_bytes()
        text = extract_pdf_text_pure(data)
        print("=== EXTRACTED TEXT FROM USER PDF ===")
        print(text)
        print("====================================")
    else:
        print("File not found:", pdf_path)
