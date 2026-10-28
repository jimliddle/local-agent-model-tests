"""Run synthetic checks against a separately managed local model server."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.parse
import urllib.request

import agent
from probes import probes
from review import outage_audit
from tasks import TASKS
from workflow import run as workflow

HERE = Path(__file__).resolve().parent


def local_url(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1')
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise argparse.ArgumentTypeError('Use a loopback HTTP URL without credentials, query or fragment')
    return value.rstrip('/')


def profile(directory, args):
    compat = {'supportsStore': False, 'supportsDeveloperRole': False,
              'supportsReasoningEffort': args.template != 'nanbeige',
              'supportsUsageInStreaming': True, 'supportsStrictMode': False,
              'maxTokensField': 'max_tokens',
              'thinkingFormat': 'qwen-chat-template' if args.template == 'nanbeige' else 'openai'}
    model = {'id': args.model, 'name': args.model, 'reasoning': True, 'input': ['text'],
             'contextWindow': 65536, 'maxTokens': 8192,
             'cost': dict.fromkeys(('input', 'output', 'cacheRead', 'cacheWrite'), 0),
             'samplingParams': {'temperature': 0.6, 'top_p': 0.95, 'top_k': 20, 'min_p': 0},
             'thinkingLevelMap': {'off': 'none', 'minimal': None, 'low': 'low', 'medium': 'medium',
                                  'high': 'high', 'xhigh': None, 'max': None}}
    directory.mkdir()
    provider = {'baseUrl': args.base_url, 'api': 'openai-completions', 'apiKey': '$BENCH_MODEL_KEY',
                'compat': compat, 'models': [model]}
    (directory/'models.json').write_text(json.dumps({'providers': {'trial': provider}}))
    (directory/'settings.json').write_text(json.dumps({
        'retry': {'enabled': False, 'provider': {'maxRetries': 0}},
        'compaction': {'enabled': False}, 'packages': [], 'quietStartup': True,
        'enableInstallTelemetry': False}))
    (directory/'auth.json').write_text('{}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', type=local_url, default='http://127.0.0.1:11434/v1')
    parser.add_argument('--model', required=True)
    parser.add_argument('--suite', choices=('all', 'coding', 'probes', 'workflow'), default='all')
    parser.add_argument('--template', choices=('default', 'flash', 'nanbeige'), default='default')
    parser.add_argument('--repeat', type=int, choices=range(1, 11), default=2)
    parser.add_argument('--live-web', action='store_true')
    parser.add_argument('--api-key-env', default='LOCAL_MODEL_API_KEY')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.live_web and not os.environ.get('TAVILY_API_KEY'):
        parser.error('--live-web requires TAVILY_API_KEY')
    coding = args.suite in ('coding', 'all')
    if coding and (sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').exists()):
        parser.error('Coding requires macOS sandbox-exec. Probes and workflow do not execute model code.')
    if coding and not shutil.which('pi'):
        parser.error('Coding requires Pi on PATH (recorded version: 0.84.2)')
    out = (args.out or Path('outputs')/datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')).resolve()
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    key = os.environ.get(args.api_key_env, 'local')
    os.environ['BENCH_TEMPLATE'] = args.template
    report = {'runner_version': 1, 'model': args.model, 'context_assumed': 65536,
              'context_enforced_by': 'server; configure separately', 'template': args.template,
              'temperature': 0.6, 'top_p': 0.95, 'output_limit': 8192,
              'request_timeout_seconds': 600, 'repair_timeout_seconds': 300,
              'results': [], 'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in HERE.iterdir() if p.suffix in ('.py', '.mjs')}}

    def persist():
        (out/'results.json').write_text(json.dumps(report, indent=2))

    def save(value):
        report['results'].append(value)
        persist()
        print(json.dumps({k: value.get(k) for k in ('name', 'passed', 'seconds')}), flush=True)

    def complete(messages, tools=None, max_tokens=8192):
        body = {'model': args.model, 'messages': messages, 'temperature': 0.6,
                'top_p': 0.95, 'seed': 4200, 'max_tokens': max_tokens}
        if args.template == 'nanbeige':
            body['chat_template_kwargs'] = {'enable_thinking': True, 'preserve_thinking': True,
                                            'tool_call_format': 'xml'}
        else:
            body['reasoning_effort'] = 'low'
        if args.template == 'flash':
            body['chat_template_kwargs'] = {'enable_thinking': True}
        if tools:
            body['tools'] = tools
        request = urllib.request.Request(args.base_url+'/chat/completions', data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+key, 'x-api-key': key})
        started = time.monotonic()
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=600) as response:
            result = json.load(response)
        return {'seconds': time.monotonic()-started, 'response': result}

    try:
        report['warmup'] = complete([{'role': 'user', 'content': 'Return OK only.'}], max_tokens=512)
        persist()
        if coding:
            from pi_runner import pi_task
            config = out/'profile'
            profile(config, args)
            for repeat in range(args.repeat):
                for task in TASKS:
                    result = pi_task(out, config, args.model, task, repeat, key)
                    save(result)
                    if result['errors'] or result['timeout'] or result['calls'] == 0:
                        raise RuntimeError('Repair stopped; inspect artifacts before continuing with another suite')
        if args.suite in ('probes', 'all'):
            probes(out, complete, save, args.live_web)
            report['outage_audit'] = outage_audit(json.loads((out/'outage.json').read_text())['messages'])
        if args.suite in ('workflow', 'all'):
            save(workflow(complete, out, agent))
    except KeyboardInterrupt:
        report['error_type'] = 'KeyboardInterrupt'
        return 130
    except Exception as error:
        # Do not persist exception text that might contain credentials or personal paths.
        report['error_type'] = type(error).__name__
        print('Stopped:', type(error).__name__, file=sys.stderr)
        return 1
    finally:
        persist()
    print('Results:', out)
    print('Review writing meaning and live evidence separately from automatic scores.')
    return 0 if all(r['passed'] for r in report['results']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
