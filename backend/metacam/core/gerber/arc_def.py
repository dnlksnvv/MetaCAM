import math


def arc_points(
    center: tuple[float, float],
    radius: float,
    start: float,
    stop: float,
    cw: bool,
    steps_per_circle: int,
) -> list[tuple[float, float]]:
    direction = -1.0 if cw else 1.0
    s, e = start, stop
    if not cw and e <= s:
        e += 2 * math.pi
    if cw and e >= s:
        e -= 2 * math.pi
    angle = abs(e - s)
    steps = int(math.ceil(angle / (2 * math.pi) * float(steps_per_circle)))
    steps = max(2, steps)
    delta = direction * angle / float(steps)
    out: list[tuple[float, float]] = []
    for i in range(steps + 1):
        th = s + delta * float(i)
        out.append(
            (center[0] + radius * math.cos(th), center[1] + radius * math.sin(th))
        )
    return out
