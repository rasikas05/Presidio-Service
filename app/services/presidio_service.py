from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = None
anonymizer = None

def get_engines():
    global analyzer, anonymizer

    if analyzer is None:
        analyzer = AnalyzerEngine()

    if anonymizer is None:
        anonymizer = AnonymizerEngine()

    return analyzer, anonymizer

def anonymize_text(text: str) -> str:
    analyzer, anonymizer = get_engines()

    results = analyzer.analyze(text=text, language="en")

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results
    )

    return anonymized.text

def analyze_text(text: str):
    analyzer, _ = get_engines()
    results = analyzer.analyze(text=text, language="en")

    entities = []
    for item in results:
        entities.append(
            {
                "entity_type": item.entity_type,
                "start": item.start,
                "end": item.end,
                "score": item.score,
                "text": text[item.start:item.end],
            }
        )

    return entities
