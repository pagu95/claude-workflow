"""Measure what a Claude Code session loads before any work, and what of it is ever used.

  python -I audit.py startup [repo_path] [--n 5]   first-call size + attachment split, newest N sessions
  python -I audit.py usage   [repo_path]           real tool_use calls per skill/agent/MCP family:
                                                   in this repo (worktrees included) vs everywhere else

Reads ~/.claude/projects/*/*.jsonl. Prints aggregates only, never message text.
"""
import argparse, collections, glob, json, os, re, sys

ROOT = os.path.join(os.path.expanduser('~'), '.claude', 'projects')
WORKSPACE = re.compile(r'^(?:[A-Za-z]*Projects|projects)-')


def short_project(slug, home=None):
    """Display name for a transcript folder: drop the home path and one *Projects workspace folder."""
    home = re.sub(r'[^A-Za-z0-9]', '-', os.path.expanduser('~') if home is None else home)
    if not slug.startswith(home + '-'):
        return slug
    rest = slug[len(home) + 1:]
    return WORKSPACE.sub('', rest, count=1) or rest


def repo_key(path):
    # Claude Code names a project folder after its path with every non-alphanumeric char as '-'
    return re.sub(r'[^A-Za-z0-9]', '-', os.path.abspath(path))


def records(f):
    with open(f, encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def startup(repo, n):
    d = os.path.join(ROOT, repo_key(repo))
    # worktree sessions get their own folder: <repo>--claude-worktrees-<name>
    files = glob.glob(os.path.join(d, '*.jsonl')) + glob.glob(os.path.join(d + '--*', '*.jsonl'))
    files = sorted(files, key=os.path.getmtime, reverse=True)[:n]
    if not files:
        sys.exit(f'no transcripts in {d} or its worktrees')
    for f in files:
        sizes = collections.Counter(); total = None; ts = ''
        for r in records(f):
            ts = ts or r.get('timestamp', '')[:10]
            if r.get('type') == 'attachment':
                a = r.get('attachment') or {}
                sizes[a.get('type', '?')] += len(json.dumps(a)) // 4  # ~4 chars per token
            u = (r.get('message') or {}).get('usage') if r.get('type') == 'assistant' else None
            if u:
                total = u.get('input_tokens', 0) + u.get('cache_creation_input_tokens', 0) + u.get('cache_read_input_tokens', 0)
                break
        if total is None:
            continue
        att = sum(sizes.values())
        split = ', '.join(f'{k} {v / 1000:.1f}k' for k, v in sizes.most_common(8))
        print(f'{os.path.basename(f)[:8]} {ts} start={total / 1000:.1f}k  attachments={att / 1000:.1f}k  floor={(total - att) / 1000:.1f}k  [{split}]')


def family(name, inp):
    if name == 'Skill':
        s = str(inp.get('skill', ''))
        return 'skill:' + (s.split(':')[0] + ':*' if ':' in s else s)
    if name in ('Agent', 'Task'):
        t = str(inp.get('subagent_type') or 'general-purpose')
        return 'agent:' + (t.split(':')[0] + ':*' if ':' in t else t)
    if name.startswith('mcp__'):
        return 'mcp:' + name.split('__')[1]
    return None


def usage(repo):
    key = repo_key(repo)
    here = collections.Counter(); other = collections.defaultdict(collections.Counter); last = {}
    for f in glob.glob(os.path.join(ROOT, '*', '*.jsonl')):
        proj = os.path.basename(os.path.dirname(f))
        mine = proj == key or proj.startswith(key + '--')  # worktrees live under <repo>/.claude/worktrees
        for r in records(f):
            for b in (r.get('message') or {}).get('content') or [] if r.get('type') == 'assistant' else []:
                if isinstance(b, dict) and b.get('type') == 'tool_use':
                    k = family(b.get('name', ''), b.get('input') or {})
                    if not k:
                        continue
                    if mine:
                        here[k] += 1
                    else:
                        other[k][short_project(proj)[:30]] += 1
                    last[k] = max(last.get(k, ''), r.get('timestamp', '')[:10])
    print(f"{'family':45} {'here':>5} {'else':>5}  last        where else")
    for k in sorted(last, key=lambda k: -(here[k] * 1000 + sum(other[k].values()))):
        top = ', '.join(f'{p} {c}' for p, c in other[k].most_common(3))
        print(f'{k[:45]:45} {here[k]:5} {sum(other[k].values()):5}  {last[k]}  {top}')
    print('\nAnything that loads at startup but is missing here was never called in any session.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=('startup', 'usage'))
    p.add_argument('repo', nargs='?', default=os.getcwd())
    p.add_argument('--n', type=int, default=5)
    args = p.parse_args()
    if args.n < 1:
        p.error('--n must be at least 1')
    startup(args.repo, args.n) if args.mode == 'startup' else usage(args.repo)
