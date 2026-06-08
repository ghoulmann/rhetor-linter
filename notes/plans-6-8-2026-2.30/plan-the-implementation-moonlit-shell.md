# Plan: jtbd-tool — New Project + rhetor-linter Integration Addendum

## Context

`jtbd-tool` is a new open-source CLI + API that infers Jobs-to-be-Done from any codebase and audits documentation for coverage gaps — no manual annotation, no LLM required for the core pipeline. It fills a real market gap: no permissive-license JTBD classifier exists.

The tool is grounded in a four-tier schema (Ulwick ODI + Software/DevOps extension + SWEBOK KAs + Organizational processes). Extraction goes beyond names and docstrings to include code-body import graphs, CI/CD config files, and call patterns. LLM is opt-in (`--model` flag), not a core dependency.

`jtbd-tool` works standalone or as a peer to `rhetor-linter`. Integration surface: stable `jtbd-manifest.json`. The two tools share no code.

**Directory**: `~/Documents/github/jtbd-tool/` (consistent with other projects in workspace; user specified `~/github/jtbd-tool/` — confirm on init).

---

## Package layout

```
jtbd-tool/
  CLAUDE.md
  pyproject.toml
  jtbd_tool/
    cli.py                Typer CLI: scan, resume, serve, version
    models.py             Pydantic: Job, JobStatement, JobManifest, CoverageReport
    extractor.py          Phase 1 orchestrator — delegates to sub-extractors
    extractors/
      symbol_extractor.py  Tree-sitter skeleton: public functions, classes, routes
      import_analyzer.py   Import graph → library_registry lookup
      config_extractor.py  CI/CD YAML + Jenkinsfile + IaC → stage-to-job mapping
      call_analyzer.py     Call pattern matching inside function bodies
    classifier.py         Phase 2 — rule-based JTBD classification
    clusterer.py          Phase 2b — spaCy word-vector clustering
    auditor.py            Phase 3 — doc coverage audit (Jaccard)
    reporter.py           Phase 4 — Markdown + JSON output
    api.py                FastAPI REST endpoints
    llm.py                Optional LiteLLM enhancement + export mode
    crawler.py            External docs BFS crawler
    chunker.py            Skeleton chunking for large codebases
    prompts.py            LLM prompt templates
    schema/
      job_map.py              Ulwick Universal Job Map (8 steps)
      job_map_software.py     DevOps/CI-CD/Testing extension (14 steps)
      job_map_organizational.py  KM/Governance/Risk/PM/Jira (10 steps)
      swebok_registry.py      SWEBOK v4 KA taxonomy backbone
      library_registry.py     Library import → JTBD signal (~200 entries)
      ci_stage_registry.py    CI stage name patterns → JTBD
      cameo_verbs.py          Organizational verb patterns (adapted from CAMEO)
    queries/
      python.scm
      typescript.scm
      javascript.scm
      go.scm
  tests/
    test_extractors.py
    test_classifier.py
    test_clusterer.py
    test_auditor.py
    test_api.py
    test_schema.py
    fixtures/
      sample_py/           Python project with imports, tests, CI config
      sample_ts/           TypeScript project
      sample_docs/         Markdown doc fixtures
      sample_ci/           Jenkinsfile, .gitlab-ci.yml, .github/workflows/
```

---

## Four-tier schema

### Tier 1 — Ulwick Universal Job Map (`job_map.py`)
Source: Ulwick ODI methodology (public domain methodology, widely published in HBR + Strategyn blog).

