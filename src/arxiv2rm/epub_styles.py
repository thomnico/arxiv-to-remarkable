"""CSS stylesheets for reMarkable-optimized EPUB."""

# reMarkable-optimized CSS stylesheet
REMARKABLE_CSS = """
/* reMarkable EPUB Stylesheet */
/* Optimized for e-ink display with OpenDyslexic font */

/* Font faces - OpenDyslexic */
@font-face {
    font-family: 'OpenDyslexic';
    src: url('../fonts/OpenDyslexic-Regular.otf') format('opentype');
    font-weight: normal;
    font-style: normal;
}

@font-face {
    font-family: 'OpenDyslexic';
    src: url('../fonts/OpenDyslexic-Bold.otf') format('opentype');
    font-weight: bold;
    font-style: normal;
}

@font-face {
    font-family: 'OpenDyslexic';
    src: url('../fonts/OpenDyslexic-Italic.otf') format('opentype');
    font-weight: normal;
    font-style: italic;
}

@font-face {
    font-family: 'OpenDyslexic';
    src: url('../fonts/OpenDyslexic-BoldItalic.otf') format('opentype');
    font-weight: bold;
    font-style: italic;
}

/* Body and general typography */
body {
    font-family: 'OpenDyslexic', 'DejaVu Sans', Arial, sans-serif;
    font-size: 14pt;
    line-height: 1.6;
    margin: 2em 1.5em;
    text-align: left;
    color: #000000;
    background-color: #FFFFFF;
}

/* Headings */
h1 {
    font-size: 20pt;
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 0.75em;
    page-break-after: avoid;
    line-height: 1.3;
}

h2 {
    font-size: 18pt;
    font-weight: bold;
    margin-top: 1.25em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    line-height: 1.3;
}

h3 {
    font-size: 16pt;
    font-weight: bold;
    margin-top: 1em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    line-height: 1.3;
}

h4, h5, h6 {
    font-size: 15pt;
    font-weight: bold;
    margin-top: 0.75em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
    line-height: 1.3;
}

/* Paragraphs */
p {
    margin-top: 0.5em;
    margin-bottom: 0.5em;
    text-align: left;
    text-indent: 0;
    orphans: 2;
    widows: 2;
}

/* Abstract */
.abstract {
    margin: 2em 2em;
    padding: 1em;
    font-style: italic;
    border-left: 3px solid #000000;
}

.abstract p {
    margin-top: 0.25em;
    margin-bottom: 0.25em;
}

/* Lists */
ul, ol {
    margin-top: 0.5em;
    margin-bottom: 0.5em;
    padding-left: 2em;
}

li {
    margin-top: 0.25em;
    margin-bottom: 0.25em;
}

/* Figures and images */
figure {
    margin: 1.5em 0;
    text-align: center;
}

img {
    max-width: 100%;
    height: auto;
    display: block;
    margin-left: auto;
    margin-right: auto;
}

figcaption {
    font-size: 12pt;
    font-style: italic;
    text-align: center;
    margin-top: 0.5em;
    padding: 0 1em;
}

/* Tables */
table {
    margin: 1.5em auto;
    border-collapse: collapse;
    width: 100%;
    font-size: 12pt;
}

thead {
    border-bottom: 2px solid #000000;
}

tbody tr {
    border-bottom: 1px solid #CCCCCC;
}

th, td {
    padding: 0.6em 0.4em;
    text-align: left;
    vertical-align: top;
}

th {
    font-weight: bold;
    background-color: #F0F0F0;
    border-bottom: 2px solid #000000;
    text-align: center;
}

td {
    border-bottom: 1px solid #E0E0E0;
}

/* Center-align numeric cells */
td:has(img) {
    text-align: center;
}

/* Table container */
.table-container {
    margin: 2em 0;
}

.table-caption {
    font-weight: bold;
    text-align: center;
    margin-bottom: 0.5em;
    font-size: 13pt;
}

/* Code blocks */
pre {
    font-family: 'Courier New', monospace;
    font-size: 11pt;
    line-height: 1.4;
    margin: 1em 0;
    padding: 1em;
    border: 1px solid #000000;
    background-color: #F8F8F8;
    overflow-x: auto;
}

code {
    font-family: 'Courier New', monospace;
    font-size: 12pt;
}

/* Inline code */
p code, li code {
    background-color: #F0F0F0;
    padding: 0.1em 0.3em;
    border: 1px solid #CCCCCC;
}

/* Blockquotes */
blockquote {
    margin: 1em 2em;
    padding-left: 1em;
    border-left: 3px solid #000000;
    font-style: italic;
}

/* Links */
a {
    color: #000000;
    text-decoration: underline;
}

/* Footnotes */
.footnote {
    font-size: 11pt;
    vertical-align: super;
}

.footnotes {
    margin-top: 2em;
    padding-top: 1em;
    border-top: 1px solid #000000;
    font-size: 12pt;
}

/* Page breaks */
.page-break {
    page-break-after: always;
}

/* E-ink optimizations */
/* High contrast, no gradients, solid colors only */
strong, b {
    font-weight: bold;
}

em, i {
    font-style: italic;
}

/* Avoid orphans and widows */
h1, h2, h3, h4, h5, h6 {
    page-break-after: avoid;
}

/* Navigation */
nav ol {
    list-style-type: none;
    padding-left: 0;
}

nav li {
    margin-bottom: 0.5em;
}

/* Title page */
.title-page {
    text-align: center;
    margin-top: 3em;
}

.title-page h1 {
    font-size: 24pt;
    margin-bottom: 1em;
}

.title-page .authors {
    font-size: 16pt;
    margin-bottom: 2em;
}

.title-page .author {
    display: block;
    margin: 0.25em 0;
}

/* Math equations (preserve from LaTeX) */
.math {
    font-family: 'STIX Two Math', 'Cambria Math', 'Latin Modern Math', serif;
    font-style: italic;
}

.math-display {
    display: block;
    text-align: center;
    margin: 1em 0;
}

/* Notes section - ruled area for handwritten notes */
.notes-section {
    margin-top: 4em;
    padding-top: 1em;
    border-top: 2px solid #000000;
}

.notes-line {
    height: 2em;
    border-bottom: 1px solid #CCCCCC;
    margin: 0;
}
"""


def get_remarkable_css() -> str:
    """
    Get CSS stylesheet optimized for reMarkable e-ink display.

    Returns:
        CSS content as string
    """
    return REMARKABLE_CSS


# Alternative: Minimal CSS without OpenDyslexic
MINIMAL_CSS = """
/* Minimal reMarkable EPUB Stylesheet */

body {
    font-family: serif;
    font-size: 14pt;
    line-height: 1.6;
    margin: 2em 1.5em;
}

h1 { font-size: 20pt; margin: 1.5em 0 0.75em; }
h2 { font-size: 18pt; margin: 1.25em 0 0.5em; }
h3 { font-size: 16pt; margin: 1em 0 0.5em; }

p { margin: 0.5em 0; }

figure { margin: 1.5em 0; text-align: center; }
img { max-width: 100%; height: auto; }
figcaption { font-size: 12pt; font-style: italic; margin-top: 0.5em; }
"""


def get_minimal_css() -> str:
    """
    Get minimal CSS stylesheet (no custom fonts).

    Returns:
        CSS content as string
    """
    return MINIMAL_CSS
