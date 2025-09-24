import re

from langsci.bib.bibnouns import (
    LANGUAGENAMES,
    OCEANNAMES,
    COUNTRIES,
    CONTINENTNAMES,
    CITIES,
    OCCURREDREPLACEMENTS,
)

PRESERVATIONPATTERN = re.compile(
    r"\b(%s)\b"
    % (
        "|".join(
            LANGUAGENAMES
            + COUNTRIES
            + OCEANNAMES
            + CONTINENTNAMES
            + CITIES
            + OCCURREDREPLACEMENTS
        )
    )
)

# Compiled pattern for Binnenmajuskeln (= CamelCase), was CONFERENCEPATTERN
CAMELCASE_RE = re.compile(r"([A-Z][A-Za-z0-9\-']*[A-Z][A-Za-z0-9\-']+)")

# Compiled pattern for capitalized proceedings-like keywords, was PROCEEDINGSPATTERN
PROCEEDINGS_RE = re.compile(r"\b(Proceedings|Workshop|Conference|Symposium)\b")

# Compiled pattern for lowercase proceedings-like keywords
PROCEEDINGS_LC_RE = re.compile(r"\b(proceedings|workshop|conference|symposium)\b")

# Compiled pattern for proceedings-like keywords (to flag suspicious booktitles fuzzily)
PROCEEDINGS_FUZZY_RE = re.compile(r"(roceedings|orkshop|onference|ymposium)", re.IGNORECASE)

# Compiled pattern for volume indication in title
TITLEVOLUME_RE = re.compile("(, )?([Vv]olume|[Vv]ol.?|Band|[Tt]ome) *([0-9IVXivx]+)")

# Compiled pattern for thesis/disseration indication
THESIS_RE = re.compile(r"(thesis(es)?|dissertation|proquest)", re.IGNORECASE)

# Fulldate patterns
yyyy = "[12][0-9][0-9][0-9]"
mm = "[10]?[0-9]"
dd = "[0123]?[0-9]"
iso_date     = rf"{yyyy}-{mm}-{dd}"
euro_date    = rf"{dd}\.{mm}\.{yyyy}"
slash_date_1 = rf"{dd}/{mm}/{yyyy}"
slash_date_2 = rf"{mm}/{dd}/{yyyy}"

# Compiled pattern for url and date, separated by space (and junk)
url_pattern = r"https?://\S+"
URL_URLDATE_RE = re.compile(rf"{url_pattern} .*?({iso_date}|{euro_date})")

# Compiled pattern for iso_date 
ISO_DATE_RE = re.compile(rf"\b{iso_date}\b")

# Compiled pattern for url, right-bounded by space or parenthesis
URL_RE = re.compile(r"(https?://[^ \(\)]+)", re.IGNORECASE)

# Compiled pattern for domain in url
DOMAIN_RE = re.compile(r"^https?://([^/]+)", re.IGNORECASE)

# Compiled pattern for unescaped ampersand
AMP_RE = re.compile(r"(?<!\\)&")

# Compiled pattern for article id: case-insensitive, match 1 to 3 article-id-keywords, capture the alphanumeric article ID
ARTICLE_ID_RE = re.compile(r"(?i)^(?:article|art\.?|id\.?|number|no\.?){1,3} *([A-Za-z0-9]+)")

# Parse type and key of bibentry. Assumes leading "@" already removed. Eat whitespace.
TYPKEYFIELDS = r"^\s*([^\{\s]+)\s*\{\s*([^,\s]+)\s*,\s*((?:.|\n)*)\}"

# Compiled pattern for main title, e.g. "Maintitle: the subtitle", to capitalize and protect
MAINTITLE_RE = re.compile(r"([:\?!]) +([a-zA-Z])")

# Compiled pattern for canonical DOI
doi_pattern = r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)"
DOI_RE = re.compile(doi_pattern, re.IGNORECASE)