```python
JOB_MAP_STEPS = {
    "Define":   ["specify", "determine", "identify", "plan", "assess", "establish", "decide"],
    "Locate":   ["find", "fetch", "retrieve", "access", "get", "gather", "load", "read"],
    "Prepare":  ["configure", "initialize", "create", "build", "setup", "install", "instantiate"],
    "Confirm":  ["validate", "verify", "check", "assert", "test", "ensure", "confirm"],
    "Execute":  ["run", "process", "perform", "apply", "execute", "dispatch", "send", "parse", "render", "generate"],
    "Monitor":  ["track", "measure", "observe", "log", "report", "audit", "watch", "count"],
    "Modify":   ["update", "edit", "change", "adjust", "transform", "convert", "patch", "fix"],
    "Conclude": ["close", "save", "export", "finalize", "complete", "cleanup", "teardown", "destroy"],
}
```

### Tier 2 — Software/DevOps Extension (`job_map_software.py`)
Sources: GitLab Handbook (CC BY-SA 4.0), Google SRE Book (CC BY 4.0), CNCF Glossary (CC BY 4.0).

```python
SOFTWARE_JOB_MAP_EXTENSION = {
    "Onboard":   ["install", "register", "activate", "migrate", "import", "bootstrap", "onboard"],
    "Debug":     ["debug", "diagnose", "trace", "reproduce", "investigate", "profile", "inspect"],
    "Deploy":    ["deploy", "release", "publish", "promote", "rollout", "ship", "push"],
    "Provision": ["provision", "allocate", "spin_up", "terraform", "scale", "create_cluster"],
    "Recover":   ["rollback", "restore", "reinstall", "failover", "remediate", "revert"],
    "Support":   ["report_incident", "escalate", "collect_logs", "bundle", "snapshot", "ticket"],
}
```

### Tier 3 — SWEBOK KA Taxonomy (`swebok_registry.py`)
Source: SWEBOK v4.0a (IEEE Computer Society, free PDF download — personal/academic use).
Reference URL: https://ieeecs-media.computer.org/media/education/swebok/swebok-v4.pdf

Test sub-types under `Confirm` step, grounded in SWEBOK Software Testing + Software Security KAs:

```python
SWEBOK_TEST_SUBTYPES = {
    "Confirm/Unit":         ["unittest", "pytest", "jest", "mocha", "rspec"],
    "Confirm/Integration":  ["testcontainers", "docker_compose_test", "integration_test"],
    "Confirm/Contract":     ["pact", "pactman", "spring_cloud_contract"],
    "Confirm/Performance":  ["locust", "k6", "jmeter", "gatling", "artillery"],
    "Confirm/SAST":         ["bandit", "semgrep", "sonarqube", "checkmarx", "flake8_security"],
    "Confirm/DAST":         ["zapv2", "owasp_zap", "nuclei", "nikto"],
    "Confirm/SCA":          ["mend", "snyk", "safety", "owasp_dependency_check", "dependabot"],
    "Confirm/Regression":   ["pytest_regression", "snapshot_test", "golden_file"],
    "Confirm/Mutation":     ["mutmut", "pitest", "stryker"],
}
# Also covers SWEBOK Software Engineering Operations KA:
SWEBOK_OPS_SUBTYPES = {
    "Deploy/CI":            ["jenkins", "github_actions", "gitlab_ci", "circle_ci", "travis"],
    "Deploy/Container":     ["docker", "podman", "buildah", "kaniko"],
    "Deploy/Orchestration": ["kubectl", "helm", "kustomize", "argocd", "flux"],
    "Provision/IaC":        ["terraform", "pulumi", "ansible", "cloudformation", "cdk"],
    "Monitor/Observability":["prometheus", "grafana", "opentelemetry", "datadog", "jaeger"],
}
```

### Tier 4 — Organizational Process Extension (`job_map_organizational.py`)
Sources: Scrum Guide (CC BY-SA 4.0), Kanban Guide (CC BY-SA 4.0), GitLab Handbook (CC BY-SA 4.0), CAMEO organizational categories 01–09 (public/academic, adapted).

