"""
Reference normalization tool

Provides
- `Record`: class for parsing and processing one reference, accepting input from a BibTeX entry 
    or a bibliography entry.
- `normalize()`: function for processing the text of a BibTeX file or a bibliography list.
"""

#import sys
import re
#import pprint
#import glob
#import string
#import argparse
from datetime import datetime

#from langsci.latex.asciify import asciify
#from langsci.latex.delatex import dediacriticize
from langsci.bib import bibpatterns
from langsci.bib.bibnouns import COUNTRIES, USSTATES, USSTATEABBREVIATIONS
from langsci.bib.bibhelpers import (
    excludefields, name_fields, in_types, strip_braces, strip_all_outermost_braces, add_braces,
    clean_and_brace_dict, is_real_value, extract_doiurl, extract_pubaddr, extract_seriesnumber,
    generate_key
)

# Tracks seen BibTeX entry keys to detect duplicates
keys = {}

class Record:
    """
    A bibliographic record parser, cleaner and formatter.

    Processes a single bibliographic entry, in either BibTeX or bibliography list format.
    Parses the input entry, normalizes fields and their values, and prepares a clean BibTeX entry.

    Attributes:
        raw_entry (str): Raw text input to parse.
        parsing_failed (bool): Whether parsing failed.
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
        - Input can be a single BibTeX entry (without leading @) or a bibliography list entry.
        - BibTeX parsing uses bibpatterns.TYPKEYFIELDS_RE regex to extract type and key.
        - Normalization injects error messages into field values to flag missing/malformed fields.
            - During field value checks, only this error is injected.
                - `author = {Smith, John \biberror{et al}},` by checketal()
            - During entry checks by type, required but missing fields are flagged.
                - e.g. `pages = {\biberror{no pages}},` for any required field, by handleerror()
        - Other warnings are printed by `self.errors`.

    """

    def __init__(self, raw_entry, bibtexformat=False, inkeysd=None, restrict=False, reporting=None):
        """
        Initialize a Record instance.

        Args:
            raw_entry(str): Input entry as a string.
                In BibTeX (less leading '@') or bibliography list format.
            bibtexformat (bool, optional):
                If True, uses `parse_bibtex()`;
                otherwise uses `parse_bibliography()` for bibliography list format.
            inkeysd (dict, optional):
                Dictionary of field keys to include in output if `restrict` is True.
            restrict (bool, optional):
                Whether to limit output to keys in `inkeysd`.
                Defaults to False.
            reporting (list of str, optional):
                Flags for controlling output verbosity.
                Defaults to None.

        Behavior:
            - Parses the input string using either `parse_bibtex()` or `parse_bibliography()`.
            - Calls `conform()` to normalize field values, first by field then by BibTeX entry type.
            - Calls `report()` to print accumulated syntax warnings (stored in `self.errors`).
        """

        self.raw_entry = raw_entry
        self.parsing_failed = False
        self.errors = []
        self.restrict = restrict
        self.inkeysd = inkeysd if inkeysd is not None else {}
        self.reporting = reporting if reporting is not None else []
        if bibtexformat:
            self.parse_bibtex(raw_entry)
        else:
            self.parse_bibliography(raw_entry)
        if not self.parsing_failed:
            self.conform()
            self.report()

    def parse_bibtex(self, raw_entry):
        """
        Parse a BibTeX entry

        Args:
            raw_entry (str): BibTex entry with leading '@' already removed.

        Expected Format:
            - Field values may be braced, unbraced, or quoted.
            - Quoted values must not contain quote marks (even escaped).
            - Field/value pairs are separated by a comma and newline.
                The final pair may omit the comma.

        Example:
            bibtype{bibkey,
                field1 = {value1},
                field2 = "value2",
                field3 = value3
            }

        Output:
            Populates `self.fields` with normalized field/value pairs.
                - Quoted values are converted to braced format.
                - Braced or quoted values have whitespace collasped and stripped.
                - Unbraced values are treated as raw strings with no whitespace.
                - Also sets `self.typ` and `self.key` for the BibTeX entry type and key, resp.

        Notes:
            - Parsing is naive.
            - The parser does not validate brace nesting or escape sequences.
            - The parser may fail if a field contains the sequence "},\n" within
                a properly balanced value.
        """

        match = bibpatterns.TYPKEYFIELDS_RE.match(raw_entry)
        if not match:
            self.parsing_failed = True
            return

        self.typ = match.group(1).lower()
        self.key = match.group(2)
        remainder = match.group(3).strip()

        # analyze remainder
        # remove possible comma at end of last field/value pair, to improve split
        remainder = re.sub(r'\s*,\s*}$', '}', remainder)

        # Split bibentry on closing brace followed by a comma and a newline
        lines = re.split(r"(?<=\})[ \t]*,[ \t]*\n\s*", remainder)

        # Clean all whitespace in lines
        lines = [re.sub(r'\s+', ' ', line.strip()) for line in lines]

        if not any(lines):
            self.errors.append("no valid field/value lines found")
            self.parsing_failed = True
            return

        # Parse line into field/value pair,
        # first finding any unbraced values,
        # then finding any final braced value.
        self.fields = {}
        for line in lines:
            while line:
                # Case: Braced value
                match = re.match(
                    r'^ ?(\w+) ?= ?\{ ?(.*?) ?\} ?,? ?$',
                    line
                )
                if match:
                    field, value = match.groups()
                    if value == "":
                        break
                    self.fields[field.lower()] = add_braces(value)
                    break  # Braced value is terminal

                # Case: Quoted value (BUT no internal quote marks, even escaped)
                match = re.match(
                    r'^ ?(\w+) ?= ?" ?([^"]*?) ?" ?,? ?(.*)$',
                    line
                )
                if match:
                    field, value, remainder = match.groups()
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
                        break

                # Case: Unbraced value
                match = re.match(
                    r'^ ?(\w+) ?= ?([^,{}"]*) ?,? ?(.*)$',
                    line
                )
                if match:
                    field, value, remainder = match.groups()
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
                        break
                break

        if not self.fields:
            self.errors.append("no fields parsed from BibTeX entry")
            self.parsing_failed = True

        # Check duplicate key
        if self.key in keys:
            self.errors.append(f"duplicate key {self.key}")
        keys[self.key] = True

    def parse_bibliography(self, raw_entry):
        """
        Parse a bibliography entry
        """
        raw_entry = raw_entry.strip()
        self.parsing_failed = False
        self.typ = "misc"
        self.key = None
        d = {}

        # Early exit for empty input
        if not raw_entry:
            self.parsing_failed = True
            return

        # assignment cascade
        parsed_by_cascade = False
        if (
            not parsed_by_cascade and
            (m := bibpatterns.THESISAPA.search(raw_entry))
        ):
            thesisschool = m.group("thesisschool")
            # split "thesisschool" into "thesistype" or "thesistype, school"
            parts = [p.strip() for p in thesisschool.split(",", 1)]
            thesistype = parts[0]
            d["school"] = parts[1] if len(parts) == 2 else None
            # strip "Unpublished " from head of thesistype and fix capitalization
            thesistype_raw = thesistype
            if thesistype_raw.lower().startswith("unpublished "):
                thesistype = re.sub(r"(?i)^unpublished ", "", thesistype_raw).strip()
                if thesistype and thesistype[0].islower():
                    thesistype = thesistype[0].upper() + thesistype[1:]
            # determine self.typ from thesistype by whitelists
            if bool(bibpatterns.PHD_RE.fullmatch(thesistype)):
                self.typ = "phdthesis"
                parsed_by_cascade = True
            elif bool(bibpatterns.MA_RE.fullmatch(thesistype)):
                self.typ = "mastersthesis"
                parsed_by_cascade = True
            elif bool(bibpatterns.THESIS_RE.fullmatch(thesistype)):
                self.typ = "thesis"
                parsed_by_cascade = True
                d["type"] = thesistype
            else:
                parsed_by_cascade = False
                d.clear()
            if parsed_by_cascade:
                self.parsing_failed = False
                d["author"] = m.group("author")
                d["year"] = m.group("year")
                d["extrayear"] = m.group("extrayear")
                d["title"] = m.group("title")
                d["endmark"] = m.group("endmark")
                tail = m.group("note") or ""
                # extract url or doi from tail of note
                tail, meta = extract_doiurl(tail)
                d.update(meta)
                # tail should now be school, if school was not set from the bracketed thesisschool
                if tail:
                    if d.get("school"):
                        d["note"] = tail
                    else:
                        d["school"] = tail

        if (
            not parsed_by_cascade and
            (m := bibpatterns.THESISLSP.search(raw_entry))
        ):
            if m.group("phd_cue"):
                self.typ = "phdsthesis"
            elif m.group("ma_cue"):
                self.typ = "mastersthesis"
            elif m.group("thesis_cue"):
                self.typ = "thesis"
                d["type"] = m.group("thesis_cue")
            parsed_by_cascade = True
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["address"] = m.group("address")
            d["school"] = m.group("school") or m.group("school_na")
            d["school"] = re.sub(r"[.,]? Unpublished ?$", "", d["school"])
            d["note"] = m.group("note")

        if (
            not parsed_by_cascade and
            (m := bibpatterns.THESISGENERIC.search(raw_entry))
        ):
            parsed_by_cascade = True
            self.parsing_failed = False
            self.typ = "thesis"
            d["author"] = m.group("author")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["address"] = m.group("address")
            d["type"] = m.group("degree_cue")
            d["school"] = m.group("school") or m.group("school_na")
            d["school"] = re.sub(r"[.,]? Unpublished ?$", "", d["school"])
            d["note"] = m.group("note")

        # APA @incollection
        match_apa = bibpatterns.INCOLLECTIONAPA.search(raw_entry)
        match_apanoeditor = bibpatterns.INCOLLECTIONAPANOEDITOR.search(raw_entry)
        if bibpatterns.EDITOR.search(raw_entry) and match_apa:
            m = match_apa
        elif bibpatterns.YEARINCUE.search(raw_entry) and match_apanoeditor:
            m = match_apanoeditor
        else:
            m = None
        if not parsed_by_cascade and m:
            self.typ = "incollection"
            parsed_by_cascade = True
            self.parsing_failed = False
            d["author"] = m.group("author")
            if match_apa:
                d["editor"] = m.group("editor")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["booktitle"] = m.group("booktitle").strip(",. ")
            d["edition"]= m.group("edition")
            d["volume"]= m.group("volume")
            d["pages"] = m.group("pages")
            d["address"] = m.group("address")
            d["publisher"] = m.group("publisher") or m.group("publisher_na")
            tail = d["publisher"]
            tail, meta = extract_doiurl(tail)
            d.update(meta)
            d["publisher"] = tail

        # LSP @incollection
        match_lsp_ed = bibpatterns.INCOLLECTIONLSP.search(raw_entry)
        match_lsp_ed_nopages = bibpatterns.INCOLLECTIONLSPNOPAGES.search(raw_entry)
        match_lsp_noed = bibpatterns.INCOLLECTIONLSPNOEDITOR.search(raw_entry)
        match_lsp_noed_nopages = bibpatterns.INCOLLECTIONLSPNOEDITORNOPAGES.search(raw_entry)
        bool_editor = bool(bibpatterns.EDITOR.search(raw_entry))
        bool_yearincue = bool(bibpatterns.YEARINCUE.search(raw_entry))
        has_editor = bool_editor and (match_lsp_ed or match_lsp_ed_nopages)
        has_pages = (match_lsp_ed or match_lsp_noed)
        if bool_editor:
            m = match_lsp_ed or match_lsp_ed_nopages
        elif bool_yearincue:
            m = match_lsp_noed or match_lsp_noed_nopages
        else:
            m = None
        if not parsed_by_cascade and m:
            self.typ = "incollection"
            parsed_by_cascade = True
            self.parsing_failed = False
            d["author"] = m.group("author")
            if has_editor:
                d["editor"] = m.group("editor")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["booktitle"] = m.group("booktitle")
            d["edition"]= m.group("edition")
            d["series"]= m.group("series")
            d["number"]= m.group("number")
            d["volume"]= m.group("volume")
            if has_pages:
                d["pages"] = m.group("pages")
            d["address"] = m.group("address")
            d["publisher"] = m.group("publisher") or m.group("publisher_na")
            tail = d["publisher"]
            tail, meta = extract_doiurl(tail)
            d.update(meta)
            d["publisher"] = tail

        if not parsed_by_cascade and (m := bibpatterns.ARTICLE.search(raw_entry)):
            # journal is greedy and may capture doi cue
            journal = m.group("journal").lower()
            if "doi:" not in journal:
                self.typ = "article"
                parsed_by_cascade = True
                self.parsing_failed = False
                d["author"] = m.group("author")
                d["year"] = m.group("year")
                d["extrayear"] = m.group("extrayear")
                d["title"] = m.group("title")
                d["endmark"] = m.group("endmark")
                d["journal"] = m.group("journal")
                d["volume"] = m.group("volume")
                d["number"] = m.group("number")
                d["pages"] = m.group("pages")
                note = m.groupdict().get("note")
                if note:
                    d["note"] = note.strip(" .")
        if not parsed_by_cascade and (m := bibpatterns.ARTICLEMLA.search(raw_entry)):
            self.typ = "article"
            parsed_by_cascade = True
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["journal"] = m.group("journal")
            d["volume"] = m.group("volume")
            d["number"] = m.group("number")
            d["pages"] = m.group("pages")
            d["note"] = m.group("note")
        if not parsed_by_cascade and (m := bibpatterns.ARTICLECHI.search(raw_entry)):
            self.typ = "article"
            parsed_by_cascade = True
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            d["title"] = m.group("title")
            d["endmark"] = m.group("endmark")
            d["journal"] = m.group("journal")
            d["volume"] = m.group("volume")
            d["number"] = m.group("number")
            d["pages"] = m.group("pages")
            d["note"] = m.group("note")

        if not parsed_by_cascade and (m := bibpatterns.BOOK.match(raw_entry)):
            editor_flag = m.group("editor_cue")
            match_pubaddr = bibpatterns.PUBADDR.search(raw_entry)
            bad_cues = {"doi", "url", "issn"}
            if match_pubaddr:
                cue = match_pubaddr.group("address").strip().lower()
                has_pubaddr = not any(bad in cue for bad in bad_cues)
            else:
                has_pubaddr = False
            if (editor_flag or has_pubaddr):
                self.typ = "book"
                parsed_by_cascade = True
                self.parsing_failed = False
                if editor_flag:
                    d["editor"] = m.group("author")
                else:
                    d["author"] = m.group("author")
                d["year"] = m.group("year")
                d["extrayear"] = m.group("extrayear")
                d["title"] = m.group("title")
                tail = d["title"]
                tail, meta = extract_doiurl(tail)
                d.update(meta)
                if has_pubaddr:
                    tail, pubaddr = extract_pubaddr(tail)
                    d.update(pubaddr)
                tail, seriesnumber = extract_seriesnumber(tail)
                d.update(seriesnumber)
                d["title"] = tail
        if not parsed_by_cascade and (m := bibpatterns.MISC.search(raw_entry)):
            self.typ = "misc"
            parsed_by_cascade = True
            self.parsing_failed = False
            d["author"] = m.group("author")
            d["year"] = m.group("year")
            d["extrayear"] = m.group("extrayear")
            tail = m.group("title")
            tail, meta = extract_doiurl(tail)
            d.update(meta)
            d["title"] = tail
        if not parsed_by_cascade:
            self.parsing_failed = True
            return

        # Find doi and url in note; clean note
        note = d.get("note")
        if isinstance(note, str) and note.strip():
            note, meta = extract_doiurl(note)
            d.update(meta)
            d["note"] = note

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

        # Replace ampersand in author or editor
        if d.get("author"):
            d["author"] = d["author"].replace(" &", " and ")
        if d.get("editor"):
            d["editor"] = d["editor"].replace(" &", " and ")

        # Find series and number in booktitle
        booktitle = d.get("booktitle")
        if booktitle:
            tail, seriesnumber = extract_seriesnumber(booktitle)
            d.update(seriesnumber)
            d["booktitle"] = tail

        self.key = generate_key(d)
        clean_and_brace_dict(d)
        self.fields = d

    def conform(self):
        """
        Normalize and validate BibTeX fields.

        This method runs a series of field-level checks and corrections to ensure consistency,
        formatting, and completeness of the BibTeX record. It may inject LaTeX messages into
        fields to flag missing or malformed data.

        Notes:
            - Removed legacy logic that set `booktitle = title` when an editor was present.
                See `checkbooktitle`.
            - Refactored `conformtitles` and `checkdecapitalizationprotection`
                into `checbookktitle` and `checkdecapitalization`.
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
        Print any accumulated error messages
        """

        if not self.errors:
            return
        if not self.restrict or self.inkeysd.get(self.key):
            print(self.key, "\n  ".join(["  "] + self.errors))

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
                    self.errors.append(f"remapped '{old}' to '{new}'")
                    del self.fields[old]
                else:
                # Both fields exist—log but preserve both
                    self.errors.append(f"both '{old}' and '{new}' present; no remap applied")

        # Special case: eventtitle → booktitle for inproceedings
        if self.typ == "inproceedings":
            eventtitle = self.fields.get("eventtitle")
            booktitle = self.fields.get("booktitle")
            if is_real_value(eventtitle) and not is_real_value(booktitle):
                self.fields["booktitle"] = eventtitle
                self.errors.append("remapped 'eventtitle' to 'booktitle'")

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
            return

        pages = self.fields["pages"]
        pages = strip_braces(pages)

        # Delete empty pages
        if pages == '':
            del self.fields["pages"]
            return

        # Delete placeholder "pages = {none},"
        if pages.lower() == "none":
            del self.fields["pages"]
            return

        # Delete pages like a page count, "pages = {123 pp.},"
        if re.match(r"^\d+\s*(pp\.?|pages)$", pages, re.IGNORECASE):
            del self.fields["pages"]
            return

        # Normalize dashes (U+2012 figure dash, U+2013 en dash, U-2014 em dash, U+2212 minus sign)
        # and strip whitespace
        pages = re.sub(r"\s*(?:-+|‒|–|—|−)+\s*", "--", pages)

        # Replace semicolons with commas for multiple ranges
        pages = re.sub(r"\s*[;,]\s*", ", ", pages)

        # Parse article id by changing it to pages,
        # e.g. "pages = {Article ID 34}," to "pages = {34},"
        match = bibpatterns.ARTICLE_ID_RE.match(pages)
        pages = match.group(1) if match else pages

        # Flag nonstandard pages
        unit = r"(?:[a-zA-Z]?\d+|[ivxlcdm]+)"
        range_ =  fr"{unit}--{unit}"
        entry = fr"(?:{unit}|{range_})"
        pattern = re.compile(fr"^{entry}(?:, {entry})*$")
        if not pattern.match(pages):
            self.errors.append(f"non-standard pages: {pages}")

        # Flag capital Roman numerals
        range_roman = re.compile(r"^[IVXLCDM]+--[IVXLCDM]+$")
        if range_roman.match(pages):
            self.errors.append(f"capital Roman numerals in pages: {pages}")

        # Flag redundant range, e.g. 12--12
        range_capture = re.compile(fr"({unit})--({unit})")
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
            propernouns, via bibpatterns.PRESERVATION_RE
            first word of a likely subtitle, e.g.
                "title = {Syntax: The comma}," -> "title = {Syntax: {T}he comma},"
            Binnenmajuskeln, (conference) acronyms or InterCaps, e.g. OpenAI, ICPhS
            lone capitals
        Skipped if langid is "german", "ngerman", or "de"
        """

        if "langid" in self.fields:
            langid = self.fields["langid"]
            langid = strip_braces(langid)
            if langid in ["german", "ngerman", "de"]:
                return
        title_fields = [
            "title", "booktitle", "subtitle", "maintitle", "mainsubtitle", "booksubtitle",
        ]
        for field in title_fields:
            original = self.fields.get(field)
            if not original:
                continue
            original = strip_braces(original)
            protected = original

            # Capitalize and protect first letter after a space after colon, question mark, or
            # exclamation mark, as a subtitle
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
            for match in bibpatterns.PRESERVATION_RE.finditer(protected):
                group = match.group(1)
                protected = protected.replace(group, f"{{{group}}}")

            # Protect entire title of proper name of conference/proceedings,
            # trusting original capitalization
            if bibpatterns.PROCEEDINGS_RE.search(protected):
                protected = add_braces(protected)

            # Flag title with lowercase conference/proceedings keyword
            if bibpatterns.PROCEEDINGS_LC_RE.search(protected):
                self.errors.append(
                    f"proper name of proceedings/conference not capitalized/protected?: {protected}"
                )

            if original != protected:
                self.fields[field] = add_braces(protected)
                if "nouns" in self.reporting or "conferences" in self.reporting:
                    print(original, " ==> ", protected)

    def checkbooktitle(self):
        """
        Move booktitle to title if there is no title
        but booktitle exists and doesn't belong in the entry type.
        E.g. @book with "booktitle = {Syntax}," should be "title = {Syntax},"
        """

        title = self.fields.get("title")
        booktitle = self.fields.get("booktitle")

        if self.typ not in in_types:
            if not is_real_value(title) and is_real_value(booktitle):
                self.fields["title"] = self.fields["booktitle"]
                self.errors.append("moved booktitle to title")
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
            volume_old = strip_braces(self.fields["volume"])
            if volume_old == volume_match:
                self.fields[fieldname] = titlelike
                self.errors.append(f"deleted redundant volume in {fieldname}")
            else:
                self.errors.append(f"mismatch: volume {volume_old} but {self.fields[fieldname]}")
        else:
            self.fields[fieldname] = titlelike
            self.fields["volume"] = add_braces(volume_match)
            self.errors.append(f"moved volume {volume_match} from {fieldname}")

    def checkvolumenumber(self):
        """
        Move volume indication from title field to volume field for a book.
        Do this volume move for the booktitle field in
        incollection-like bibentry types (incollection, inproceedings, inbook).
        """

        # For book, move volume indication from title if found
        if self.typ == "book":
            self.move_volume("title")
        # For in incollection-like type, move volume indication from booktitle if found
        if self.typ in in_types:
            self.move_volume("booktitle")

    def checkinitials(self):
        """
        Make sure that initials have a space between them and that initials have a period
        Flag suspicious double initials (e.g. "Watt, JJ")
        """

        capcap_re = re.compile(r' [A-Z][A-Z] ')
        finalcapcap_re = re.compile(r' [A-Z][A-Z]}$')
        suffix_period_re = re.compile(r"\b(Jr|Sr)\b(?!\.)")
        for field in name_fields:
            value = self.fields.get(field)
            if is_real_value(value):
                # Normalize double initials: "J.J" → "J. J"
                # (missing second period to be added below)
                value = re.sub(r"([A-Z])\.([A-Z])", r"\1. \2", value)
                # Add missing period after single initial: " J " → " J. "
                value = re.sub(" ([A-Z])(?= )", r" \1.", value)
                # Add missing period before closing brace: " J}" → " J.}"
                value = re.sub(" ([A-Z])}$", r" \1.}", value)
                # Add missing period after Jr or Sr: "Smith, Jr, John" → "Smith, Jr., John"
                value = suffix_period_re.sub(r"\1.", value)
                # Flag suspicious double initials (e.g. "Watt, JJ")
                if capcap_re.search(value) or finalcapcap_re.search(value):
                    self.errors.append(f"possible double initials: {self.fields[field]}")
                self.fields[field] = value

    def checkampersand(self):
        """
        Replace "&" by " and " as required by BibTeX, or escape as required by LaTeX.
        Flag any other unescaped ampersand.
        """

        comma_amp_re = re.compile(r",\s*(\\&|&)\s*")

        for field in name_fields:
            value = self.fields.get(field)
            if is_real_value(value):
                value = comma_amp_re.sub(' and ', value)
                value = value.replace(' & ', ' and ')
                value = value.replace(r' \& ', ' and ')
                self.fields[field] = value
                if bibpatterns.AMP_RE.search(value):
                    self.errors.append(f"unescaped ampersand {field}: {value}")

        for field in [
            "address", "publisher", "school", "institution", "journal", "series",
            "title", "booktitle", "maintitle", "subtitle",
            "volume", "number", "note", "howpublished", "addendum"
        ]:
            value = self.fields.get(field)
            if is_real_value(value):
                value = value.replace(' & ', r' \& ')
                self.fields[field] = value
                if bibpatterns.AMP_RE.search(value):
                    self.errors.append(f"unescaped ampersand {field}: {value}")

    def checketal(self):
        """
        Check whether literal 'et al' is used in author or editor fields
        """

        for field in name_fields:
            name = self.fields.get(field)
            if name:
                if re.search(r" et\.? al", name):
                    self.fields[field] = re.sub(
                        r" et\.? al",
                        r" \\biberror{et al}",
                        name
                    )
                    self.errors.append(f"literal et al {field}: {self.fields[field]}")

    def checkand(self):
        """
        Check for asyndetic coordination (commas used instead of 'and') and validate name structure:
        - Split on ' and ' to isolate names
        - Each name should have 0, 1, or 2 commas
        - If 2 commas, middle group should be a known suffix
        """

        for field in name_fields:
            value = self.fields.get(field)
            if is_real_value(value):
                raw = strip_braces(value)
                names = re.split(r"\s+and\s+", raw)

                for name in names:
                    comma_parts = [part.strip() for part in name.split(",")]
                    if len(comma_parts) == 2:
                        pass  # "Lastname, Firstname" — valid
                    elif len(comma_parts) == 1:
                        pass  # "Firstname Lastname" — valid but informal
                    elif len(comma_parts) == 3:
                        middle = comma_parts[1]
                        if middle not in bibpatterns.suffix_tokens:
                            self.errors.append(f"suspicious middle group in {field}: {name}")
                    elif len(comma_parts) > 3:
                        self.errors.append(f"too many commas in {field}: {name}")

    def checknamesuffix(self):
        """
        Fix or flag suspicious suffix placement in name fields.
        BibTeX expects suffixes (e.g., Jr., III) to appear as the second comma-separated group:
            "Van Valin, Jr., Robert D." → valid

        This method:
        - Fixes names with suffix fused to surname before comma
            (e.g., "Clifton III, Charles" → "Clifton, III, Charles")
        - Fixes names with suffix trailing after given name
            (e.g., "Roberts, Frank H. III" → "Roberts, III, Frank H.")
        - Flags suffixes at end of string with no commas (e.g., "Charles Clifton III")
        - Flags suffixes present but comma structure unclear (e.g., "Smith Jr" or "John Jr.")

        Recognized suffixes: Jr., Sr., II, III, IV, V
        """

        for field in name_fields:
            value = self.fields.get(field)
            if is_real_value(value):
                raw = strip_braces(value)
                names = re.split(r"\s+and\s+", raw)
                fixed_names = []

                for name in names:
                    # Case A: "Clifton III, Charles" → fix to "Clifton, III, Charles"
                    match = bibpatterns.fused_suffix_re.match(name)
                    if match:
                        fixed = f"{match.group('surname')}, {match.group('suffix')}, {match.group('given')}"
                        fixed_names.append(fixed)
                        continue

                    # Case B: "Roberts, Frank H. III" → fix to "Roberts, III, Frank H."
                    match = bibpatterns.misplaced_suffix_re.match(name)
                    if match:
                        fixed = f"{match.group('surname')}, {match.group('suffix')}, {match.group('given')}"
                        fixed_names.append(fixed)
                        continue

                    # Case C: "Charles Clifton III" → fix to "Clifton, III, Charles"
                    if bibpatterns.suffix_at_end_re.search(name) and name.count(",") == 0:
                        tokens = name.split()
                        if len(tokens) == 3 and tokens[-1] in bibpatterns.suffix_tokens:
                            given = tokens[0]
                            surname = tokens[1]
                            suffix = tokens[2]
                            fixed = f"{surname}, {suffix}, {given}"
                            fixed_names.append(fixed)
                            continue

                    # Case D: "Charles Henry Clifton III" → flag for manual review
                    if bibpatterns.suffix_at_end_re.search(name) and name.count(",") == 0:
                        tokens = name.split()
                        if len(tokens) != 3 and tokens[-1] in bibpatterns.suffix_tokens:
                            self.errors.append(f"ambiguous suffix at end in {field}: {name}")
                            fixed_names.append(name)
                            continue

                    # Case E: "John Jr." or "Smith Jr"
                    # Suffix present but not in valid comma-separated structure
                    if bibpatterns.suffix_boundary_re.search(name) and name.count(",") < 2:
                        self.errors.append(f"suffix placement unclear in {field}: {name}")
                        fixed_names.append(name)
                        continue

                    # Default: no suffix issue
                    fixed_names.append(name)

                # Replace field with fixed names if any were corrected
                new_value = " and ".join(fixed_names)
                if new_value != raw:
                    self.fields[field] = add_braces(new_value)

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

        # Strip braces, strip whitespace, and lowercase
        edn = strip_braces(edn)
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
                edn = ordinal_map.get(candidate)
        try:
            int(edn)
            self.fields["edition"] = add_braces(edn)
        except ValueError:
            self.errors.append(f"incorrect format for edition: {raw}")

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
            cleaned = strip_braces(cleaned)
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

        # Find url in another field
        if not self.fields.get("url"):
            # Case 1: Recover from handle
            if "handle" in self.fields:
                handle = strip_braces(self.fields["handle"])
                match = bibpatterns.HANDLE_RE.fullmatch(handle)
                if match:
                    url = f"http://hdl.handle.net/{match.group('handle')}"
                    self.fields["url"] = add_braces(url)
                    del self.fields["handle"]
                    return  # Clean handle-based URL: exit method

            # Case 2: Recover from stableurl or opturl
            for url_field in ["stableurl", "opturl"]:
                if url_field in self.fields:
                    self.fields["url"] = self.fields[url_field]
                    del self.fields[url_field]
                    break  # Exit loop, continue with normalization

            # Case 3: Recover from note-like fields
            for note_field in ["note", "addendum"]:
                value = self.fields.get(note_field)
                if value:
                    clean_value = strip_braces(value)
                    if bibpatterns.URL_RE.fullmatch(clean_value):
                        self.fields["url"] = add_braces(value)
                        del self.fields[note_field]
                        break  # Exit loop, continue with normalization
                    if re.search(bibpatterns.URL_RE, clean_value):
                        self.errors.append(f"url found in {note_field}: {value}")

        # Get url field
        braced_url = self.fields.get("url")
        if not braced_url:
            return  # No URL recovered: exit

        url = strip_braces(braced_url)

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

        # Flag space in url
        if url and " " in url:
            self.errors.append(f"url contains space: {url}")

        # Flag comma in url
        if url.count(",") > 0:
            self.errors.append(f"Url contains comma: {url}")

        # Check for doi in url by whitelist of publishers or generic
        # Extract domain
        domain_match = bibpatterns.DOMAIN_RE.match(url)
        url_domain = domain_match.group(1) if domain_match else None
        if url_domain:
            doi_pattern = bibpatterns.DOI_WHITELIST_RE.get(url_domain)
            pattern = doi_pattern or bibpatterns.GENERIC_DOI_RE
            doi_match = pattern.search(url)
            if doi_match:
                doi = doi_match.group(1)
                braced_doi = add_braces(doi)
                if doi_pattern:
                    # Trusted DOI source - update fields
                    if "doi" in self.fields:
                        if self.fields["doi"].lower() != braced_doi.lower():
                            self.errors.append(
                                f"DOI mismatch: URL-extracted ({doi}) "
                                f"differs from ({self.fields['doi']})"
                            )
                        else:
                            del self.fields["url"]
                    else:
                        self.fields["doi"] = braced_doi
                        self.errors.append(f"doi set from trusted url: {doi} via {url_domain}")
                        del self.fields["url"]
                        return # exit checkurl()
                else:
                    # Fallback match - log only
                    self.errors.append(
                        f"doi-like string found in generic url: {doi} from {url_domain}"
                    )

        # check if url *is* doi
        match = bibpatterns.DOI_RE.fullmatch(url)
        if match:
            extracted_doi = match.group("doi")
            existing_braced_doi = self.fields.get("doi")
            if existing_braced_doi:
                existing_doi = strip_braces(existing_braced_doi)
                if existing_doi.lower() != extracted_doi.lower():
                    self.errors.append(
                        f"doi mismatch: url extracted ({extracted_doi}) "
                        f"differs from ({existing_doi})"
                    )
                else:
                    # DOI matches - clean up redundant URL
                    del self.fields["url"]
            else:
                # No DOI field yet, set it from URL
                self.fields["doi"] = add_braces(extracted_doi)
                self.errors.append(f"doi set from url: {extracted_doi}")
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
        for site in nonsites:
            if site in url:
                self.errors.append(
                    f"use url only for for true repositories or "
                    f"for material not available elsewhere: {url}"
                )

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
            clean_date = strip_braces(urldate)
            try:
                date = datetime.strptime(clean_date, "%Y-%m-%d")
                self.fields["urldate"] = add_braces(date.strftime("%Y-%m-%d"))
            except ValueError:
                self.errors.append(f"invalid urldate format: {clean_date}")

        # Scan note-like fields for ISO-like dates, but only for @misc
        if self.typ == 'misc' and url and not urldate:
            for field in ["note", "addendum"]:
                value = self.fields.get(field)
                if value:
                    clean_text = strip_braces(value)
                    if bibpatterns.ISO_DATE_RE.search(clean_text):
                        self.errors.append(f"ISO-like date found in {field}: {clean_text}")

    def checkdoi(self):
        """
        Check doi syntax
        """

        raw = self.fields.get("doi")
        if not raw:
            return

        raw = strip_braces(raw)
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
            doi = match.group("doi")
            self.fields["doi"] = add_braces(doi)
            if doi != original:
                self.errors.append(f"doi extracted and normalized: {doi}")
            return

        # Check if we have a handle misidentified as a doi
        handle_match = bibpatterns.HANDLE_RE.fullmatch(raw)
        if handle_match:
            handle = handle_match.group("handle")
            url = add_braces(f"https://hdl.handle.net/{handle}")
            if "url" in self.fields:
                if self.fields["url"] == url:
                    del self.fields["doi"]
                    self.errors.append(f"deleted handle in doi; keep matching url: {url}")
                    return
                self.errors.append(
                    f"possible handle in doi doesn't match url; "
                    f"check both: doi = {raw}, url = {url}"
                )
            else:
                del self.fields["doi"]
                self.fields["url"] = url
                self.errors.append(f"handle detected in doi and converted to url: {handle}")
                return

        # Check if we have an URL, with a doi (accept any domain; no whitelist)
        if raw.lower().startswith("http"):
            doi_match = bibpatterns.DOI_RE.search(raw)
            if doi_match:
                doi = doi_match.group("doi")
                braced_doi = add_braces(doi)
                if "url" in self.fields:
                    url = self.fields["url"]
                    if doi in url:
                        self.fields["doi"] = braced_doi
                        del self.fields["url"]
                        self.errors.append(f"fix doi, delete similar: {doi}")
                        return
                    self.fields["doi"] = braced_doi
                    self.errors.append(
                        f"fix doi, keep url: check both: url = {url}, doi = {raw}"
                    )
                    return
                self.fields["doi"] = braced_doi
                self.errors.append(f"doi extracted from url-like string: {doi}")
                return
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
        if (
            self.fields.get("school") is not None
            and self.fields["school"] in bibpatterns.SCHOOL_FULL
        ):
            self.fields["school"] = bibpatterns.SCHOOL_FULL[self.fields["school"]]

        # Lookup address if school but no address
        if (
            self.fields.get("address") is None
            and self.fields.get("school") is not None
            and self.fields["school"] in bibpatterns.SCHOOL_ADDRESS
        ):
            self.fields["address"] = bibpatterns.SCHOOL_ADDRESS[self.fields["school"]]

        mandatory = ["author", "title", "address", "school", "year"]
        for field in mandatory:
            self.handleerror(field)
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
        for field in mandatory:
            self.handleerror(field)

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

        # books should have either author or editor, probably but not both,
        # and definitely not neither
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

        for field in mandatory:
            self.handleerror(field)
        self.addsortname()

        self.requirepages()

    def checkpublisheraddress(self):
        """
        Normalize publisher and address fields (replaces placelookup()).
            - Look for colon in publisher and extract address.
            - Look for colon in address and extract publisher.
            - Normalize publisher by canonical name (acronum, variant, substring).
            - Set canonincal address by publisher.
        """

        address_raw = self.fields.get("address", "")
        publisher_raw = self.fields.get("publisher", "")
        publisher_strip = strip_all_outermost_braces(publisher_raw)
        address_strip = strip_all_outermost_braces(address_raw)
        address_norm = address_strip
        publisher_norm = publisher_strip

        # Colon-based extraction from publisher field
        if (
            publisher_strip and
            ": " in publisher_strip and
            "{" not in publisher_strip and
            "}" not in publisher_strip
        ):
            address_extracted, publisher_extracted = publisher_strip.rsplit(": ", 1)
            if not address_raw:
                address_strip = address_extracted
                publisher_strip = publisher_extracted
                self.errors.append(
                    f"Extracted address {address_extracted} from publisher: {publisher_strip}"
                )
            elif address_extracted == address_strip:
                publisher_strip = publisher_extracted
                self.errors.append(
                    f"Removed duplicate address {address_extracted} "
                    f"from publisher: {publisher_strip}"
                )
            else:
                self.errors.append(
                    f"Address {address_raw} mismatch in publisher?: {publisher_raw}"
                )

        # Colon-based extraction from address field
        if (
            address_strip and
            ": " in address_strip and
            "{" not in address_strip and
            "}" not in address_strip
        ):
            address_extracted, publisher_extracted = address_strip.rsplit(": ", 1)
            if not publisher_raw:
                address_strip = address_extracted
                publisher_strip = publisher_extracted
                self.errors.append(
                    f"Extracted publisher {publisher_extracted} from address: {address_strip}"
                )
            elif publisher_extracted == publisher_strip:
                address_strip = address_extracted
                self.errors.append(
                    f"Removed duplicate publisher {publisher_extracted} "
                    f"from address: {address_strip}"
                )
            else:
                self.errors.append(
                    f"Publisher {publisher_raw} mismatch in address?: {address_raw}"
                )

        # Normalize "Washington, DC"
        if address_strip and "Washington" in address_strip:
            dc_check = re.sub(r"[.,\s]", "", address_strip.lower())
            if dc_check == "washingtondc":
                address_strip = "Washington, DC"
                address_norm = "Washington, DC"
                self.errors.append("Normalized address: Washington, DC")

        if address_strip and address_strip != "Washington, DC":
            # Remove known country and state after comma in address
            parts = address_strip.rsplit(",", 1)
            if len(parts) == 2:
                main, suffix = parts[0].strip(), parts[1].strip()
                if (
                    suffix in COUNTRIES or
                    suffix in USSTATES or
                    suffix in USSTATEABBREVIATIONS
                ):
                    address_strip = main
                    self.errors.append(f"Removed {suffix} after address: {address_strip}")

            # Detect multiple address
            multiple_address_delimiters = [",", ";", "/", "&", " and "]
            if address_strip:
                for delim in multiple_address_delimiters:
                    if delim in address_strip:
                        self.errors.append(f"Address contains multiple locations: {address_strip}")
                        break

        # Normalize publisher: acronym match
        for acronyms, publisher_canon in bibpatterns.PUBLISHER_FULL.items():
            if publisher_strip in acronyms:
                publisher_norm = publisher_canon
                self.errors.append(f"Normalized publisher {publisher_strip}: {publisher_norm}")
                break

        # Normalize publisher: variant match
        if not publisher_norm:
            for variants, publisher_canon in bibpatterns.PUBLISHER_VARIANT.items():
                if publisher_strip in variants:
                    publisher_norm = publisher_canon
                    self.errors.append(f"Normalized publisher {publisher_strip}: {publisher_norm}")
                    break

        # Normalize publisher: substring match
        publisher_bare = publisher_strip.lower().replace(".", "")
        if not publisher_norm:
            for substrings, publisher_canon in bibpatterns.PUBLISHER_SUBSTRING.items():
                if any(sub in publisher_bare for sub in substrings):
                    publisher_norm = publisher_canon
                    self.errors.append(f"Normalized publisher {publisher_strip}: {publisher_norm}")
                    break

        # Set address from canonical publisher
        if not address_strip and publisher_norm in bibpatterns.PUBLISHER_ADDRESS:
            address_norm = bibpatterns.PUBLISHER_ADDRESS[publisher_norm]

        # Set address from publisher substring
        publisher_clean = publisher_norm or publisher_strip
        if not address_strip and not address_norm and publisher_clean:
            publisher_clean = publisher_clean.lower()
            for substrings, address_canon in bibpatterns.PUBLISHER_SUBSTRING_ADDRESS.items():
                if any(sub in publisher_clean for sub in substrings):
                    address_norm = address_canon
                    self.errors.append(
                        f"Set address {address_norm} from publisher: {publisher_clean}"
                    )
                    break

        # Assign normalized publisher
        if publisher_norm and publisher_norm != publisher_strip:
            self.fields["publisher"] = add_braces(publisher_norm)
            self.errors.append(f"normalized publisher: {publisher_strip} → {publisher_norm}")

        # Assign normalized address
        if address_norm and address_norm != address_strip:
            self.fields["address"] = add_braces(address_norm)
            self.errors.append(f"normalized address: {address_strip} → {address_norm}")

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
                f"@inbook has bookauthor and editor. "
                f"Is the entry really @incollection for a chapter by {author} in a book "
                f"edited by {editor}, or @inbook for a contribution by {author} in a book "
                f"authored by {bookauthor}?"
            )
        elif editor and not bookauthor:
            self.errors.append(
                f"If {editor} is really the editor of the book, "
                f"then use @incollection instead of @inbook. "
                f"If {editor} is actually the author of the book, "
                f"then use the 'bookauthor' field instead."
            )
        elif not editor and not bookauthor:
            self.errors.append("who is the author of the book?")
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
        for field in mandatory:
            self.handleerror(field)

        # Expect either 'note' or 'howpublished'
        if self.fields.get("note") is None and self.fields.get("howpublished") is None:
            self.errors.append("no note or howpublished")

    def checkothertype(self):
        """
        Perform some checks for other types, not otherwise specified
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
        for field in mandatory:
            self.handleerror(field)
        self.addsortname()
        self.checkpublisheraddress()

    def checkquestionmarks(self):
        """
        Check for fields with ??, which are not to be printed
        """

        for field, value in self.fields.items():
            if value and "??" in value:
                self.errors.append(f"?? in {field}")

    def handleerror(self, field):
        """
        Check whether a mandatory field is present.
        If missing, inject an error message.
        """

        if not self.fields.get(field):
            self.fields[field] = fr"{{\biberror{{no {field}}}}}"
            self.errors.append(f"missing {field}")

    def bibtex(self):
        """
        Recreate the BibTeX record.

        Returns:
            str: BibTeX-formatted entry, or empty string if excluded or malformed.
        """

        if self.parsing_failed:
            return ""

        if not hasattr(self, "typ"):
            print("Skipping phantom record—probably a comment.")
            return ""

        if self.restrict and self.key not in self.inkeysd:
            return ""

        fields = [
            f"{field} = {self.fields[field]}"
            for field in sorted(self.fields)
            if field not in excludefields
        ]

        body = ",\n\t".join(fields)
        entry = f"@{self.typ}{{{self.key},\n\t{body}\n}}"
        return entry.replace(",,", ",")


