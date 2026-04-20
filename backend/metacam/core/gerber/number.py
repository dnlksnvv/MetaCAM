def pow10(n: int) -> float:
    if n >= 0:
        x = 1.0
        for _ in range(n):
            x *= 10.0
        return x
    x = 1.0
    for _ in range(-n):
        x /= 10.0
    return x


def parse_gerber_number(s: str, int_digits: int, frac_digits: int, zeros: str) -> float:
    if not s:
        raise ValueError("empty number")
    v = int(s, 10)
    if zeros in ("L", "D"):
        return float(v) * pow10(-frac_digits)
    if zeros == "T":
        exp = (int_digits + frac_digits) - len(s)
        if exp < 0:
            exp = 0
        return float(v) * pow10(exp) * pow10(-frac_digits)
    return float(v) * pow10(-frac_digits)