# Whitelist of trusted DOI compiled patterns by domain
DOI_WHITELIST_RE = {
    "www.degruyter.com": re.compile(rf"/{doi_pattern}(?:/html|/pdf)?", re.IGNORECASE),
    "academic.oup.com": re.compile(rf"/doi/{doi_pattern}", re.IGNORECASE),
    "www.tandfonline.com": re.compile(rf"/doi/(?:full|abs|pdf)?/{doi_pattern}", re.IGNORECASE),
    "doi.org": re.compile(rf"doi\.org/{doi_pattern}", re.IGNORECASE),
    "dx.doi.org": re.compile(rf"dx\.doi\.org/{doi_pattern}", re.IGNORECASE),
    "doi.acm.org": re.compile(rf"doi\.acm\.org/{doi_pattern}", re.IGNORECASE),
    "journals.sagepub.com": re.compile(rf"/doi/{doi_pattern}", re.IGNORECASE),
    "asa.scitation.org": re.compile(rf"/doi/{doi_pattern}", re.IGNORECASE),
    "doi.wiley.com": re.compile(rf"doi\.wiley\.com/{doi_pattern}", re.IGNORECASE),
    "link.springer.com": re.compile(rf"/{doi_pattern}", re.IGNORECASE),
    "jbe-platform.com": re.compile(rf"/{doi_pattern}", re.IGNORECASE),
    "pubs.asha.org": re.compile(rf"/doi/{doi_pattern}", re.IGNORECASE),
    "dx.plos.org": re.compile(r"/(10\.1371/journal\.pone\.\d+)", re.IGNORECASE),  # special case
    "frontiersin.org": re.compile(rf"/articles/{doi_pattern}(?:/full|/abstract)?", re.IGNORECASE)
}
GENERIC_DOI_RE =  re.compile(
    rf"doi/.*?({doi_pattern})(?:[/.](?:full|abstract|abs|html|pdf))?$",
    re.IGNORECASE
)

# Compiled pattern for handle
handle_pattern = r"(\d{4,5}\.\d{4,5}/[-._;()/:A-Z0-9]+)"
HANDLE_RE = re.compile(handle_pattern, re.IGNORECASE)

# Patterns to normalize school, address, publisher
SCHOOL_FULL = {
    "{MIT}": "{Massachusetts Institute of Technology}",
    "{Ohio State University}": "{The Ohio State University}",
    "{UC Berkeley}": "{University of California, Berkeley}",
    "{UCLA}": "{University of California, Los Angeles}",
    "{University of Texas at Austin}": "{The University of Texas at Austin}",
    "{University of Texas at Arlington}": "{The University of Texas at Arlington}",
    "{University of Massachusetts Amherst}": "{University of Massachusetts, Amherst}"
}
SCHOOL_ADDRESS = {
    "{Australian National University}": "{Canberra}",
    "{Cornell University}": "{Ithaca}",
    "{Harvard University}": "{Cambridge}",
    "{Indiana University}": "{Bloomington}",
    "{Leiden University}": "{Leiden}",
    "{Massachusetts Institute of Technology}": "{Cambridge}",
    "{Rice University}": "{Houston}",
    "{Stanford University}": "{Stanford}",
    "{The Ohio State University}": "{Columbus}",
    "{The University of Texas at Arlington}": "{Arlington}",
    "{The University of Texas at Austin}": "{Austin}",
    "{Universidade Estadual de Campinas}": "{Campinas}",
    "{University of California, Berkeley}":  "{Berkeley}",
    "{University of California, Los Angeles}": "{Los Angeles}",
    "{University of Cambridge}": "{Cambridge}",
    "{University of Chicago}": "{Chicago}",
    "{University of Connecticut}": "{Storrs}",
    "{University of Illinois at Urbana-Champaign}": "{Urbana-Champaign}",
    "{University of Kansas}": "{Lawrence}",
    "{University of Massachusetts, Amherst}": "{Amherst}",
    "{University of Pennsylvania}": "{Philadelphia}", 
    "{University of Sydney}": "{Sydney}",
    "{Yale University}": "{New Haven}"
}
PUBLISHER_ADDRESS = {
    ("benjamins",): "{Amsterdam}",
    ("cambridge", "cup"): "{Cambridge}",
    ("oxford", "oup"): "{Oxford}",
    ("blackwell", "routledge"): "{London}",
    ("gruyter", "mouton"): "{Berlin}",
    ("wiley",): "{Hoboken}",
    ("brill",): "{Leiden}",
    ("lincom",): "{München}",
    ("foris",): "{Dordrecht}",
    ("mit press",): "{Cambridge}",
}
PUBLISHER_FULL = {
    "{Ablex Publishing Co}": "{Ablex}",
    "{Ablex Publishing Corporation}": "{Ablex}",
    "{Association for Computational Linguistics (ACL)}": "{Association for Computational Linguistics}",
    "{The Association for Computational Linguistics}": "{Association for Computational Linguistics}",
    "{The Association for Computational Linguistics (ACL)}": "{Association for Computational Linguistics}",
    "{ACL}": "{Association for Computational Linguistics}",
    "{CUP}": "{Cambridge University Press}",
    "{Chicago Linguistics Society}": "{Chicago Linguistic Society}",
    "{CSLI}": "{CSLI Publications}",
    "{de Gruyter}": "{De Gruyter}",
    "{de Gruyter Mouton}": "{De Gruyter Mouton}",
    "{Elsevier Science Ltd}": "{Elsevier Science}",
    "{Elsevier Science Ltd.}": "{Elsevier Science}",
    "{Elsevier B.V}": "{Elsevier Science}",
    "{Elsevier Inc}": "{Elsevier Science}",
    "{Foris Publications}": "{Foris}",
    "{IEEE COMPUTER SOC}": "{IEEE}",
    "{John Benjamins Publishing Company}": "{John Benjamins}",
    "{Benjamins}": "{John Benjamins}",
    "{J. Benjamins}": "{John Benjamins}",
    "{John Wiley \& Sons, Ltd}": "{John Wiley \& Sons",
    "{John Wiley \& Sons Ltd}": "{John Wiley \& Sons",
    "{John Wiley and Sons, Ltd}": "{John Wiley \& Sons",
    "{John Wiley and Sons Ltd}": "{John Wiley \& Sons",
    "{John Wiley and Sons}": "{John Wiley \& Sons",
    "{Editions L’Harmattan}": "{L'Harmattan}",
    "{Editions L'Harmattan}": "{L'Harmattan}",
    "{l'Harmattan}": "{L'Harmattan}",
    "{LINCOM}": "{Lincom Europa}",
    "{The MIT Press}": "{MIT Press}",
    "{MIT press}": "{MIT Press}",
    "{Multilingual matters}": "{Multilingual Matters}",
    "{North Holland}": "{North-Holland}",
    "{North-Holland Publishing Company}": "{North-Holland}",
    "{OUP}": "{Oxford University Press}",
    "{Pergamon}": "{Pergamon Press}",
    "{Routeledge}": "{Routledge}",
    "{Rüdiger Köppe Verlag}": "{Rüdiger Köppe}",
    "{Köppe}": "{Rüdiger Köppe}",
    "{Sage Publications}": "{SAGE}",
    "{SAGE Publications}": "{SAGE}",
    "{Sage}": "{SAGE}",
    "{Springer Verlag}": "{Springer}",
    "{Springer Berlin Heidelberg}": "{Springer}",
    "{Springer Netherlands}": "{Springer}",
    "{University of Chicago Press}": "{The University of Chicago Press}",
    "{Walter de Gruyter GmbH \& Co. KG}": "{Walter de Gruyter}",
    "{World Scientific Publishing}": "{World Scientific}",    
}
# todo: ELRA, SIL, Niemeyer, Lang, Reidel, Buske, Erlbaum, Steiner

