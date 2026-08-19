#!/usr/bin/env python3
"""VTS Meeting Analytics CLI using only the Python standard library."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
from collections import Counter, defaultdict
from typing import Any


REQUIRED_COLUMNS = {"speaker", "start_time", "end_time", "text"}
DEFAULT_SPEAKERS = ["Speaker A", "Speaker B", "Speaker C", "Speaker D"]
CSV_COLUMN_ALIASES = {
    "speaker": {
        "speaker",
        "name",
        "person",
        "participant",
        "participant_name",
        "user",
        "author",
        "talker",
    },
    "start_time": {
        "start_time",
        "start",
        "begin",
        "begin_time",
        "from",
        "timestamp",
        "start_seconds",
        "start_sec",
        "time_start",
    },
    "end_time": {
        "end_time",
        "end",
        "finish",
        "stop",
        "to",
        "end_seconds",
        "end_sec",
        "time_end",
    },
    "text": {
        "text",
        "utterance",
        "transcript",
        "content",
        "sentence",
        "message",
        "caption",
        "subtitle",
        "line",
    },
}
STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "you",
    "your",
    "our",
    "are",
    "was",
    "were",
    "will",
    "from",
    "have",
    "has",
    "let",
    "lets",
    "about",
    "into",
    "και",
    "την",
    "το",
    "να",
    "σε",
    "der",
    "die",
    "das",
    "und",
    "wir",
    "les",
    "des",
    "nous",
}
POSITIVE_WORDS = {
    "good",
    "great",
    "agree",
    "agreed",
    "solid",
    "growth",
    "increased",
    "realistic",
    "clear",
    "thanks",
    "ευχαριστώ",
    "συμφωνώ",
    "gut",
    "d'accord",
    "bonne",
}
NEGATIVE_WORDS = {
    "risk",
    "drop",
    "problem",
    "issue",
    "failed",
    "bad",
    "worse",
    "πτώση",
    "risiko",
    "schlecht",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run VTS meeting analytics.")
    parser.add_argument(
        "input_path",
        nargs="?",
        default="sample_meeting.csv",
        help="Path to transcript file: CSV, TXT, SRT, or VTT.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to save JSON results. Defaults to <csv_name>_analytics.json.",
    )
    return parser.parse_args()


def resolve_csv_path(path: str) -> str:
    if os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    if ext.lower() == ".cvs":
        csv_path = f"{root}.csv"
        if os.path.exists(csv_path):
            return csv_path
    raise FileNotFoundError(f"CSV file not found: {path}")


def detect_file_type(filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower()
    if extension == ".csv" or extension == ".cvs":
        return "csv"
    if extension == ".txt":
        return "txt"
    if extension == ".srt":
        return "srt"
    if extension == ".vtt":
        return "vtt"
    return "unknown"


def converted_csv_path(input_path: str) -> str:
    base, _ = os.path.splitext(input_path)
    return f"{base}.csv"


def canonical_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def map_csv_columns(fieldnames: list[str]) -> dict[str, str]:
    normalized = {canonical_header(name): name for name in fieldnames}
    mapping: dict[str, str] = {}

    for required, aliases in CSV_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[required] = normalized[alias]
                break

    return mapping


def normalize_csv(input_file: str, output_file: str | None = None) -> str:
    resolved = resolve_csv_path(input_file)
    with open(resolved, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV file has no header row.")

        fieldnames = list(reader.fieldnames)
        if REQUIRED_COLUMNS <= set(fieldnames):
            return resolved

        mapping = map_csv_columns(fieldnames)
        missing = REQUIRED_COLUMNS - set(mapping)
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        target = output_file or f"{os.path.splitext(resolved)[0]}_normalized.csv"
        rows = []
        for row in reader:
            rows.append(
                {
                    "speaker": row.get(mapping["speaker"], ""),
                    "start_time": parse_time_to_seconds(row.get(mapping["start_time"], "0")),
                    "end_time": parse_time_to_seconds(row.get(mapping["end_time"], "0")),
                    "text": row.get(mapping["text"], ""),
                }
            )

    write_segments_csv(target, rows)
    return target


def write_segments_csv(output_file: str, rows: list[dict[str, Any]]) -> None:
    with open(output_file, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["speaker", "start_time", "end_time", "text"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "speaker": clean_text(row.get("speaker") or "Unknown"),
                    "start_time": f"{float(row.get('start_time') or 0):.3f}",
                    "end_time": f"{float(row.get('end_time') or 0):.3f}",
                    "text": clean_text(row.get("text") or ""),
                }
            )


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?;])\s+|\n+", text)
    sentences: list[str] = []
    for chunk in chunks:
        cleaned = clean_text(chunk)
        if cleaned:
            sentences.append(cleaned)
    return sentences


def convert_txt_to_csv(
    input_file: str,
    output_file: str,
    num_speakers: int = 4,
    speaker_names: list[str] | None = None,
) -> None:
    speakers = speaker_names or DEFAULT_SPEAKERS[: max(1, num_speakers)]
    if not speakers:
        speakers = DEFAULT_SPEAKERS

    with open(input_file, "r", encoding="utf-8-sig") as handle:
        sentences = split_sentences(handle.read())

    rows: list[dict[str, Any]] = []
    current_time = 0.0
    for index, sentence in enumerate(sentences):
        word_count = len(re.findall(r"[\wÀ-ÖØ-öø-ÿΑ-Ωα-ωΆ-ώ']+", sentence))
        duration = word_count * 0.3 + random.uniform(1.0, 3.0)
        end_time = current_time + max(duration, 1.0)
        rows.append(
            {
                "speaker": speakers[index % len(speakers)],
                "start_time": current_time,
                "end_time": end_time,
                "text": sentence,
            }
        )
        current_time = end_time

    write_segments_csv(output_file, rows)


def convert_srt_to_csv(input_file: str, output_file: str, speaker_names: list[str] | None = None) -> None:
    speakers = speaker_names or DEFAULT_SPEAKERS
    rows: list[dict[str, Any]] = []
    current_start: float | None = None
    current_end: float | None = None
    current_text: list[str] = []

    def flush_block() -> None:
        nonlocal current_start, current_end, current_text
        if current_start is not None and current_end is not None and current_text:
            text = clean_text(" ".join(current_text))
            rows.append(
                {
                    "speaker": speakers[len(rows) % len(speakers)],
                    "start_time": current_start,
                    "end_time": current_end,
                    "text": text,
                }
            )
        current_start = None
        current_end = None
        current_text = []

    with open(input_file, "r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                flush_block()
                continue
            if line.upper() == "WEBVTT" or line.startswith(("NOTE", "STYLE", "REGION")):
                continue
            if re.fullmatch(r"\d+", line):
                continue
            if "-->" in line:
                flush_block()
                start, end = parse_subtitle_timing(line)
                current_start = start
                current_end = end
                continue
            if current_start is not None:
                current_text.append(strip_subtitle_markup(line))

    flush_block()
    write_segments_csv(output_file, rows)


def parse_subtitle_timing(line: str) -> tuple[float, float]:
    start_raw, end_raw = line.split("-->", 1)
    end_raw = end_raw.strip().split()[0]
    return parse_time_to_seconds(start_raw.strip()), parse_time_to_seconds(end_raw.strip())


def parse_time_to_seconds(value: Any) -> float:
    text = str(value or "0").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass

    text = text.replace(",", ".")
    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {value}") from exc

    raise ValueError(f"Invalid timestamp: {value}")


def strip_subtitle_markup(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return clean_text(text)


def auto_detect_language(text: str) -> str:
    return detect_language(text)


def prepare_input_file(input_path: str) -> str:
    file_type = detect_file_type(input_path)
    if file_type == "unknown":
        raise ValueError(f"Unsupported input file type: {input_path}")
    if file_type == "csv":
        return normalize_csv(input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    csv_file = converted_csv_path(input_path)
    if file_type == "txt":
        convert_txt_to_csv(input_path, csv_file)
    elif file_type in {"srt", "vtt"}:
        convert_srt_to_csv(input_path, csv_file)

    print(f"Converted {file_type} to CSV: {csv_file}")
    return csv_file


def default_output_path(path: str) -> str:
    base, _ = os.path.splitext(path)
    return f"{base}_analytics.json"


def load_segments(path: str) -> list[dict[str, Any]]:
    resolved = resolve_csv_path(path)
    segments: list[dict[str, Any]] = []
    with open(resolved, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV file has no header row.")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

        for line_number, row in enumerate(reader, start=2):
            try:
                start_time = float(row.get("start_time") or 0)
                end_time = float(row.get("end_time") or start_time)
            except ValueError as exc:
                raise ValueError(f"Invalid start/end time at line {line_number}.") from exc

            speaker = clean_text(row.get("speaker") or "Unknown") or "Unknown"
            text = clean_text(row.get("text") or "")
            duration = max(end_time - start_time, 0.0)
            segments.append(
                {
                    "speaker": speaker,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "text": text,
                    "detected_language": detect_language(text, row.get("language")),
                }
            )

    segments.sort(key=lambda item: (item["start_time"], item["end_time"]))
    return segments


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def detect_language(text: str, existing: str | None = None) -> str:
    if existing:
        return existing.strip().lower() or "unknown"
    if re.search(r"[Α-Ωα-ωΆ-ώ]", text):
        return "el"
    lowered = text.lower()
    if re.search(r"[àâçéèêëîïôùûüÿœ]", lowered) or any(
        word in lowered
        for word in ["bonjour", "france", "campagne", "vais", "préparer", "tous", "merci"]
    ):
        return "fr"
    if re.search(r"[äöüß]", lowered) or any(
        word in lowered for word in ["guten", "deutschland", "zahlen", "bitte", "zusammen"]
    ):
        return "de"
    if re.search(r"[ñ¿¡]", lowered) or any(
        word in lowered for word in ["hola", "gracias", "buenos", "reunión", "vamos"]
    ):
        return "es"
    if any(
        word in lowered
        for word in ["buongiorno", "grazie", "riunione", "andiamo", "tutti", "ciao"]
    ):
        return "it"
    if len(text) > 0:
        return "en"
    return "unknown"


def gini(values: list[float]) -> float:
    cleaned = sorted(value for value in values if value >= 0)
    if len(cleaned) <= 1:
        return 0.0
    total = sum(cleaned)
    if total <= 0:
        return 0.0
    n = len(cleaned)
    weighted_sum = sum(index * value for index, value in enumerate(cleaned, start=1))
    return (2 * weighted_sum / (n * total)) - ((n + 1) / n)


def sentiment_score(text: str) -> float:
    words = [word.lower() for word in re.findall(r"[\wÀ-ÖØ-öø-ÿΑ-Ωα-ωΆ-ώ']+", text)]
    if not words:
        return 0.0
    positive = sum(1 for word in words if word in POSITIVE_WORDS)
    negative = sum(1 for word in words if word in NEGATIVE_WORDS)
    return max(-1.0, min(1.0, (positive - negative) / max(len(words) ** 0.5, 1.0)))


def analyze(segments: list[dict[str, Any]]) -> dict[str, Any]:
    if not segments:
        raise ValueError("CSV file contains no transcript rows.")

    speakers: dict[str, dict[str, Any]] = {}
    for segment in segments:
        stats = speakers.setdefault(
            segment["speaker"],
            {
                "speaker": segment["speaker"],
                "total_speaking_time": 0.0,
                "segment_count": 0,
                "avg_segment_length": 0.0,
            },
        )
        stats["total_speaking_time"] += segment["duration"]
        stats["segment_count"] += 1

    total_talk = sum(item["total_speaking_time"] for item in speakers.values())
    for item in speakers.values():
        item["speaking_time_pct"] = item["total_speaking_time"] / max(total_talk, 1e-9) * 100
        item["avg_segment_length"] = item["total_speaking_time"] / max(item["segment_count"], 1)

    speaker_rows = sorted(
        speakers.values(), key=lambda item: item["total_speaking_time"], reverse=True
    )
    balance = round((1 - gini([item["total_speaking_time"] for item in speaker_rows])) * 100, 2)

    language_counts = Counter(segment["detected_language"] for segment in segments)
    language_distribution = [
        {
            "detected_language": language,
            "segments": count,
            "segment_pct": count / len(segments) * 100,
        }
        for language, count in language_counts.most_common()
    ]
    language_switches = sum(
        1
        for previous, current in zip(segments, segments[1:])
        if previous["detected_language"] != current["detected_language"]
    )

    transitions = Counter(
        (previous["speaker"], current["speaker"])
        for previous, current in zip(segments, segments[1:])
        if previous["speaker"] != current["speaker"]
    )
    transition_rows = [
        {"from_speaker": source, "to_speaker": target, "count": count}
        for (source, target), count in transitions.most_common()
    ]

    sentiment_rows = []
    for segment in segments:
        polarity = sentiment_score(segment["text"])
        sentiment_rows.append({**segment, "polarity": polarity, "category": sentiment_label(polarity)})

    polarities = [row["polarity"] for row in sentiment_rows]
    overall_sentiment = sum(polarities) / max(len(polarities), 1)
    volatility = math.sqrt(
        sum((score - overall_sentiment) ** 2 for score in polarities) / max(len(polarities), 1)
    )

    keywords = keyword_extraction(segments)
    quality = quality_score(balance, overall_sentiment, len(transitions), len(segments), len(speakers))

    return {
        "summary": {
            "total_meeting_duration": max(item["end_time"] for item in segments)
            - min(item["start_time"] for item in segments),
            "total_speaking_time": total_talk,
            "unique_speakers": len(speakers),
            "languages_used": len([lang for lang in language_counts if lang != "unknown"]),
            "utterances": len(segments),
        },
        "speakers": {
            "stats": speaker_rows,
            "dominant_speaker": speaker_rows[0]["speaker"] if speaker_rows else None,
        },
        "languages": {
            "distribution": language_distribution,
            "primary_languages": [row["detected_language"] for row in language_distribution[:3]],
            "language_switches": language_switches,
        },
        "participation_balance": balance,
        "sentiment": {
            "overall_polarity": overall_sentiment,
            "sentiment_volatility": volatility,
            "sentiment_category": sentiment_label(overall_sentiment),
            "segments": sentiment_rows,
        },
        "turn_taking": {
            "total_transitions": sum(transitions.values()),
            "most_common_transition": transition_rows[0] if transition_rows else None,
            "transition_counts": transition_rows,
        },
        "keywords": keywords,
        "quality": quality,
        "note": "Generated by the standard-library VTS analytics engine.",
    }


def sentiment_label(polarity: float) -> str:
    if polarity > 0.1:
        return "positive"
    if polarity < -0.1:
        return "negative"
    return "neutral"


def keyword_extraction(segments: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
    text = " ".join(segment["text"].lower() for segment in segments)
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿΑ-Ωα-ωΆ-ώ]+", text)
    words = [token for token in tokens if len(token) > 2 and token not in STOPWORDS]
    return [{"word": word, "frequency": count} for word, count in Counter(words).most_common(top_n)]


def quality_score(
    balance: float, overall_sentiment: float, transitions: int, utterances: int, speakers: int
) -> dict[str, Any]:
    sentiment = round((overall_sentiment + 1) * 50, 2)
    turn_factor = transitions / max(utterances - 1, 1)
    speaker_factor = min(speakers / 4, 1.0)
    engagement = round(min(100.0, turn_factor * 70 + speaker_factor * 30), 2)
    score = round(balance * 0.4 + sentiment * 0.3 + engagement * 0.3, 2)
    return {
        "score": max(0.0, min(100.0, score)),
        "breakdown": {
            "participation_balance": balance,
            "sentiment_positivity": sentiment,
            "engagement": engagement,
        },
        "weights": {
            "participation_balance": 0.4,
            "sentiment_positivity": 0.3,
            "engagement": 0.3,
        },
    }


def print_report(results: dict[str, Any]) -> None:
    summary = results["summary"]
    quality = results["quality"]
    print("\n" + "=" * 72)
    print("VTS MEETING ANALYTICS REPORT")
    print("=" * 72)
    print(f"Duration: {summary['total_meeting_duration']:.1f}s")
    print(f"Utterances: {summary['utterances']}")
    print(f"Speakers: {summary['unique_speakers']}")
    print(f"Languages used: {summary['languages_used']}")
    print(f"Language switches: {results['languages']['language_switches']}")
    print(f"Meeting quality score: {quality['score']:.1f}/100")
    print(f"Participation balance: {results['participation_balance']:.1f}/100")
    print(
        "Overall sentiment: "
        f"{results['sentiment']['sentiment_category']} "
        f"({results['sentiment']['overall_polarity']:.2f})"
    )
    print(f"Dominant speaker: {results['speakers']['dominant_speaker'] or 'N/A'}")

    print("\nSpeaker Metrics")
    print("-" * 72)
    for row in results["speakers"]["stats"]:
        print(
            f"{row['speaker']:<24} "
            f"{row['total_speaking_time']:>7.1f}s "
            f"{row['speaking_time_pct']:>6.1f}% "
            f"{row['segment_count']:>3} segments"
        )

    print("\nLanguage Distribution")
    print("-" * 72)
    for row in results["languages"]["distribution"]:
        print(
            f"{row['detected_language']:<8} "
            f"{row['segments']:>3} segments "
            f"{row['segment_pct']:>6.1f}%"
        )

    print("\nTop Keywords")
    print("-" * 72)
    print(", ".join(f"{item['word']} ({item['frequency']})" for item in results["keywords"][:15]))
    if results.get("note"):
        print(f"\nNote: {results['note']}")
    print("=" * 72 + "\n")


def main() -> int:
    args = parse_args()

    try:
        csv_path = prepare_input_file(args.input_path)
        output_path = args.output or default_output_path(csv_path)

        segments = load_segments(csv_path)
        results = analyze(segments)
        print_report(results)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=2)
        print(f"Saved JSON results to: {output_path}")
    except Exception as exc:
        print(f"Error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
