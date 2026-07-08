#!/usr/bin/env python3
"""Generate docs/dokumentation.pdf (German user documentation) via reportlab.

Usage: uv run python docs/build_pdf.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).parent / "dokumentation.pdf"

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1x", parent=styles["Heading1"], spaceBefore=18, spaceAfter=8)
H2 = ParagraphStyle("H2x", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle("Bodyx", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=6)
CODE = ParagraphStyle(
    "Codex", parent=styles["Code"], fontSize=9, leading=12, backColor=colors.whitesmoke,
    borderPadding=6, spaceAfter=8, spaceBefore=2,
)
TITLE = ParagraphStyle("Titlex", parent=styles["Title"], fontSize=24, spaceAfter=6)
SUBTITLE = ParagraphStyle(
    "Subtitlex", parent=styles["Normal"], fontSize=12, textColor=colors.grey, spaceAfter=24
)

TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3552")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
)


def p(text: str, style=BODY) -> Paragraph:
    return Paragraph(text, style)


def table(header: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    cell = ParagraphStyle("cell", parent=BODY, fontSize=9, leading=12, spaceAfter=0)
    head = ParagraphStyle("head", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    data = [[Paragraph(h, head) for h in header]] + [
        [Paragraph(c, cell) for c in row] for row in rows
    ]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TABLE_STYLE)
    return t


def build() -> None:
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
        title="SEC Filing Analyzer – Dokumentation",
        author="sec-filing-analyzer",
    )
    W = doc.width
    story = []

    # ------------------------------------------------------------- Titelseite
    story += [
        Spacer(1, 3 * cm),
        p("SEC Filing Analyzer", TITLE),
        p("Technische Dokumentation und Anwenderleitfaden (Deutsch)", SUBTITLE),
        p(
            "Automatisierte Analyse von 10-K-, 10-Q- und 8-K-Berichten: Download über "
            "die offiziellen SEC-EDGAR-Schnittstellen, Zerlegung in Sektionen, Extraktion "
            "der Kernfinanzdaten aus XBRL, Jahresvergleich der Risikofaktoren und "
            "regelbasierte Red-Flag-Erkennung – optional angereichert durch die "
            "Anthropic-API."
        ),
        p(
            "<b>Hinweis:</b> Alle Ergebnisse dienen Recherche- und Ausbildungszwecken "
            "und sind keine Anlageberatung."
        ),
        PageBreak(),
    ]

    # ------------------------------------------------------------------ EDGAR
    story += [
        p("1&nbsp;&nbsp;Wie funktioniert SEC EDGAR?", H1),
        p(
            "EDGAR (<i>Electronic Data Gathering, Analysis, and Retrieval</i>) ist das "
            "elektronische Einreichungssystem der US-Börsenaufsicht SEC. Alle in den USA "
            "börsennotierten Unternehmen müssen ihre Pflichtberichte dort einreichen – "
            "unter anderem den Jahresbericht (<b>10-K</b>), den Quartalsbericht "
            "(<b>10-Q</b>) und Ad-hoc-Meldungen (<b>8-K</b>). Sämtliche Einreichungen "
            "sind öffentlich und kostenlos abrufbar; ein API-Schlüssel ist nicht nötig."
        ),
        p("Der Analyzer nutzt vier offizielle Endpunkte:", BODY),
        table(
            ["Endpunkt", "Zweck"],
            [
                ["www.sec.gov/files/company_tickers.json", "Zuordnung Ticker → CIK (Central Index Key, die eindeutige Unternehmensnummer der SEC)"],
                ["data.sec.gov/submissions/CIK##########.json", "Index aller Einreichungen eines Unternehmens (Formulartyp, Datum, Accession Number, Hauptdokument)"],
                ["www.sec.gov/Archives/edgar/data/…", "Die eigentlichen Filing-Dokumente (HTML)"],
                ["data.sec.gov/api/xbrl/companyfacts/…", "Alle strukturierten XBRL-Finanzfakten eines Unternehmens als JSON"],
            ],
            [W * 0.42, W * 0.58],
        ),
        p("1.1&nbsp;&nbsp;Zugriffsregeln der SEC (Compliance)", H2),
        p(
            "Die SEC verlangt für automatisierte Zugriffe zwei Dinge: "
            "<b>(1)</b> einen User-Agent-Header, der den Aufrufer mit einer "
            "Kontakt-E-Mail-Adresse identifiziert, und <b>(2)</b> maximal "
            "<b>10 Anfragen pro Sekunde</b>. Der Analyzer erzwingt beides: Ohne gültige "
            "Umgebungsvariable <font face='Courier'>SEC_USER_AGENT</font> (Platzhalter "
            "werden erkannt und abgelehnt) startet das Tool nicht, und ein integrierter "
            "Rate-Limiter hält standardmäßig konservative 5 Anfragen pro Sekunde ein. "
            "Heruntergeladene Dokumente werden unter <font face='Courier'>data/</font> "
            "zwischengespeichert, damit wiederholte Läufe EDGAR nicht erneut belasten."
        ),
    ]

    # ------------------------------------------------------------------- XBRL
    story += [
        p("2&nbsp;&nbsp;Was ist XBRL?", H1),
        p(
            "XBRL (<i>eXtensible Business Reporting Language</i>) ist ein Standard, mit "
            "dem Finanzkennzahlen maschinenlesbar ausgezeichnet werden. Seit 2009 müssen "
            "SEC-Emittenten ihre Abschlüsse zusätzlich in XBRL einreichen. Jede Kennzahl "
            "wird dabei einem <b>Konzept</b> aus einer standardisierten Taxonomie "
            "zugeordnet – für US-Unternehmen der <font face='Courier'>us-gaap</font>-"
            "Taxonomie. Beispiele: <font face='Courier'>NetIncomeLoss</font> "
            "(Jahresüberschuss), <font face='Courier'>Assets</font> (Bilanzsumme), "
            "<font face='Courier'>RevenueFromContractWithCustomerExcludingAssessedTax"
            "</font> (Umsatzerlöse nach ASC 606)."
        ),
        p(
            "Die SEC aggregiert alle XBRL-Fakten eines Unternehmens im "
            "<i>companyfacts</i>-Endpunkt. Jeder Fakt trägt Metadaten: Periode "
            "(Start/Ende), Einheit (USD, USD/Aktie), Formulartyp, Geschäftsjahr "
            "(<font face='Courier'>fy</font>/<font face='Courier'>fp</font>) und die "
            "Accession Number der Einreichung. Der Analyzer wählt daraus die passenden "
            "Fakten aus: Für Stromgrößen (Umsatz, Ergebnis, Cashflow) akzeptiert er im "
            "10-K nur Perioden von ca. 330–400 Tagen – so werden Quartals- und "
            "Vorjahreswerte zuverlässig aussortiert. Da Unternehmen Umsätze "
            "unterschiedlich taggen, probiert er je Kennzahl eine geordnete Liste von "
            "Konzepten durch und dokumentiert im Report, welches Konzept verwendet wurde "
            "(Provenienz)."
        ),
    ]

    # --------------------------------------------------------------- Pipeline
    story += [
        p("3&nbsp;&nbsp;Die Analyse-Pipeline", H1),
        p(
            "Der Aufruf <font face='Courier'>sec-analyze AAPL --form 10-K</font> "
            "durchläuft pro Filing fünf Schritte:"
        ),
        table(
            ["Schritt", "Modul", "Was passiert"],
            [
                ["1. Download", "EdgarClient", "Ticker → CIK auflösen, Filing-Index laden, Hauptdokument (HTML) und XBRL-Fakten herunterladen (rate-limitiert, gecacht)"],
                ["2. Parsing", "Section Parser", "HTML → Text; Item-Überschriften (Item 1A, Item 7, bei 8-K Item 4.01 …) lokalisieren; pro Item gewinnt das längste Vorkommen, damit das Inhaltsverzeichnis nicht fälschlich als Sektion gilt"],
                ["3. Diff-Analyse", "Risk Diff", "Item 1A des aktuellen und des Vorjahres-Filings in einzelne Risikofaktoren zerlegen und per Ähnlichkeitsvergleich einander zuordnen (Details in Kapitel 4)"],
                ["4. Red Flags", "Red-Flag Rules", "Deterministische Mustersuche nach Warnsignalen inkl. Negations-Guards (Kapitel 5); bei 8-Ks zusätzlich Item-basierte Flags (4.01/4.02)"],
                ["5. Report", "Reporting", "Markdown- und JSON-Report unter reports/&lt;TICKER&gt;/&lt;FORM&gt;_&lt;Periode&gt;/ schreiben"],
            ],
            [W * 0.18, W * 0.18, W * 0.64],
        ),
        p(
            "<b>Rolle der KI:</b> Ist ein <font face='Courier'>ANTHROPIC_API_KEY</font> "
            "gesetzt, erstellt Claude die Sektionszusammenfassungen, kommentiert "
            "veränderte Risikofaktoren in einem Satz und beurteilt zu jedem Red Flag, ob "
            "die Fundstelle substanziell oder Boilerplate wirkt. Ohne Schlüssel läuft "
            "die Pipeline vollständig deterministisch weiter (extraktive "
            "Zusammenfassungen, reine Ähnlichkeits- und Regellogik). Die Erkennung von "
            "Risiko-Änderungen und Red Flags hängt bewusst <i>nie</i> von der KI ab – "
            "das hält die Ergebnisse reproduzierbar und testbar."
        ),
    ]

    # ------------------------------------------------------------ Diff-Report
    story += [
        p("4&nbsp;&nbsp;Den Diff-Report interpretieren", H1),
        p(
            "Risikofaktoren (Item 1A) ändern sich von Jahr zu Jahr nur punktuell – genau "
            "diese Änderungen sind analytisch wertvoll, weil Unternehmen neue Probleme "
            "häufig zuerst dort verklausuliert offenlegen. Der Analyzer zerlegt beide "
            "Fassungen in einzelne Risiko-Absätze, berechnet paarweise Textähnlichkeiten "
            "(difflib-Ratio, 0…1) und klassifiziert jeden aktuellen Risikofaktor:"
        ),
        table(
            ["Status", "Kriterium", "Interpretation"],
            [
                ["unchanged", "Ähnlichkeit ≥ 0,92", "Im Wesentlichen wortgleich übernommen – Standardfall, wenig Informationswert"],
                ["modified", "0,55 ≤ Ähnlichkeit &lt; 0,92", "Derselbe Risikofaktor, aber inhaltlich überarbeitet – genau lesen: Was wurde verschärft, konkretisiert oder relativiert?"],
                ["new", "Ähnlichkeit &lt; 0,55 zu allen Vorjahres-Risiken", "Neu aufgenommenes Risiko – oft das wichtigste Signal (neue Rechtsstreitigkeiten, Regulierung, Liquiditätslage)"],
                ["removed", "Vorjahres-Risiko ohne Entsprechung", "Gestrichenes Risiko – kann Entwarnung bedeuten, aber auch strategische Umformulierung"],
            ],
            [W * 0.14, W * 0.28, W * 0.58],
        ),
        p(
            "Im Markdown-Report steht vor jedem Eintrag der Ähnlichkeitswert in Klammern, "
            "z.&nbsp;B. <font face='Courier'>(0.88)</font>. Werte knapp unter 0,92 sind "
            "meist redaktionelle Anpassungen; Werte um 0,6–0,8 deuten auf substanzielle "
            "Überarbeitung hin. Mit API-Schlüssel ergänzt eine <i>AI note</i> pro "
            "geändertem Risiko, was sich materiell geändert hat."
        ),
    ]

    # -------------------------------------------------------------- Red Flags
    story += [
        p("5&nbsp;&nbsp;Red Flags interpretieren", H1),
        p(
            "Die Red-Flag-Erkennung sucht präzisionsorientiert nach Formulierungen, die "
            "in US-Filings stark standardisiert sind. Negations-Guards verhindern "
            "Fehlalarme bei Sätzen wie „did <i>not</i> identify any material weakness“. "
            "Jeder Treffer wird mit Fundstellen-Auszug und Quell-Item ausgewiesen:"
        ),
        table(
            ["Flag", "Schwere", "Bedeutung"],
            [
                ["going_concern", "hoch", "Der Abschlussprüfer oder das Management äußert erhebliche Zweifel an der Unternehmensfortführung („substantial doubt … going concern“) – eines der stärksten Warnsignale überhaupt"],
                ["restatement", "hoch", "Bereits veröffentlichte Abschlüsse werden korrigiert oder für nicht mehr verlässlich erklärt (auch 8-K Item 4.02) – historisch typisch für Bilanzskandale"],
                ["material_weakness", "hoch", "Wesentliche Schwäche im internen Kontrollsystem der Finanzberichterstattung – erhöht das Risiko fehlerhafter Zahlen"],
                ["bankruptcy", "hoch", "Chapter-11-Verfahren oder Insolvenzanträge"],
                ["auditor_change", "mittel", "Wechsel des Abschlussprüfers (auch 8-K Item 4.01) – harmlos bei Routinerotation, kritisch nach Meinungsverschiedenheiten"],
                ["accounting_change", "mittel", "Ungewöhnliche Bilanzierungsänderungen oder SEC-Korrespondenz (Comment Letter, Untersuchung)"],
                ["covenant_breach", "mittel", "Bruch von Kreditauflagen, Waiver, verpasste Zins-/Tilgungszahlungen – Frühindikator für Liquiditätsstress"],
            ],
            [W * 0.20, W * 0.11, W * 0.69],
        ),
        p(
            "<b>Wichtig:</b> Ein Red Flag ist ein Prüfauftrag, kein Urteil. Die Regeln "
            "markieren Kandidatenstellen; ob das Signal substanziell ist, zeigt erst die "
            "Lektüre der Fundstelle im Filing (der Report verlinkt Accession Number und "
            "Item). Umgekehrt bedeutet „keine Flags“ nicht Unbedenklichkeit – die "
            "Regelliste ist bewusst konservativ."
        ),
    ]

    # ------------------------------------------------------------- Validierung
    story += [
        p("6&nbsp;&nbsp;Validierung (evals/)", H1),
        p(
            "Statt eines Backtests validiert das Projekt die Analysestufen historisch "
            "gegen bekannte Wahrheiten. Drei Prüfgruppen: <b>(a)</b> aus XBRL "
            "extrahierte Kennzahlen müssen den offiziell berichteten Werten entsprechen "
            "(±1&nbsp;% im Live-Modus), <b>(b)</b> die Diff-Analyse muss bekannte "
            "Risikofaktor-Änderungen erkennen (Stichproben-Assertions), <b>(c)</b> die "
            "Red-Flag-Erkennung muss beim historischen Problemfall anschlagen und bei "
            "gesunden Unternehmen stumm bleiben. Problemfall ist <b>Hertz Global "
            "Holdings (FY2020)</b>: Chapter-11-Antrag im Mai 2020, Going-Concern-Zweifel "
            "im 10-K, Covenant-Brüche, Umsatzeinbruch von 9.779 auf 5.258 Mio. USD."
        ),
        p(
            "Der Offline-Modus (Standard, läuft in CI ohne Netzzugriff) prüft die "
            "komplette Assertion-Suite gegen mitgelieferte Fixture-Filings, die den "
            "realen Vorbildern nachgebildet sind. Der Live-Modus "
            "(<font face='Courier'>--live</font>) führt dieselben Checks gegen echte "
            "EDGAR-Daten von AAPL, MSFT, JNJ, KO und HTZ aus. Ergebnisse liegen unter "
            "<font face='Courier'>evals/results/</font>."
        ),
    ]

    # ---------------------------------------------------------------- Grenzen
    story += [
        p("7&nbsp;&nbsp;Grenzen des Tools", H1),
        p(
            "<b>Parsing:</b> Die Sektionserkennung arbeitet heuristisch auf dem "
            "Dokumenttext. Exotische Layouts (gescannte Alt-Filings, ungewöhnliche "
            "Item-Nummerierung, reine XBRL-Inline-Dokumente) können zu unvollständigen "
            "Sektionen führen.<br/><br/>"
            "<b>XBRL-Mapping:</b> Abgedeckt sind die gängigen us-gaap-Konzepte. "
            "Unternehmen mit eigenwilligem Tagging (Extension-Konzepte) erfordern eine "
            "Erweiterung der Konzeptliste; der Report weist das verwendete Konzept "
            "deshalb immer aus.<br/><br/>"
            "<b>Diff-Analyse:</b> Die Ähnlichkeitsschwellen sind kalibrierte "
            "Kompromisse. Komplett umstrukturierte Risikokapitel können einzelne "
            "Zuordnungen verfälschen (ein stark umgeschriebenes Risiko erscheint dann "
            "als „new“ + „removed“).<br/><br/>"
            "<b>Red Flags:</b> Schlüsselwortregeln erkennen nur, was sprachlich "
            "erwartbar formuliert ist. Bewusst verschleiernde Formulierungen werden "
            "nicht garantiert erkannt; Vollständigkeit ist nicht das Ziel, Präzision "
            "schon.<br/><br/>"
            "<b>KI-Anteile:</b> Zusammenfassungen und Anmerkungen eines Sprachmodells "
            "können Fehler enthalten. Alle entscheidungsrelevanten Rohdaten stehen "
            "deshalb deterministisch im JSON-Report.<br/><br/>"
            "<b>Kein Anlagerat:</b> Das Tool ersetzt weder die Lektüre der Filings noch "
            "professionelle Analyse."
        ),
        Spacer(1, 0.8 * cm),
        p(
            "<i>Projekt: https://github.com/OhneisB/SEC-Filing-Analyzer · Lizenz: MIT · "
            "Diese PDF wird mit</i> <font face='Courier'>uv run python "
            "docs/build_pdf.py</font> <i>aus dem Repository generiert.</i>",
            ParagraphStyle("foot", parent=BODY, fontSize=9, textColor=colors.grey),
        ),
    ]

    doc.build(story)
    print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
