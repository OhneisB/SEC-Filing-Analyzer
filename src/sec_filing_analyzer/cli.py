"""Command-line interface.

Examples:
    sec-analyze AAPL --form 10-K
    sec-analyze AAPL --form 10-Q --last 4
    sec-analyze AAPL --diff          # compare the last two 10-Ks
"""

from __future__ import annotations

import logging
import sys

import click

from .config import ConfigError, load_settings
from .edgar.client import EdgarClient, EdgarError
from .pipeline import analyze_filing, parse_filing
from .reporting.writer import write_reports


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("ticker")
@click.option("--form", "form", default="10-K", show_default=True,
              type=click.Choice(["10-K", "10-Q", "8-K"], case_sensitive=False),
              help="Filing type to analyze.")
@click.option("--last", "last", default=1, show_default=True, type=click.IntRange(1, 20),
              help="Number of most recent filings to analyze.")
@click.option("--diff", "diff_mode", is_flag=True,
              help="Compare the two most recent 10-Ks (risk factor diff).")
@click.option("--no-ai", is_flag=True, help="Skip Anthropic API calls; heuristics only.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging.")
def main(ticker: str, form: str, last: int, diff_mode: bool, no_ai: bool, verbose: bool) -> None:
    """Analyze SEC filings of TICKER: summaries, risk diff, red flags, XBRL financials."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        settings = load_settings()
    except ConfigError as exc:
        raise click.ClickException(str(exc))

    form = form.upper()
    if diff_mode:
        form, last = "10-K", 2

    client = EdgarClient(settings)
    try:
        company = client.lookup_company(ticker)
        click.echo(f"Company: {company.name} (CIK {company.cik})")
        refs = client.list_filings(company, form=form, last=last)
    except EdgarError as exc:
        raise click.ClickException(str(exc))

    # Fetch one extra prior filing so the newest filing can be diffed.
    prior_refs = []
    if form == "10-K":
        try:
            prior_refs = client.list_filings(company, form=form, last=len(refs) + 1)
        except EdgarError:
            prior_refs = refs

    facts = None
    if form in ("10-K", "10-Q"):
        try:
            facts = client.get_company_facts(company)
        except Exception as exc:
            click.echo(f"Warning: could not fetch XBRL company facts ({exc})", err=True)

    parsed_cache: dict[str, object] = {}

    def get_parsed(ref):
        if ref.accession_number not in parsed_cache:
            parsed_cache[ref.accession_number] = parse_filing(client, ref)
        return parsed_cache[ref.accession_number]

    exit_code = 0
    for i, ref in enumerate(refs):
        click.echo(f"\nAnalyzing {ref.form} filed {ref.filing_date} ({ref.accession_number}) …")
        parsed = get_parsed(ref)

        previous = None
        if form == "10-K":
            later = [r for r in prior_refs if r.filing_date < ref.filing_date]
            if later:
                previous = get_parsed(later[0])

        try:
            analysis = analyze_filing(
                client, settings, parsed,
                previous=previous, use_ai=not no_ai, company_facts=facts,
            )
        except Exception as exc:
            click.echo(f"Error analyzing {ref.accession_number}: {exc}", err=True)
            exit_code = 1
            continue

        md_path, json_path = write_reports(analysis, settings.reports_dir)
        click.echo(f"  report: {md_path}")
        click.echo(f"  json:   {json_path}")
        if analysis.red_flags:
            for flag in analysis.red_flags:
                click.echo(f"  🚩 {flag.severity.upper()}: {flag.label}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