def normalize(text_block, inkeysd=None, restrict=False, split_preamble=True, bibtexformat=True):
    """
    Normalize a BibTeX file or bibliography list into BibTeX format.

    Args:
        text_block (str): Contents of input file as a string.
        inkeysd (dict): Dictionary of keys to include in output if `restrict` is True.
        restrict (bool): Whether to limit output to keys in `inkeysd`.
        split_preamble (bool): Legacy argument, now ignored.
        bibtexformat (bool): If True, expects BibTeX entries;
            if False, expects one reference per line.

    Returns:
        str: Text of all normalized entries in BibTeX format.
    """

    if inkeysd is None:
        inkeysd = {}

    text_block = text_block.strip()

    input_entries = []
    if bibtexformat:
        bibtex_entries = re.split(r"\n\s*@", text_block)
        if text_block.startswith('@'):
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
            for line in text_block.splitlines()
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
        except Exception as ex:
            # verbose error message for debugging
            import traceback
            print("  Error processing record:")
            print("  Record preview:", repr(entry[:200]))
            print("  Record type:", getattr(temp_record, "typ", "unknown"))
            print("  Record key:", getattr(temp_record, "key", "unknown"))
            print("  Fields:", getattr(temp_record, "fields", "not available"))
            print("  Exception type:", type(ex).__name__)
            print("  Exception message:", str(ex))
            traceback.print_exc()
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
