import requests

url = "http://localhost:8000/api/auth/oauth/exchange"
data = {
    "provider": "google",
    "code": "dummy_code",
    "redirect_uri": "http://localhost:3000/auth/callback/google"
}
resp = requests.post(url, json=data)
print(resp.status_code, resp.text)