import json
import os
import urllib.error
import urllib.parse
import urllib.request


API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def main():
    if not API_KEY:
        raise SystemExit("ERROR: GEMINI_API_KEY is not set")

    model = MODEL.removeprefix("models/")
    url = (
        f"{API_BASE}/models/{urllib.parse.quote(model)}:generateContent"
        f"?key={urllib.parse.quote(API_KEY)}"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Ответь одним словом: работает?"}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 32,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
            parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts).strip()
            print("OK: Gemini responded")
            print(f"MODEL: {MODEL}")
            print(f"ANSWER: {text or '<empty>'}")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP_ERROR: {error.code}")
        print(body)
        raise SystemExit(1)
    except urllib.error.URLError as error:
        print(f"NETWORK_ERROR: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
