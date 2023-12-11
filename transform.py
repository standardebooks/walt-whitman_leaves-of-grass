#!/usr/bin/env python3

import os
import re
import sys

# The name of the input file (used solely for error messages).
infilename = ''

# The prolog and epilog for all output files
prolog = '''\
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/, se: https://standardebooks.org/vocab/1.0" xml:lang="en-US">
<head>
<title>%s</title>
<link href="../css/core.css" rel="stylesheet" type="text/css"/>
<link href="../css/local.css" rel="stylesheet" type="text/css"/>
</head>
<body epub:type="bodymatter">
<section id="%s" epub:type="chapter">
'''
epilog = '''\
</section>
</body>
</html>
'''

# The list of valid indentation levels.
#  2 = unindented line of poetry
#  7 = section header or label (differentiated by a terminating colon)
# 10 = line indented 4 ems
# 12 = line indented 5 ems
# 14 = line indented 6 ems
# 16 = line indented 7 ems
# (No indentation marks a title, subtitle, or a separator line.)
indentlevels = (2, 7, 10, 12, 14, 16)

# The list of parser states.
EmptyState    = 0   # initial null state
BookCreated   = 1   # at the top of a new output file
OutsidePoem   = 2   # in between poems
TitleRead     = 3   # at the start of a poem, having parsed its title
InSubtitle    = 4   # parsing a poem's subtitle/bridgehead
BetweenVerses = 5   # inside a poem, in between stanzas
VerseStarted  = 6   # at the beginning of a stanza
InsideVerse   = 7   # inside a stanza

# Construct a valid ID from a title. The usedids hash is used to
# ensure that all IDs are unique.
usedids = {}
def mkid(title):
    global usedids
    id = re.sub(r'[- ]+', '-', title.lower())
    id = id.strip('-')
    id = re.sub(r'[^-\w]+', '', id)
    if id in usedids:
        usedids[id] += 1
        id = '%s-%d' % (id, usedids[id])
    else:
        usedids[id] = 1
    return id

# Decode the basic markup characters for the output.
# _foo_ for italicized <q>
# +foo+ for <em>
# *foo* for small-caps <b>
# =foo= for italics <i>
def markup(text):
    if '_' in text:
        text = re.sub(r'_([^_]+)_', r'<q>\1</q>', text)
    if '+' in text:
        text = re.sub(r'\+([^+]+)\+', r'<em>\1</em>', text)
    if '*' in text:
        text = re.sub(r'\*([^*]+)\*', r'<b>\1</b>', text)
    if '=' in text:
        text = re.sub(r'=([^=]+)=', r'<i>\1</i>', text)
    if '&' in text:
        text = text.replace('&', '&amp;')
    return text