```python
ORGANIZATIONAL_JOB_MAP = {
    "Plan":             ["plan", "roadmap", "estimate", "prioritize", "groom", "refine", "sprint_plan"],
    "Assign":           ["assign", "delegate", "allocate", "own", "triage"],
    "Track":            ["track", "status", "transition", "update_ticket", "unblock"],
    "Review":           ["review", "approve", "reject", "request_changes", "comment_on"],
    "Govern":           ["authorize", "enforce_policy", "certify", "comply", "sign_off"],
    "RiskManage":       ["identify_risk", "assess_risk", "mitigate", "accept_risk", "escalate_risk"],
    "KnowledgeCapture": ["document", "capture", "record_decision", "write_runbook", "annotate"],
    "KnowledgeShare":   ["share", "publish", "present", "transfer_knowledge", "onboard_team"],
    "Retrospect":       ["retrospect", "postmortem", "lessons_learned", "improve_process"],
    "Close":            ["close_ticket", "resolve", "archive", "done", "won_t_fix"],
}
```

**CAMEO integration** (`cameo_verbs.py`): Adapt CAMEO categories 01–09 (cooperative/organizational acts) from `/home/rik/Documents/github/dateline/resources/ontology.parus.json`. Strip geopolitical context tokens; re-anchor to software/PM vocabulary. Use CAMEO's pattern syntax (`verb + context → category`) as the matching grammar for organizational verbs in docstrings and config files. The `ontology.merged.json` confidence scoring model maps directly to jtbd-tool's confidence field.

---

## Extraction strategies (four signals)

### Signal 1 — Import graph (`import_analyzer.py`)
Walk all `import` AST nodes across the codebase. Map library root name → `LIBRARY_TO_JTBD` registry entry. Highest confidence signal (0.90).

### Signal 2 — CI/CD config files (`config_extractor.py`)
| File type | Parser | Stage extraction |
|---|---|---|
| `.github/workflows/*.yml` | PyYAML | `jobs[*].steps[*].name`, `jobs[*].name` |
| `.gitlab-ci.yml` | PyYAML | top-level keys (stages), `stage:` values |
| `Jenkinsfile` | regex (`stage\('([^']+)'\)`) | stage name strings |
| `terraform/*.tf` | regex + hcl2 | resource type names |
| `docker-compose.yml` | PyYAML | service names + command values |
| `.snyk`, `mend.config`, `.whitesource` | file existence | → SCA job signal |

Stage names feed `ci_stage_registry.py` (pattern → JTBD). Confidence: 0.95.

### Signal 3 — Call patterns (`call_analyzer.py`)
Tree-sitter `.scm` queries on function bodies extract:
- `subprocess.run([...])` → extract command tokens → map to JTBD
- `requests.*()` / `httpx.*()` + URL patterns → external service signals
- `boto3.client("ec2")` → provisioning signal
- Known CI API call patterns (Jenkins REST, Jira REST)

Confidence: 0.75.

### Signal 4 — Name/docstring (`symbol_extractor.py`)
Existing approach: spaCy dep parse on docstring first sentence → root verb + dobj → job map lookup. Fallback: split function name tokens. Confidence: 0.45–0.65.

### Confidence hierarchy and merge
When multiple signals fire for the same symbol, take highest confidence. Conflict resolution: CI config > library import > call pattern > docstring > name.

---

## Library registry seed (`library_registry.py`)

~200 entries covering major toolchains. Sample:

