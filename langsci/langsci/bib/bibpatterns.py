"""
Regexes and compiled patterns for references for bibtools.py
"""

import re

from langsci.bib.bibnouns import (
    LANGUAGENAMES,
    OCEANNAMES,
    COUNTRIES,
    CONTINENTNAMES,
    CITIES,
    USSTATES,
    OCCURREDREPLACEMENTS,
)

# Proper names, from bibnouns; was PRESERVATIONPATTERN
PRESERVATION_RE = re.compile(
    r"\b(%s)\b"
    % (
        "|".join(
            LANGUAGENAMES
            + COUNTRIES
            + OCEANNAMES
            + CONTINENTNAMES
            + CITIES
            + USSTATES
            + OCCURREDREPLACEMENTS
        )
    )
)

# Binnenmajuskeln (= CamelCase), was CONFERENCEPATTERN
CAMELCASE_RE = re.compile(r"([A-Z][A-Za-z0-9\-']*[A-Z][A-Za-z0-9\-']+)")

# Capitalized proceedings-like keywords, was PROCEEDINGSPATTERN
PROCEEDINGS_RE = re.compile(r"\b(Proceedings|Workshop|Conference|Symposium)\b")

# Lowercase proceedings-like keywords
PROCEEDINGS_LC_RE = re.compile(r"\b(proceedings|workshop|conference|symposium)\b")

# Proceedings-like keywords (to flag suspicious booktitles fuzzily)
PROCEEDINGS_FUZZY_RE = re.compile(r"(roceedings|orkshop|onference|ymposium)", re.IGNORECASE)

# Volume indication in title
TITLEVOLUME_RE = re.compile("(, )?([Vv]olume|[Vv]ol.?|Band|[Tt]ome) *([0-9IVXivx]+)")

# iso_date
ISO_DATE_RE = re.compile(r"\b[12][0-9]{3}-[01][0-9]-[0-3][0-9]\b")

# url, right-bounded by space or parenthesis
URL_RE = re.compile(r"(https?://[^ \(\)]+)", re.IGNORECASE)

# Domain in url
DOMAIN_RE = re.compile(r"^https?://([^/]+)", re.IGNORECASE)

# Unescaped ampersand
AMP_RE = re.compile(r"(?<!\\)&")

# Article id
# case-insensitive, match 1 to 3 article-id-keywords, capture the alphanumeric article ID
ARTICLE_ID_RE = re.compile(r"(?i)^(?:article|art\.?|id\.?|number|no\.?){1,3} *([A-Za-z0-9]+)")

# Parse type and key of bibentry. Assume leading "@" already removed. Consume whitespace.
TYPKEYFIELDS_RE = re.compile(r"^\s*([^\{\s]+)\s*\{\s*([^,\s]+)\s*,\s*((?:.|\n)*)\}")

# Main title, e.g. "Maintitle: the subtitle", to capitalize and protect
MAINTITLE_RE = re.compile(r"([:\?!]) +([a-zA-Z])")

# DOI, url, handle
doi_regex = r"(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)"
doi_named = rf"(?P<doi>{doi_regex})"
DOI_RE = re.compile(doi_named)
url_named =  r"(?P<url>https?://[^ ]+)"
url_cue = r"(Retrieved from|Available from)"
handle_regex = r"(\d{4,5}\.\d{4,5}/[-._;()/:A-Za-z0-9]+)"
handle_named = rf"(?P<handle>{handle_regex})"
HANDLE_RE = re.compile(handle_named)

