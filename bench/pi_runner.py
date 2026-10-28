"""Run the original repair tasks through an isolated Pi profile."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from tasks import TASKS
from control import CHECKS, score
from evaluate import SAFE

HERE = Path(__file__).resolve().parent

def readlines(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def pi_task(out, profile, model, task, repeat, key):
    work=out/f'pi-{task}-{repeat}'
    work.mkdir()
    data=TASKS[task]
    (work/'solution.py').write_text(data['source'])
    (work/'state.json').write_text(json.dumps({'task':task,'receipts':{},'checks':[],
                                             'inject_transient':data.get('transient',False)}))
    prompt=data['spec']+'\nCurrent solution.py:\n'+data['source']+(
        '\nRepair the function and obtain passing syntax, unit and integration checks. '
        'Use available tools efficiently. Functions only; no imports or private attributes. '
        'Available builtins: '+', '.join(sorted(SAFE))+'. '
        'On failure inspect the receipt and resolve it; a simulated temporary verifier failure '
        'requires a retry, not a code change. End with a short factual result.')
    (work/'prompt.txt').write_text(prompt)
    env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR','LANG') if k in os.environ}
    env.update(PI_CODING_AGENT_DIR=str(profile),PI_OFFLINE='1',PI_TELEMETRY='0',
        PILOT_WORK=str(work),PILOT_SEED=str(4200+repeat),PILOT_PYTHON=sys.executable,
        BENCH_MODEL_KEY=key,PYTHONDONTWRITEBYTECODE='1')
    if os.environ.get('BENCH_TEMPLATE') == 'flash':
        env['BENCH_FLASH']='1'
    command=['pi','--provider','trial','--model',model,'--thinking','low','--offline',
        '--no-approve','--no-extensions','--no-skills','--no-context-files','--no-prompt-templates',
        '--no-builtin-tools','--extension',str(HERE/'extension.mjs'),'--system-prompt',
        'You repair small Python functions. Use the provided tools and verify the result. '
        'Do not claim checks passed without tool receipts.', '--no-session','--mode','json','-p',prompt]
    start=time.monotonic()
    timeout=False
    with (work/'events.jsonl').open('w') as stdout, (work/'stderr.log').open('w') as stderr:
        child=subprocess.Popen(command,cwd=work,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        try:
            child.wait(timeout=300)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            os.killpg(child.pid,signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait()
            if isinstance(error, KeyboardInterrupt):
                raise
            timeout=True
    elapsed=time.monotonic()-start
    state=json.loads((work/'state.json').read_text())
    digest=hashlib.sha256((work/'solution.py').read_bytes()).hexdigest()
    receipts=all(state['receipts'].get(c)==digest for c in CHECKS)
    heldout=score(work,task,'heldout')
    usage=readlines(work/'usage.jsonl')
    requests=readlines(work/'requests.jsonl')
    totals={k:sum(u.get('usage',{}).get(k,0) for u in usage)
            for k in ('input','output','cacheRead','cacheWrite','totalTokens')}
    result={'name':f'pi-{task}-{repeat}','passed':bool(receipts and heldout['ok'] and not timeout and child.returncode==0),
        'seconds':elapsed,'timeout':timeout,'exit':child.returncode,'heldout':heldout,'fresh_receipts':receipts,
        'calls':len(requests),'tokens':totals,'usage_complete':len(requests)==len(usage) and bool(usage),
        'tools':len(readlines(work/'tools.jsonl')),'errors':[u for u in usage if u.get('error')]}
    (work/'result.json').write_text(json.dumps(result,indent=2))
    return result
