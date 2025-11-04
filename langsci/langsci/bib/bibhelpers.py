"""
Helper functions and constants for bibtools
"""

import re

from langsci.bib import bibpatterns

# Constants

# Fields to exclude from the output
excludefields = [
    "abstract",
    "language",
    "date-added",
    "date-modified",
    "rating",
    "keywords",
    "issn",
    "timestamp",
    "owner",
    "optannote",
    "optkey",
    "optmonth",
    "optnumber",
    "url_checked",
    "optaddress",
    "eprinttype",
    "bdsk-file-1",
    "bdsk-file-2",
    "bdsk-file-3",
    "bdsk-url-1",
    "bdsk-url-2",
    "bdsk-url-3",
]

# Fields to output; currently unused
FIELDS = [
    "key",
    "title",
    "booktitle",
    "author",
    "editor",
    "year",
    "journal",
    "volume",
    "number",
    "pages",
    "address",
    "publisher",
    "note",
    "url",
    "series",
]

"""
Name-like BibTeX fields
Deliberately omitted:
    "editora", "editorb", "commentator", "annotator", "foreword", "introduction",
    "afterword", "contributor", "organizer",
"""
name_fields = [
    "author",
    "editor",
    "bookauthor",
    "translator"
]

# Incollection-like BibTeX types
in_types = [
    "inproceedings",
    "incollection",
    "inbook",
]

# Helper functions, mostly parsing

def strip_braces(text):
    """Remove outermost braces from a string."""
    if text.startswith("{") and text.endswith("}"):
        return text[1:-1]
    return text

def strip_all_outermost_braces(text):
    """Remove all (balanced) outermost braces from a string, assuming no inner braces."""
    open_count = 0
    for char in text:
        if char == "{":
            open_count += 1
        else:
            break
    # Count trailing closing braces
    close_count = 0
    for char in reversed(text):
        if char == "}":
            close_count += 1
        else:
            break
    # Only strip if counts match and inner has no braces
    if open_count and open_count == close_count:
        inner = text[open_count: -close_count]
        if "{" not in inner and "}" not in inner:
            return inner
    return text

def add_braces(text):
    """Wrap a string in braces."""
    return "{" + text + "}"

def clean_and_brace_dict(data):
    """Clean string values in a dict and wrap them in braces."""
    data.pop("extrayear", None)
    for key in list(data.keys()):
        value = data[key]
        if not value or not isinstance(value, str):
            del data[key]
            continue
        cleaned = " ".join(value.strip().split())
        if cleaned == "":
            del data[key]
        else:
            data[key] = add_braces(cleaned)

def is_real_value(text):
    """
    Return True if x is a real BibTeX field value with entry content.

    Typically used to test the result of self.fields.get("field"),
    which may be None if the field is absent.
    A value is considered False if it is:
        - None or an empty string
        - Exactly "{}" (an empty braced value)
        - An injected error like "{\\biberror{...}}"
    """
    if text is None or text== "":
        return False
    if text== "{}":
        return False
    if text.startswith("{\\biberror{"):
        return False
    return True

def extract_url(tail: str) -> tuple[str, dict[str, str]]:
    """
    Extract a trailing URL from the tail string.
    Returns the cleaned tail and a dict with 'url' if matched.
    """
    tail = tail.strip("., ")
    metadata = {}
    match = re.search(rf"{bibpatterns.url_named}$", tail)
    if match:
        metadata["url"] = match.group("url")
        tail = tail[:match.start()].strip("., ")
        tail = re.sub(
            rf"(?i)[ .,;:]*{bibpatterns.url_cue}[ .,;:]*$",
            "",
            tail
        )
    return tail, metadata

def extract_doi(tail: str) -> tuple[str, dict[str, str]]:
    """
    Extract a trailing DOI from the tail string.
    Returns the cleaned tail and a dict with 'doi' if matched.
    """
    tail = tail.strip("., ")
    metadata = {}
    match = re.search(
        rf"(?:doi(?::| ) *)?{bibpatterns.doi_named}$",
        tail,
        re.IGNORECASE
    )
    if match:
        metadata["doi"] = match.group("doi")
        tail = tail[:match.start()].strip("., ")
    return tail, metadata