# Theses
thesis_cue = [
    "BA thesis",
    "BA dissertation",
    "B\.? ?A\.? thesis",
    "B\.? ?A\.? dissertation",
    "Bachelor[’']s thesis",
    "Bachelor[’']s dissertation",
    "Honours thesis",
    "Honours dissertation",
    "Hons\. thesis",
    "Hons\. dissertation",
    "Undergraduate thesis",
    "Undergraduate dissertation",
    "Licentiate thesis",
    "Lic\. thesis",
    "Tesi di laurea",
    "Candidate of sciences dissertation",
    "Candidate dissertation",
    "Doctor of Sciences dissertation",
    "Higher doctoral dissertation",
    "Thèse en préparation",
    "Unpublished dissertation",
    "Unpublished thesis",
    "Graduation thesis",
    "Graduation dissertation",
    "Final project",
    "Dissertation",
    "Thesis"
]
ma_cue = [
    "M\.? ?A\.? thesis",
    "M\.? ?A\?. dissertation",
    "Master[’']s thesis",
    "Master[’']s dissertation",
    "Master of Arts thesis",
    "Master of Arts dissertation",
    "Master of Science thesis",
    "Master of Science dissertation",
    "MPhil thesis",
    "MPhil dissertation",
    "Mémoire de maîtrise",
    "Mémoire de master",
    "Mémoire de master 1",
    "Mémoire de master 2",
    "Thèse de maître",
    "Thèse de maîtrise",
    "Tesis de maestría",
    "Dissertação de mestrado",
    "Tesi di laurea magistrale",
    "Diplomarbeit",
    "Magisterarbeit",
    "Masterarbeit",
    "Abschlussarbeit"
]
phd_cue = [
    "Ph\.? ?D\?. thesis",
    "Ph\.? ?D\.? dissertation",
    "Doctoral thesis",
    "Doctoral dissertation",
    "DPhil thesis",
    "DPhil dissertation",
    "Doctor of Philosophy thesis",
    "Doctor of Philosophy dissertation",
    "Thèse de doctorat",
    "Thèse de troisième cycle",
    "Dissertação de doutorado",
    "Tesis doctoral",
    "Proefschrift",
    "Doktorarbeit",
    "Dissertation zum Erwerb des Doktorgrades",
    "Dissertation zum Erwerb des Doktorgrades der Medizin"
]

MA_RE = re.compile(r"(" + "|".join(ma_cue) + r")")
PHD_RE = re.compile(r"(" + "|".join(phd_cue) + r")")
THESIS_RE = re.compile(r"(" + "|".join(thesis_cue) + r")")
ma_cue_i = r"(?P<ma_cue>" + "|".join(sorted(ma_cue, key=len, reverse=True)) + r")"
phd_cue_i = r"(?P<phd_cue>" + "|".join(sorted(phd_cue, key=len, reverse=True)) + r")"
thesis_cue_i = r"(?P<thesis_cue>" + "|".join(sorted(thesis_cue, key=len, reverse=True)) + r")"
degree_cue_i = r"(?P<degree_cue>\(?[A-Za-z .]{2,6} (?:thesis|dissertation)\)?)"

# Name suffix patterns, for checkand() and checknamesuffix()
suffix_tokens = {"Jr.", "Sr.", "II", "III", "IV", "V"}
suffix_pattern = "|".join(re.escape(s) for s in suffix_tokens)
# Suffix appears as standalone word
suffix_boundary_re = re.compile(rf"\b({suffix_pattern})\b")
# Suffix fused to surname before comma: "Clifton III, Charles"
fused_suffix_re = re.compile(
    rf"^(?P<surname>[^{{}}]+?) (?P<suffix>{suffix_pattern}), (?P<given>.+)$"
)
# Suffix trailing after given name: "Roberts, Frank H. III"
misplaced_suffix_re = re.compile(
    rf"^(?P<surname>[^{{}}]+?), (?P<given>[^{{}}]+?) (?P<suffix>{suffix_pattern})$"
)
# Suffix at end of string with no commas: "Charles Clifton III"
suffix_at_end_re = re.compile(rf"\b({suffix_pattern})\b$")

