from threading import Lock

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

analyzer = None
anonymizer = None
_engine_lock = Lock()

# Map Presidio entity types to placeholders. Replacement preserves sentence structure.
ENTITY_REPLACEMENTS = {
    "PERSON": "[NAME]",
    "EMAIL_ADDRESS": "[EMAIL]",
    "PHONE_NUMBER": "[PHONE]",
    "PAN_NUMBER": "[PAN]",
    "AADHAAR_NUMBER": "[AADHAAR]",
    "PASSPORT_NUMBER": "[PASSPORT]",
}


def _build_nlp_engine():
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    }
    provider = NlpEngineProvider(nlp_configuration=configuration)
    return provider.create_engine()


def _register_indian_recognizers(analyzer_engine: AnalyzerEngine) -> None:
    pan_recognizer = PatternRecognizer(
        supported_entity="PAN_NUMBER",
        name="india_pan_recognizer",
        patterns=[
            Pattern(
                name="india_pan_pattern",
                regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
                score=0.85,
            )
        ],
    )

    aadhaar_recognizer = PatternRecognizer(
        supported_entity="AADHAAR_NUMBER",
        name="india_aadhaar_recognizer",
        patterns=[
            Pattern(
                name="india_aadhaar_pattern",
                regex=r"\b\d{4}\s\d{4}\s\d{4}\b",
                score=0.85,
            )
        ],
    )

    passport_recognizer = PatternRecognizer(
        supported_entity="PASSPORT_NUMBER",
        name="india_passport_recognizer",
        patterns=[
            Pattern(
                name="india_passport_pattern",
                regex=r"\b[A-Z][0-9]{7}\b",
                score=0.8,
            )
        ],
    )

    analyzer_engine.registry.add_recognizer(pan_recognizer)
    analyzer_engine.registry.add_recognizer(aadhaar_recognizer)
    analyzer_engine.registry.add_recognizer(passport_recognizer)


def get_engines():
    global analyzer, anonymizer

    if analyzer is not None and anonymizer is not None:
        return analyzer, anonymizer

    with _engine_lock:
        if analyzer is None:
            nlp_engine = _build_nlp_engine()
            analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
            _register_indian_recognizers(analyzer)

        if anonymizer is None:
            anonymizer = AnonymizerEngine()

    return analyzer, anonymizer


def anonymize_text(text: str) -> str:
    analyzer_engine, anonymizer_engine = get_engines()
    results = analyzer_engine.analyze(text=text, language="en")

    operators = {
        entity_type: OperatorConfig("replace", {"new_value": replacement})
        for entity_type, replacement in ENTITY_REPLACEMENTS.items()
    }

    anonymized = anonymizer_engine.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )
    return anonymized.text


def analyze_text(text: str):
    analyzer_engine, _ = get_engines()
    results = analyzer_engine.analyze(text=text, language="en")

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
