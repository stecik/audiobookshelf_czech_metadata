from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import httpx


@dataclass(frozen=True)
class SearchCheck:
    name: str
    path: str
    query: str
    author: str | None
    expected_title: str


@dataclass(frozen=True)
class CheckResult:
    name: str
    path: str
    ok: bool
    duration_seconds: float
    message: str
    attempts: int = 1
    status_code: int | None = None
    match_count: int | None = None
    sample_titles: tuple[str, ...] = ()


SEARCH_CHECKS: tuple[SearchCheck, ...] = (
    SearchCheck(
        name="global search",
        path="/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    # Alza is intentionally excluded from the scheduled GitHub Actions smoke checks
    # because GitHub-hosted runner IPs intermittently trigger upstream anti-bot
    # responses even when the scraper works from local/manual clients.
    SearchCheck(
        name="albatrosmedia search",
        path="/albatrosmedia/search",
        query="Podzimní děsy",
        author="Agatha Christie",
        expected_title="Podzimní děsy",
    ),
    SearchCheck(
        name="audiolibrix search",
        path="/audiolibrix/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="audioteka search",
        path="/audioteka/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="databazeknih search",
        path="/databazeknih/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="kanopa search",
        path="/kanopa/search",
        query="Hypotéza zla",
        author="Donato Carrisi",
        expected_title="Hypotéza zla",
    ),
    SearchCheck(
        name="knihydobrovsky search",
        path="/knihydobrovsky/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="kosmas search",
        path="/kosmas/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="luxor search",
        path="/luxor/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="megaknihy search",
        path="/megaknihy/search",
        query="Šikmý kostel",
        author="Karin Lednická",
        expected_title="Šikmý kostel",
    ),
    SearchCheck(
        name="naposlech search",
        path="/naposlech/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="onehotbook search",
        path="/onehotbook/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="o2knihovna search",
        path="/o2knihovna/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="palmknihy search",
        path="/palmknihy/search",
        query="Prasklé zrcadlo",
        author="Agatha Christie",
        expected_title="Prasklé zrcadlo",
    ),
    SearchCheck(
        name="progresguru search",
        path="/progresguru/search",
        query="Okamžitá pomoc proti úzkosti",
        author="Matthew McKay",
        expected_title="Okamžitá pomoc proti úzkosti",
    ),
    SearchCheck(
        name="radioteka search",
        path="/radioteka/search",
        query="1984",
        author="George Orwell",
        expected_title="1984",
    ),
    SearchCheck(
        name="rozhlas search",
        path="/rozhlas/search",
        query="Skořápka",
        author="Ian McEwan",
        expected_title="Skořápka",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run live smoke checks against the metadata provider endpoints.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000"),
        help="Provider base URL.",
    )
    parser.add_argument(
        "--report-file",
        default=os.getenv("SMOKE_REPORT_FILE", "smoke-report.md"),
        help="Path to the generated report file.",
    )
    parser.add_argument(
        "--startup-wait-seconds",
        type=float,
        default=float(os.getenv("SMOKE_STARTUP_WAIT_SECONDS", "60")),
        help="Maximum time to wait for /health to respond before failing.",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=float(os.getenv("SMOKE_REQUEST_TIMEOUT_SECONDS", "90")),
        help="Timeout for each smoke-check HTTP request.",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=int(os.getenv("SMOKE_RETRY_ATTEMPTS", "3")),
        help="Total attempts per endpoint check before failing.",
    )
    parser.add_argument(
        "--retry-wait-seconds",
        type=float,
        default=float(os.getenv("SMOKE_RETRY_WAIT_SECONDS", "60")),
        help="Delay between failed endpoint attempts.",
    )
    return parser.parse_args()


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(character for character in normalized if not unicodedata.combining(character))
    collapsed = " ".join(without_marks.split())
    return collapsed.casefold()


def format_exception(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def response_snippet(response: httpx.Response) -> str:
    text = response.text.strip()
    if len(text) > 200:
        text = f"{text[:197]}..."
    return text or "<empty body>"


async def wait_for_service(client: httpx.AsyncClient, timeout_seconds: float) -> None:
    deadline = perf_counter() + timeout_seconds
    last_error = "service did not answer yet"

    while perf_counter() < deadline:
        try:
            response = await client.get("/health")
            if response.status_code == 200:
                return
            last_error = f"/health returned {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = format_exception(exc)

        await asyncio.sleep(1.0)

    raise RuntimeError(f"service was not ready within {timeout_seconds:.0f}s: {last_error}")


async def run_health_check(client: httpx.AsyncClient) -> CheckResult:
    started_at = perf_counter()
    try:
        response = await client.get("/health")
        duration = perf_counter() - started_at
        if response.status_code != 200:
            return CheckResult(
                name="global health",
                path="/health",
                ok=False,
                duration_seconds=duration,
                status_code=response.status_code,
                message=f"expected 200, got {response.status_code}: {response_snippet(response)}",
            )

        payload = response.json()
        if not isinstance(payload, dict):
            return CheckResult(
                name="global health",
                path="/health",
                ok=False,
                duration_seconds=duration,
                status_code=response.status_code,
                message=f"unexpected health payload type: {type(payload).__name__}",
            )
        if payload.get("status") != "ok":
            return CheckResult(
                name="global health",
                path="/health",
                ok=False,
                duration_seconds=duration,
                status_code=response.status_code,
                message=f"unexpected health payload: {json.dumps(payload, ensure_ascii=False)}",
            )

        return CheckResult(
            name="global health",
            path="/health",
            ok=True,
            duration_seconds=duration,
            attempts=1,
            status_code=response.status_code,
            message='returned {"status": "ok"}',
        )
    except (ValueError, httpx.HTTPError) as exc:
        return CheckResult(
            name="global health",
            path="/health",
            ok=False,
            duration_seconds=perf_counter() - started_at,
            message=format_exception(exc),
        )


def extract_titles(payload: dict[str, object], *, limit: int | None = 3) -> tuple[str, ...]:
    matches = payload.get("matches")
    if not isinstance(matches, list):
        return ()

    titles: list[str] = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        title = match.get("title")
        if isinstance(title, str) and title.strip():
            titles.append(title.strip())
        if limit is not None and len(titles) == limit:
            break
    return tuple(titles)


async def run_search_check(
    client: httpx.AsyncClient,
    check: SearchCheck,
) -> CheckResult:
    started_at = perf_counter()
    params = {"query": check.query}
    if check.author:
        params["author"] = check.author

    try:
        response = await client.get(check.path, params=params)
        duration = perf_counter() - started_at
        if response.status_code != 200:
            return CheckResult(
                name=check.name,
                path=check.path,
                ok=False,
                duration_seconds=duration,
                status_code=response.status_code,
                message=f"expected 200, got {response.status_code}: {response_snippet(response)}",
            )

        payload = response.json()
        if not isinstance(payload, dict):
            return CheckResult(
                name=check.name,
                path=check.path,
                ok=False,
                duration_seconds=duration,
                status_code=response.status_code,
                message=f"unexpected payload type: {type(payload).__name__}",
            )
        matches = payload.get("matches")
        if not isinstance(matches, list):
            return CheckResult(
                name=check.name,
                path=check.path,
                ok=False,
                duration_seconds=duration,
                status_code=response.status_code,
                message=f"response is missing a matches list: {json.dumps(payload, ensure_ascii=False)}",
            )

        if not matches:
            return CheckResult(
                name=check.name,
                path=check.path,
                ok=False,
                duration_seconds=duration,
                status_code=response.status_code,
                match_count=0,
                message="response returned zero matches",
            )

        all_titles = extract_titles(payload, limit=None)
        sample_titles = all_titles[:3]
        expected = normalize_text(check.expected_title)
        if not any(expected in normalize_text(title) for title in all_titles):
            rendered_titles = ", ".join(sample_titles) or "<missing titles>"
            return CheckResult(
                name=check.name,
                path=check.path,
                ok=False,
                duration_seconds=duration,
                status_code=response.status_code,
                match_count=len(matches),
                sample_titles=sample_titles,
                message=f'expected a title containing "{check.expected_title}", got: {rendered_titles}',
            )

        return CheckResult(
            name=check.name,
            path=check.path,
            ok=True,
            duration_seconds=duration,
            attempts=1,
            status_code=response.status_code,
            match_count=len(matches),
            sample_titles=sample_titles,
            message="returned matches",
        )
    except (ValueError, httpx.HTTPError) as exc:
        return CheckResult(
            name=check.name,
            path=check.path,
            ok=False,
            duration_seconds=perf_counter() - started_at,
            message=format_exception(exc),
        )


def build_headers() -> dict[str, str]:
    token = os.getenv("AUDIOBOOKSHELF_AUTH_TOKEN", "").strip()
    if not token:
        return {}
        return {"AUTHORIZATION": token}


async def run_with_retries(
    check_runner,
    *,
    retry_attempts: int,
    retry_wait_seconds: float,
) -> CheckResult:
    total_attempts = max(1, retry_attempts)
    last_result: CheckResult | None = None

    for attempt in range(1, total_attempts + 1):
        result = await check_runner()
        result = CheckResult(
            name=result.name,
            path=result.path,
            ok=result.ok,
            duration_seconds=result.duration_seconds,
            message=result.message,
            attempts=attempt,
            status_code=result.status_code,
            match_count=result.match_count,
            sample_titles=result.sample_titles,
        )
        if result.ok:
            if attempt == 1:
                return result
            return CheckResult(
                name=result.name,
                path=result.path,
                ok=True,
                duration_seconds=result.duration_seconds,
                message=f"{result.message} after retry {attempt}/{total_attempts}",
                attempts=attempt,
                status_code=result.status_code,
                match_count=result.match_count,
                sample_titles=result.sample_titles,
            )
        last_result = result
        if attempt < total_attempts:
            await asyncio.sleep(retry_wait_seconds)

    assert last_result is not None
    if total_attempts == 1:
        return last_result
    return CheckResult(
        name=last_result.name,
        path=last_result.path,
        ok=False,
        duration_seconds=last_result.duration_seconds,
        message=f"{last_result.message} after {total_attempts} attempts",
        attempts=total_attempts,
        status_code=last_result.status_code,
        match_count=last_result.match_count,
        sample_titles=last_result.sample_titles,
    )


def render_report(*, base_url: str, results: list[CheckResult]) -> str:
    passed = sum(1 for result in results if result.ok)
    failed = len(results) - passed

    lines = [
        "# Scheduled scrape smoke report",
        "",
        f"- Base URL: {base_url}",
        f"- Total checks: {len(results)}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        "",
        "## Results",
        "",
    ]

    for result in results:
        state = "PASS" if result.ok else "FAIL"
        details = [
            f"{state} {result.name}",
            f"path={result.path}",
            f"time={result.duration_seconds:.2f}s",
            f"attempt={result.attempts}",
        ]
        if result.status_code is not None:
            details.append(f"status={result.status_code}")
        if result.match_count is not None:
            details.append(f"matches={result.match_count}")
        lines.append(f"- {' | '.join(details)}")
        lines.append(f"  {result.message}")
        if result.sample_titles:
            lines.append(f"  sample titles: {', '.join(result.sample_titles)}")
        lines.append("")

    failing_results = [result for result in results if not result.ok]
    if failing_results:
        lines.extend(
            [
                "## Failures",
                "",
            ]
        )
        for result in failing_results:
            lines.append(f"- {result.name}: {result.message}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


async def main_async(args: argparse.Namespace) -> int:
    results: list[CheckResult] = []
    headers = build_headers()

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        headers=headers,
        follow_redirects=True,
        timeout=args.request_timeout_seconds,
    ) as client:
        try:
            await wait_for_service(client, timeout_seconds=args.startup_wait_seconds)
        except Exception as exc:
            results.append(
                CheckResult(
                    name="service startup",
                    path="/health",
                    ok=False,
                    duration_seconds=0.0,
                    message=format_exception(exc),
                )
            )
            Path(args.report_file).write_text(
                render_report(base_url=args.base_url, results=results),
                encoding="utf-8",
            )
            return 1

        results.append(
            await run_with_retries(
                lambda: run_health_check(client),
                retry_attempts=args.retry_attempts,
                retry_wait_seconds=args.retry_wait_seconds,
            )
        )
        for check in SEARCH_CHECKS:
            results.append(
                await run_with_retries(
                    lambda current_check=check: run_search_check(client, current_check),
                    retry_attempts=args.retry_attempts,
                    retry_wait_seconds=args.retry_wait_seconds,
                )
            )

    Path(args.report_file).write_text(
        render_report(base_url=args.base_url, results=results),
        encoding="utf-8",
    )
    return 0 if all(result.ok for result in results) else 1


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