```python
@dataclass
class JobSignal:
    statement: str
    job_map_step: str
    swebok_ref: str       # e.g. "swebok:security/sast"
    confidence: float = 0.90

LIBRARY_TO_JTBD: dict[str, JobSignal] = {
    # SWEBOK: Security KA / SAST
    "bandit":        JobSignal("Identify security vulnerabilities in source code", "Confirm/SAST",  "swebok:security/sast"),
    "semgrep":       JobSignal("Identify security vulnerabilities in source code", "Confirm/SAST",  "swebok:security/sast"),
    "sonarqube":     JobSignal("Analyse code quality and security",                "Confirm/SAST",  "swebok:security/sast"),
    # SWEBOK: Security KA / DAST
    "zapv2":         JobSignal("Test application security at runtime",             "Confirm/DAST",  "swebok:security/dast"),
    "owasp_zap":     JobSignal("Test application security at runtime",             "Confirm/DAST",  "swebok:security/dast"),
    # SWEBOK: Security KA / SCA
    "mend":          JobSignal("Audit dependencies for known vulnerabilities",     "Confirm/SCA",   "swebok:security/sca"),
    "snyk":          JobSignal("Audit dependencies for known vulnerabilities",     "Confirm/SCA",   "swebok:security/sca"),
    "safety":        JobSignal("Check Python packages for CVEs",                   "Confirm/SCA",   "swebok:security/sca"),
    # SWEBOK: Testing KA / contract
    "pact":          JobSignal("Verify service interface contracts",               "Confirm/Contract","swebok:testing/contract"),
    # SWEBOK: Testing KA / performance
    "locust":        JobSignal("Validate system performance under load",           "Confirm/Performance","swebok:testing/performance"),
    "k6":            JobSignal("Validate system performance under load",           "Confirm/Performance","swebok:testing/performance"),
    # SWEBOK: Operations KA / deploy
    "ansible":       JobSignal("Provision and configure infrastructure",           "Provision/IaC", "swebok:operations/provisioning"),
    "terraform":     JobSignal("Provision cloud infrastructure",                   "Provision/IaC", "swebok:operations/provisioning"),
    "helm":          JobSignal("Deploy application to Kubernetes",                 "Deploy/Orchestration","swebok:operations/deployment"),
    # Org / PM tier
    "jira":          JobSignal("Track and transition work items",                  "Track",         "org:pm/tracking"),
    "atlassian_python_api": JobSignal("Manage project issues and workflow",        "Track",         "org:pm/tracking"),
}
```

---

## Stable manifest schema

```json
{
  "version": "1.0",
  "source_path": "/abs/path",
  "generated_at": "2026-06-06T12:00:00Z",
  "schema_tiers": ["ulwick", "software", "swebok", "organizational"],
  "jobs": [
    {
      "id": "JOB-001",
      "statement": {"verb": "validate", "object": "dependencies for CVEs", "context": "in CI pipeline"},
      "statement_text": "validate dependencies for CVEs in CI pipeline",
      "job_map_step": "Confirm/SCA",
      "swebok_ref": "swebok:security/sca",
      "symbols": ["check_dependencies", "run_snyk"],
      "signal_source": "library_import",
      "confidence": 0.90,
      "coverage": "missing"
    }
  ]
}
```

---

## API endpoints (`api.py` — FastAPI)

```
POST /scan        {path, docs_dir?, model?}  → JobManifest
POST /audit       {manifest, docs_dir}        → CoverageReport
GET  /manifest/{id}                           → JobManifest
GET  /schema/steps                            → all job map steps across tiers
GET  /health                                  → {"status":"ok"}
```

---

## CLI

```bash
jtbd-tool scan ./my-project [--docs-dir ./docs] [--model claude-sonnet-4-6] \
  [--output report.md] [--format markdown|json] [--skeleton-only] [--tiers ulwick,software,swebok,org]
jtbd-tool resume response.json [--phase infer|audit]
jtbd-tool serve [--port 8080]
jtbd-tool version
```

---

## Dependencies

| Package | License | Purpose |
|---|---|---|
| typer | MIT | CLI |
| pydantic | MIT | models |
| tree-sitter + tree-sitter-languages | MIT | AST extraction |
| spacy + en_core_web_md | MIT / CC BY-SA | NLP + word vectors (md not sm) |
| PyYAML | MIT | CI config parsing |
| hcl2 | MIT | Terraform parsing |
| fastapi + uvicorn | MIT | REST API |
| litellm | MIT | optional LLM |
| httpx + beautifulsoup4 | MIT/MIT | optional crawler |

