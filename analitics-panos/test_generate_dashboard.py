import tempfile
import unittest
from pathlib import Path

from generate_dashboard import create_sentiment_timeline_plot, write_dashboard


SAMPLE_ANALYTICS = {
    "summary": {
        "utterances": 2,
        "unique_speakers": 2,
        "total_meeting_duration": 60,
        "languages_used": 1,
    },
    "quality": {"score": 75, "breakdown": {"participation_balance": 80}},
    "participation_balance": 80,
    "speakers": {
        "stats": [
            {
                "speaker": "Maria",
                "total_speaking_time": 30,
                "speaking_time_pct": 50,
                "segment_count": 1,
            },
            {
                "speaker": "John",
                "total_speaking_time": 30,
                "speaking_time_pct": 50,
                "segment_count": 1,
            },
        ]
    },
    "sentiment": {
        "segments": [
            {"speaker": "Maria", "start_time": 0, "end_time": 30, "polarity": 0.2, "text": "Good"},
            {"speaker": "John", "start_time": 30, "end_time": 60, "polarity": -0.1, "text": "Risk"},
        ]
    },
    "languages": {"distribution": [{"detected_language": "en", "segments": 2, "segment_pct": 100}]},
    "turn_taking": {"transition_counts": []},
    "keywords": [],
}


class GenerateDashboardTest(unittest.TestCase):
    def render_html(self) -> str:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dashboard.html"
            write_dashboard(SAMPLE_ANALYTICS, str(output))
            return output.read_text(encoding="utf-8")

    def test_generated_dashboard_uses_dark_mode_palette(self):
        html = self.render_html()

        self.assertIn("--bg: #0f172a", html)
        self.assertIn("--panel: #111827", html)
        self.assertIn("color: var(--ink)", html)

    def test_speaker_labels_are_large_and_not_rotated(self):
        html = self.render_html()

        self.assertIn("ctx.font = '700 18px system-ui'", html)
        self.assertNotIn("ctx.rotate(-0.45)", html)

    def test_sentiment_line_is_rounded_without_closed_area_edges(self):
        html = self.render_html()

        self.assertIn("sentimentChart", html)
        self.assertIn("_sentiment_timeline.png", html)
        self.assertNotIn("function drawLineChart()", html)
        self.assertNotIn("ctx.closePath();\n      ctx.fillStyle = 'rgba(31, 119, 180, 0.05)'", html)

    def test_matplotlib_sentiment_plot_uses_spline_and_300_points(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sentiment.png"
            metadata = create_sentiment_timeline_plot(SAMPLE_ANALYTICS, str(output))

            self.assertTrue(output.exists())
            self.assertEqual(metadata["interpolated_points"], 300)
            self.assertEqual(metadata["raw_points"], 2)
            self.assertEqual(metadata["x_label"], "Time (minutes)")
            self.assertEqual(metadata["y_tick_labels"], ["Negative", "Neutral", "Positive"])


if __name__ == "__main__":
    unittest.main()