# Parse the input file line by line and output one or more XHTML files.
# outdir specifies the directory in which to create output files.
def transform(input, outdir):
    outfilename = ''
    output = None
    lineno = 0
    state = EmptyState
    sectioned = False
    nhead = 0
    title = None
    id = None
    prefix = ''

    for line in input.split('\n'):
        lineno += 1
        if line.startswith(' '):
            indent = re.search(r'\S', line).start()
            line = line[indent:]
        else:
            indent = 0

        if line.startswith('<!--'):
            # Start of a new output file
            if state != EmptyState and state != OutsidePoem:
                sys.exit('%s:%d: book terminated unexpectedly:\n%s\n' %
                         (infilename, lineno, line))
            if output:
                output.write(epilog)
                output.close()
            title = line.replace('<!-- ', '', 1).replace(' -->', '', 1)
            id = mkid(title)
            outfilename = os.path.join(outdir, id + '.xhtml')
            output = open(outfilename, 'w')
            output.write(prolog % (title, id))
            output.write('<h2 epub:type="title">%s</h2>\n' % markup(title))
            nhead = 3
            state = BookCreated
            continue
        elif line.startswith('<'):
            sys.exit('%s:%d: unexpected HTML in file:\n%s\n' %
                     (infilename, lineno, line))

        if state == EmptyState:
            if line:
                sys.exit('%s:%d: unexpected content before first book:\n%s\n' %
                         (infilename, lineno, line))
            continue
        if state == OutsidePoem:
            if line == '' or line == '.':
                continue
            elif indent:
                sys.exit('%s:%d: poem with no title:\n%s\n' %
                         (infilename, lineno, line))
            id = mkid(line)
            title = markup(line)
            output.write('<article id="%s" epub:type="z3998:poem">\n' % id)
            prefix = '\t'
            state = TitleRead
            continue
        if state == TitleRead:
            if line == '':
                # Title with no subtitle/bridgehead
                output.write('\t<h%d epub:type="title">%s</h%d>\n' %
                             (nhead, title, nhead))
                nhead += 1
                state = BetweenVerses
            elif line.startswith('['):
                # Title with subtitle/bridgehead
                output.write('\t<header>\n')
                output.write('\t\t<h%d epub:type="title">%s</h%d>\n' %
                             (nhead, title, nhead))
                output.write('\t\t<p epub:type="bridgehead">')
                nhead += 1
                if line.endswith(']'):
                    output.write('%s</p>\n\t</header>\n' % markup(line[1:-1]))
                    state = BetweenVerses
                else:
                    output.write(markup(line[1:]))
                    state = InSubtitle
            else:
                sys.exit('%s:%d: invalid subtitle:\n%s\n' %
                         (infilename, lineno, line))
            continue
        if state == InSubtitle:
            if line.endswith(']'):
                output.write(' %s</p>\n\t</header>\n' % markup(line[:-1]))
                state = BetweenVerses
            else:
                output.write(' ' + markup(line))
            continue

        if state == BookCreated:
            if line == '':
                continue
            elif line == '.':
                state = OutsidePoem
                continue
            else:
                output.write('<article id="%s" epub:type="z3998:poem">\n' % id)
                state = BetweenVerses
                # No continue; process line under the BetweenVerses state.

        if state == BetweenVerses:
            if line == '':
                continue
            elif line == '.':
                # End of current poem
                if sectioned:
                    output.write('\t</section>\n')
                    sectioned = False
                output.write('</article>\n')
                nhead -= 1
                state = OutsidePoem
                continue
            elif indent == 7:
                # Begin section
                if sectioned:
                    output.write('\t</section>\n')
                partid = mkid('%s-%s' % (id, line))
                output.write('\t<section id="%s" epub:type="part">\n' % partid)
                heading = markup(line)
                if heading.endswith(':'):
                    heading = heading[:-1]
                    output.write('\t\t<header class="speaker">\n')
                    output.write('\t\t\t<p epub:type="bridgehead">%s</p>\n' %
                                 heading)
                    output.write('\t\t</header>\n')
                elif line.isnumeric():
                    output.write('\t\t<h%d epub:type="ordinal">%s</h%d>\n' %
                                 (nhead, heading, nhead))
                else:
                    output.write('\t\t<h%d epub:type="title">%s</h%d>\n' %
                                 (nhead, heading, nhead))
                output.write('\t\t<p>\n')
                state = VerseStarted
                sectioned = True
                prefix = '\t\t'
                continue
            elif indent > 0:
                output.write('%s<p>\n' % prefix)
                state = VerseStarted
                # No continue, keep processing the current line.
        elif state == VerseStarted or state == InsideVerse:
            if line == '':
                output.write('%s</p>\n' % prefix)
                state = BetweenVerses
                continue
            else:
                pass
                # No continue, keep processing the current line.

        # Shared processing for VerseStarted and InsideVerse.
        if line == '.':
            sys.exit('%s:%d: poem ended without blank line' %
                     (infilename, lineno))
        if indent == 0:
            sys.exit('%s:%d: title found in mid-poem:\n%s' %
                     (infilename, lineno, line))
        elif indent == 7:
            sys.exit('%s:%d: subhead in mid-stanza:\n%s' %
                     (infilename, lineno, line))
        elif indent not in indentlevels:
            sys.exit('%s:%d: unexpected indent level %d:\n%s' %
                     (infilename, lineno, indent, line))
        if state == InsideVerse:
            output.write('%s\t<br/>\n' % prefix)
        else:
            state = InsideVerse
        if indent == 2:
            output.write('%s\t<span>' % prefix)
        else:
            output.write('%s\t<span class="i%d">' % (prefix, (indent - 8) / 2))
        output.write(markup(line) + '</span>\n')

    # All done: close the last output file and return.
    if output:
        output.write(epilog)
        output.close()


# Process the command-line arguments as input files.
def main(argv):
    global infilename
    for arg in argv:
        infilename = arg
        path = os.path.split(arg)
        if len(path) > 1:
            outdir = path[0]
        else:
            outdir = '.'
        file = open(infilename, 'rt')
        text = file.read()
        file.close()
        transform(text, outdir)


if __name__ == "__main__":
    main(sys.argv[1:])
