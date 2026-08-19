import pandas as pd
import unittest

from dashboard import metric_status_class, prepare_speaker_table, sentiment_marker_color


class DashboardHelperTest(unittest.TestCase):
    def test_metric_status_class_uses_requested_thresholds(self):
        self.assertEqual(metric_status_class(80), "metric-good")
        self.assertEqual(metric_status_class(60), "metric-medium")
        self.assertEqual(metric_status_class(59.9), "metric-bad")

    def test_sentiment_marker_color_distinguishes_positive_negative_and_neutral(self):
        self.assertEqual(sentiment_marker_color(0.1), "#16a34a")
        self.assertEqual(sentiment_marker_color(-0.1), "#dc2626")
        self.assertEqual(sentiment_marker_color(0), "#f59e0b")

    def test_prepare_speaker_table_formats_minutes_percentage_and_utterances(self):
        speaker_stats = pd.DataFrame(
            [
                {
                    "speaker": "Maria",
                    "total_speaking_time": 120,
                    "speaking_time_pct": 60,
                    "segment_count": 3,
                },
                {
                    "speaker": "John",
                    "total_speaking_time": 80,
                    "speaking_time_pct": 40,
                    "segment_count": 2,
                },
            ]
        )

        table = prepare_speaker_table(speaker_stats)

        self.assertEqual(
            table.to_dict(orient="records"),
            [
                {
                    "Speaker": "Maria",
                    "Speaking Time (min)": 2.0,
                    "Percentage": "60.0%",
                    "Number of Utterances": 3,
                },
                {
                    "Speaker": "John",
                    "Speaking Time (min)": 1.3,
                    "Percentage": "40.0%",
                    "Number of Utterances": 2,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
