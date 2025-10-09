# app/chat_utils.py
from typing import List, Dict, Any, Tuple

def build_context_from_results(results: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Возвращает (context, scarcity_note).
    context — текст с релевантными сниппетами или сообщение об отсутствии.
    scarcity_note — дополнительная подсказка модели, если сниппетов нет.
    """
    if results:
        lines = ["Relevant TechNova company information:"]
        for item in results:
            category = item.get("Category", "N/A")
            q = item.get("Question", "N/A")
            a = item.get("Answer", "N/A")
            lines.append(f"Category: {category}\nQ: {q}\nA: {a}\n")
        return "\n".join(lines), ""
    else:
        context = "No directly relevant TechNova snippets were found in the local FAQ."
        scarcity_note = (
            "\n\nNote: No matching company FAQ snippets were found. "
            "If you must rely on general knowledge, say so explicitly."
        )
        return context, scarcity_note