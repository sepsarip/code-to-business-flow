#!/usr/bin/env python3
"""Map a codebase for business-flow analysis (stdlib only, read-only).

Usage:
  scan_repo.py ROOT [--output FILE|-] [--max-per-category N] [--exclude DIR ...]

Prints JSON listing where to look: entry points (routes, screens, jobs,
webhooks), status/state signals, role/permission checks, integrations,
data entities, and a suggested reading order. It is a keyword map, not an
analysis: expect false positives and misses.

Options:
  --output FILE   Write the JSON to FILE; '-' (default) writes to stdout.
  --max-per-category N
                  Items shown per category (default 25, max 5 per file).
  --exclude DIR   Extra directory names to skip (repeatable).

Exit codes: 0 ok, 2 bad arguments (e.g. ROOT is not a directory).
Diagnostics go to stderr; JSON goes to stdout or --output.

Example:
  scan_repo.py ./my-app --output /tmp/scan.json
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", ".next", ".nuxt", "__pycache__",
    ".venv", "venv", "env", "target", ".idea", ".vscode", "coverage", "storage", "bin",
    "obj", ".gradle", ".dart_tool", "Pods", ".terraform", "site-packages", ".cache",
}
TEXT_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".php", ".rb", ".java", ".kt",
    ".kts", ".go", ".rs", ".cs", ".swift", ".dart", ".vue", ".svelte", ".sql", ".prisma",
    ".yml", ".yaml", ".erb", ".ejs", ".twig", ".html",
}
MANIFESTS = {
    "package.json": "node", "composer.json": "php", "pyproject.toml": "python",
    "requirements.txt": "python", "Pipfile": "python", "pom.xml": "java",
    "build.gradle": "jvm", "build.gradle.kts": "jvm", "go.mod": "go", "Gemfile": "ruby",
    "Cargo.toml": "rust", "pubspec.yaml": "dart", "mix.exs": "elixir",
}
FRAMEWORKS = [
    "laravel/framework", "symfony", "django", "flask", "fastapi", "express", "@nestjs/core",
    "next", "react", "vue", "nuxt", "@angular/core", "svelte", "spring-boot", "rails",
    "gin-gonic/gin", "gofiber/fiber", "prisma", "sequelize", "typeorm", "mongoose",
    "sqlalchemy", "celery", "stripe", "midtrans", "xendit",
]
MAX_FILE_BYTES = 512 * 1024
MAX_PER_FILE = 5
SECRETISH = re.compile(r"[A-Za-z0-9_\-]{32,}")

# (label, line regex, optional file-path regex that the file must match)
LINE_PATTERNS = {
    "entry_points": [
        ("http-route", re.compile(r"\b(?:app|router|server|fastify|api)\.(get|post|put|patch|delete)\s*\(\s*['\"`]([^'\"`]+)"), None),
        ("http-route", re.compile(r"@\w+\.(route|get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)"), None),
        ("http-route", re.compile(r"Route::(get|post|put|patch|delete|resource|apiResource|match|any)\s*\("), None),
        ("http-route", re.compile(r"\b(?:re_)?path\s*\(\s*['\"]([^'\"]*)['\"]\s*,"), re.compile(r"urls?\.py$")),
        ("http-route", re.compile(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\b"), None),
        ("http-route", re.compile(r"^\s*(resources?|get|post|put|patch|delete|root)\s+['\":]"), re.compile(r"routes?\.rb$")),
        ("http-route", re.compile(r"\.(HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE)\s*\(\s*\"([^\"]+)\""), re.compile(r"\.go$")),
        ("ui-route", re.compile(r"<Route\s+[^>]*path=\{?['\"]([^'\"]+)"), None),
        ("ui-route", re.compile(r"\bpath:\s*['\"](/[^'\"]*)['\"]"), re.compile(r"(router|routes?)[^/]*\.(js|ts)$")),
        ("job/scheduler", re.compile(r"(\$schedule->|@Scheduled|@Cron\(|crontab|cron\.schedule|@shared_task|@(?:app|celery)\.task|beat_schedule|ShouldQueue)"), None),
        ("webhook", re.compile(r"webhook", re.I), None),
        ("cli-command", re.compile(r"(extends Command\b|@click\.command|cobra\.Command|class \w+\(BaseCommand\)|@Command\()"), None),
    ],
    "state_signals": [
        ("status-assign", re.compile(r"\b(?:status|stage)\b\s*(?:=|==|===|!=|:)\s*['\"]?[A-Za-z_]"), None),
        ("enum/constant", re.compile(r"(\benum\b|\bSTATUS_[A-Z_]+|\b[A-Z_]*STATUS[A-Z_]*\s*=)"), None),
        ("lifecycle-timestamp", re.compile(r"\b(approved|paid|cancel(?:l)?ed|rejected|completed|submitted|expired|shipped|verified|published)_(?:at|on|date)\b"), None),
    ],
    "auth_signals": [
        ("role/permission", re.compile(r"(\bisAdmin\b|\bis_admin\b|\bhasRole\b|\bhas_role\b|\brole\s*(?:==|===|=|in)\s|Gate::|@PreAuthorize|@RolesAllowed|login_required|permission_required|\bcan\(|\bcannot\(|\bauthorize\()"), None),
        ("role/permission", re.compile(r"\b(permissions?|policy|policies)\b", re.I), re.compile(r"(polic|permission|role|auth|guard|ability)", re.I)),
    ],
    "integrations": [
        ("provider/messaging", re.compile(r"\b(stripe|midtrans|xendit|paypal|twilio|sendgrid|mailgun|smtp|nodemailer|firebase|slack|whatsapp|oauth)\b", re.I), None),
        ("email/notify", re.compile(r"(Mail::|send_mail|sendmail|\bnotify\(|Notification::)"), None),
        ("outbound-http", re.compile(r"\b(axios\.|requests\.(?:get|post|put)|Http::|HttpClient|RestTemplate|WebClient)"), None),
        ("storage", re.compile(r"\b(S3Client|boto3|Storage::|GCS|MinIO)\b"), None),
    ],
    "entities": [
        ("model", re.compile(r"\bclass\s+\w+\s*\(\s*(?:models\.Model|db\.Model|Base)\s*\)"), None),
        ("model", re.compile(r"\bclass\s+\w+\s+extends\s+(?:Model|Authenticatable)\b"), None),
        ("model", re.compile(r"\bclass\s+\w+\s*<\s*(?:ApplicationRecord|ActiveRecord::Base)"), None),
        ("table", re.compile(r"Schema::create\s*\(\s*['\"](\w+)"), None),
        ("table", re.compile(r"\bCREATE\s+TABLE\s+(?:IF NOT EXISTS\s+)?[`\"]?(\w+)", re.I), None),
        ("model", re.compile(r"(@Entity\b|\bmongoose\.model\(|\bsequelize\.define\()"), None),
        ("model", re.compile(r"^\s*model\s+(\w+)\s*\{"), re.compile(r"\.prisma$")),
    ],
}
PATH_ENTRY = [
    ("ui-route(file)", re.compile(r"(^|/)app/(.*/)?page\.(tsx|jsx|js|ts)$")),
    ("ui-route(file)", re.compile(r"(^|/)pages/.+\.(tsx|jsx|js|ts|vue)$")),
    ("http-route(file)", re.compile(r"(^|/)(app/.*/)?route\.(ts|js)$")),
    ("route-file", re.compile(r"(^|/)routes/[^/]+\.php$")),
    ("scheduler(file)", re.compile(r"\.github/workflows/[^/]+\.ya?ml$")),
]
BOOST_NAME = re.compile(r"(route|urls|polic|permission|role|status|workflow|schedule|job|listener|webhook|service)", re.I)
WEIGHTS = {"entry_points": 3, "state_signals": 3, "auth_signals": 2, "integrations": 2, "entities": 1}


def is_test(rel):
    return bool(re.search(r"(^|/)(tests?|spec|__tests__|e2e)(/|$)|\.(test|spec)\.", rel))


def clip(line):
    line = SECRETISH.sub("<redacted>", line.strip())
    return line if len(line) <= 140 else line[:137] + "..."


def round_robin(items, cap):
    """Spread the cap across files so one busy file cannot hide the others."""
    by_file = defaultdict(list)
    for it in items:
        by_file[it["file"]].append(it)
    queues = list(by_file.values())
    picked = []
    while queues and len(picked) < cap:
        for q in list(queues):
            picked.append(q.pop(0))
            if not q:
                queues.remove(q)
            if len(picked) >= cap:
                break
    return picked


def detect_stack(root, manifests_found):
    stack = []
    for rel in manifests_found:
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="ignore") as fh:
                text = fh.read(200_000).lower()
        except OSError:
            continue
        hits = [f for f in FRAMEWORKS if re.search(r"(?<![\w@/.-])" + re.escape(f) + r"(?![\w-])", text)]
        stack.append({"manifest": rel, "ecosystem": MANIFESTS[os.path.basename(rel)], "frameworks": hits})
    return stack


def scan(root, cap, extra_skip):
    skip = SKIP_DIRS | set(extra_skip)
    found = {k: [] for k in LINE_PATTERNS}
    totals = Counter()
    per_file_cat = defaultdict(Counter)
    ext_count = Counter()
    manifests, scanned, skipped_big = [], 0, 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for name in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            if name in MANIFESTS and rel.count("/") <= 2:
                manifests.append(rel)
            if name.startswith(".env"):  # may hold secrets: never read
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXT or name.endswith(".min.js"):
                continue
            full = os.path.join(dirpath, name)
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    skipped_big += 1
                    continue
                with open(full, encoding="utf-8", errors="ignore") as fh:
                    lines = fh.read().splitlines()
            except OSError:
                continue
            scanned += 1
            ext_count[ext] += 1
            for label, rx in PATH_ENTRY:
                if rx.search(rel):
                    totals["entry_points"] += 1
                    per_file_cat[rel]["entry_points"] += 1
                    found["entry_points"].append({"file": rel, "line": 1, "kind": label, "snippet": "(file location convention)"})
            for cat, pats in LINE_PATTERNS.items():
                shown_here = 0
                for lineno, line in enumerate(lines, 1):
                    if len(line) > 1000:
                        continue
                    for label, rx, file_rx in pats:
                        if file_rx and not file_rx.search(rel):
                            continue
                        if rx.search(line):
                            totals[cat] += 1
                            per_file_cat[rel][cat] += 1
                            if shown_here < MAX_PER_FILE:
                                found[cat].append({"file": rel, "line": lineno, "kind": label, "snippet": clip(line)})
                                shown_here += 1
                            break
    categories = {}
    for cat, items in found.items():
        picked = round_robin(items, cap)
        categories[cat] = {"total_matches": totals[cat], "shown": len(picked), "items": picked}
    order = []
    for rel, cats in per_file_cat.items():
        score = sum(min(n, 10) * WEIGHTS[c] for c, n in cats.items())
        if BOOST_NAME.search(os.path.basename(rel)):
            score *= 1.5
        if is_test(rel):
            score *= 0.3
        order.append({"file": rel, "score": round(score, 1), "signals": sorted(cats), "is_test": is_test(rel)})
    order.sort(key=lambda d: -d["score"])
    return {
        "root": os.path.abspath(root),
        "scanned_files": scanned,
        "skipped_large_files": skipped_big,
        "stack": detect_stack(root, manifests),
        "top_extensions": dict(ext_count.most_common(8)),
        "categories": categories,
        "reading_order": order[:20],
        "notes": [
            "Heuristic keyword map: use it to decide where to read, not as the flow itself.",
            "Files named .env* are never read. Long token-like strings in snippets are redacted.",
            "Tests are down-weighted in reading_order but remain useful as secondary evidence.",
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Map a codebase for business-flow analysis.", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--output", default="-")
    ap.add_argument("--max-per-category", type=int, default=25)
    ap.add_argument("--exclude", action="append", default=[])
    args = ap.parse_args(argv)
    if not os.path.isdir(args.root):
        print(f"Error: ROOT must be an existing directory. Received: {args.root!r}", file=sys.stderr)
        return 2
    if args.max_per_category < 1:
        print("Error: --max-per-category must be >= 1.", file=sys.stderr)
        return 2
    result = scan(args.root, args.max_per_category, args.exclude)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output == "-":
        print(text)
    else:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"Wrote {args.output}: {result['scanned_files']} files scanned.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
