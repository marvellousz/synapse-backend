"""Dynamic categorization of content using Google Gemini."""

import logging
from typing import Optional

from app.config import EXTRACTION_SUMMARY_MAX_CHARS
from app.services.extraction.gemini_client import GEMINI_MODEL, get_client

logger = logging.getLogger(__name__)

# A broad, generic set of categories intended to cover "all categories of this world"
# This acts as a hint for the LLM to choose from or it can suggest a very close one.
GENERIC_CATEGORIES = [
    "Personal", "Work", "Education", "Technology", "Finance", 
    "Health", "Entertainment", "Science", "Legal", "Travel",
    "Home", "Family", "Art", "Music", "Social", "News",
    "Business", "Politics", "Philosophy", "History", "Nature",
    "Sports", "Food", "Fashion", "Spirituality", "Space"
]

def generate_category(extracted_text: str, title: Optional[str] = None) -> str:
    """
    Classify the content into ONE generic, high-level category.
    Returns a single string for the category.
    """
    if not extracted_text.strip():
        return "Uncategorized"
        
    client = get_client()
    if not client:
        return "Uncategorized"
        
    text = extracted_text[:EXTRACTION_SUMMARY_MAX_CHARS]
    if len(extracted_text) > EXTRACTION_SUMMARY_MAX_CHARS:
        text += "\n\n[Truncated...]"
        
    categories_str = ", ".join(GENERIC_CATEGORIES)
    
    prompt = (
        f"Categorize the following content into exactly ONE short, generic, high-level category. "
        f"Prefer one of these if they fit: {categories_str}. "
        "The category should be a single word or a short phrase (max 2 words). "
        "Only output the category name, nothing else.\n\n"
    )
    if title:
        prompt += f"Title: {title}\n\n"
    prompt += "Content:\n" + text
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        if response and getattr(response, "text", None):
            category = response.text.strip().title()
            # Basic validation
            if len(category) > 30:
                category = category[:27] + "..."
            return category
    except Exception as e:
        logger.warning("Gemini categorization failed: %s", e)
        
    return "Miscellaneous"
