"""What each traced step records on the durable trace: plain dicts only.

Each entry is `(input_fn, output_fn)` for `TraceSession.instrument(..., payloads=...)`.
`input_fn` receives the wrapped call's arguments and `output_fn` its result.
Nothing here runs on the local (metadata-only) route.
"""

EXCERPT_CHARS = 600


def _document(document):
    return {
        "document_id": document.document_id,
        "title": document.title,
        "version": document.version,
        "status": document.status,
        "excerpt": document.content[:EXCERPT_CHARS],
    }


def _search_input(query, top_k=3, *, attempt_number=1):
    return {"query": query, "top_k": top_k, "attempt_number": attempt_number}


def _search_output(results):
    return {"documents": [{**_document(item.document), "score": item.score} for item in results]}


def _request_input(operation, output_type, instruction, context, validate=None):
    # The system text is fixed apart from these parts; the schema is not recorded.
    return {"stage": operation, "instruction": instruction, "context": context}


def _dump(value):
    return value.model_dump()


RETRIEVAL_PAYLOADS = {"search": (_search_input, _search_output)}

CONTROLLED_MODEL_PAYLOADS = {
    "classify_question": (lambda question: {"question": question}, _dump),
    "formulate_query": (
        lambda question, classification: {
            "question": question,
            "classification": classification.model_dump(),
        },
        _dump,
    ),
    "assess_evidence": (
        lambda question, classification, documents: {
            "question": question,
            "required_facts": list(classification.required_facts),
            "document_ids": [document.document_id for document in documents],
        },
        _dump,
    ),
    "refine_query": (
        lambda question, classification, assessment, previous_query: {
            "question": question,
            "missing_facts": list(assessment.missing_facts),
            "previous_query": previous_query.query,
        },
        _dump,
    ),
    "generate_answer": (
        lambda question, classification, documents, assessment: {
            "question": question,
            "required_facts": list(classification.required_facts),
            "documents": [_document(document) for document in documents],
            "assessment": assessment.model_dump(),
        },
        _dump,
    ),
}

LIVE_MODEL_PAYLOADS = {"_request": (_request_input, _dump)}
