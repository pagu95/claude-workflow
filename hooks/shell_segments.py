"""Split a shell command into simple commands (token lists), quote-aware, for the PreToolUse guards.

`a "x|y" && b c` -> [["a", "x|y"], ["b", "c"]]. Splits on ; & | ( ) and newlines outside quotes and
drops leading VAR=value assignments. If the command can't be tokenised (an unbalanced quote, often an
apostrophe inside a heredoc body), it falls back to splitting on those characters without quote
awareness, which may over-split but never merges two commands into one.
"""
import re
import shlex

OPS = ";&|()\n"
ENV_ASSIGN = re.compile(r"^\w+=")


def _strip_env(tokens):
    while tokens and ENV_ASSIGN.match(tokens[0]):
        tokens = tokens[1:]
    return tokens


def segments(command):
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=OPS)
        lex.whitespace = " \t\r"
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        parts = re.split(r"[;&|()\n]", command)
        out = []
        for part in parts:
            toks = _strip_env(part.split())
            if toks:
                out.append(toks)
        return out
    out, cur = [], []
    for tok in tokens:
        if tok and all(ch in OPS for ch in tok):
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return [s for s in (_strip_env(s) for s in out) if s]
