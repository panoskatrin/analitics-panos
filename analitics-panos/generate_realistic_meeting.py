#!/usr/bin/env python3
"""Generate a realistic multilingual meeting transcript CSV."""

from __future__ import annotations

import csv
import random


DURATION_SECONDS = 1800
OUTPUT_FILE = "realistic_meeting.csv"

SPEAKERS = [
    {"name": "Μαρία Παπαδοπούλου", "lang": "el", "role": "moderator"},
    {"name": "Hans Mueller", "lang": "de", "role": "expert"},
    {"name": "Pierre Dubois", "lang": "fr", "role": "politician"},
    {"name": "John Smith", "lang": "en", "role": "analyst"},
    {"name": "Carmen Lopez", "lang": "es", "role": "activist"},
]

PHRASES = {
    "el": {
        "opening": [
            "Καλημέρα σε όλους, ας ξεκινήσουμε τη συζήτηση για την κλιματική αλλαγή.",
            "Λοιπόν, ποιες είναι οι απόψεις σας για την πράσινη συμφωνία;",
        ],
        "statement": [
            "Πιστεύω ότι πρέπει να μειώσουμε τις εκπομπές άμεσα.",
            "Η Ελλάδα έχει τεράστιο δυναμικό σε ανανεώσιμες πηγές.",
            "Οι τοπικές κοινωνίες χρειάζονται οικονομική στήριξη.",
            "Δεν συμφωνώ με αυτή την προσέγγιση.",
            "Μήπως να εξετάσουμε και την κοινωνική διάσταση;",
        ],
        "question": [
            "Τι προτείνετε για τη χρηματοδότηση;",
            "Πώς θα επηρεαστούν οι αγρότες;",
            "Υπάρχουν στοιχεία που να το υποστηρίζουν;",
        ],
        "agreement": [
            "Συμφωνώ απόλυτα.",
            "Έχετε δίκιο.",
            "Ακριβώς, αυτό εννοούσα.",
        ],
        "disagreement": [
            "Διαφωνώ κάθετα.",
            "Δεν νομίζω ότι είναι έτσι.",
            "Μα αυτό είναι ανέφικτο.",
        ],
        "backchannel": [
            "Μάλιστα.",
            "Ναι, ναι.",
            "Ενδιαφέρον...",
        ],
        "filler": ["εεε", "λοιπόν", "ας πούμε", "εμ...", "χμμ"],
    },
    "de": {
        "opening": [
            "Guten Morgen, lassen Sie uns über die Klimapolitik sprechen.",
            "Also, was sind Ihre Gedanken zur Energiewende?",
        ],
        "statement": [
            "Ich glaube, wir müssen die Emissionen sofort senken.",
            "Deutschland setzt auf Wind- und Solarenergie.",
            "Wir brauchen einen fairen Übergang für die Industrie.",
            "Das ist zu teuer und nicht umsetzbar.",
            "Vielleicht sollten wir die Kernenergie nicht ausschließen.",
        ],
        "question": [
            "Wie finanzieren wir das?",
            "Welche Auswirkungen hat das auf die Arbeitsplätze?",
            "Haben Sie Beweise dafür?",
        ],
        "agreement": [
            "Ich stimme vollkommen zu.",
            "Sie haben recht.",
            "Genau, das meine ich auch.",
        ],
        "disagreement": [
            "Da bin ich anderer Meinung.",
            "Das sehe ich anders.",
            "Das ist doch unrealistisch.",
        ],
        "backchannel": [
            "Ach so.",
            "Ja, genau.",
            "Interessant...",
        ],
        "filler": ["äh", "also", "quasi", "hmm", "naja"],
    },
    "fr": {
        "opening": [
            "Bonjour à tous, discutons du changement climatique.",
            "Alors, quelles sont vos positions sur le pacte vert?",
        ],
        "statement": [
            "Je pense qu'il faut réduire les émissions immédiatement.",
            "La France mise sur le nucléaire décarboné.",
            "Nous devons protéger les plus vulnérables.",
            "Je ne suis pas d'accord avec cette méthode.",
            "Et si on investissait dans les transports en commun?",
        ],
        "question": [
            "Comment financer cela?",
            "Quel impact sur l'emploi?",
            "Avez-vous des preuves scientifiques?",
        ],
        "agreement": [
            "Tout à fait d'accord.",
            "Vous avez raison.",
            "Exactement, c'est ce que je disais.",
        ],
        "disagreement": [
            "Je ne suis pas du tout d'accord.",
            "C'est impossible.",
            "Je vois les choses autrement.",
        ],
        "backchannel": [
            "D'accord.",
            "Oui, oui.",
            "Intéressant...",
        ],
        "filler": ["euh", "donc", "enfin", "bah", "hein"],
    },
    "en": {
        "opening": [
            "Good morning everyone, let's discuss climate change.",
            "So, what are your views on the Green Deal?",
        ],
        "statement": [
            "I believe we must reduce emissions now.",
            "The UK is investing heavily in offshore wind.",
            "We need a global approach, not just European.",
            "I disagree with that approach entirely.",
            "Perhaps we could consider carbon capture technology.",
        ],
        "question": [
            "How do we finance this?",
            "What about developing countries?",
            "Do we have enough data to support this?",
        ],
        "agreement": [
            "I completely agree.",
            "You're right.",
            "Exactly my point.",
        ],
        "disagreement": [
            "I strongly disagree.",
            "That doesn't make sense.",
            "This is simply not feasible.",
        ],
        "backchannel": [
            "Right.",
            "Yeah.",
            "Interesting...",
        ],
        "filler": ["um", "uh", "like", "you know", "I mean"],
    },
    "es": {
        "opening": [
            "Buenos días a todos, hablemos del cambio climático.",
            "Entonces, ¿qué piensan del Pacto Verde?",
        ],
        "statement": [
            "Creo que debemos reducir las emisiones ya.",
            "España apuesta por la energía solar.",
            "Hay que apoyar a las regiones mineras.",
            "No estoy de acuerdo con esa política.",
            "Quizás deberíamos fomentar el transporte público.",
        ],
        "question": [
            "¿Cómo financiamos esto?",
            "¿Qué impacto tendrá en el empleo?",
            "¿Hay datos que lo respalden?",
        ],
        "agreement": [
            "Totalmente de acuerdo.",
            "Tiene razón.",
            "Exactamente, eso digo yo.",
        ],
        "disagreement": [
            "No estoy de acuerdo en absoluto.",
            "Eso no es posible.",
            "Lo veo de otra manera.",
        ],
        "backchannel": [
            "Vale.",
            "Sí, sí.",
            "Interesante...",
        ],
        "filler": ["eh", "pues", "o sea", "bueno", "mmm"],
    },
}


