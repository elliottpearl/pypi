"""
Reference normalization tool

Provides
- `Record`: class for parsing and processing one reference, accepting input 
    from a BibTeX entry or a bibliography entry.
- `normalize()`: function for processing the text of an BibTeX file or 
    a bibliography list.
"""

import sys
import re
import pprint
import glob
import string
import argparse
from datetime import datetime

from langsci.latex.asciify import asciify
from langsci.latex.delatex import dediacriticize
from langsci.bib import bibpatterns

# Dictionary of keys of processed entries, for detecting duplicates.
# Key: bibtex entry key (string)
# Value: Boolean flag (True) indicating seen
keys = {}  

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

# Name fields
name_fields = [
    "author", 
    "editor",
    "bookauthor",
    "translator"
]

def trim_braces(s):
    if s.startswith("{") and s.endswith("}"):
        return s[1:-1]
    return s
        
def add_braces(s):
    return "{" + s + "}"
    
def clean_and_brace_natural(d):
    for k in list(d.keys()):
        v = d[k]
        if not v or not isinstance(v, str):
            del d[k]
            continue
        cleaned = " ".join(v.strip().split())
        if cleaned == "":
            del d[k]
        else:
            d[k] = add_braces(cleaned)

def is_real_value(x):
    """
    Return True if x is a real BibTeX field value with entry content.

    Typically used to test the result of self.fields.get("field"), 
    which may be None if the field is absent. 
    A value is considered False if it is:
        - None or an empty string
        - Exactly "{}" (an empty braced value)
        - An injected error like "{\\biberror{...}}"
    """
    
    if x is None or x == "":
        return False
    if x == "{}":
        return False
    if x.startswith("{\\biberror{"):
        return False
    return True

def extract_url(tail: str) -> tuple[str, str | None]:
    """
    Extract an URL from the tail string, and return the cleaned tail and the URL.
    """
    match = re.search(r"(https?://[^ ]+)\.?$", tail)
    if match:
        url = match.group(1)
        clean_tail = tail[:match.start()].rstrip(" .,")
        return clean_tail, url
    return tail, None

def extract_doi(tail: str) -> tuple[str, str | None]:
    """
    Extract a DOI from the tail string, and return the cleaned tail and the DOI.
    """
    match = re.search(
        r"(?:doi(?::| )\s*)?(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\.?$",
        tail,
        re.IGNORECASE
    )
    if match:
        doi = match.group(1)
        clean_tail = tail[:match.start()].rstrip(" .,")
        return clean_tail, doi
    return tail, None
    
def extract_pubaddr(tail: str) -> tuple[str, dict[str, str]]:
    """
    Extract a trailing 'address: publisher' from the tail string.
    Returns the cleaned tail and a dict with 'address' and 'publisher' if matched.
    """
    match = re.search(r"^(.+?)([.!?]) ([^:]+?): ([^:]+?)\.?$", tail)
    if match:
        cleaned_tail = match.group(1)
        endmark = match.group(2)
        if endmark in "!?":
            cleaned_tail += endmark
        address = match.group(3).strip()
        publisher = match.group(4).strip()
        return cleaned_tail.strip(), {"address": address, "publisher": publisher}
    return tail, {}

def extract_seriesnumber(tail: str) -> tuple[str, dict[str, str] | None]:
    """
    Extracts series and number from a trailing parenthetical like:
    'Language and Cognition (Studies in Linguistics 12)'
    Returns the cleaned title and a dict with 'series' and 'number' if matched.
    """
    match = re.search(r"^(?P<newtitle>.*?)\s*\((?P<series>.+?)\s+(?P<number>[-.0-9/]+)\)\s*$", tail)
    if match:
        newtitle = match.group("newtitle").strip(" .")
        return newtitle, {
            "series": match.group("series").strip(),
            "number": match.group("number").strip()
        }
    return tail, None

def extract_pages_from_note(note):
    # Extracts pages from the head of a note.
    # Used to post-process pages value in unusually separated book reference.
    if not note:
        return None, note
    match = re.match(rf"^ *{bibpatterns.pages}[ .,;:]*", note)
    if match:
        pages = match.group("pages").strip()
        cleaned_note = note[match.end():].lstrip()
        return pages, cleaned_note
    return None, note

def clean_booktitle(booktitle):
    # Remove trailing fragments like "pp.", "(pp.", "(pages", etc. from a greedy booktitle.
    return re.sub(r"[.,]?\s*\(?\b(pp\.?|p\.)\b.*$", "", booktitle).strip()

def get_hyphen(value):
    for h in ("–", "—", "-"):  # en dash, em dash, hyphen-minus
        if h in value:
            return h
    return None

def is_joint_issue(value, hyphen):
    # Decides if value, e.g. "2-3", is likely a joint issue number.
    # Used to post-process ambiguous number or pages value.
    parts = value.split(hyphen)
    if len(parts) != 2:
        return False
    try:
        first = int(parts[0].strip())
        second = int(parts[1].strip())
        return 0 < second - first <= 3
    except ValueError:
        return False