# Pattern definitions, mosty for parse_natural()
author = r"(?P<author>.*?)"
year = r"\(? *(?P<year>[12][0-9]{3})(?P<extrayear>[a-z]?) *\)?"
pages = r"(?P<pages>[A-Za-z]?[0-9ivxlcIXVLC]+(?: *[-–—]+ *[A-Za-z]?[0-9ivxlcIVXLC]+)?)"
pppages = rf"(?:pp?\.? *)?{pages}"
title = r"(?P<title>.*?)"
title_ne = r"(?P<title>.+?)"
title_g = r"(?P<title>.+)"
endmark_strict = r"(?P<endmark>[.!?])"
endmark = r"(?P<endmark>[.!?,])"
endmark1 = r"(?P<endmark1>[.!?,])"
endmark2 = r"(?P<endmark2>[.!?])"
editor = r"(?P<editor>.+)"
ed = r"\([Ee]ds?\.?\)"
ed_flag =  rf"(?P<ed>{ed})?"
booktitle = r"(?P<booktitle>.+)"
journal = r"(?P<journal>[^a-z].+?)"
note = r"(?P<note>.*)"
mathesis = "\(?(MA|Master's|Masters|Master|M\. ?A\.) [Tt]hesis\)?"
phdthesis = r"\(?([Dd]octoral|PhD|Ph\.D\.)? ?([Tt]hesis|[Dd]issertation)\)?"
numbervolume = "(?P<volume>[-.0-9/]+) *(\((?P<number>[-0-9/]+)\))?"
pubaddr = r"(?P<address>.+) *:(?!/) *(?P<publisher>[^:]\.?[^.]+)"
pubaddrng = r"(?:(?P<address>.+?) *:(?!//|doi:|handle:) *)?(?P<publisher>.+)"
pword = r"(?:pp\.?|p\.?|pages|Page[s]?)\s*"
seriesnumber = r"(?P<newtitle>.*) \((?P<series>.*?) +(?P<number>[-.0-9/]+)\)"
SERIESNUMBER = re.compile(seriesnumber)
roman = r"[ivxlcdmIVXLCDM]+"
arabic = r"[A-Za-z]{0,2}[0-9]+"
joint = rf"(?:{arabic}|{roman})(?:[-–—/]{arabic}|{roman})?"
volumenumber = (
    rf"(?:"
        rf"(?P<volume_paren>{joint}) *\((?P<number_paren>{joint})\)"
        rf"|"
        rf"(?P<volume_sep>{joint})[ ,:;]+(?:no\.|number|num\.|#)? *(?P<number_sep>{joint})"
        rf"|"
        rf"(?P<volume_only>{joint})"
    rf")"
)
BOOK = re.compile(
    "{author}[., ]* {ed}[., ]*{year}[\., ]*{title}".format(
        author=author,
        ed=ed_flag,
        year=year,
        title=title_g,
    )
)
ARTICLE = re.compile(
    "{author}[., ]*{year}[., ]*{title}{endmark} +{journal}[.,]? {volumenumber}(?: *[.:,] *| +)?(?:{pages})?\. *{note}".format(
        author=author,
        year=year,
        title=title_ne,
        endmark=endmark,
        journal=journal,
        volumenumber=volumenumber,
        pages=pages,
        note=note,
    )
)
INCOLLECTION = re.compile(
    "{author}[., ]*{year}[., ]*{title}{endmark} In:? {editor} {ed}[.,]? {booktitle}{endmark1} \(?{pages}\)?\. +{pubaddrng}".format(
        author=author,
        year=year,
        title=title,
        endmark=endmark,
        editor=editor,
        ed=ed,
        booktitle=booktitle,
        endmark1=endmark1,
        pages=pages,
        pubaddrng=pubaddrng,
    )
)
INCOLLECTIONPARENS = re.compile(
    "{author}[., ]*{year}[., ]*{title}{endmark} In:? {editor} {ed}[.,]? {booktitle}[.,]? \((?:{pword})?{pages}\)\. +{pubaddrng}".format(
        author=author,
        year=year,
        title=title,
        endmark=endmark,
        editor=editor,
        ed=ed,
        booktitle=booktitle,
        pword=pword,
        pages=pages,
        pubaddrng=pubaddrng,
    )
)
INCOLLECTIONMISSING = re.compile(
    "{author}[., ]*{year}[., ]*{title}{endmark} *In:? *{editor} *{ed}[.,]? {booktitle}".format(
        author=author,
        year=year,
        title=title,
        endmark=endmark,
        editor=editor,
        ed=ed,
        booktitle=booktitle,
    )
)
MASTERSTHESIS = re.compile(
    "{author}[., ]*{year}[., ]*{title}{endmark} +{pubaddrng}\. *{mathesis}{note}".format(
        author=author,
        year=year,
        title=title,
        endmark=endmark,
        pubaddrng=pubaddrng,
        mathesis=mathesis,
        note=note,
    )
)
PHDTHESIS = re.compile(
    "{author}[., ]*{year}[., ]*{title}{endmark} +{pubaddrng}\. *{phdthesis}{note}".format(
        author=author,
        year=year,
        title=title,
        endmark=endmark,
        pubaddrng=pubaddrng,
        phdthesis=phdthesis,
        note=note,
    )
)
XMISC = re.compile(
    "{author}[., ]*{year}[., ]*{title}{endmark} *(note)".format(
        author=author,
        year=year,
        title=title,
        endmark=endmark,
        note=note,
    )
)
MISC = re.compile(
    "{author}[., ]*{year}[., ]*{title}{endmark} *{note}".format(
        author=author,
        year=year,
        title=title_g,
        endmark=endmark,
        note=note,
    )
)

# Compiled patterns for determining @incollection: year then editor indication
EDITOR = re.compile(f"{year}.*{ed}")

PUBADDR = re.compile(pubaddr)

# Legacy
PAGES = re.compile(pages)
URLDATE = re.compile(rf"[\[\(]?({yyyy}-{mm}-{dd}|{dd}.{mm}.{yyyy}|{dd}/{mm}/{yyyy}|{mm}/{dd}/{yyyy})[\]\)]?")
url = r"(?P<url>(https?://)?www\.[a-zA-Z0-9-]+\.[-A-Za-z0-9\.]+(/[^ ]+)?)\.?"
URL = re.compile(url)
NUMBERVOLUME = re.compile(numbervolume)