import re

# Compile Regex nur einmal fürs Performance-Plus
_pattern_cleanup = re.compile(r"[^A-ZÄÖÜ0-9]")
_pattern_kennzeichen = re.compile(r"^([A-ZÄÖÜ]{1,3})([A-ZÄÖÜ]{0,2})(\d{1,4}[A-Z]?)$")
_pattern_validate = re.compile(r"^[A-ZÄÖÜ]{1,3}\s?[A-ZÄÖÜ]{0,2}\s?\d{1,4}[A-Z]?$")

# Mapping der häufigsten OCR-Fehler – in-place übersichtlich
_error_map = str.maketrans({
    "O": "0",
    "I": "1",
    "B": "8",
    "Z": "7",  # Z wird oft für 7 gehalten
})

def format_plate(text: str) -> str:
    """Formatiert rohen OCR-Text zu einem standardisierten deutschen Kennzeichen."""
    if not isinstance(text, str) or len(text) < 4:
        return text

    text = text.strip().upper()

    # Führendes 'D' entfernen, falls von EU-Symbol
    if text.startswith("D") and len(text) > 4:
        text = text[1:]

    # Zeichen filtern und häufige OCR-Fehler korrigieren
    cleaned = _pattern_cleanup.sub("", text).translate(_error_map)

    match = _pattern_kennzeichen.match(cleaned)
    if match:
        parts = match.groups()
        return " ".join(filter(None, parts))

    return cleaned  # Fallback falls kein klares Kennzeichen erkannt

def validate_plate(text: str) -> bool:
    """Prüft, ob ein Text einem deutschen Kennzeichenformat entspricht."""
    return bool(_pattern_validate.match(text))
