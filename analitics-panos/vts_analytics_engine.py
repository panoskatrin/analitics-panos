"""VTS Meeting Analytics Engine.

This module is intentionally self-contained so it can be imported by a
Streamlit app or run from a small CLI wrapper.  It expects transcript rows with:

    speaker, start_time, end_time, text[, language]

The implementation favors simple, explainable metrics over heavy NLP models.
Optional dependencies such as langdetect and TextBlob are used when available,
with graceful fallbacks so prototype usage is not blocked by one missing package.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

try:
    from langdetect import DetectorFactory, LangDetectException, detect

    DetectorFactory.seed = 42
except Exception:  # pragma: no cover - depends on optional local installation
    detect = None
    LangDetectException = Exception

try:
    from textblob import TextBlob
except Exception:  # pragma: no cover - depends on optional local installation
    TextBlob = None


LANGUAGE_NAMES = {
    "el": "Greek",
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "unknown": "Unknown",
}

DEFAULT_STOPWORDS = {
    "a",
    "about",
    "after",
    "again",
    "all",
    "also",
    "am",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "but",
    "by",
    "can",
    "could",
    "do",
    "for",
    "from",
    "have",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "let",
    "lets",
    "me",
    "my",
    "no",
    "not",
    "of",
    "on",
    "or",
    "our",
    "so",
    "that",
    "the",
    "their",
    "this",
    "to",
    "we",
    "will",
    "with",
    "you",
    "your",
    # Small multilingual additions for the bundled sample.
    "και",
    "το",
    "τη",
    "την",
    "να",
    "σε",
    "der",
    "die",
    "das",
    "und",
    "wir",
    "le",
    "la",
    "les",
    "des",
    "nous",
}


@dataclass
class QualityWeights:
    """Weights for the composite quality score."""

    participation_balance: float = 0.40
    sentiment_positivity: float = 0.30
    engagement: float = 0.30

    @classmethod
    def from_dict(cls, weights: Optional[Dict[str, float]]) -> "QualityWeights":
        if not weights:
            return cls()

        merged = cls().__dict__
        merged.update({k: float(v) for k, v in weights.items() if k in merged})
        total = sum(merged.values())
        if total <= 0:
            return cls()
        return cls(**{k: v / total for k, v in merged.items()})


def create_sample_meeting() -> pd.DataFrame:
    """Create a small multilingual transcript for smoke tests and demos."""

    rows = [
        ("Maria", 0, 18, "Good morning everyone, today we need to agree on the launch plan.", "en"),
        ("Nikos", 19, 35, "Καλημέρα, πιστεύω ότι το χρονοδιάγραμμα είναι ρεαλιστικό.", "el"),
        ("Anna", 36, 52, "Ich sehe ein Risiko bei der Datenmigration, aber wir können es lösen.", "de"),
        ("Claire", 53, 70, "Nous devons aussi préparer un message clair pour les clients.", "fr"),
        ("Maria", 71, 92, "The action item for me is to update the budget forecast by Friday.", "en"),
        ("Nikos", 93, 110, "Συμφωνώ, και θα ελέγξω τα τεχνικά θέματα αύριο.", "el"),
        ("Anna", 111, 128, "Das klingt gut. Ich übernehme die Qualitätssicherung.", "de"),
        ("Claire", 129, 145, "Je suis d'accord, mais il faut confirmer les dépendances.", "fr"),
        ("Maria", 146, 160, "Great, then we have a decision and clear owners.", "en"),
    ]
    return pd.DataFrame(rows, columns=["speaker", "start_time", "end_time", "text", "language"])


def load_transcript_csv(path: str) -> pd.DataFrame:
    """Load a transcript CSV and return a pandas DataFrame."""

    resolved_path = _resolve_csv_path(path)
    return pd.read_csv(resolved_path)


def _resolve_csv_path(path: str) -> str:
    """Resolve common transcript path mistakes without hiding real errors."""

    if os.path.exists(path):
        return path

    root, ext = os.path.splitext(path)
    if ext.lower() == ".cvs":
        csv_path = f"{root}.csv"
        if os.path.exists(csv_path):
            return csv_path

    raise FileNotFoundError(f"CSV file not found: {path}")


def _clean_text(value: Any) -> str:
    text = "" if pd.isna(value) else str(value)
    return re.sub(r"\s+", " ", text).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except Exception:
        pass
    return default


def _language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(str(code).lower(), str(code).upper())


def _json_safe(value: Any) -> Any:
    """Convert numpy/pandas objects into JSON-serializable Python objects."""

    if isinstance(value, pd.DataFrame):
        return [_json_safe(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return _json_safe(value.to_dict())
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item") and callable(value.item):
        return _json_safe(value.item())
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


class VTSAnalyticsEngine:
    """Analytics engine for meeting transcript data."""

    required_columns = {"speaker", "start_time", "end_time", "text"}

    def __init__(self, df: pd.DataFrame):
        self.df = self._prepare_dataframe(df)
        self._last_results: Optional[Dict[str, Any]] = None

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate required columns, normalize types, and compute duration."""

        if df is None:
            df = pd.DataFrame(columns=sorted(self.required_columns))

        missing = self.required_columns - set(df.columns)
        if missing:
            raise ValueError(f"Transcript is missing required columns: {sorted(missing)}")

        prepared = df.copy()
        prepared["speaker"] = prepared["speaker"].fillna("Unknown").astype(str).str.strip()
        prepared["speaker"] = prepared["speaker"].replace("", "Unknown")
        prepared["text"] = prepared["text"].apply(_clean_text)
        prepared["start_time"] = pd.to_numeric(prepared["start_time"], errors="coerce").fillna(0.0)
        prepared["end_time"] = pd.to_numeric(prepared["end_time"], errors="coerce").fillna(prepared["start_time"])
        prepared["duration"] = (prepared["end_time"] - prepared["start_time"]).clip(lower=0)
        prepared = prepared.sort_values(["start_time", "end_time"]).reset_index(drop=True)
        return prepared

    @classmethod
    def from_csv(cls, path: str) -> "VTSAnalyticsEngine":
        return cls(load_transcript_csv(path))

    def detect_languages(self) -> pd.DataFrame:
        """Detect or normalize language codes for every segment."""

        if "language" in self.df.columns:
            detected = self.df["language"].fillna("unknown").astype(str).str.strip().str.lower()
            detected = detected.replace("", "unknown")
        else:
            detected_values = []
            for text in self.df["text"]:
                if len(text) <= 15 or detect is None:
                    detected_values.append("unknown")
                    continue
                try:
                    detected_values.append(detect(text))
                except LangDetectException:
                    detected_values.append("unknown")
            detected = pd.Series(detected_values, index=self.df.index)

        self.df["detected_language"] = detected
        self.df["language_name"] = self.df["detected_language"].apply(_language_name)
        return self.df[["speaker", "start_time", "end_time", "text", "detected_language", "language_name"]]

    def language_stats(self) -> Dict[str, Any]:
        """Summarize language usage, switches, and per-speaker distribution."""

        self._ensure_languages()
        total_segments = len(self.df)
        total_duration = float(self.df["duration"].sum())

        if total_segments == 0:
            return {
                "distribution": [],
                "primary_languages": [],
                "language_switches": 0,
                "per_speaker": [],
            }

        grouped = self.df.groupby("detected_language", dropna=False).agg(
            segments=("detected_language", "size"),
            duration=("duration", "sum"),
        )
        grouped["segment_pct"] = grouped["segments"] / max(total_segments, 1) * 100
        grouped["duration_pct"] = grouped["duration"] / max(total_duration, 1e-9) * 100
        grouped = grouped.reset_index().sort_values(["segments", "duration"], ascending=False)
        grouped["language_name"] = grouped["detected_language"].apply(_language_name)

        switches = int(
            (self.df["detected_language"] != self.df["detected_language"].shift(1)).iloc[1:].sum()
        )

        speaker_lang = (
            self.df.groupby(["speaker", "detected_language"], dropna=False)
            .agg(segments=("text", "size"), duration=("duration", "sum"))
            .reset_index()
            .sort_values(["speaker", "segments"], ascending=[True, False])
        )
        speaker_lang["language_name"] = speaker_lang["detected_language"].apply(_language_name)

        return {
            "distribution": _json_safe(grouped),
            "primary_languages": grouped.head(3)["detected_language"].tolist(),
            "language_switches": switches,
            "per_speaker": _json_safe(speaker_lang),
        }

    def speaker_stats(self) -> pd.DataFrame:
        """Return per-speaker talk-time, segment count, and average segment length."""

        if self.df.empty:
            return pd.DataFrame(
                columns=[
                    "speaker",
                    "total_speaking_time",
                    "speaking_time_pct",
                    "segment_count",
                    "avg_segment_length",
                ]
            )

        stats = self.df.groupby("speaker").agg(
            total_speaking_time=("duration", "sum"),
            segment_count=("text", "size"),
            avg_segment_length=("duration", "mean"),
        )
        total = float(stats["total_speaking_time"].sum())
        stats["speaking_time_pct"] = stats["total_speaking_time"] / max(total, 1e-9) * 100
        return (
            stats.reset_index()
            .sort_values("total_speaking_time", ascending=False)
            .reset_index(drop=True)
        )

    def dominant_speaker(self) -> Optional[str]:
        stats = self.speaker_stats()
        if stats.empty:
            return None
        return str(stats.iloc[0]["speaker"])

    def participation_balance(self) -> float:
        """Return a 0-100 participation balance score based on Gini coefficient."""

        stats = self.speaker_stats()
        values = sorted(float(value) for value in stats["total_speaking_time"].tolist())
        if len(values) <= 1:
            return 100.0 if len(values) == 1 else 0.0

        total = sum(values)
        if total <= 0:
            return 0.0

        n = len(values)
        weighted_sum = sum(index * value for index, value in enumerate(values, start=1))
        gini = (2 * weighted_sum / (n * total)) - ((n + 1) / n)
        return round(float((1 - max(0.0, min(1.0, gini))) * 100), 2)

    def sentiment_analysis(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Compute TextBlob sentiment per segment and aggregate it."""

        polarities: List[float] = []
        subjectivities: List[float] = []

        for text in self.df["text"]:
            if not text or TextBlob is None:
                polarity = 0.0
                subjectivity = 0.0
            else:
                blob = TextBlob(text)
                polarity = float(blob.sentiment.polarity)
                subjectivity = float(blob.sentiment.subjectivity)
            polarities.append(polarity)
            subjectivities.append(subjectivity)

        sentiment_df = self.df.copy()
        sentiment_df["polarity"] = polarities
        sentiment_df["subjectivity"] = subjectivities
        sentiment_df["sentiment_category"] = sentiment_df["polarity"].apply(self._sentiment_category)
        self.df["polarity"] = sentiment_df["polarity"]
        self.df["subjectivity"] = sentiment_df["subjectivity"]
        self.df["sentiment_category"] = sentiment_df["sentiment_category"]

        overall = float(sentiment_df["polarity"].mean()) if not sentiment_df.empty else 0.0
        volatility = float(sentiment_df["polarity"].std(ddof=0)) if len(sentiment_df) > 1 else 0.0

        per_speaker = (
            sentiment_df.groupby("speaker")
            .agg(
                avg_polarity=("polarity", "mean"),
                avg_subjectivity=("subjectivity", "mean"),
                sentiment_volatility=("polarity", "std"),
                segments=("text", "size"),
            )
            .fillna(0)
            .reset_index()
            if not sentiment_df.empty
            else pd.DataFrame()
        )

        self._ensure_languages()
        per_language = (
            sentiment_df.assign(detected_language=self.df["detected_language"])
            .groupby("detected_language")
            .agg(
                avg_polarity=("polarity", "mean"),
                avg_subjectivity=("subjectivity", "mean"),
                sentiment_volatility=("polarity", "std"),
                segments=("text", "size"),
            )
            .fillna(0)
            .reset_index()
            if not sentiment_df.empty
            else pd.DataFrame()
        )
        if not per_language.empty:
            per_language["language_name"] = per_language["detected_language"].apply(_language_name)

        stats = {
            "overall_polarity": overall,
            "overall_subjectivity": float(sentiment_df["subjectivity"].mean()) if not sentiment_df.empty else 0.0,
            "sentiment_volatility": volatility,
            "sentiment_category": self._sentiment_category(overall),
            "per_speaker": _json_safe(per_speaker),
            "per_language": _json_safe(per_language),
        }
        return sentiment_df, stats

    def turn_taking(self) -> Dict[str, Any]:
        """Count speaker-to-speaker transitions and return matrix-friendly data."""

        speakers = self.df["speaker"].tolist()
        transition_counts: Counter[Tuple[str, str]] = Counter()
        for previous, current in zip(speakers, speakers[1:]):
            if previous != current:
                transition_counts[(previous, current)] += 1

        records = [
            {"from_speaker": src, "to_speaker": dst, "count": count}
            for (src, dst), count in transition_counts.most_common()
        ]

        matrix = pd.DataFrame(0, index=sorted(set(speakers)), columns=sorted(set(speakers)))
        for (src, dst), count in transition_counts.items():
            matrix.loc[src, dst] = count

        most_common = records[0] if records else None
        return {
            "total_transitions": int(sum(transition_counts.values())),
            "most_common_transition": most_common,
            "transition_counts": records,
            "transition_matrix": _json_safe(matrix.reset_index().rename(columns={"index": "from_speaker"})),
        }

    def keyword_extraction(
        self, top_n: int = 20, extra_stopwords: Optional[Iterable[str]] = None
    ) -> List[Tuple[str, int]]:
        """Return top word-frequency keywords after simple stopword removal."""

        stopwords = set(DEFAULT_STOPWORDS)
        if extra_stopwords:
            stopwords.update(word.lower() for word in extra_stopwords)

        all_text = " ".join(self.df["text"].fillna("").astype(str)).lower()
        tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿΑ-Ωα-ωΆ-ώ]+", all_text)
        words = [token for token in tokens if len(token) > 2 and token not in stopwords]
        return Counter(words).most_common(top_n)

    def meeting_quality_score(self, weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Build a 0-100 composite meeting quality score."""

        quality_weights = QualityWeights.from_dict(weights)
        participation = self.participation_balance()

        if "polarity" not in self.df.columns:
            _, sentiment_stats = self.sentiment_analysis()
            overall_polarity = float(sentiment_stats["overall_polarity"])
        else:
            overall_polarity = float(self.df["polarity"].mean()) if not self.df.empty else 0.0

        # Map TextBlob polarity [-1, 1] to [0, 100].
        sentiment_score = round((overall_polarity + 1) * 50, 2)
        engagement = self._engagement_score()

        score = (
            participation * quality_weights.participation_balance
            + sentiment_score * quality_weights.sentiment_positivity
            + engagement * quality_weights.engagement
        )

        return {
            "score": round(float(max(0, min(100, score))), 2),
            "breakdown": {
                "participation_balance": participation,
                "sentiment_positivity": sentiment_score,
                "engagement": engagement,
            },
            "weights": quality_weights.__dict__,
        }

    def summary_statistics(self) -> Dict[str, Any]:
        self._ensure_languages()
        return {
            "total_meeting_duration": float(
                max(self.df["end_time"].max() - self.df["start_time"].min(), 0) if not self.df.empty else 0
            ),
            "total_speaking_time": float(self.df["duration"].sum()),
            "unique_speakers": int(self.df["speaker"].nunique()),
            "languages_used": int(
                self.df.loc[self.df["detected_language"] != "unknown", "detected_language"].nunique()
            ),
            "utterances": int(len(self.df)),
        }

    def decision_and_action_items(self) -> Dict[str, List[Dict[str, Any]]]:
        """Simple keyword-based extraction for dashboard prototypes."""

        decision_pattern = re.compile(r"\b(agree|agreed|decision|decide|approved|συμφωνώ|d'accord)\b", re.I)
        action_pattern = re.compile(r"\b(action item|todo|to do|owner|follow up|αναλαμβάνω|übernehme)\b", re.I)
        decisions = []
        actions = []
        for row in self.df.to_dict(orient="records"):
            payload = {
                "speaker": row["speaker"],
                "start_time": row["start_time"],
                "text": row["text"],
            }
            if decision_pattern.search(row["text"]):
                decisions.append(payload)
            if action_pattern.search(row["text"]):
                actions.append(payload)
        return {"decisions": decisions, "action_items": actions}

    def full_analysis(self) -> Dict[str, Any]:
        """Run every analysis category and return a JSON-ready dictionary."""

        self.detect_languages()
        sentiment_segments, sentiment_stats = self.sentiment_analysis()
        results = {
            "summary": self.summary_statistics(),
            "languages": self.language_stats(),
            "speakers": {
                "stats": _json_safe(self.speaker_stats()),
                "dominant_speaker": self.dominant_speaker(),
            },
            "participation_balance": self.participation_balance(),
            "sentiment": {
                "segments": _json_safe(
                    sentiment_segments[
                        [
                            "speaker",
                            "start_time",
                            "end_time",
                            "text",
                            "polarity",
                            "subjectivity",
                            "sentiment_category",
                        ]
                    ]
                ),
                "stats": sentiment_stats,
            },
            "turn_taking": self.turn_taking(),
            "keywords": [{"word": word, "frequency": freq} for word, freq in self.keyword_extraction()],
            "quality": self.meeting_quality_score(),
            "decisions_and_actions": self.decision_and_action_items(),
        }
        self._last_results = _json_safe(results)
        return self._last_results

    def save_json(self, path: str, results: Optional[Dict[str, Any]] = None) -> None:
        """Save full-analysis results to a JSON file."""

        payload = results or self._last_results or self.full_analysis()
        with open(path, "w", encoding="utf-8") as file:
            json.dump(_json_safe(payload), file, ensure_ascii=False, indent=2)

    def print_report(self, results: Optional[Dict[str, Any]] = None) -> None:
        """Print a compact console report."""

        data = results or self._last_results or self.full_analysis()
        summary = data["summary"]
        quality = data["quality"]
        speakers = data["speakers"]["stats"]
        languages = data["languages"]["distribution"]
        sentiment = data["sentiment"]["stats"]

        print("\n" + "=" * 72)
        print("VTS MEETING ANALYTICS REPORT")
        print("=" * 72)
        print(f"Duration: {summary['total_meeting_duration']:.1f}s")
        print(f"Utterances: {summary['utterances']}")
        print(f"Speakers: {summary['unique_speakers']}")
        print(f"Languages used: {summary['languages_used']}")
        print(f"Meeting quality score: {quality['score']:.1f}/100")
        print(f"Overall sentiment: {sentiment['sentiment_category']} ({sentiment['overall_polarity']:.2f})")
        print(f"Sentiment volatility: {sentiment['sentiment_volatility']:.2f}")
        print(f"Participation balance: {data['participation_balance']:.1f}/100")
        print(f"Dominant speaker: {data['speakers']['dominant_speaker'] or 'N/A'}")

        print("\nSpeaker Metrics")
        print("-" * 72)
        for row in speakers:
            print(
                f"{row['speaker']:<20} "
                f"{row['total_speaking_time']:>8.1f}s "
                f"{row['speaking_time_pct']:>6.1f}% "
                f"{row['segment_count']:>4} segments"
            )

        print("\nLanguage Distribution")
        print("-" * 72)
        for row in languages:
            print(
                f"{row['language_name']:<15} "
                f"{row['segments']:>4} segments "
                f"{row['segment_pct']:>6.1f}%"
            )

        print("\nTop Keywords")
        print("-" * 72)
        print(", ".join(f"{item['word']} ({item['frequency']})" for item in data["keywords"][:15]) or "None")
        print("=" * 72 + "\n")

    def _ensure_languages(self) -> None:
        if "detected_language" not in self.df.columns:
            self.detect_languages()

    @staticmethod
    def _sentiment_category(polarity: float) -> str:
        if polarity > 0.1:
            return "positive"
        if polarity < -0.1:
            return "negative"
        return "neutral"

    def _engagement_score(self) -> float:
        """Estimate engagement from turns, speaker participation, and language richness."""

        utterances = len(self.df)
        if utterances == 0:
            return 0.0

        unique_speakers = max(int(self.df["speaker"].nunique()), 1)
        transitions = self.turn_taking()["total_transitions"]
        turns_per_utterance = transitions / max(utterances - 1, 1)
        speaker_factor = min(unique_speakers / 4, 1.0)

        self._ensure_languages()
        language_count = int(
            self.df.loc[self.df["detected_language"] != "unknown", "detected_language"].nunique()
        )
        language_factor = min(language_count / 3, 1.0)

        score = (turns_per_utterance * 50) + (speaker_factor * 30) + (language_factor * 20)
        return round(float(max(0, min(100, score))), 2)


if __name__ == "__main__":
    engine = VTSAnalyticsEngine(create_sample_meeting())
    analysis = engine.full_analysis()
    engine.print_report(analysis)
