def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    """Safe division returning None on zero denominator or None inputs."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    return numerator / denominator
