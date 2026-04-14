import re
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
    "PAN": "[PAN]",
    "AADHAAR": "[AADHAAR]",
    "PASSPORT": "[PASSPORT]",
}

CANONICAL_ENTITY_TYPES = {
    "PERSON": "NAME",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "PAN": "PAN",
    "AADHAAR": "AADHAAR",
    "PASSPORT": "PASSPORT",
}

SUPPORTED_ANALYZE_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "PAN",
    "AADHAAR",
    "PASSPORT",
]

def _build_nlp_engine():
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    }
    provider = NlpEngineProvider(nlp_configuration=configuration)
    return provider.create_engine()


def _register_indian_recognizers(analyzer_engine: AnalyzerEngine) -> None:
    # Supports lowercase names in conversational text (e.g., "my name is rahul")
    # while avoiding false positives on general text like locations.
    person_context_recognizer = PatternRecognizer(
        supported_entity="PERSON",
        name="person_context_recognizer",
        patterns=[
            Pattern(
                name="person_after_my_name_is",
                regex=r"(?i)(?<=\bmy name is\s)[^\W\d_][^\W\d_'’.`-]{1,30}(?:\s[^\W\d_][^\W\d_'’.`-]{1,30})?",
                score=0.92,
            ),
            Pattern(
                name="person_after_i_am",
                regex=r"(?i)(?<=\bi am\s)[^\W\d_][^\W\d_'’.`-]{1,30}(?:\s[^\W\d_][^\W\d_'’.`-]{1,30})?",
                score=0.9,
            ),
            Pattern(
                name="person_after_im",
                regex=r"(?i)(?<=\bi(?:'|’)m\s)[^\W\d_][^\W\d_'’.`-]{1,30}(?:\s[^\W\d_][^\W\d_'’.`-]{1,30})?",
                score=0.9,
            ),
            Pattern(
                name="person_after_this_is",
                regex=r"(?i)(?<=\bthis is\s)[^\W\d_][^\W\d_'’.`-]{1,30}(?:\s[^\W\d_][^\W\d_'’.`-]{1,30})?",
                score=0.88,
            ),
        ],
    )

    pan_recognizer = PatternRecognizer(
        supported_entity="PAN",
        name="india_pan_recognizer",
        patterns=[
            Pattern(
                name="india_pan_pattern",
                regex=r"\b[A-Z]{5}[0-9]{4}[A-Z](?=\b|[0-9]\.)",
                score=0.85,
            )
        ],
    )

    aadhaar_recognizer = PatternRecognizer(
        supported_entity="AADHAAR",
        name="india_aadhaar_recognizer",
        patterns=[
            Pattern(
                name="india_aadhaar_pattern",
                regex=r"\b\d{4}\s\d{4}\s\d{4}(?=\b|[0-9]\.)",
                score=0.85,
            )
        ],
    )

    passport_recognizer = PatternRecognizer(
        supported_entity="PASSPORT",
        name="india_passport_recognizer",
        patterns=[
            Pattern(
                name="india_passport_pattern",
                regex=r"\b[A-Z][0-9]{7}\b",
                score=0.8,
            )
        ],
    )

    # Handles local 10-digit mobile numbers and +91-prefixed numbers.
    phone_recognizer = PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        name="india_phone_recognizer",
        patterns=[
            Pattern(
                name="india_phone_pattern",
                regex=r"(?:(?<=\D)|^)(?:\+91[\s-]?)?[6-9]\d{9}(?=\D|$)",
                score=0.85,
            )
        ],
    )

    analyzer_engine.registry.add_recognizer(pan_recognizer)
    analyzer_engine.registry.add_recognizer(aadhaar_recognizer)
    analyzer_engine.registry.add_recognizer(passport_recognizer)
    analyzer_engine.registry.add_recognizer(phone_recognizer)
    analyzer_engine.registry.add_recognizer(person_context_recognizer)


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


def _normalize_entity_type(entity_type: str) -> str:
    return CANONICAL_ENTITY_TYPES.get(entity_type, entity_type)


def _deduplicate_results(results):
    best_by_key = {}
    for result in results:
        key = (result.start, result.end, result.entity_type)
        existing = best_by_key.get(key)
        if existing is None or result.score > existing.score:
            best_by_key[key] = result

    deduped = list(best_by_key.values())
    deduped.sort(key=lambda item: item.start)
    return deduped


def _resolve_overlaps(results):
    if not results:
        return []

    priority = {"AADHAAR": 3, "PAN": 3, "PASSPORT": 3, "PERSON": 2, "EMAIL_ADDRESS": 2, "PHONE_NUMBER": 1}

    sorted_results = sorted(
        results,
        key=lambda item: (
            item.start,
            -(item.end - item.start),  # prefer longer full-entity spans
            -priority.get(item.entity_type, 0),
            -item.score,
        ),
    )

    kept = []
    for candidate in sorted_results:
        overlaps = False
        for existing in kept:
            if candidate.start < existing.end and existing.start < candidate.end:
                overlaps = True
                break
        if not overlaps:
            kept.append(candidate)

    kept.sort(key=lambda item: item.start)
    return kept


def _build_entities_payload(text: str, results):
    entities = []
    for item in results:
        entities.append(
            {
                "type": _normalize_entity_type(item.entity_type),
                "value": text[item.start:item.end],
                "start": item.start,
                "end": item.end,
            }
        )
    return entities


def _analyze_internal(text: str):
    analyzer_engine, _ = get_engines()
    results = analyzer_engine.analyze(
        text=text,
        language="en",
        entities=SUPPORTED_ANALYZE_ENTITIES,
        score_threshold=0.45,
    )
    return _resolve_overlaps(_deduplicate_results(results))


def _anonymize_from_results(text: str, results) -> str:
    _, anonymizer_engine = get_engines()
    operators = {
        entity_type: OperatorConfig("replace", {"new_value": replacement})
        for entity_type, replacement in ENTITY_REPLACEMENTS.items()
    }

    anonymized = anonymizer_engine.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )
    sanitized = anonymized.text
    # Preserve readability for numbered lists after replacement.
    sanitized = re.sub(r"(\[[A-Z]+\])(?=\d+\.)", r"\1 ", sanitized)
    sanitized = re.sub(r"(?<=[a-zA-Z\]])(?=\d+\.)", " ", sanitized)
    return sanitized


def anonymize_text(text: str) -> str:
    results = _analyze_internal(text)
    return _anonymize_from_results(text, results)


def analyze_text(text: str):
    results = _analyze_internal(text)
    return _build_entities_payload(text, results)


def anonymize_with_entities(text: str):
    results = _analyze_internal(text)
    entities = _build_entities_payload(text, results)
    anonymized_text = _anonymize_from_results(text, results)
    return {
        "originalText": text,
        "sanitizedText": anonymized_text,
        "entities": entities,
    }
