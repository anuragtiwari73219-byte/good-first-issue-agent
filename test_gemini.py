import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY .env file mein nahi mili.")
    raise SystemExit(1)

try:
    client = genai.Client(api_key=api_key)
    print("Testing Gemini API without tools...")
    response = client.models.generate_content(
        model="gemma-4-26b-a4b-it",
        contents="Reply with exactly: Gemini API works."
    )
    print("\nSUCCESS: Gemini API is working.")
    print("Response:", response.text)
except Exception as error:
    print("\nFAILED: Gemini API test unsuccessful.")
    print("Error type:", type(error).__name__)
    print("Error details:", error)