def get_phrase(speaker: dict[str, str], category: str) -> str:
    return random.choice(PHRASES[speaker["lang"]][category])


def add_filler(text: str, lang: str) -> str:
    if random.random() >= 0.3:
        return text

    filler = random.choice(PHRASES[lang]["filler"])
    if random.random() < 0.5:
        return f"{filler}, {text}"

    words = text.split()
    if len(words) > 2:
        position = random.randint(1, len(words) - 1)
        words.insert(position, filler)
        return " ".join(words)
    return text


def generate_segments() -> list[dict[str, str | float]]:
    random.seed(42)
    segments: list[dict[str, str | float]] = []
    current_time = 0.0
    previous_speaker = None
    topic_phase = 0

    while current_time < DURATION_SECONDS:
        possible = [speaker for speaker in SPEAKERS if speaker["name"] != previous_speaker]
        speaker = random.choice(possible or SPEAKERS)
        lang = speaker["lang"]

        category = "statement"
        roll = random.random()
        if roll < 0.1 and previous_speaker:
            category = "backchannel"
            phrase = get_phrase(speaker, "backchannel")
            duration = len(phrase.split()) * 0.2 + random.uniform(0.5, 1.5)
        elif roll < 0.3:
            category = "question"
            phrase = get_phrase(speaker, "question")
            duration = len(phrase.split()) * 0.3 + random.uniform(1.5, 3.0)
        elif roll < 0.5 and previous_speaker:
            category = "agreement" if random.random() < 0.6 else "disagreement"
            phrase = get_phrase(speaker, category)
            duration = len(phrase.split()) * 0.3 + random.uniform(1.0, 2.5)
        else:
            phrase = get_phrase(speaker, "statement")
            duration = len(phrase.split()) * 0.3 + random.uniform(2.0, 5.0)

        if category != "backchannel":
            phrase = add_filler(phrase, lang)

        gap = random.uniform(0.2, 1.5)
        if previous_speaker and random.random() < 0.15:
            overlap_amount = min(duration * 0.3, 2.0)
            start = round(max(current_time - overlap_amount, 0.0), 1)
            if segments and float(segments[-1]["end_time"]) > start:
                segments[-1]["end_time"] = round(start - 0.1, 1)
        else:
            start = round(current_time + gap, 1)

        end = round(start + duration, 1)
        if start >= DURATION_SECONDS:
            break
        if end > DURATION_SECONDS:
            end = float(DURATION_SECONDS)

        segments.append(
            {
                "speaker": speaker["name"],
                "start_time": start,
                "end_time": end,
                "text": phrase,
            }
        )

        current_time = end
        previous_speaker = speaker["name"]

        if current_time > (topic_phase + 1) * 400:
            topic_phase += 1

    return segments


def write_csv(segments: list[dict[str, str | float]], output_file: str) -> None:
    with open(output_file, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["speaker", "start_time", "end_time", "text"])
        writer.writeheader()
        writer.writerows(segments)


def main() -> int:
    segments = generate_segments()
    write_csv(segments, OUTPUT_FILE)

    print(f"Created '{OUTPUT_FILE}'")
    print(f"Duration: {segments[-1]['end_time']:.1f} seconds (~{float(segments[-1]['end_time']) / 60:.1f} minutes)")
    print(f"Segments: {len(segments)}")
    print(f"Speakers: {', '.join(speaker['name'] for speaker in SPEAKERS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
