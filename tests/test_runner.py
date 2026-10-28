import argparse
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

from agent import parse_json
from control import score
from run import local_url, profile

ROOT = Path(__file__).resolve().parents[1]
SOLUTIONS = {
    'ranges': 'def ranges(values):\n    result = []\n    for x in sorted(set(values)):\n        if result and x == result[-1][1] + 1:\n            result[-1][1] = x\n        else:\n            result.append([x, x])\n    return result\n',
    'chunks': 'def chunks(items, size):\n    if size <= 0:\n        raise ValueError()\n    return [items[i:i+size] for i in range(0, len(items), size)]\n',
    'duration': 'def duration(text):\n    parts = text.split(":")\n    if len(parts) != 3 or any(len(p) != 2 or not p.isascii() or not p.isdigit() for p in parts):\n        raise ValueError()\n    h, m, s = map(int, parts)\n    if m > 59 or s > 59:\n        raise ValueError()\n    return h * 3600 + m * 60 + s\n',
}


def tool_call(name, args):
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': 'test-call', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}


def scripted_reply(body):
    messages = body['messages']
    def content(message):
        value = message['content']
        return value if isinstance(value, str) else ''.join(b.get('text', '') for b in value)
    users = [content(m) for m in messages if m['role'] == 'user']
    if users[-1] == 'Return OK only.':
        return {'role': 'assistant', 'content': 'OK'}
    prompt = users[-1]
    plain = None
    if prompt.startswith('Return only JSON with name='):
        plain = json.dumps({'name': 'Local trial', 'status': 'ready', 'context': 65536})
    elif prompt.startswith('Answer from these passages only.'):
        plain = json.dumps({'current_fee': 19, 'source': 'current-policy section 7', 'founder': None})
    elif prompt.startswith('Return only JSON mapping ORION'):
        plain = json.dumps({'ORION': 'K7-193', 'LYRA': 'M2-847', 'VEGA': 'P9-416'})
    elif prompt.startswith('Redraft naturally'):
        plain = 'We tried local OCR on an 18-page PDF on Tuesday. Two pages needed manual correction. The files stayed on the Mac. We have not tested handwriting. I expected it to take longer.'
    if plain is not None:
        return {'role': 'assistant', 'content': plain}
    receipts = [json.loads(content(m)) for m in messages if m['role'] == 'tool']
    if prompt.startswith('Use tavily_search'):
        if receipts:
            return {'role': 'assistant', 'content': 'Evidence unavailable.'}
        return tool_call('tavily_search', {'query': 'Gemma E4B context window'})
    if prompt.startswith('Read missing.txt.'):
        if not receipts:
            return tool_call('read_file', {'path': 'missing.txt'})
        if receipts[-1].get('error'):
            return tool_call('read_file', {'path': 'index.json'})
        if receipts[-1].get('text', '').startswith('{'):
            return tool_call('read_file', {'path': 'chapter.txt'})
        if receipts[-1].get('text'):
            return tool_call('write_file', {'path': 'result.json', 'content': json.dumps(
                {'arrival': '17 April', 'key_colour': 'teal', 'fare': 37, 'architect': None})})
        return {'role': 'assistant', 'content': 'Written.'}
    if users[0].startswith('Implement '):
        task = next(t for t in SOLUTIONS if users[0].startswith('Implement '+t+'('))
        receipts = [json.loads(content(m)) for m in messages if m['role'] == 'tool']
        if not receipts:
            return tool_call('write_source', {'source': SOLUTIONS[task]})
        last = receipts[-1]
        if last.get('written'):
            return tool_call('run_check', {'check': 'syntax'})
        if last.get('simulated'):
            return tool_call('run_check', {'check': 'unit'})
        if last.get('check') in ('syntax', 'unit'):
            return tool_call('run_check', {'check': {'syntax': 'unit', 'unit': 'integration'}[last['check']]})
        return {'role': 'assistant', 'content': 'All required checks passed.'}
    # Exercise both phases of the evidence workflow, including the fetch retry.
    revision = users[-1].startswith('Revision:')
    after_user = messages[max(i for i, m in enumerate(messages) if m['role'] == 'user')+1:]
    receipts = [json.loads(m['content']) for m in after_user if m['role'] == 'tool']
    if receipts and receipts[-1].get('saved'):
        return {'role': 'assistant', 'content': 'Decision saved.'}
    if not revision:
        have = {r.get('id') for r in receipts if 'text' in r}
        for doc in ('requirements', 'atlas', 'birch-old', 'birch-current', 'cedar'):
            if doc not in have:
                return tool_call('fetch_document', {'id': doc})
    decision = {'version': 2 if revision else 1, 'choice': None if revision else 'Birch',
                'budget': 6 if revision else 9, 'handwriting_accuracy': None,
                'sources': ['requirements', 'atlas', 'birch-current', 'cedar'],
                'reason': 'Atlas fails latency; Cedar uploads files; Birch meets the first budget but not the second.'}
    return tool_call('save_decision', {'json': json.dumps(decision)})


