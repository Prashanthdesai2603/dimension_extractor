import os
import json
import logging
from google import genai

logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def parse_dimension(text: str) -> dict:
    """
    Uses Gemini to parse raw OCR text into structured dimension data.
    Input: "50 +/- 0.1"
    Output: {"dim": 50.0, "utol": 0.1, "ltol": -0.1}
    """
    if not GEMINI_API_KEY:
        logger.warning("[Gemini Parser] GEMINI_API_KEY not found. Returning empty structure.")
        return {"dim": 0, "utol": 0, "ltol": 0}

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
        Extract dimensional data from this OCR text: "{text}"
        Return ONLY a JSON object with:
        - "dim": numerical nominal value (float)
        - "utol": upper tolerance (float, default 0)
        - "ltol": lower tolerance (float, default 0, keep it negative if it's a symmetric or bottom tolerance like -0.1)
        
        If the text is just a number, utol and ltol should be 0.
        If it's "50 +/- 0.1", dim=50, utol=0.1, ltol=-0.1.
        
        JSON:
        """
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
        
        content = response.text.strip()
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:].strip()
            content = content.strip("```").strip()
            
        parsed = json.loads(content)
        logger.info(f"[Gemini Parser] Parsed '{text}' -> {parsed}")
        return parsed
        
    except Exception as e:
        logger.error(f"[Gemini Parser] Error parsing with Gemini: {e}")
        return {"dim": 0, "utol": 0, "ltol": 0}