# Pattern definitions, mosty for parse_natural()
author = r"(?P<author>.+?)"
year = r"\(?(?P<year>[12][0-9]{3})(?P<extrayear>[a-z]?)\)?"
year_np = r"(?P<year>[12][0-9]{3})(?P<extrayear>[a-z]?)?"
title = r"(?P<title>.*?)"
title_ne = r"(?P<title>.+?)"
title_g = r"(?P<title>.+)"
endmark_strict = r"(?P<endmark>[.!?])"
endmark = r"(?P<endmark>[.!?,])"
endmark1 = r"(?P<endmark1>[.!?,])"
editor = r"(?P<editor>.+)"
editor_cue = r"(?P<editor_cue>\([Ee]ds?\.\))"
booktitle = r"(?P<booktitle>.+?)"
journal = r"(?P<journal>.+?)"
note = r"(?P<note>.*)"
roman = r"[ivxlcdmIVXLCDM]+"
arabic = r"[A-Za-z]{0,2}[0-9]+"
joint = r"(?:[A-Za-z]{0,2}[0-9]+|[ivxlcdmIVXLCDM]+)(?: ?([-–—]{1,2}|/|&) ?(?:[A-Za-z]{0,2}[0-9]+|[ivxlcdmIVXLCDM]+))?"
number = rf"(?P<number>{joint})"
series = rf"(?P<series>[^)]+?)"
address = r"(?P<address>[^:]+?)"
publisher = r"(?P<publisher>(?!https?://|doi:|DOI:|handle:|HANDLE:).+)"
publisher_na = r"(?P<publisher_na>(?!https?://|doi:|DOI:|handle:|HANDLE:).+)"
school = r"(?P<school>.+?)"
school_na = r"(?P<school_na>.+?)"
thesisschool_apa = r"(?P<thesisschool>[^\]]+)"
volume_cue = r"(P?<volume_cue>[Vv]olume|[Vv]ol[.]?|[Vv][.]?)"
edition = r"(?P<edition>\d+(?:st|nd|rd|th))"
edition_cue = r"(edn?\.?|edition)"
pages_cue = r"([Pp]ages?|[Pp]p\.|[Pp]\.|(?:[Aa]rticle|Art\.|[Pp]aper|[Cc]ontribution)(?: ID| id| [Nn]o\.)?)"
pages = rf"(?P<pages>{joint})"
volume = rf"(?P<volume>{joint})"

# Extract series and number after title
seriesnumber = r"^(?P<title>.*?) \((?P<series>.+?) (?P<number>[-.0-9/]+)\) ?$"
SERIESNUMBER = re.compile(seriesnumber)

# Match @incollection: year then editor indication
EDITOR = re.compile(f"{year}.*{editor_cue}")

# Match @incollection: year then "In" indication
YEARINCUE = re.compile(f"{year}.*{endmark} In:? ")

# Match @book: title, then address, ": " and publisher
pubaddr = rf"^{title_ne}{endmark_strict} {address}: {publisher}\.?$"
PUBADDR = re.compile(pubaddr, re.IGNORECASE)

# thesis for APA
THESISAPA = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}[.,]? \[{thesisschool_apa}\]{note}"
)
# thesis for LSP
THESISLSP = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}{endmark} "
    rf"(?:{address}: {school}|{school_na})[., ]+"
    rf"\(?({phd_cue_i}|{ma_cue_i}|{thesis_cue_i})\)?"
    rf"[., ]*{note}"
)
# Generic thesis, fuzzy not whitelist
THESISGENERIC = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}{endmark} "
    rf"(?:{address}: {school}|{school_na})[., ]+"
    rf"{degree_cue_i}[., ]*{note}"
)

# @incollection reference in APA, with editor, with parens for edition/volume/pages
INCOLLECTIONAPA = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}{endmark} "
    rf"In:? {editor} {editor_cue}[.,]? {booktitle}[.,]? "
    rf"\((?:{edition} {edition_cue}(?:, )?)?(?:{volume_cue} {volume}(?:, )?)?(?:{pages_cue} {pages})?\)\."
    rf" (?:{address}: {publisher}|{publisher_na})"
)
# @incollection reference in APA, without editor, with parens for edition/volume/pages
INCOLLECTIONAPANOEDITOR = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}{endmark} "
    rf"In:? {booktitle}[.,]? "
    rf"\((?:{edition} {edition_cue}(?:, )?)?(?:{volume_cue} {volume}(?:, )?)?(?:{pages_cue} {pages})?\)\."
    rf" (?:{address}: {publisher}|{publisher_na})"
)
# @incollection reference in LSP, with editor and pages
INCOLLECTIONLSP = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}{endmark} "
    rf"In:? {editor} {editor_cue}[.,]? {booktitle}"
    rf"(?:, {edition} {edition_cue})?"
    rf"(?: \({series} {number}\))?"
    rf"(?:, {volume_cue} {volume})?"
    f"(?:, (?:{pages_cue}[ ]*)?{pages}\.)"
    rf" (?:{address}: {publisher}|{publisher_na})"
)
# @incollection reference in LSP, with editor, without pages
INCOLLECTIONLSPNOPAGES = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}{endmark} "
    rf"In:? {editor} {editor_cue}[.,]? {booktitle}"
    rf"(?:, {edition} {edition_cue})?"
    rf"(?: \({series} {number}\))?"
    rf"(?:, {volume_cue} {volume})?"
    rf"\. (?:{address}: {publisher}|{publisher_na})"
)
# @incollection reference in LSP, without editor, with pages
INCOLLECTIONLSPNOEDITOR = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}{endmark} "
    rf"In:? {booktitle}"
    rf"(?:, {edition} {edition_cue})?"
    rf"(?: \({series} {number}\))?"
    rf"(?:, {volume_cue} {volume})?"
    f"(?:, (?:{pages_cue}[ ]*)?{pages}\.)"
    rf" (?:{address}: {publisher}|{publisher_na})"
)
# @incollection reference in LSP, without editor, without pages
INCOLLECTIONLSPNOEDITORNOPAGES = re.compile(
    rf"{author}[., ]+{year}[., ]+{title}{endmark} "
    rf"In:? {booktitle}"
    rf"(?:, {edition} {edition_cue})?"
    rf"(?: \({series} {number}\))?"
    rf"(?:, {volume_cue} {volume})?"
    rf"\. (?:{address}: {publisher}|{publisher_na})"
)