class Record:
    """
    A bibliographic record parser, cleaner and formatter.
    
    The class processes a single bibliographic entry, from either BibTeX or bibliography list format.
    It parses the input entry, normalizes fields and their values, and prepares a clean BibTeX entry.

    Attributes:
        typ (str): BibTeX entry type (e.g., "article", "book").
        key (str): BibTeX entry key (e.g., "Smith2001").
        fields (dict): Parsed BibTeX field/value pairs.
        errors (list of str): Accumulated syntax warnings or parsing issues.
        reporting (list of str): Optional flags for controlling output verbosity. Possibly unused?
        inkeysd (dict): Keys to include in output if `restrict` is True.
        restrict (bool): Whether to limit output to keys in `inkeysd`.
        
    Methods:
        bibtex() -> str: Render the (normalized) entry as text in BibTeX format.

    Notes:
        - Input can be single BibTeX entry (without leading @) or a bibliography list entry.
        - BibTeX parsing uses the TYPKEYFIELDS regex from langsci.bib.bibpatterns to extract type and key.
        - Normalization may inject LaTeX-safe error messages in field values to flag missing or malformed fields.
            - During serial field checks, exactly these two errors may be injected.
                - `author = {Smith, John \biberror{et al}},` by checketal()
                - `url = {\biberror{remove space and check url: ...}},` by checkurl()
            - During parallel entry checks by type, required but missing fields are flagged.
                - e.g. `pages = {\biberror{no pages}},` for any required field, by handleerror()
        - Other warnings are printed by `self.errors`.  
            
    """

    def __init__(self, s, bibtexformat=False, inkeysd=None, restrict=False, reporting=None):
        """
        Initialize a Record instance.
        
        Parses a bibliographic record entry, either in BibTeX format or bibliography list format, 
        and prepares it for formatting and output. Also performs normalization and prints any syntax warnings.

        Args:
            s (str): Input entry as a string. In BibTeX (less leading '@') or bibliography list format.
            bibtexformat (bool, optional): 
                If True, uses `parse_bibtex()`; 
                otherwise uses `parse_natural()` for bibliograph list format.
            inkeysd (dict, optional): Dictionary of field keys to include in output if `restrict` is True.
            restrict (bool, optional): Whether to limit output to keys in `inkeysd`. Defaults to False.
            reporting (list of str, optional): Flags for controlling output verbosity. Defaults to None.

        Behavior:
            - Parses the input string using either `parse_bibtex()` or `parse_natural()`.
            - Calls `conform()` to normalize field values, first by field then by BibTeX entry type.
            - Calls `report()` to print accumulated syntax warnings (stored in `self.errors`).
        """
        
        self.raw_entry = s
        self.parsing_failed = False
        self.errors = []
        self.restrict = restrict
        self.inkeysd = inkeysd if inkeysd is not None else {}
        self.reporting = reporting if reporting is not None else []
        if bibtexformat:
            self.parse_bibtex(s)
        else:
            self.parse_natural(s)
        if not self.parsing_failed:
            self.conform()
            self.report()
 
    def parse_bibtex(self, s):
        """
        Parse a BibTeX entry
        
        Args:
            s (str): BibTex entry with leading '@' already removed.
            
        Expected Format:
            - Field values may be braced, unbraced, or quoted.
            - Quoted values must not contain quote marks (even escaped).
            - Field/value pairs are separated by a comma and newline. The final pair may omit the comma.
        
        Example:
            bibtype{bibkey,
                field1 = {value1},
                field2 = "value2",
                field3 = value3
            }

        Output:
            Populates `self.fields` with normalized field/value pairs. 
                - Quoted values are converted to braced format.
                - Braced or quoted values have whitespace collasped and trimmed.
                - Unbraced values are treated as raw strings with no whitespace.
                - Also sets `self.typ` and `self.key` for the BibTeX entry type and key, resp.

        Notes:
            - Parsing is naive.
            - The paser does not validate brace nesting or escape sequences.
            - The parser may fail if a field contains the sequence "},\n" within a properly balanced value.
        """
        
        m = re.match(bibpatterns.TYPKEYFIELDS, s)
        if not m:
            self.parsing_failed = True
            return
        
        self.typ = m.group(1).lower()
        self.key = m.group(2)
        remainder = m.group(3).strip()        

        # analyze remainder
        # remove possible comma at end of last field/value pair, to improve split
        remainder = re.sub(r'\s*,\s*}$', '}', remainder)

        # Split bibentry on closing brace followed by a comma and a newline
        lines = re.split(r"(?<=\})[ \t]*,[ \t]*\n\s*", remainder)

        # Clean all whitespace in lines
        lines = [re.sub(r'\s+', ' ', line.strip()) for line in lines]
        
        if not any(lines):
            self.errors.append("No valid field/value lines found")
            self.parsing_failed = True
            return

        # Parse line into field/value pair, 
        # first finding any unbraced values, 
        # then find any final braced value.
        self.fields = {}
        for line in lines:
            # print(f"Parsing line: {line}") # DEBUG
            while line:
                # Case: Braced value
                match = re.match(
                    r'^\s*(\w+)\s*=\s*\{\s*(.*?)\s*\}\s*,?\s*$', 
                    line
                )
                if match:
                    field, value = match.groups()
                    if value == "":
                        # print(f"Skipping empty braced value for field '{field}'") #DEBUG
                        break
                    self.fields[field.lower()] = add_braces(value)
                    break  # Braced value is terminal

                # Case: Quoted value (BUT no internal quote marks, even escaped) 
                match = re.match(
                    r'^\s*(\w+)\s*=\s*"\s*([^"]*?)\s*"\s*,?\s*(.*)$',
                    line
                )
                if match:
                    field, value, remainder = match.groups()
                    # print(f'Matched: field = {field}, value = "{value}", remainder = {remainder}') # DEBUG
                    field = field.lower()
                    if value:
                        if remainder:
                            self.fields[field] = add_braces(value)
                            line = remainder
                            continue
                        else:
                            self.fields[field] = add_braces(value)
                            break
                    else:
                        if remainder:
                            line = remainder
                            continue
                        else:
                            # print(f"Skipping empty quoted value for field '{field}'") # DEBUG
                            break

                # Case: Unbraced value
                match = re.match(
                    r'^\s*(\w+)\s*=\s*([^,{}"]*)\s*,?\s*(.*)$', 
                    line
                )
                if match:
                    field, value, remainder = match.groups()
                    # print(f'Matched: field = {field}, value = {value}, remainder = {remainder}') # DEBUG
                    field = field.lower()
                    if value:
                        if remainder:
                            self.fields[field] = value
                            line = remainder
                            continue
                        else:
                            self.fields[field] = value
                            break
                    else:
                        if remainder:
                            line = remainder
                            continue
                        else:
                            # print(f"Skipping empty unbraced value for field '{field}'") # DEBUG
                            break
                else:
                    break

        if not self.fields:
            self.errors.append("No fields parsed from BibTeX entry")
            self.parsing_failed = True
        
        # Check duplicate key
        if self.key in keys:
            self.errors.append("duplicate key %s" % self.key)
        keys[self.key] = True

    def parse_natural(self, s):
        s = s.strip()
        self.parsing_failed = False
        self.typ = "misc"
        self.key = None
        d = {}
        
        # Early exit for empty input
        if not s:
            self.parsing_failed = True
            return

        m = bibpatterns.MASTERSTHESIS.search(s)
        if m:
            self.typ = "mastersthesis"
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["address"] = m.group("address")
            d["school"] = m.group("publisher")
            d["note"] = m.group("note")
        elif (m := bibpatterns.PHDTHESIS.search(s)):
            self.typ = "phdthesis"
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["address"] = m.group("address")
            d["school"] = m.group("publisher")
            d["note"] = m.group("note")
        elif (bibpatterns.EDITOR.search(s)) and (m := bibpatterns.INCOLLECTION.search(s)):
            self.typ = "incollection"
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["editor"] = m.group("editor")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["booktitle"] = clean_booktitle(m.group("booktitle"))
            d["endmark1"] = m.group("endmark1")
            d["pages"] = m.group("pages")
            d["address"] = m.group("address")
            d["publisher"] = m.group("publisher")
            tail = d["publisher"]
            tail, url = extract_url(tail)
            if url:
                d["url"] = url
            tail, doi = extract_doi(tail)
            if doi:
                d["doi"] = doi
            d["publisher"] = tail.rstrip(" .") if tail.strip() else None
        elif (bibpatterns.EDITOR.search(s)) and (m := bibpatterns.INCOLLECTIONPARENS.search(s)):
            self.typ = "incollection"
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["editor"] = m.group("editor")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["booktitle"] = clean_booktitle(m.group("booktitle"))
            d["pages"] = m.group("pages")
            d["address"] = m.group("address")
            d["publisher"] = m.group("publisher")
            tail = d["publisher"]
            tail, url = extract_url(tail)
            if url:
                d["url"] = url
            tail, doi = extract_doi(tail)
            if doi:
                d["doi"] = doi
            d["publisher"] = tail.rstrip(" .") if tail.strip() else None
        elif (bibpatterns.EDITOR.search(s)) and (m := bibpatterns.INCOLLECTIONMISSING.search(s)):
            self.typ = "incollection"
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["editor"] = m.group("editor")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["booktitle"] = m.group("booktitle")
            tail = d["booktitle"]
            tail, url = extract_url(tail)
            if url:
                d["url"] = url
            tail, doi = extract_doi(tail)
            if doi:
                d["doi"] = doi
            tail, pubaddr = extract_pubaddr(tail)
            if pubaddr:
                d.update(pubaddr)
            d["booktitle"] = tail if tail.strip() else None
        elif (m := bibpatterns.ARTICLE.search(s)):
            self.typ = "article"
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["journal"] = m.group("journal")
            volume = (
                m.group("volume_paren")
                or m.group("volume_sep")
                or m.group("volume_only")
            )
            number = (
                m.group("number_paren")
                or m.group("number_sep")
            )
            pages = m.group("pages")
            note = m.group("note")
            d["volume"] = volume
            if number:
                d["number"] = number
            if pages:
                d["pages"] = pages
            else:
                hyphen = get_hyphen(number)
                if hyphen:
                    extracted_pages, cleaned_note = extract_pages_from_note(note)
                    is_joint = is_joint_issue(number, hyphen)
                    if is_joint and extracted_pages:
                        # case 1 "Journal of Syntax 12, 2–4. 55–70"
                        d["number"] = number
                        d["pages"] = extracted_pages
                        note = cleaned_note
                    elif is_joint and not extracted_pages:
                        # case 2 "Journal of Syntax 12, 2–4"
                        # Ambiguous. Examine original separator between bolume and number? Probe if doi or url exists?
                        d["pages"] = number
                        d["number"] = None
                    elif not is_joint and extracted_pages:
                        # case 3 "Journal of Syntax 12, 55–70. 200–215"
                        # This should never happen
                        d["pages"] = number + ", " + extracted_pages
                        note = cleaned_note
                    else: # not is_joint_issue and not extracted_pages
                        # case 4 "Journal of Syntax 12, 99–113"
                        d["pages"] = number
                        d["number"] = None # This will be deleted in final processing before d is assigned to self.fields
            d["note"] = note
        elif (m := bibpatterns.BOOK.match(s)):
            editor_flag = m.group("ed")
            has_pubaddr = bibpatterns.PUBADDR.search(s)
            if (editor_flag or has_pubaddr):
                self.typ = "book"
                self.parsing_failed = False
                d["author"] = m.group("author")
                if editor_flag:
                    d["editor"] = m.group("author")
                    d["author"] = None
                d["year"] = m.group("year")
                d["extrayear"] = m.group("extrayear")
                d["title"] = m.group("title")
                tail = d["title"]
                tail, url = extract_url(tail)
                if url:
                    d["url"] = url
                tail, doi = extract_doi(tail)
                if doi:
                    d["doi"] = doi
                if has_pubaddr:
                    tail, pubaddr = extract_pubaddr(tail)
                    if pubaddr:
                        d.update(pubaddr)
                tail, seriesnumber = extract_seriesnumber(tail)
                if seriesnumber:
                    d.update(seriesnumber)
                d["title"] = tail if tail.strip() else None
        elif (m := bibpatterns.MISC.search(s)):
            self.typ = "misc"
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["note"] = m.group("note")

        if self.parsing_failed:
            return

        # Find doi and url in note; clean note
        note = d.get("note")
        if isinstance(note, str) and note.strip():
            note, url = extract_url(note)
            if url:
                d["url"] = url
            note, doi = extract_doi(note)
            if doi:
                d["doi"] = doi
            d["note"] = note.strip(" .") if note.strip(" .") else None            

        # Restore endmark to title
        if d.get("endmark"):
            if d["endmark"] in {"!", "?"} and d.get("title"):
                d["title"] += d["endmark"]
            d.pop("endmark", None)
        # Restore endmark1 to booktitle
        if d.get("endmark1"):
            if d["endmark1"] in {"!", "?"} and d.get("booktitle"):
                d["booktitle"] += d["endmark1"]
            d.pop("endmark1", None)

        # Replace ampersand in author or title
        if d.get("author"):
            d["author"] = d["author"].replace(" &", " and ")
        if d.get("editor"):
            d["editor"] = d["editor"].replace(" &", " and ")

        # Find series and number in booktitle
        booktitle = d.get("booktitle")
        if booktitle:
            tail, seriesnumber = extract_seriesnumber(booktitle)
            if seriesnumber:
                d.update(seriesnumber)
                d["booktitle"] = tail if tail.strip() else None

        # Set key from author/editor, year, extrayear
        creator = ""
        creatorpart = "Anonymous"
        yearpart = "9999"
        author = d.get("author")
        editor = d.get("editor")
        if author:
            creator = author
            try:
                creatorpart = author.split(",")[0].replace(" ", "")
            except Exception:
                pass
        elif editor:
            creator = editor
            try:
                creatorpart = editor.split(",")[0].split(" ")[0]
            except Exception:
                pass
        year = d.get("year")
        extrayear = d.get("extrayear", "")
        if year:
            try:
                yearpart = year[:4] + extrayear
            except Exception:
                pass
        d.pop("extrayear", None)  # remove extrayear if present

        andcount = creator.count(" and ") if creator else 0
        ampcount = creator.count("&") if creator else 0
        authorcount = 1 + andcount + ampcount
        if authorcount > 2:
            creatorpart += "EtAl"
        if authorcount == 2:
            try:
                secondcreator = re.split(" and ", creator)[-1].strip()
                if "," in secondcreator:
                    creatorpart += secondcreator.split(",")[0]
                elif " " in secondcreator:
                    creatorpart += secondcreator.split(" ")[-1]
                else:
                    creatorpart += secondcreator
            except Exception:
                pass
        self.key = creatorpart + yearpart

        clean_and_brace_natural(d)
        self.fields = d

    def conform(self):
        """
        Normalize and validate BibTeX fields.
        
        This method runs a series of field-level checks and corrections to ensure consistency,
        formatting, and completeness of the BibTeX record. It may inject LaTeX messages into 
        fields to flag missing or malformed data.

        Notes:
            - Removed legacy logic that set `booktitle = title` when an editor was present. See `checkbooktitle`.
            - Refactored `conformtitles` and `checkdecapitalizationprotection` into `checbookktitle` and `checkdecapitalization`.
            - Renamed `conforminitials` to `checkinitials`, `correctampersand` to `checkampersand`.
        """

        # Field checks, serially
        self.remap_fields()
        self.checkpages()
        self.checkbooktitle() 
        self.checkvolumenumber()
        self.checkinitials()
        self.checkampersand()
        self.checketal()
        self.checkand()
        self.checkedition()
        self.checkurl()
        self.checkurldate()
        self.checkdoi()
        self.checkquestionmarks()
        self.checkbookisthesis()
        self.checkmonth()
        self.checkdecapitalization()

        # Entry checks in parallel by BibTeX type (= `self.typ`)
        self.checkarticle()
        self.checkthesis()
        self.checkbook()
        self.checkincollection()
        self.checkinproceedings()
        self.checkinbook()
        self.checkmisc()
        self.checkothertype()

    def report(self):
        """
        print errors, if any
        """
        
        try:
            if len(self.errors) > 0:
                if self.restrict == False or self.inkeysd.get(self.key):
                    print(self.key, "\n  ".join(["  "] + self.errors))
        except AttributeError:
            pass

    def remap_fields(self):
        """
        Remap some field names
        """
        
        fieldaliases = (
            ("location", "address"),
            ("date", "year"),
            ("journaltitle", "journal"),
        )
        # General field remapping
        for old, new in fieldaliases:
            old_val = self.fields.get(old)
            new_val = self.fields.get(new)
            
            if is_real_value(old_val):
                if not is_real_value(new_val):
                    self.fields[new] = old_val
                    self.errors.append(f"Remapped '{old}' to '{new}'")
                    del self.fields[old]
                else:
                # Both fields exist—log but preserve both
                    self.errors.append(f"Both '{old}' and '{new}' present; no remap applied")

        # Special case: eventtitle → booktitle for inproceedings
        if self.typ == "inproceedings":
            eventtitle = self.fields.get("eventtitle")
            booktitle = self.fields.get("booktitle")
            if is_real_value(eventtitle) and not is_real_value(booktitle):
                self.fields["booktitle"] = eventtitle
                self.errors.append("Remapped 'eventtitle' to 'booktitle'")
    
    def checkpages(self):
        """
        Check "pages" field
        """
        
        # Convert "page" to "pages" if needed, e.g. typo "page = {12--34},"
        if "page" in self.fields and "pages" not in self.fields:
            self.fields["pages"] = self.fields["page"]
            del self.fields["page"]

        # If "pages" is missing, exit gracefully
        if "pages" not in self.fields or not self.fields["pages"].strip():
            return ""

        pages = self.fields["pages"]
        pages = trim_braces(pages)
        
        # Delete empty pages
        if pages == '':
            del self.fields["pages"]
            return ""
        
        # Delete placeholder "pages = {none},"
        if pages.lower() == "none":
            del self.fields["pages"]
            return ""
        
        # Delete pages like a page count, "pages = {123 pp.},"
        if re.match(r"^\d+\s*(pp\.?|pages)$", pages, re.IGNORECASE):
            del self.fields["pages"]
            return ""

        # Normalize dashes (U+2012 figure dash, U+2013 en dash, U-2014 em dash, U+2212 minus sign) and trim whitespace
        pages = re.sub(r"\s*(?:-+|‒|–|—|−)+\s*", "--", pages)

        # Replace semicolons with commas for multiple ranges
        pages = re.sub(r"\s*[;,]\s*", ", ", pages)
        
        # Parse article id by changing it to pages, e.g. "pages = {Article ID 34}," to "pages = {34},"
        match = bibpatterns.ARTICLE_ID_RE.match(pages)
        pages = match.group(1) if match else pages

        # Flag nonstandard pages
        unit = r'(?:[a-zA-Z]?\d+|[ivxlcdm]+)'
        range_ =  fr'{unit}--{unit}'
        entry = fr'(?:{unit}|{range_})'
        pattern = re.compile(fr'^{entry}(?:, {entry})*$')
        if not pattern.match(pages):
            self.errors.append(f"non-standard pages: {pages}")
            
        # Flag capital Roman numerals
        range_Roman = re.compile(fr'^[IVXLCDM]+--[IVXLCDM]+$')
        if range_Roman.match(pages):
            self.errors.append(f"capital Roman numerals in pages: {pages}")
            
        # Flag redundant range, e.g. 12--12
        range_capture = re.compile(fr'({unit})--({unit})')
        match = range_capture.fullmatch(pages)
        if match:
            start, end = match.groups()
            if start == end:
                self.errors.append(f"weird range: {pages}")

        self.fields["pages"] = add_braces(pages)

    def checkdecapitalization(self):
        """
        Apply decapitalization protection, i.e. curly braces {}, to all title-like fields
        Decapitalization applies to:
            likely titles of proceedings, via bibpatterns.PROCEEDINGS_RE
            propernouns, via bibpatterns.PRESERVATIONPATTERN
            first word of a likely subtitle, e.g. "title = {Syntax: The comma}," -> "title = {Syntax: {T}he comma},"
            Binnenmajuskeln, (conference) acronyms or InterCaps, e.g. OpenAI, ICPhS
            lone capitals
        Skipped if langid is "german", "ngerman", or "de"
        """
        
        if "langid" in self.fields:
            langid = self.fields["langid"]
            langid = trim_braces(langid)
            if langid in ["german", "ngerman", "de"]:
                return ""
        title_fields = [
            "title", "booktitle", "subtitle", "maintitle", "mainsubtitle", "booksubtitle", 
        ] 
        for field in title_fields:
            original = self.fields.get(field)
            if not original:
                continue 
            original = trim_braces(original)
            protected = original
            
            # Capitalize and protect first letter after a space after colon, question mark, or exclamation mark, as a subtitle
            # Example: "Maintitle: the subtitle" → "Maintitle: {T}he subtitle"
            protected = bibpatterns.MAINTITLE_RE.sub(
                lambda match: match.group(1) + " " + add_braces(match.group(2).upper()),
                protected
            )
            
            # Protect Binnenmajuskeln, acronyms, InterCaps
            protected = bibpatterns.CAMELCASE_RE.sub(r"{\1}", protected)

            # Protect lone capitals (e.g., " A " → " {{A}} ")
            protected = re.sub(r" ([A-Z]) ", r" {{\1}} ", protected)

            # Protect proper nouns
            for match in bibpatterns.PRESERVATIONPATTERN.finditer(protected):
                group = match.group(1)
                protected = protected.replace(group, "{%s}" % group)

            # Protect entire title of proper name of conference/proceedings, trusting original capitalization 
            if bibpatterns.PROCEEDINGS_RE.search(protected):
                protected = add_braces(protected)
            
            # Flag title with lowercase conference/proceedings keyword
            if bibpatterns.PROCEEDINGS_LC_RE.search(protected):
                self.errors.append(f"Proper name of proceedings/conference not capitalized/protected?: {protected}")
            
            if original != protected:
                self.fields[field] = add_braces(protected)
                if "nouns" in self.reporting or "conferences" in self.reporting:
                    print(original, " ==> ", protected)

    def checkbooktitle(self):
        """
        Move booktitle to title if no title but booktitle exists and doesn't belong in the entry type.
        E.g. @book with "booktitle = {Syntax}," should be "title = {Syntax},"
        """

        title = self.fields.get("title")
        booktitle = self.fields.get("booktitle")
        
        if self.typ not in {"inproceedings", "incollection", "inbook"}:
            if not is_real_value(title) and is_real_value(booktitle):
                self.fields["title"] = self.fields["booktitle"]
                self.errors.append(f"moved booktitle to title")
                del self.fields["booktitle"]

    def move_volume(self, fieldname):
        """
        Extract volume info title-like field (i.e. title or booktitle), 
        move it to self.fields['volume'], and clean up the original field.
        """
        
        # Short-circuit if field is missing or not meaningful
        if fieldname not in self.fields or not is_real_value(self.fields[fieldname]):
            return
        
        value = self.fields[fieldname]
        
        match = bibpatterns.TITLEVOLUME_RE.search(value)
        if not match:
            return  # No volume pattern found
        
        volume_match = match.group(3)
        volumepattern_match = match.group()
        
        # Isolate title by removing volume_patternmatch
        titlelike = value.replace(volumepattern_match, "")

        # Clean up trailing punctuation 
        trailing_re = re.compile(r'^\{(.*?)[,:;. ]+\}$')
        trailing_match = trailing_re.search(titlelike)
        if trailing_match:
            titlelike = add_braces(trailing_match.group(1))

        # Clean up leading punctuation
        leading_re = re.compile(r'^\{[,:;. ]+(.*?)\}$')
        leading_match = leading_re.search(titlelike)
        if leading_match:
            titlelike = add_braces(leading_match.group(1))

        # If cleanup results in empty braces, log and exit
        if titlelike == "{}":
            self.errors.append(f"{fieldname} is just {self.fields[fieldname]}")
            return
        
        # Write volume
        if "volume" in self.fields:
            volume_old = trim_braces(self.fields["volume"])
            if volume_old == volume_match:
                self.fields[fieldname] = titlelike
                self.errors.append(f"deleted redundant volume in {fieldname}")
            else:
                self.errors.append(f"mismatch: volume {volume_old} but {self.fields[fieldname]}")
        else:
            self.fields[fieldname] = titlelike
            self.fields["volume"] = add_braces(volume_match)
            self.errors.append(f"Moved volume {volume_match} from {fieldname}")    
    
    def checkvolumenumber(self):
        """
        Move volume indication from title field to volume field for a book.
        Do this volume move for the booktitle field in incollection-like bibentry types (incollection, inproceedings, inbook).
        """
        
        # For book, move volume indication from title if found
        if self.typ == "book":
            self.move_volume("title")
        # For in incollection-like type, move volume indication from booktitle if found
        if self.typ in ["incollection", "inproceedings", "inbook"]:
            self.move_volume("booktitle")

    def checkinitials(self):
        """
        Make sure that initials have a space between them and that initials have a period
        Flag double initials (e.g. "Watt, JJ"
        """
        
        capcap_re = re.compile(r' [A-Z][A-Z] ')
        finalcapcap_re = re.compile(r' [A-Z][A-Z]}$')
        for t in name_fields:
            value = self.fields.get(t)
            if is_real_value(value):
                value = re.sub(r"([A-Z])\.([A-Z])", r"\1. \2", value)
                value = re.sub(" ([A-Z])(?= )", r" \1.", value)
                value = re.sub(" ([A-Z])}$", r" \1.}", value)
                if capcap_re.search(value) or finalcapcap_re.search(value):
                    self.errors.append(f"possible double initials: {self.fields[t]}")
                self.fields[t] = value

    def checkampersand(self):
        """
        Replace "&" by " and " as required by BibTeX, or escape as required by LaTeX.
        Flag any other unescape ampersand.
        """
        
        for t in name_fields:
            value = self.fields.get(t)
            if is_real_value(value):
                value = value.replace(r" & ", " and ")
                value = value.replace(r" \& ", " and ")
                self.fields[t] = value
                if bibpatterns.AMP_RE.search(value):
                    self.errors.append(f"unescaped ampersand {t}: {value}")

        for t in [
            "address", "publisher", "school", "institution", "journal", "series", 
            "title", "booktitle", "maintitle", "subtitle", 
            "volume", "number", "note", "howpublished", "addendum"
        ]:
            value = self.fields.get(t)
            if is_real_value(value):
                value = value.replace(r" & ", " \& ")
                self.fields[t] = value
                if bibpatterns.AMP_RE.search(value):
                    self.errors.append(f"unescaped ampersand {t}: {value}")

    def checkand(self):
        """
        Check whether commas are used instead of 'and' (asyndetic coordination)
        """
        
        for t in name_fields:
            value = self.fields.get(t)
            if is_real_value(value):
                ands = value.count(" and ")
                commas = value.count(",")
                if commas > ands + 1:
                    self.errors.append(f"problem with commas in {t}: {value}")

    def checketal(self):
        """
        Check whether literal 'et al' is used in author or editor fields
        """

        for t in name_fields:
            name = self.fields.get(t)
            if name:
                if re.search(r" et\.? al", name):
                    self.fields[t] = re.sub(
                        r" et\.? al",
                        r" \\biberror{et al}",
                        name
                    )
                    self.errors.append(f"literal et al {t}: {self.fields[t]}")

    def checkedition(self):
        """
        Check the correct format of the edition field (a numeral)
        Extract edition numeral if found, e.g. "edition = {3rd ed.}"
        Otherwise log an error, but do not change edition field
        """

        edn = self.fields.get("edition")
        if not edn:
            return  # Graceful exit if no edition field
                
        raw = edn  # Preserve original for logging if needed
                
        # Strip braces, trim whitespace, and lowercase
        edn = trim_braces(edn)
        edn = edn.lower()  

        ordinal_map = {
            "first": "1", "1st": "1",
            "second": "2", "2nd": "2",
            "third": "3", "3rd": "3",
            "fourth": "4", "4th": "4",
            "fifth": "5", "5th": "5",
            "sixth": "6", "6th": "6",
            "seventh": "7", "7th": "7",
            "eighth": "8", "8th": "8",
            "ninth": "9", "9th": "9",
            "tenth": "10", "10th": "10"
        }
        edition_keywords = {"ed", "ed.", "edn", "edn.", "edition"}
        
        parts = edn.split()
        candidate = None
        if (len(parts) == 2 and parts[1] in edition_keywords) or len(parts) == 1:
            candidate = parts[0]
        if candidate:
            if candidate.isdigit():
                edn = candidate
            elif candidate in ordinal_map:
                edn = ordinal_map[candidate]
        try:
            int(edn)
            self.fields["edition"] = add_braces(edn)
        except ValueError:
            self.errors.append("incorrect format for edition: %s" % raw)

    def checkmonth(self):
        """
        Normalize month. Output numerical month in braces.
        The month field is not actually used by the bibliography style.
        """

        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, 
            "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        }

        raw = self.fields.get("month")

        if not raw:
            return
        if raw == "{}":
            del self.fields["month"]
            return

        cleaned = raw
        # Strip braces, and lowercase
        if "{" in cleaned:
            cleaned = trim_braces(cleaned)
        cleaned = cleaned.lower()
        # Remove leading zero if present
        if cleaned.startswith("0") and len(cleaned) == 2:
            cleaned = cleaned[1:]
        # Convert letter month to number if needed
        if cleaned in month_map:
            cleaned = str(month_map[cleaned])

        # Validate numeric month
        try:
            cleaned_num = int(cleaned)
            if 1 <= cleaned_num <= 12:
                self.fields["month"] = add_braces(cleaned)  # Normalize format
            else:
                self.errors.append(f"incorrect format for month: {raw}")
                del self.fields["month"]
        except ValueError:
            self.errors.append(f"incorrect format for month: {raw}")
            del self.fields["month"]

    def checkurl(self):
        """
        Check url
        """
        
        braced_url = self.fields.get("url", None)

        # Find url in another field
        if not braced_url:
            # Case 1: Get url from "handle = {10125/4345},"
            if "handle" in self.fields:
                braced_handle = self.fields["handle"]
                handle = trim_braces(braced_handle)
                match = bibpatterns.HANDLE_RE.fullmatch(handle)
                if match:
                    handle_id = match.group(1)
                    url = f"http://hdl.handle.net/{handle_id}"
                    self.fields["url"] = add_braces(url)
                    del self.fields["handle"]
                    return # exit checkurl()
            # Case 2: Move url from stableurl or opturl
            for url_field in ["stableurl", "opturl"]:
                if url_field in self.fields:
                    braced_url = self.fields[url_field]
                    self.fields["url"] = braced_url
                    del self.fields[url_field]
                    break # exit for loop on first pass
            # Case 3: Flag url in note-like field
            for note_field in ["note", "addendum", "annote"]:
                if note_field in self.fields:
                    if re.search(r'http', self.fields[note_field]):
                        self.errors.append(f"URL found in {note_field}: {self.fields[note_field]}")

        # Reget url, which could have only been changed in Cases 1 and 2
        braced_url = self.fields.get("url")
        if not braced_url:
            return

        # Continue processing url, which is now True
        url = trim_braces(braced_url)
        
        # Remove trailing period if present
        if url.endswith("."):
            url = url[:-1]

        # Check if remove-trailing-period kills the url
        if not url:
            del self.fields["url"]
            return

        # remove "file:" url
        if url.startswith("file:"):
            del self.fields["url"]
            return

        # Flag if url doesn't start with http (for https:// and http://)
        if not url.startswith("http"):
            self.errors.append("url does not start with http")
        
        # Check space in url
        if url.count(" ") > 0:
            self.errors.append("space in url")
            # Check if urldate is in url
            match = bibpatterns.URL_URLDATE_RE.search(url)
            if match and match.lastindex >= 2:
                matched_url = match.group(1)
                matched_urldate = match.group(2)
                if "urldate" in self.fields:
                    raw_urldate = trim_braces(self.fields["urldate"])
                    if matched_urldate != raw_urldate:
                        # urldate mismatch
                        url = matched_url
                        # todo: validate raw_urldate, compare to matched_urldate, keep latest
                    else:
                        # same date was in url and urldate values
                        url = matched_url
                else:
                    # url value had url and (new) urldate
                    url = matched_url
                    self.fields["urldate"] = add_braces(matched_urldate)
            else:
                # url has a space but no urldate to remove
                # match first semantic url in url
                match = bibpatterns.URL_RE.search(url)
                if match:
                    url = match.group(1)
                else:
                    self.errors.append(f"url has space and nothing url-like: {url}")
                    self.fields["url"] = "{\\biberror{remove space and check url: " + url + "}}"
                    return
            
        # Flag comma in url
        if url.count(",") > 0:
            self.errors.append(f"comma in url: {url}")
            
        # Check for doi in url by whitelist of publishers or generic
        # Extract domain
        domain_match = bibpatterns.DOMAIN_RE.match(url)
        url_domain = domain_match.group(1) if domain_match else None
        if url_domain:
            doi_pattern = bibpatterns.DOI_WHITELIST_RE.get(url_domain)
            doi_match = doi_pattern.search(url) if doi_pattern else bibpatterns.GENERIC_DOI_RE.search(url)
            if doi_match:
                doi = doi_match.group(1)
                braced_doi = add_braces(doi)
                if doi_pattern:
                    # Trusted DOI source - update fields
                    if "doi" in self.fields:
                        if self.fields["doi"].lower() != braced_doi.lower():
                            self.errors.append(f"DOI mismatch: extracted from URL ({doi}) differs from existing DOI ({self.fields['doi']})")
                        else:
                            del self.fields["url"]
                    else:
                        self.fields["doi"] = braced_doi
                        self.errors.append(f"DOI set from trusted URL: {doi} via {url_domain}")
                        del self.fields["url"]
                        return # exit checkurl()
                else:
                    # Fallback match - log only
                    self.errors.append(f"DOI-like string found in generic URL: {doi} from {url_domain}")
            
        # check if url *is* doi
        match = bibpatterns.DOI_RE.fullmatch(url)
        if match:
            extracted_doi = match.group(1)
            existing_braced_doi = self.fields.get("doi")
            if existing_braced_doi:
                existing_doi = trim_braces(existing_braced_doi)
                if existing_doi.lower() != extracted_doi.lower():
                    self.errors.append(
                        f"DOI mismatch: extracted from URL field ({extracted_doi}) differs from existing DOI field ({existing_doi})"
                    )
                else: 
                    # DOI matches - clean up redundant URL
                    del self.fields["url"]
            else:
                # No DOI field yet, set it from URL
                self.fields["doi"] = add_braces(extracted_doi)
                self.errors.append(f"DOI set from URL field: {extracted_doi}")
                del self.fields["url"]
            return
        
        # Flag blacklist of urls
        nonsites = (
            "ebrary",
            "degruyter",
            "myilibrary",
            "academia",
            "ebscohost",
            "researchgate",
        )
        for n in nonsites:
            if n in url:
                self.errors.append(f"use url only for for true repositories or for material not available elsewhere: {url}")
        
        # Reset surviving url
        if url:
            self.fields["url"] = add_braces(url)
        
    def checkurldate(self):
        """
        Check urldate
        """
        
        url = self.fields.get("url")
        urldate = self.fields.get("urldate")

        # Flag if urldate exists but url is missing
        if urldate and not url:
            self.errors.append("urldate exists but url is missing")

        # Validate urldate format
        if urldate:
            clean_date = trim_braces(urldate)
            try:
                dt = datetime.strptime(clean_date, "%Y-%m-%d")
                self.fields["urldate"] = add_braces(dt.strftime("%Y-%m-%d"))
            except ValueError:
                self.errors.append(f"invalid urldate format: {clean_date}")

        # Scan note-like fields for ISO-like dates, but only for @misc
        if self.typ == 'misc' and url and not urldate:
            for field in ["note", "addendum", "annote"]:
                value = self.fields.get(field)
                if value:
                    clean_text = trim_braces(value)
                    if bibpatterns.ISO_DATE_RE.search(clean_text):
                        self.errors.append(f"ISO-like date found in {field}: {clean_text}")
    
    def checkdoi(self):
        """
        Check doi syntax
        """

        raw = self.fields.get("doi")
        if not raw:
            return

        raw = trim_braces(raw)
        original = raw

        # Remove trailing period if present; unescape underscore; remove known doi-like prefix
        if raw.endswith("."):
            raw = raw[:-1]
        raw = raw.replace("\\_", "_")
        raw = re.sub(r"\bdoi:\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\bhttps?://(?:dx\.)?doi\.org/", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\bdoi\.org/", "", raw, flags=re.IGNORECASE)

        # Check if doi remains
        match = bibpatterns.DOI_RE.fullmatch(raw)
        if match:
            doi = match.group(1)
            self.fields["doi"] = add_braces(doi)
            if doi != original:
                self.errors.append(f"DOI extracted and normalized: {doi}")
            return

        # Check if we have a handle misidentified as a doi
        handle_match = bibpatterns.HANDLE_RE.fullmatch(raw)
        if handle_match:
            handle = handle_match.group(1)
            url = add_braces(f"https://hdl.handle.net/{handle}")
            if "url" in self.fields:
                if self.fields["url"] == url:
                    del self.fields["doi"]
                    self.errors.append(f"Deleted handle in doi; keep matching url: {url}")
                    return
                else: 
                    self.errors.append(f"Possible handle in doi doesn't match url; check both: doi = {raw}, url = {url}")
            else:
                del self.fields["doi"]
                self.fields["url"] = url
                self.errors.append(f"Handle detected in doi and converted to URL: {handle}")
                return
            
        # Check if we have an URL, with a doi (accept any domain; no whitelist)
        if raw.lower().startswith("http"):
            doi_match = bibpatterns.DOI_RE.search(raw)
            if doi_match:
                doi = doi_match.group(1)
                braced_doi = add_braces(doi)
                if "url" in self.fields:
                    url = self.fields["url"]
                    if doi in url:
                        self.fields["doi"] = braced_doi
                        del self.fields["url"]
                        self.errors.append(f"fix doi, delete similar: {doi}")
                        return
                    else:
                        self.fields["doi"] = braced_doi                        
                        self.errors.append(f"fix doi, keep url: check both: url = {url}, doi = {raw}")
                        return
                else:
                    self.fields["doi"] = braced_doi
                    self.errors.append(f"DOI extracted from URL-like string: {doi}")
                    return
            else:
                del self.fields["doi"]
                self.errors.append(f"delete url-like doi that doesnt' have a DOI: {raw}")
                return

        # Delete unrecognizable doi
        del self.fields["doi"]
        self.errors.append(f"Invalid DOI: {raw}")

    
    def checkbookisthesis(self):
        """
        Flag thesis/dissertation indicators in fields of a @book entry.
        Flags if publisher, url, or note suggest the entry might be better typed as @phdthesis.
        """

        if self.typ != "book":
            return

        for field in ("publisher", "url", "note"):
            value = self.fields.get(field)
            if is_real_value(value):
                if bibpatterns.THESIS_RE.search(value):
                    self.errors.append(f"possible thesis indicator in {field}: {value}")
                    break

    def checkthesis(self):
        """
        Perform checks for thesis-type entries.
        """

        if self.typ not in ("phdthesis", "mastersthesis", "thesis"):
            return

        # Map 'institution' to 'school' if needed
        if self.fields.get("school") is None and self.fields.get("institution") is not None:
            self.fields["school"] = self.fields["institution"]
            del self.fields["institution"]

        # Expand school name
        if self.fields.get("school") is not None and self.fields["school"] in bibpatterns.SCHOOL_FULL:
            self.fields["school"] = bibpatterns.SCHOOL_FULL[self.fields["school"]]

        # Lookup address if school but no address
        if self.fields.get("address") is None and self.fields.get("school") is not None and self.fields["school"] in bibpatterns.SCHOOL_ADDRESS:
            self.fields["address"] = bibpatterns.SCHOOL_ADDRESS[self.fields["school"]]
        
        mandatory = ["author", "title", "address", "school", "year"]
        for m in mandatory:
            self.handleerror(m)
        self.addsortname()

        # 'type' is mandatory for generic 'thesis' entries
        if self.typ == "thesis":
            self.handleerror("type")

        # Check 'type' field if present
        thesistype = self.fields.get("type")
        if thesistype:
            # Flag unwanted capitalization e.g. "type = {Doctoral Dissertation}," 
            if re.search(r"\s.*?(Thesis|Dissertation)", thesistype):
                self.errors.append(f"type field may be in Title Case: {thesistype}")

    def checkbook(self):
        """
        Perform check for type book
        """

        if self.typ != "book":
            return

        self.checkpublisheraddress()

        mandatory = ["year", "title", "address", "publisher"]
        for m in mandatory:
            self.handleerror(m)

        if self.fields.get("series") is not None:
            # people often mix up the field 'number' and 'volume' for series
            # if both are present, we leave everything as is
            # if only volume is present, we assign the content to
            # number and delete the field volume
            number = self.fields.get("number")
            volume = self.fields.get("volume")
            if volume is not None and number is None:
                self.fields["number"] = volume
                del self.fields["volume"]

        # books should have either author or editor, probably but not both, and definitely not neither
        author = self.fields.get("author")
        editor = self.fields.get("editor")
        if author and editor:
            self.errors.append("both author and editor")
            self.addsortname(author)
        elif author or editor:
            self.addsortname(author or editor)
        else:
            self.errors.append("no author or editor")
            self.handleerror("author")
            
        if is_real_value(self.fields.get("pages")):
            self.errors.append("book shouldn't have pages")

    def addsortname(self, name=None):
        """
        add an additional field for sorting for names with diacritics
        """
        
        name = name or self.fields.get("author")
        if is_real_value(name):
            # self.fields["sortname"] = asciify(dediacriticize(name))
            # EP pause sortname
            pass

    def requirepages(self):
        """
        Require pages, if not electronic journal, i.e. doi or url
        """

        if not self.fields.get("pages"):
            if not self.fields.get("url") and not self.fields.get("doi"):
                self.handleerror("pages")
            else:
                self.errors.append("no pages")

    def checkarticle(self):
        """
        Perform some checks for type article
        """

        if self.typ != "article":
            return

        mandatory = ["author", "year", "title", "journal", "volume"]

        # Move number to volume, if number but no volume
        volume = self.fields.get("volume")
        number = self.fields.get("number")
        if volume is None and number is not None:
            self.fields["volume"] = number
            del self.fields["number"]

        for m in mandatory:
            self.handleerror(m)
        self.addsortname()
       
        self.requirepages()

    def checkpublisheraddress(self):
        """
        Normalize publisher and address fields (replaces placelookup())
            Use canonical publisher name
            Lookup address in publisher whitelist, if address was missing.
        Todo 
            factor into checkpublisher() and checkaddress()
            flag ": " in address
            if colon in either, match whitelist of addresses and publishers
        """

        address = self.fields.get("address", "")
        publisher = self.fields.get("publisher", "")
        
        if publisher:
            if ": " in publisher:
                self.errors.append(f"separate address from publisher: {publisher}")
            if publisher in bibpatterns.PUBLISHER_FULL:
                publisher = bibpatterns.PUBLISHER_FULL[publisher]
                self.fields["publisher"] = publisher

        if address:
            # clean address
            if ", " in address:
                # todo: remove country using bibnouns.COUNTRIES
                self.errors.append(f"use one place only: {address}")
        else:
            publisher_lower = publisher.lower()
            for substrings, address in bibpatterns.PUBLISHER_ADDRESS.items():
                if any(sub in publisher_lower for sub in substrings):
                    self.fields["address"] = address
                    break

    def checkincollection(self):
        """
        Perform checks for type @incollection.
        """

        if self.typ != "incollection":
            return

        # Normalize and validate publisher/address early
        self.checkpublisheraddress()

        # Mandatory: author, title
        self.handleerror("author")
        self.addsortname()
        self.handleerror("title")

        # Mandatory: pages (with DOI/URL fallback)
        self.requirepages()

        # Mandatory: year, booktitle, editor, publisher, address unless crossref is present, 
        # but allow no editor, publisher, address if booktitle suggests proceedings
        has_crossref = "crossref" in self.fields
        booktitle = self.fields.get("booktitle", "")
        is_proceedings = bibpatterns.PROCEEDINGS_FUZZY_RE.search(booktitle)

        if is_proceedings:
            self.errors.append("booktitle suggests proceedings: use @inproceedings for proceedings")
        
        if has_crossref:
            return
        
        self.handleerror("year")
        if booktitle:
            if not is_proceedings:
                for field in ("editor", "publisher", "address"):
                    self.handleerror(field)
        else: 
            for field in ("booktitle", "editor", "publisher", "address"):
                self.handleerror(field)

    def checkinproceedings(self):
        """
        Perform checks for type @inproceedings.
        """

        if self.typ != "inproceedings":
            return

        # Normalize and validate publisher/address early
        self.checkpublisheraddress()

        # Mandatory: author and title
        self.handleerror("author")
        self.addsortname()
        self.handleerror("title")

        # Mandatory: pages (with DOI/URL fallback)
        self.requirepages()
        
        # Mandatory: year, booktitle if no crossref
        if "crossref" not in self.fields:
            self.handleerror("booktitle")
            self.handleerror("year")
        
        # editor, publisher, address not mandatory for inproceedings

    def checkinbook(self):
        """
        Perform checks for type @inbook.
        """

        if self.typ != "inbook":
            return

        # Normalize and validate publisher/address early
        self.checkpublisheraddress()

        # Mandatory: author and title
        self.handleerror("author")
        self.addsortname()
        self.handleerror("title")

        # Mandatory: chapter or pages (with fallback logic)
        chapter = self.fields.get("chapter")
        pages = self.fields.get("pages")
        if not chapter and not pages:
            self.errors.append("@inbook entry must have either 'chapter' or 'pages'")
            self.handleerror("chapter")
            self.handleerror("pages")

        # Mandatory: year, booktitle, bookauthor, publisher, address if no crossref
        if "crossref" in self.fields:
            return

        self.handleerror("year")
        self.handleerror("booktitle")

        # Contributor sanity check
        editor = self.fields.get("editor")
        bookauthor = self.fields.get("bookauthor")
        author = self.fields.get("author")

        if editor and bookauthor:
            self.errors.append(
                f"@inbook has bookauthor and editor. Is the entry really @incollection for a chapter by {author} in book edited by {editor}, "
                f"or @inbook for a contribution by {author} in a book authored by {bookauthor}?"
            )
        elif editor and not bookauthor:
            self.errors.append(
                f"If {editor} is really the editor of the book, then use @incollection instead of @inbook. "
                f"If {editor} is actually the author of the book, then use the 'bookauthor' field instead."
            )
        elif not editor and not bookauthor:
            self.errors.append("Who is the author of the book?")
            self.handleerror("bookauthor")

        # Mandatory continued
        for field in ("publisher", "address"):
            self.handleerror(field)

    def checkmisc(self):
        """
        Perform some checks for type misc
        """

        if self.typ != "misc":
            return

        mandatory = ["author", "title", "year"]
        for m in mandatory:
            self.handleerror(m)

        # Expect either 'note' or 'howpublished'
        if self.fields.get("note") is None and self.fields.get("howpublished") is None:
            self.errors.append("no note or howpublished")

    def checkothertype(self):
        """
        Perform some checks for other types, not otherwise specified
        Todo: checkmanual, checktechreport, etc.
        """

        known_types = {
            "article", "book", 
            "inbook", "incollection", "inproceedings",
            "thesis", "phdthesis", "mastersthesis", 
            "misc"
        }
        if self.typ in known_types:
            return

        mandatory = ["author", "title", "year"]
        for m in mandatory:
            self.handleerror(m)
        self.addsortname()
        self.checkpublisheraddress()
    
    def checkquestionmarks(self):
        """
        Check for fields with ??, which are not to be printed
        """
        
        for field, value in self.fields.items():
            if value and "??" in value:
                self.errors.append("?? in %s" % field)

    def handleerror(self, m):
        """
        Check whether a mandatory field is present
        Replace with error mark if not present
        """
        
        if not self.fields.get(m):
            self.fields[m] = r"{\biberror{no %s}}" % m
            self.errors.append("missing %s" % m)

    def bibtex(self):
        """
        Recreate the bibtex record.
        Output fields are sorted alphabetically.
        Omit all fields in excludefields
        """
        
        if self.parsing_failed:
            return ""
        
        try:
            self.typ
        except AttributeError:
            print("skipping phantom record, probably a comment")
            return ""
        if self.restrict and self.key not in self.inkeysd:
            return ""
        s = """@%s{%s,\n\t%s\n}""" % (
            self.typ,
            self.key,
            ",\n\t".join(
                [
                    "%s = %s" % (f, self.fields[f])
                    for f in sorted(self.fields.keys())
                    if f not in excludefields
                ]
            ),
        )
        s = s.replace(",,", ",")
        return s

def normalize(s, inkeysd=None, restrict=False, split_preamble=True, bibtexformat=True):
    """
    Normalize a BibTeX file or bibliography list into BibTeX format.

    Args:
        s (str): Contents of input file as a string.
        inkeysd (dict): Dictionary of keys to include in output if `restrict` is True.
        restrict (bool): Whether to limit output to keys in `inkeysd`.
        split_preamble (bool): Legacy argument, now ignored.
        bibtexformat (bool): If True, expects BibTeX entries; if False, expects one reference per line.

    Returns:
        str: Text of all normalized entries in BibTeX format.
    """
 
    if inkeysd is None:
        inkeysd = {}

    s = s.strip()
    
    input_entries = []
    if bibtexformat:
        bibtex_entries = re.split(r"\n\s*@", s)
        if s.startswith('@'):
            input_entries = bibtex_entries[:]
            if input_entries:
                input_entries[0] = input_entries[0].lstrip('@')
            preamble = ''
        else:
            preamble = bibtex_entries[0].strip()
            input_entries = bibtex_entries[1:]
    else:
        input_entries = [
            re.sub(r'\s+', ' ', line).strip()
            for line in s.splitlines()
            if line.strip()
        ]
        preamble = ''

    processed_records = []
    for entry in input_entries:
        temp_record = None
        try:
            temp_record = Record(
                entry,
                bibtexformat=bibtexformat,
                inkeysd=inkeysd,
                restrict=restrict,
                reporting=[]
            )
            processed_records.append(temp_record)
        except Exception as e:
            # verbose error message for debugging
            print("  Error processing record:")
            print("  Record preview:", repr(entry[:200]))
            print("  Record type:", getattr(temp_record, "typ", "unknown"))
            print("  Record key:", getattr(temp_record, "key", "unknown"))
            print("  Fields:", getattr(temp_record, "fields", "not available"))
            print("  Exception type:", type(e).__name__)
            print("  Exception message:", str(e))
            raise

    nonparsed = [record for record in processed_records if record.parsing_failed]
    any_failed = bool(nonparsed)
    if any_failed:
        if bibtexformat:
            parsing_failure = "\n\n".join(
                "@" + record.raw_entry for record in nonparsed
            )
        else:
            parsing_failure = "\n\n".join(
                record.raw_entry for record in nonparsed
            )

    parsed_records = [record for record in processed_records if not record.parsing_failed]
 
    # Reverse order by type, then alpahbetical order by key
    records_by_key = sorted(
        parsed_records,
        key=lambda record: record.key or ""
    )
    sorted_records = sorted(
        records_by_key,
        key=lambda record: record.typ or "",
        reverse=True
    )
   
    output = "\n\n".join(
        record.bibtex() for record in sorted_records if record.bibtex()
    )
    
    if preamble:
        output = preamble + "\n\n" + output
        
    if any_failed:
        output = parsing_failure + "\n\n" + output
    
    return output