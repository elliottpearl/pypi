"""
Get rid of selected LaTeX features which cause problems in various respects
Todo:
    Fix \i and \j
    Fix {\' a}
    author = {Ha{\"\i}k, Isabelle},
    author = {Fran{\c c}ois, Alexandre},
    author = {David P.\ B.\ Massamba},
    author = {Chavez‐Peon, Mario E.}, U+2010 hyphen, also U+2011 non-breaking hypen
    author = {Bickel, Balthasar and Hildebrandt., Kristine A. and Schiering, René},
    author = {Robert, St{e}phane},
"""

import re

#LATEXDIACRITICS = """'`^~"=.vdHuk"""
LATEXDIACRITICS = """'`^~"=.vdHukcrb"""


def dediacriticize(s, stripbraces=True):
    """
    Remove all LaTeX styles diacritics from the input and return the bare string

    LaTeX offers a variety of diacritics via {\_{x}}, where the underscore can be any of the following
    - ' : acute
    - ` : grave
    - ^ : circumflex
    - ~ : tilde
    - " : dieresis
    - = : macron
    - . : dot above
    - v : hacek
    - d : dot below
    - H : double acute
    - u : breve
    - k : ogonek
    - c : cedilla
    - r : ring above
    - b : bar under
    
    The braces are optional, but commonly used.

    Args:
      s (str): the string to dediacriticize

    Returns:
      str: the input string stripped of LaTeX diacritics

    """
    tmpstring = s
    if stripbraces:
        # get rid of Latex diacritics like {\'{e}}
        tmpstring = re.sub(r"{\\[%s]{([A-Za-z])}}" % LATEXDIACRITICS, r"\1", tmpstring)
    # get rid of Latex diacritics like \'{e}
    tmpstring = re.sub(r"\\[%s]{([A-Za-z])}" % LATEXDIACRITICS, r"\1", tmpstring)
    # get rid of Latex diacritics like \'e
    result = re.sub(r"\\[%s]([A-Za-z])" % LATEXDIACRITICS, r"\1", tmpstring)
    return result
