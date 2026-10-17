from google.genai import types
from google import genai

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="My name is Areeb",
    config=types.GenerateContentConfig(
        system_instruction="if the user enters a name, send back only the name in all caps, no other text. If the user enters anything else, send back the word IN",
        temperature=0.7,
    ),
)
print(response.text)