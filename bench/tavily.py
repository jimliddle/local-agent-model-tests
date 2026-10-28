"""Optional public-document lookup through Tavily's HTTP API."""
import json
import os
import urllib.error
import urllib.request


def call(name, arguments):
    key = os.environ.get('TAVILY_API_KEY')
    if not key:
        return {'error': 'TAVILY_API_KEY is not set'}
    endpoint = {'tavily_search': 'search', 'tavily_extract': 'extract'}[name]
    request = urllib.request.Request(
        'https://api.tavily.com/' + endpoint,
        data=json.dumps(arguments).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
    try:
        with urllib.request.urlopen(request, timeout=55) as response:
            value = json.load(response)
    except urllib.error.HTTPError as error:
        return {'error': 'Tavily HTTP error', 'status': error.code}
    except (urllib.error.URLError, TimeoutError, ValueError):
        return {'error': 'Tavily request failed'}
    if value.get('failed_results') or value.get('error'):
        return {'error': 'Tavily returned failed results'}
    return {'content': [{'type': 'text', 'text': json.dumps(value)}]}