ARTICLE = re.compile(
    rf"^{author}[.,;:]? [(]?{year_np}[)]?[.,:;]? {title_ne}{endmark} "
    rf"{journal}[.,]? {volume}(?: ?\({number}\))?(?:[.,:;]? (?:{pages}))?(?:\.{note})?$"
)
ARTICLECHI = re.compile(
    rf'{author}\. [“"]{title_ne}{endmark}[”"] {journal} '
    rf'{volume}(?:, [Nn]o\. {number})? \({year}\)(?:: {pages})?\. *{note}'
)
ARTICLEMLA = re.compile(
    rf'{author}\. [“"]{title_ne}{endmark}[”"] {journal}, '
    rf'[Vv]ol\. {volume}(?:, [Nn]o\. {number})?, {year}(?:, (?:p|pp|P|PP)\. {pages})?\. *{note}'
)

BOOK = re.compile(
    rf"{author}(?:[.,]? {editor_cue})?[.,]? {year}[.,]? {title_g}"
)

MISC = re.compile(
    rf"{author}[., ]+{year}[., ]+{title_g}"
)

# Whitelist of trusted DOI compiled patterns by domain
DOI_WHITELIST_RE = {
    "www.degruyter.com": re.compile(rf"/{doi_regex}(?:/html|/pdf)?", re.IGNORECASE),
    "academic.oup.com": re.compile(rf"/doi/{doi_regex}", re.IGNORECASE),
    "www.tandfonline.com": re.compile(rf"/doi/(?:full|abs|pdf)?/{doi_regex}", re.IGNORECASE),
    "doi.org": re.compile(rf"doi\.org/{doi_regex}", re.IGNORECASE),
    "dx.doi.org": re.compile(rf"dx\.doi\.org/{doi_regex}", re.IGNORECASE),
    "doi.acm.org": re.compile(rf"doi\.acm\.org/{doi_regex}", re.IGNORECASE),
    "journals.sagepub.com": re.compile(rf"/doi/{doi_regex}", re.IGNORECASE),
    "asa.scitation.org": re.compile(rf"/doi/{doi_regex}", re.IGNORECASE),
    "doi.wiley.com": re.compile(rf"doi\.wiley\.com/{doi_regex}", re.IGNORECASE),
    "link.springer.com": re.compile(rf"/{doi_regex}", re.IGNORECASE),
    "jbe-platform.com": re.compile(rf"/{doi_regex}", re.IGNORECASE),
    "pubs.asha.org": re.compile(rf"/doi/{doi_regex}", re.IGNORECASE),
    "journals.plos.org": re.compile(rf"article\?id\={doi_regex}", re.IGNORECASE),
    "frontiersin.org": re.compile(rf"/articles/{doi_regex}(?:/full|/abstract)?", re.IGNORECASE),
}
GENERIC_DOI_RE =  re.compile(
    rf"doi/.*?({doi_regex})(?:[/.](?:full|abstract|abs|html|pdf))?$",
    re.IGNORECASE
)

