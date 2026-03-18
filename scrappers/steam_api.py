import requests
import json

url = 'https://csgoskins.gg/api/v1/prices'
payload = {
    "range": "30d",
    "aggregator": "max"
}
headers = {
  'Authorization': 'Bearer {YOUR_API_KEY}',
  'Content-Type': 'application/json'
}

response = requests.request('GET', url, headers=headers, json=payload)
response.json()
print(response)