import google.generativeai as genai
import os
from dotenv import load_dotenv


load_dotenv() # Load environment variables from .env


genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


print("Finding available models for your API key...")

for model in genai.list_models():
  if 'generateContent' in model.supported_generation_methods:
    print(f"- {model.name}")

print("\nFinished.")