@contextmanager
def fake_server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            message = scripted_reply(body)
            finish = 'tool_calls' if message.get('tool_calls') else 'stop'
            envelope = {'id': 'test-response', 'created': 0, 'model': 'test-model'}
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if body.get('stream') else 'application/json')
            self.end_headers()
            if body.get('stream'):
                if message.get('tool_calls'):
                    for i, call in enumerate(message['tool_calls']):
                        call['index'] = i
                chunks = [dict(envelope, object='chat.completion.chunk', choices=[{'index': 0, 'delta': message, 'finish_reason': None}]),
                          dict(envelope, object='chat.completion.chunk', choices=[{'index': 0, 'delta': {}, 'finish_reason': finish}],
                               usage={'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120})]
                self.wfile.write((''.join('data: '+json.dumps(c)+'\n\n' for c in chunks)+'data: [DONE]\n\n').encode())
            else:
                self.wfile.write(json.dumps(dict(envelope, object='chat.completion',
                    choices=[{'index': 0, 'message': message, 'finish_reason': finish}],
                    usage={'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120})).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:'+str(server.server_port)+'/v1'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class RunnerTests(unittest.TestCase):
    def test_json_contract(self):
        self.assertEqual(parse_json('{"a": 1}'), {'a': 1})
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {'a': 1})
        for text in ('```', 'prefix {"a":1}', '```json\n{"a":1}\n```\nextra'):
            self.assertIsNone(parse_json(text))

    def test_endpoint_is_local(self):
        self.assertEqual(local_url('http://127.0.0.1:11434/v1/'), 'http://127.0.0.1:11434/v1')
        for url in ('https://example.com/v1', 'http://127.0.0.1.evil.test', 'http://user:pass@localhost/v1', 'http://localhost/v1?key=x'):
            with self.assertRaises(argparse.ArgumentTypeError):
                local_url(url)

    def test_profile_uses_environment_key(self):
        with tempfile.TemporaryDirectory() as temp:
            args = argparse.Namespace(template='nanbeige', model='example', base_url='http://localhost:1234/v1')
            path = Path(temp)/'profile'
            profile(path, args)
            provider = json.loads((path/'models.json').read_text())['providers']['trial']
            self.assertEqual(provider['apiKey'], '$BENCH_MODEL_KEY')
            self.assertFalse(provider['compat']['supportsReasoningEffort'])

    def cli(self, suite):
        with fake_server() as base, tempfile.TemporaryDirectory() as temp:
            out = Path(temp)/'run'
            result = subprocess.run([sys.executable, '-B', str(ROOT/'bench/run.py'), '--model', 'test-model',
                '--base-url', base, '--suite', suite, '--repeat', '1', '--out', str(out)],
                cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            report = json.loads((out/'results.json').read_text())
            self.assertTrue(all(r['passed'] for r in report['results']))
            return report

    def test_workflow_over_http(self):
        result = self.cli('workflow')['results'][0]
        self.assertEqual(result['birch_fetch_attempts'], 2)
        self.assertIsNone(result['decisions'][-1]['value']['choice'])

    def test_probes_over_http(self):
        report = self.cli('probes')
        self.assertEqual(len(report['results']), 6)
        self.assertTrue(report['outage_audit']['passed'])

    @unittest.skipUnless(sys.platform == 'darwin' and shutil.which('pi'), 'Requires macOS and Pi')
    def test_pi_over_http(self):
        self.assertEqual(len(self.cli('coding')['results']), 3)

    @unittest.skipUnless(sys.platform == 'darwin', 'Recorded code replay uses macOS sandbox-exec')
    def test_recorded_code_replay(self):
        evidence = json.loads((ROOT/'results/repair-evidence.json').read_text())
        study = json.loads((ROOT/'results/study.json').read_text())
        expected = {(run['id'], r['name']): r['heldout'] for run in study['runs']
                    for r in run['results'] if 'heldout' in r}
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            for record in evidence:
                with self.subTest(run=record['run'], case=record['case']):
                    source = record['final_source'].encode()
                    self.assertEqual(hashlib.sha256(source).hexdigest(), record['final_source_sha256'])
                    (work/'solution.py').write_bytes(source)
                    actual = score(work, record['case'].split('-')[1], 'heldout')
                    original = expected[record['run'], record['case']]
                    self.assertEqual(actual.get('passed'), original.get('passed'), actual)
                    self.assertEqual(actual['ok'], original['ok'])


if __name__ == '__main__':
    unittest.main()
