#!/usr/bin/env python3
"""Label episodes with Jev.

Choice questions pick one option, so each topic is a separate yes/no question.
An episode keeps every topic whose probability is at least the threshold.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "public" / "episodes.json"
RAW = ROOT / "data" / "jev-labels.jsonl"
SUMMARY = ROOT / "data" / "jev-label-run.json"
API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.14.0"
PRICE_PER_MILLION = 0.042
THRESHOLD = 0.5
WORKERS = 8

# One yes/no question per topic so an episode can carry several labels.
CRITERIA: dict[str, str] = {
    "history": "a past event, era, historical figure, or how something changed over time",
    "science": "physics, chemistry, experiments, or a scientific explanation of how something works",
    "body": "human anatomy, health, disease, medicine, sleep, or the physical body",
    "mind": "psychology, emotions, memory, dreams, mental health, or how people think",
    "food": "food, drink, cooking, or farming something in order to eat it",
    "animals": "animals, insects, or other creatures, rather than people or plants",
    "nature": "plants, weather, geology, oceans, landscapes, or the natural environment",
    "space": "outer space, astronomy, planets, or spaceflight",
    "crime": "a crime, criminal, investigation, prison, or law-enforcement case",
    "mysteries": "an unsolved disappearance, unexplained event, or real mystery",
    "money": "money, business, economics, taxes, or markets",
    "culture": "movies, books, art, toys, fashion, celebrities, or popular culture",
    "music": "music, musicians, songs, or instruments",
    "sports": "sports, athletes, or athletic competition",
    "technology": "machines, inventions, computers, vehicles, or how a device works",
    "politics": "government, elections, law, or political power",
    "war": "a war, battle, military force, or armed conflict",
    "language": "words, language, grammar, or how people speak and write",
    "weird": "the paranormal, a conspiracy, a cryptid, ghosts, or something presented as strange",
    "holidays": "a holiday, festival, or seasonal celebration",
    "religion": "religion, faith, gods, or a religious institution",
}

QUESTIONS = {
    topic: {
        "type": "noul",
        "instructions": (
            "Is this a main subject of the episode, not a passing mention? "
            f"The subject is {definition}."
        ),
    }
    for topic, definition in CRITERIA.items()
}


def load_token() -> str:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("JEV_API_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                if token:
                    return token
    token = os.environ.get("JEV_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("JEV_API_TOKEN is missing from .env")
    return token


def load_done() -> dict[str, dict]:
    done: dict[str, dict] = {}
    if not RAW.exists():
        return done
    for line in RAW.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        done[row["id"]] = row
    return done


def label_one(token: str, episode: dict) -> dict:
    payload = {
        "model": MODEL,
        "state": {
            "title": episode["title"],
            "description": episode.get("summary") or "",
        },
        "questions": QUESTIONS,
    }
    body = json.dumps(payload).encode()
    started = time.perf_counter()
    delay = 1.0
    last_error = "unknown error"
    for _attempt in range(6):
        request = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = json.loads(response.read().decode())
            elapsed = time.perf_counter() - started
            answers = raw["answers"]
            scores = {topic: float(answers[topic]["noul"]) for topic in CRITERIA}
            labels = [topic for topic, score in scores.items() if score >= THRESHOLD]
            usage = raw.get("usage") or {}
            return {
                "id": episode["id"],
                "title": episode["title"],
                "scores": scores,
                "topics": labels,
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
                "model": raw.get("model"),
                "seconds": round(elapsed, 3),
            }
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            last_error = f"HTTP {error.code}"
            if error.code == 401:
                raise SystemExit("Jev rejected the API token") from error
            if error.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {error.code}: {detail}") from error
            time.sleep(delay)
            delay = min(delay * 2, 30)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = type(error).__name__
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RuntimeError(last_error)


def main() -> None:
    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    token = load_token()
    episodes = json.loads(EPISODES.read_text())
    if limit is not None:
        episodes = episodes[:limit]
    done = load_done()
    pending = [episode for episode in episodes if episode["id"] not in done]
    RAW.parent.mkdir(parents=True, exist_ok=True)
    lock = Lock()
    started = time.perf_counter()
    failures = 0
    print(f"pending {len(pending)} of {len(episodes)} already done {len(done)}", flush=True)

    def record(row: dict) -> None:
        with lock:
            with RAW.open("a") as handle:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    if pending:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(label_one, token, episode): episode for episode in pending}
            finished = 0
            for future in as_completed(futures):
                episode = futures[future]
                try:
                    row = future.result()
                except Exception as error:  # noqa: BLE001 — keep the batch going
                    failures += 1
                    print(f"fail {episode['title'][:60]}: {error}", flush=True)
                    continue
                record(row)
                finished += 1
                if finished % 25 == 0 or finished == len(pending):
                    elapsed = time.perf_counter() - started
                    print(
                        f"{finished}/{len(pending)} in {elapsed:.0f}s failures {failures}",
                        flush=True,
                    )

    wanted = {episode["id"] for episode in episodes}
    rows = [row for row in load_done().values() if row["id"] in wanted]
    wall = time.perf_counter() - started
    input_tokens = sum(row["input_tokens"] for row in rows)
    # Cost is for this process's new calls only when resuming; report all stored rows
    # plus wall clock of this invocation. Also store cumulative token cost.
    summary = {
        "model": rows[0]["model"] if rows else MODEL,
        "threshold": THRESHOLD,
        "episodes_requested": len(episodes),
        "episodes_labeled": len(rows),
        "failures_this_run": failures,
        "new_calls_this_run": len(pending) - failures,
        "wall_seconds_this_run": round(wall, 1),
        "input_tokens": input_tokens,
        "output_tokens": sum(row["output_tokens"] for row in rows),
        "cost_usd": round(input_tokens / 1_000_000 * PRICE_PER_MILLION, 6),
        "mean_call_seconds": round(
            sum(row["seconds"] for row in rows) / len(rows), 3
        )
        if rows
        else 0,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