# Patterns to normalize school, address, publisher
SCHOOL_FULL = {
    "MIT": "Massachusetts Institute of Technology",
    "Ohio State University": "The Ohio State University",
    "UC Berkeley": "University of California, Berkeley",
    "UCLA": "University of California, Los Angeles",
    "University of Texas at Austin": "The University of Texas at Austin",
    "University of Texas at Arlington": "The University of Texas at Arlington",
    "University of Massachusetts Amherst": "University of Massachusetts, Amherst"
}
SCHOOL_ADDRESS = {
    "Australian National University": "Canberra",
    "Cornell University": "Ithaca",
    "Harvard University": "Cambridge",
    "Indiana University": "Bloomington",
    "Leiden University": "Leiden",
    "Massachusetts Institute of Technology": "Cambridge",
    "Rice University": "Houston",
    "Stanford University": "Stanford",
    "The Ohio State University": "Columbus",
    "The University of Texas at Arlington": "Arlington",
    "The University of Texas at Austin": "Austin",
    "Universidade Estadual de Campinas": "Campinas",
    "University of California, Berkeley":  "Berkeley",
    "University of California, Los Angeles": "Los Angeles",
    "University of Cambridge": "Cambridge",
    "University of Chicago": "Chicago",
    "University of Connecticut": "Storrs",
    "University of Illinois at Urbana-Champaign": "Urbana-Champaign",
    "University of Kansas": "Lawrence",
    "University of Massachusetts, Amherst": "Amherst",
    "University of Pennsylvania": "Philadelphia",
    "University of Sydney": "Sydney",
    "Yale University": "New Haven"
}

PUBLISHER_SUBSTRING_ADDRESS = {
    ("blackwell", "routledge"): "London",
    ("wiley",): "Hoboken",
    ("gruyter", "mouton",): "Berlin",
}

PUBLISHER_ADDRESS = {
    ("Ablex",): "Norwood",
    ("Brill",): "Leiden",
    ("Cambridge University Press",): "Cambridge",
    ("Chicago Linguistic Society",): "Chicago",
    ("CSLI Publications",): "Stanford",
    ("Elsevier Science",): "Amsterdam",
    ("Foris",): "Dordrecht",
    ("John Benjamins",): "Amsterdam",
    ("Lawrence Erlbaum Associates",): "Mahwah",
    ("Lincom Europa",): "München",
    ("MIT Press",): "Cambridge",
    ("Oxford University Press",): "Oxford",
    ("University of Chicago Press",): "Chicago",
    ("World Scientific",): "Singapore",
}

# ignorecase, .replace(".", "")
PUBLISHER_SUBSTRING = {
    ("ablex",): "Ablex",
    ("(acl)", "association for computational linguistics"): "Association for Computational Linguistics",
    ("brill",): "Brill",
    ("cambridge univ press", "cambridge university press"): "Cambridge University Press",
    ("chicago linguistics society", "chicago linguistic society"): "Chicago Linguistic Society",
    ("(csli)", "center for the study of language and information", "csli publications",): "CSLI Publications",
    ("elsevier",): "Elsevier Science",
    ("erlbaum",): "Lawrence Erlbaum Associates",
    ("de gruyter mouton",): "De Gruyter Mouton",
    ("foris",): "Foris",
    ("ieee", "institute of electrical and electronics engineers",): "IEEE",
    ("benjamins",): "John Benjamins",
    ("wiley & sons", "wiley \& sons", "wiley and sons",): "John Wiley \& Sons",
    ("harmattan",): "L'Harmattan",
    ("lincom",): "Lincom Europa",
    ("mit press",): "MIT Press",
    ("mouton de gruyter",): "Mouton de Gruyter",
    ("multilingual matters",): "Multilingual Matters",
    ("north holland", "north-holland",): "North-Holland",
    ("oxford univ press", "oxford university press"): "Oxford University Press",
    ("pergamon",): "Pergamon Press",
    ("routledge", ): "Routledge",
    ("köppe",): "Rüdiger Köppe",
    ("sage pub",): "SAGE",
    ("springer",): "Springer",
    ("university of chicago press", "chicago univ press"): "University of Chicago Press",
    ("walter de gruyter",): "Walter de Gruyter",
    ("wiley blackwell", "wiley-blackwell", ): "Wiley-Blackwell",
    ("world scientific",): "World Scientific",
}
# ELRA, SIL, Niemeyer, Lang, Reidel, Buske, Erlbaum, Steiner

PUBLISHER_FULL = {
    ("ACL",): "Association for Computational Linguistics",
    ("CUP",): "Cambridge University Press",
    ("CLS",): "Chicago Linguistic Society",
    ("CLSI",): "CSLI Publications",
    ("OUP",): "Oxford University Press",
}

PUBLISHER_VARIANT = {
    ("de Gruyter",): "De Gruyter",
    ("Sage",): "SAGE",
    ("Routeledge",): "Routledge",
}