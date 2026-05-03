# Writing a scraper

<!--
Test fixture for rhetoric-lint false-positive remediation.
H1 is intentionally short ("Writing a scraper" — 2 content words) to exercise
the Heading.InformationScent threshold gate. See plan:
.claude/plans/investigate-fols-positives-and-structured-avalanche.md

Region A (lines below): MUST NOT fire after fixes. Each section names the
rule(s) it targets in an HTML comment.
Region B (further down): MUST STILL fire. These are recall guardrails.
-->

This document explains how to build a scraper for a county court site. Scraper
authors should read each section in order before writing code.

## Add a Site class

<!--
TARGETS: Heading.InformationScent (FP-1, FP-4)
EXPECT: no warning. "Site class" is topically coherent with parent context.
The H1 has only 2 content words; ancestor-path bridging should suppress this.
-->

The main task in contributing a scraper is creating a `Site` class that provides
a `search` method capable of scraping one or more case numbers. The class lives
in the `court_scraper.scrapers` namespace under a package named for the
jurisdiction. For Westchester County the module is
`court_scraper.scrapers.ny_westchester.site.py`.

Each scraper subclasses the same base, so the public surface stays uniform
across jurisdictions. A scraper that follows this contract integrates with the
CLI without further configuration.

### Add tests for the scraper

<!--
TARGETS: Heading.InformationScent ancestor-path bridging
EXPECT: no warning. H3 "Add tests" coheres with parent H2 "Add a Site class".
Without ancestor bridging, the rule compares only against the H1 and warns.
-->

New site classes should include test coverage for the `search` and
`search_by_date` methods. Review the existing Odyssey, Oklahoma, and Wisconsin
test modules for examples that fit the scraper test pattern.

## Configure the runner with {py:class}`court_scraper.cli.Runner`

<!--
TARGETS: MyST role stripping (FP-2)
EXPECT: heading should not be flagged for unrelated tokens like "py" or "class".
After the role stripper, the heading reads "Configure the runner with Runner".
-->

The {py:class}`Runner` class instantiates the {py:class}`Site` and calls
{code}`Site.search` with values from {py:mod}`court_scraper.cli`. Use
{ref}`Place ID <place id>` to identify the jurisdiction. The runner is
responsible for caching scraped artifacts and logging progress.

## Handling CAPTCHAs safely

<!--
TARGETS: Resilience.ErrorPathPresence (FP-3, FP-6)
EXPECT: no warning. The {warning} admonition supplies failure guidance and
should satisfy the rule once admonition fences are recognized.
-->

Some sites present CAPTCHAs on every search. The scraper must detect the
CAPTCHA page and route it to the configured solver service. Set
`captcha_service_required=True` in the sites_meta entry and provide an API key.

```{warning}
If the CAPTCHA solver returns an error or times out, the scraper must abort
the current case and log a `CaptchaFailure` exception rather than retrying
indefinitely. Repeated failures usually indicate that the solver account is
out of credit.
```

After the warning above, normal scraping resumes once the solver is healthy.

## Understand the data flow

<!--
TARGETS: Resilience.ErrorPathPresence procedural classifier (FP-3)
EXPECT: no warning. Verb-led heading ("Understand") but the body is conceptual,
not procedural. Tightened classifier should not require failure guidance here.
-->

The scraper produces three artifacts for each case: a metadata record, the raw
search-results HTML, and (when available) the case-detail HTML. Downstream
pipelines join these on the case number. The metadata record is the canonical
identifier and survives even if the raw HTML is later purged.

