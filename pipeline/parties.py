"""Party label normalisation. Model parties: DEM, REP, IND (independent / third party treated as its own)."""
from __future__ import annotations

_MAP = {
    "democratic": "DEM", "democrat": "DEM", "dem": "DEM", "dfl": "DEM", "democratic-farmer-labor": "DEM",
    "republican": "REP", "rep": "REP", "gop": "REP",
    "libertarian": "LIB", "lib": "LIB",
    "green": "GRN", "grn": "GRN", "pacific green": "GRN", "green mountain": "GRN",
    "independent": "IND", "ind": "IND",
}


def norm_party(label: str | None) -> str:
    if label is None:
        return "OTH"
    key = str(label).strip().lower()
    if key in _MAP:
        return _MAP[key]
    if "democrat" in key:  # Democratic–NPL (ND), Progressive/Democratic (VT)
        return "DEM"
    if "republican" in key:
        return "REP"
    return "OTH"