Groovy/Jenkinsfile: regex-based (Tier 1), tree-sitter-groovy MIT community parser (Tier 3).

---

## CLAUDE.md init content

Cover: architecture + four-tier schema rationale, extraction signal hierarchy, confidence scoring, `en_core_web_md` install trap, how to add a library to the registry, how to add a CI stage pattern, test patterns, SWEBOK reference note (free PDF, personal use).

---

## Implementation tiers

| Tier | Subplan | Content | Depends |
|---|---|---|---|
| 0 | Scaffold | pyproject, CLAUDE.md, schema/ all four tiers, models.py | — |
| 1 | Core extraction + classification | symbol_extractor.py (Python), import_analyzer.py, library_registry.py (~50 entries), classifier.py, cli.py scan skeleton | 0 |
| 2 | CI config + clustering + audit + report | config_extractor.py, ci_stage_registry.py, clusterer.py, auditor.py, reporter.py, full scan pipeline | 1 |
| 3 | API + CAMEO org verbs | api.py (FastAPI), serve command, cameo_verbs.py (adapted from dateline ontology.parus.json), org tier classifier | 2 |
| 4 | LLM + export mode | llm.py, prompts.py, resume command, chunker.py | 2 |
| 5 | Call patterns + full library registry | call_analyzer.py, library_registry.py (~200 entries), swebok_registry.py complete | 3 |
| 6 | TS/JS/Go grammars + Groovy + crawler | additional .scm files, tree-sitter-groovy, crawler.py | 3 |
| 7 | Pipeline library flavor coverage | Groovy shared lib extractor + per-flavor scoped audit — see `.claude/plans/pipeline-library-flavor-coverage.md` | 2 |

---

## Part 2: rhetor-linter Addendum — SP12

Append to `/home/rik/Documents/github/rhetor-linter/.claude/plans/plan-support-for-markdownlint-joyful-teacup.md`.

**SP12: JTBD Coverage Integration**
- Depends on: SP1 (CrossFileContext), jtbd-tool Tier 3 (API stable)
- New rule: `Coverage.MissingJobCoverage` in `rhetoric_lint/rules/jtbd_coverage.py`
- New const: `JTBD_MANIFEST_PATH: str = ""`, `JTBD_COVERAGE_JACCARD_MIN: float = 0.30`
- New CLI flag: `--jtbd-manifest <path>`
- Engine: load manifest → `context["jtbd_manifest"]` if path set
- Rule logic: for each job where `coverage == "missing"`, compute Jaccard against doc paragraphs using existing `overlap.py::set_overlap_metrics()`; fire finding if max Jaccard < threshold
- Finding: `check="Coverage.MissingJobCoverage"`, `severity="warning"`, message includes job statement + SWEBOK ref
- Tests: must-fire + must-not-fire against `tests/fixtures/corpus/technical/`

---

## Verification

**jtbd-tool**:
1. `jtbd-tool scan ./rhetoric_lint --skeleton-only` → symbols extracted, JSON valid
2. `jtbd-tool scan ./rhetoric_lint --docs-dir ./docs` → manifest with step assignments + confidence scores
3. `jtbd-tool scan . --tiers software,swebok` → CI config parsed, SAST/SCA/performance jobs detected
4. `pytest tests/ -q` → all pass
5. `jtbd-tool serve & curl localhost:8080/health` → `{"status":"ok"}`
6. `curl -X POST localhost:8080/scan -d '{"path":"./rhetoric_lint"}'` → manifest JSON

**rhetor-linter SP12**:
1. `rhetoric-lint --jtbd-manifest jtbd-manifest.json docs/api.md` → `Coverage.MissingJobCoverage` fires on uncovered jobs
2. `pipenv run python -m pytest tests/test_jtbd_coverage.py -q` → passes
3. Zero findings against `tests/fixtures/corpus/technical/`