def extract_doiurl(tail: str) -> tuple[str, dict[str, str]]:
    """
    Extract a trailing URL and/or DOI from the tail string, in any order.
    Returns the cleaned tail and a dict with keys 'url' and/or 'doi' if matched.
    """
    tail = tail.strip("., ")
    metadata = {}

    # First pass: try URL
    tail, meta = extract_url(tail)
    metadata.update(meta)

    # Second pass: try DOI
    tail, meta = extract_doi(tail)
    metadata.update(meta)

    # Third pass: re-check tail has URL before DOI (unconventionally)
    if "url" not in metadata:
        tail, meta = extract_url(tail)
        metadata.update(meta)

    return tail, metadata

def extract_pubaddr(tail: str) -> tuple[str, dict[str, str]]:
    """
    Extract a trailing 'address: publisher' from the tail string.
    Returns the cleaned tail and a dict with 'address' and 'publisher' if matched.
    """
    tail = tail.strip("., ")
    metadata = {}
    match = bibpatterns.PUBADDR.search(tail)
    if match:
        tail = match.group("title") + match.group("endmark")
        tail = tail.strip(" .,")
        metadata["address"] = match.group("address")
        metadata["publisher"] = match.group("publisher")
    return tail, metadata

def extract_seriesnumber(tail: str) -> tuple[str, dict[str, str] | None]:
    """
    Extracts series and number from a trailing parenthetical like:
    'Language and Cognition (Studies in Linguistics 12)'
    Returns the cleaned title and a dict with 'series' and 'number' if matched.
    """
    match = bibpatterns.SERIESNUMBER.search(tail)
    if match:
        title = match.group("title").strip(" .")
        return title, {
            "series": match.group("series").strip(),
            "number": match.group("number").strip()
        }
    return tail, {}

def extract_pages_from_note(note):
    """
    Extracts pages from the head of a note.
    Used to post-process pages value in an unusually separated book reference.
    """
    if not note:
        return None, note
    match = re.match(rf"^ *{bibpatterns.pages}[ .,;:]*", note)
    if match:
        pages = match.group("pages").strip()
        cleaned_note = note[match.end():].lstrip()
        return pages, cleaned_note
    return None, note

def clean_booktitle(booktitle):
    """
    Remove trailing fragments like "pp.", "(pp.", "(pages", etc. from a greedy booktitle.
    """
    return re.sub(r"[.,]?\s*\(?\b(pp\.?|p\.)\b.*$", "", booktitle).strip()

def get_hyphen(value):
    """
    Identify hyphen
    """
    for hyphen in ("–", "—", "-"):  # en dash, em dash, hyphen-minus
        if hyphen in value:
            return hyphen
    return None

def is_joint_issue(value, hyphen):
    """
    Decides if value, e.g. "2-3", is likely a joint issue number.
    Used to post-process ambiguous number or pages value.
    """
    parts = value.split(hyphen)
    if len(parts) != 2:
        return False
    try:
        first = int(parts[0].strip())
        second = int(parts[1].strip())
        return 0 < second - first <= 3
    except ValueError:
        return False

def generate_key(entry: dict[str, str]) -> str:
    """
    Generate a citation key from author/editor and year/extrayear.
    Returns a string like 'Chomsky2021a' or 'SmithEtAl2020'.
    """
    creator = entry.get("author") or entry.get("editor") or ""
    creatorpart = "Anonymous"

    if creator:
        parts = creator.split(",")
        if parts:
            creatorpart = parts[0].replace(" ", "")

    year = entry.get("year", "")
    extrayear = entry.get("extrayear", "")
    if year and len(year) >= 4:
        yearpart = year[:4] + extrayear
    else:
        yearpart = "9999"

    andcount = creator.count(" and ")
    ampcount = creator.count("&")
    authorcount = 1 + andcount + ampcount

    if authorcount > 2:
        creatorpart += "EtAl"
    elif authorcount == 2:
        secondcreator = re.split(" and ", creator)[-1].strip()
        if "," in secondcreator:
            creatorpart += secondcreator.split(",")[0]
        elif " " in secondcreator:
            creatorpart += secondcreator.split(" ")[-1]
        else:
            creatorpart += secondcreator

    return creatorpart + yearpart
