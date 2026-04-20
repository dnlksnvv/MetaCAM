"""Gerber statement splitting (FlatCAM line_generator semantics)."""


def trim_rn(s: str) -> str:
    s = s.strip(" \t")
    while s and s[-1] in "\r\n \t":
        s = s[:-1]
    return s


def statements_from_bytes(data: bytes) -> list[str]:
    out: list[str] = []
    for raw in data.splitlines():
        line = trim_rn(raw.decode("utf-8", errors="replace"))
        while line:
            if line.endswith("%"):
                out.append(line)
                break
            star = line.find("*")
            if star >= 0:
                out.append(line[: star + 1])
                line = trim_rn(line[star + 1 :])
                continue
            out.append(line)
            break
    return out
