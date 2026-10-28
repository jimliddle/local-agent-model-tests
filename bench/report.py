"""Print the recorded first-repetition coding and retrieval comparison."""
import json
from pathlib import Path


def rows():
    study = json.loads((Path(__file__).resolve().parents[1]/'results/study.json').read_text())
    for run in study['runs']:
        if run['excluded_from_comparison']:
            continue
        repairs = [r for r in run['results'] if r['name'].startswith('pi-') and r['name'].endswith('-0')]
        retrieval = next((r for r in run['results'] if r['name'] == 'long-retrieval'), None)
        if not repairs and not retrieval:
            continue
        yield run['id'], repairs, retrieval


if __name__ == '__main__':
    print('run | first-repetition repairs | repair seconds | retrieval seconds')
    for name, repairs, retrieval in rows():
        score = f'{sum(r["passed"] for r in repairs)}/{len(repairs)}' if repairs else 'not run'
        elapsed = f'{sum(r["seconds"] for r in repairs):.1f}' if repairs else '-'
        long_time = f'{retrieval["seconds"]:.1f}' if retrieval else '-'
        print(f'{name} | {score} | {elapsed} | {long_time}')
