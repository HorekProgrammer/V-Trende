"""Обложки-исключения, которые источники чартов не должны перезаписывать."""

MANUAL_COVERS = {
    ("music", "michael jackson|billie jean"): (
        "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/32/4f/fd/"
        "324ffda2-9e51-8f6a-0c2d-c6fd2b41ac55/074643811224.jpg/600x600bb.jpg"
    ),
}


def manual_cover(category: str, match_key: str) -> str | None:
    return MANUAL_COVERS.get((category, match_key))
