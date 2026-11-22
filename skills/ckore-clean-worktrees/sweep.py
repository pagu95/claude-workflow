#!/usr/bin/env python3
"""Free disk by removing leftover git worktrees in every repo under one folder.

Each worktree, leftover folder and loose file under <repo>/.claude/worktrees lands in one tier:
  auto  safe to remove without asking
  ask   the owner decides (shown in one table)
  keep  left alone: changed in the last 2 hours, or a loose file under 7 days old

Usage:
  python3 sweep.py [ROOT]                 # dry run: print the plan, remove nothing
  python3 sweep.py [ROOT] --apply         # remove the auto tier, print what needs a call
  python3 sweep.py [ROOT] --remove P...   # remove approved rows the plain way
  python3 sweep.py [ROOT] --force P...    # remove approved rows that hold uncommitted files

ROOT is the folder that holds the repos; default: the parent of the repo you are in.

It never deletes a branch, pushes or commits, never forces unless a path is named with --force,
and refuses anything changed in the last 2 hours even then.
"""
import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

RECENT_SECONDS = 2 * 3600
LOOSE_SECONDS = 7 * 24 * 3600
WORKTREES = os.path.join(".claude", "worktrees")
GIB = 2 ** 30


def run_git(cwd, *args):
    out = subprocess.run(["git", "--no-optional-locks", "-C", cwd, *args],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.returncode, out.stdout.rstrip(), out.stderr.strip()


def key(path):
    return os.path.normcase(os.path.realpath(path))


def last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1].strip() if lines else "failed"


# ---------------------------------------------------------------- inventory

def find_repos(root):
    """Main checkouts directly under root. A linked worktree has a .git file, not a folder."""
    return sorted(os.path.join(root, d) for d in os.listdir(root)
                  if os.path.isdir(os.path.join(root, d, ".git")))


def registered_worktrees(repo):
    """Linked worktrees of repo (the main checkout is skipped)."""
    code, out, _ = run_git(repo, "worktree", "list", "--porcelain")
    if code:
        return []
    found = []
    for block in out.split("\n\n"):
        wt = {"branch": None, "locked": False}
        for line in block.splitlines():
            word, _, rest = line.partition(" ")
            if word == "worktree":
                wt["path"] = os.path.normpath(rest)
            elif word == "HEAD":
                wt["head"] = rest
            elif word == "branch":
                wt["branch"] = rest.removeprefix("refs/heads/")
            elif word == "locked":
                wt["locked"] = True
        if "path" in wt:
            found.append(wt)
    return found[1:]


def gh_prs(repo):
    """{branch: [{number, state, oid}]} for every PR of the repo, or None when gh cannot say."""
    try:
        out = subprocess.run(
            ["gh", "pr", "list", "--state", "all", "--limit", "1000",
             "--json", "number,state,headRefName,headRefOid"],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        if out.returncode:
            return None
        prs = {}
        for pr in json.loads(out.stdout):
            prs.setdefault(pr["headRefName"], []).append(
                {"number": pr["number"], "state": pr["state"], "oid": pr["headRefOid"]})
        return prs
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return None


def newest_change(wt_path):
    """Latest change to the worktree's git state: a checkout, commit, stage or new top-level entry."""
    paths = [wt_path]
    code, admin, _ = run_git(wt_path, "rev-parse", "--absolute-git-dir")
    if code == 0 and admin:
        paths += [admin] + [os.path.join(admin, name) for name in ("index", "HEAD", "ORIG_HEAD", "logs/HEAD")]
    newest = 0.0
    for path in paths:
        try:
            newest = max(newest, os.path.getmtime(path))
        except OSError:
            pass
    return newest


def newest_under(path):
    """Latest mtime of path and, for a folder, of everything inside it."""
    newest = 0.0
    try:
        newest = os.lstat(path).st_mtime
    except OSError:
        return newest
    if os.path.isdir(path) and not os.path.islink(path):
        for folder, dirs, files in os.walk(path):
            for name in dirs + files:
                try:
                    newest = max(newest, os.lstat(os.path.join(folder, name)).st_mtime)
                except OSError:
                    pass
    return newest


def changed_paths(status_z):
    """File names from `git status --porcelain -z`; a rename's old name is skipped."""
    names, entries = [], iter(status_z.split("\0"))
    for entry in entries:
        if len(entry) < 4:
            continue
        names.append(entry[3:])
        if entry[0] in "RC":
            next(entries, None)
    return names


def judge_branch(repo, wt, prs):
    """(tier, why) for a clean worktree on a named branch."""
    if prs is None:
        return "ask", "PR state unknown (gh could not answer)"
    mine = prs.get(wt["branch"], [])
    for pr in mine:
        if pr["state"] == "MERGED" and pr["oid"] == wt.get("head"):
            return "auto", f"PR #{pr['number']} merged"
    for state, text in (("OPEN", "open"), ("MERGED", "merged, but the branch has moved since"),
                        ("CLOSED", "closed, not merged")):
        for pr in mine:
            if pr["state"] == state:
                return "ask", f"PR #{pr['number']} {text}"
    _, count, _ = run_git(repo, "rev-list", "--count", wt["branch"], "--not", "--remotes")
    extra = f", {count} commit(s) not on any remote" if count.isdigit() and int(count) else ""
    return "ask", "no PR" + extra


def judge_worktree(repo, wt, prs, now):
    row = {"repo": os.path.basename(repo), "repo_path": repo, "path": wt["path"], "kind": "worktree",
           "branch": wt["branch"], "recent": False, "locked": wt["locked"], "suggest": "keep",
           "flag": "--remove"}
    inside = key(os.path.dirname(wt["path"])) == key(os.path.join(repo, WORKTREES))
    if now - newest_change(wt["path"]) < RECENT_SECONDS:
        row.update(tier="keep", why="changed in the last 2 hours", recent=True)
        return row
    code, status, err = run_git(wt["path"], "status", "--porcelain", "-z")
    names = changed_paths(status) if code == 0 else []
    edited = 0.0
    for name in names:
        full = os.path.join(wt["path"], name)
        # The parent folder's time catches a file that was just deleted.
        edited = max(edited, newest_under(full))
        try:
            edited = max(edited, os.lstat(os.path.dirname(full.rstrip("/\\"))).st_mtime)
        except OSError:
            pass
    if now - edited < RECENT_SECONDS:
        row.update(tier="keep", why="files changed in the last 2 hours", recent=True)
        return row
    if names:
        row["flag"] = "--force"
    if code:
        tier, why = "ask", "git status failed: " + last_line(err)
    elif wt["locked"]:
        tier, why = "ask", "locked (git worktree unlock first)"
    elif names:
        more = f", +{len(names) - 3} more" if len(names) > 3 else ""
        tier, why = "ask", "uncommitted or untracked: " + ", ".join(names[:3]) + more
    elif wt["branch"]:
        tier, why = judge_branch(repo, wt, prs)
    else:
        _, on_ref, _ = run_git(repo, "for-each-ref", "--count=1", "--contains", wt.get("head", ""),
                               "refs/heads", "refs/remotes")
        tier, why = ("auto", "detached, clean") if on_ref else ("ask", "detached commit is on no branch")
    if not inside:
        if tier == "auto":
            row["suggest"] = "remove if no longer needed"
        tier, why = "ask", "outside .claude/worktrees; " + why
    row.update(tier=tier, why=why)
    return row


def judge_leftovers(repo, registered, now):
    """Folders and files directly under .claude/worktrees that are not registered worktrees."""
    folder = os.path.join(repo, WORKTREES)
    rows = []
    if not os.path.isdir(folder):
        return rows
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if key(path) in registered:
            continue
        row = {"repo": os.path.basename(repo), "repo_path": repo, "path": path, "branch": None,
               "recent": False, "locked": False, "suggest": "keep", "flag": "--remove"}
        try:
            age = now - newest_under(path)
            if os.path.isdir(path):
                entries = len(os.listdir(path))
                row["kind"] = "leftover"
                if age < RECENT_SECONDS:
                    row.update(tier="keep", why="changed in the last 2 hours", recent=True)
                elif entries == 0:
                    row.update(tier="auto", why="empty leftover folder")
                else:
                    row.update(tier="ask", why=f"not a registered worktree, {entries} entries inside",
                               suggest="remove", flag="--force")
            else:
                row["kind"] = "loose"
                if age > LOOSE_SECONDS:
                    row.update(tier="auto", why="loose file older than 7 days")
                else:
                    row.update(tier="keep", why="loose file under 7 days old")
        except OSError as exc:
            row.update(kind="leftover", tier="ask", why=f"could not read: {exc.strerror}")
        rows.append(row)
    return rows


def inventory(root, now=None, pr_lookup=None):
    now = time.time() if now is None else now
    pr_lookup = pr_lookup or gh_prs
    jobs, rows, repos = [], [], find_repos(root)
    for repo in repos:
        worktrees = [wt for wt in registered_worktrees(repo) if os.path.isdir(wt["path"])]
        prs = pr_lookup(repo) if any(wt["branch"] for wt in worktrees) else {}
        jobs += [(repo, wt, prs) for wt in worktrees]
    # One repo's worktree can sit in another repo's folder; it is never a leftover there.
    registered = {key(wt["path"]) for _, wt, _ in jobs}
    for repo in repos:
        rows += judge_leftovers(repo, registered, now)
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows += pool.map(lambda job: judge_worktree(*job, now), jobs)
    return sorted(rows, key=lambda r: (r["repo"].lower(), r["path"].lower()))


# ---------------------------------------------------------------- removal

def _clear_readonly(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_row(row, force=False):
    """Remove one row. Returns None on success, else the reason it failed."""
    path = row["path"]
    try:
        if row["kind"] == "worktree":
            args = ["worktree", "remove"] + (["--force"] if force else []) + [path]
            code, _, err = run_git(row["repo_path"], *args)
            if code:
                return last_line(err)
        elif row["kind"] == "leftover":
            if force:
                shutil.rmtree(path, onexc=_clear_readonly)
            else:
                os.rmdir(path)
        else:
            os.remove(path)
    except OSError as exc:
        return exc.strerror or str(exc)
    return "still there after the removal" if os.path.lexists(path) else None


def _remove_all(rows, force=False):
    removed, failed = [], []
    for row in rows:
        error = remove_row(row, force)
        if error:
            failed.append(dict(row, error=error))
        else:
            removed.append(row)
    for repo in sorted({row["repo_path"] for row in rows}):
        run_git(repo, "worktree", "prune")
    return removed, failed


def apply(root, now=None, pr_lookup=None):
    """Remove the auto tier. Returns the rows removed, failed, to ask about and kept."""
    before = shutil.disk_usage(root).free
    rows = inventory(root, now, pr_lookup)
    removed, failed = _remove_all([r for r in rows if r["tier"] == "auto"])
    return {"removed": removed, "failed": failed,
            "ask": [r for r in rows if r["tier"] == "ask"],
            "keep": [r for r in rows if r["tier"] == "keep"],
            "free_before": before, "free_after": shutil.disk_usage(root).free}


def remove(root, paths, force=(), now=None, pr_lookup=None):
    """Remove rows the owner approved. Only paths the inventory lists; `force` ones lose their files."""
    before = shutil.disk_usage(root).free
    by_path = {key(r["path"]): r for r in inventory(root, now, pr_lookup)}
    removed, failed = [], []
    for forced, group in ((False, paths), (True, force)):
        todo = []
        for path in group:
            row = by_path.get(key(path))
            if row is None:
                failed.append({"path": path, "error": "not in the inventory; nothing done"})
            elif row["recent"]:
                failed.append(dict(row, error="changed in the last 2 hours; left alone"))
            elif row["locked"]:
                failed.append(dict(row, error="locked; run git worktree unlock first"))
            else:
                todo.append(row)
        done, errors = _remove_all(todo, forced)
        removed += done
        failed += errors
    return {"removed": removed, "failed": failed,
            "free_before": before, "free_after": shutil.disk_usage(root).free}


# ---------------------------------------------------------------- report

def shown(row):
    rel = os.path.relpath(row["path"], row["repo_path"]).replace(os.sep, "/")
    return rel.removeprefix(".claude/worktrees/")


def per_repo(rows):
    counts = {}
    for row in rows:
        counts[row["repo"]] = counts.get(row["repo"], 0) + 1
    return ", ".join(f"{repo} {n}" for repo, n in sorted(counts.items(), key=lambda kv: -kv[1]))


def print_failed(failed):
    if failed:
        print(f"failed {len(failed)}:")
        for row in failed:
            print(f"- {row['path']}: {row['error']}")


def print_free(result):
    print(f"free space: {result['free_before'] / GIB:.1f} GB -> {result['free_after'] / GIB:.1f} GB")


def print_ask(rows):
    print(f"\n## Needs your call ({len(rows)})\n")
    if not rows:
        print("Nothing.")
        return
    print("| # | repo | path | branch | why it was not removed | suggested | remove with |")
    print("|---:|---|---|---|---|---|---|")
    for n, row in enumerate(rows, 1):
        print(f"| {n} | {row['repo']} | {shown(row)} | {row['branch'] or 'detached'} | {row['why']} "
              f"| {row['suggest']} | {'unlock first' if row['locked'] else row['flag']} |")
    print("\nFull paths, in the same order, for --remove / --force:")
    for n, row in enumerate(rows, 1):
        print(f"{n}. {row['path']}")


def print_kept(rows):
    recent = [r for r in rows if r["recent"]]
    loose = [r for r in rows if not r["recent"]]
    if recent:
        print(f"kept, changed in the last 2 hours: {len(recent)} ({per_repo(recent)})")
    if loose:
        print(f"kept, loose files under 7 days old: {len(loose)} ({per_repo(loose)})")


def default_root():
    code, common, _ = run_git(os.getcwd(), "rev-parse", "--path-format=absolute", "--git-common-dir")
    if code or not common:
        return None
    return os.path.dirname(os.path.dirname(os.path.normpath(common)))


def main(argv=None, now=None, pr_lookup=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", help="folder that holds the repos")
    parser.add_argument("--apply", action="store_true", help="remove the auto tier")
    parser.add_argument("--remove", nargs="+", default=[], metavar="PATH", help="remove approved rows")
    parser.add_argument("--force", nargs="+", default=[], metavar="PATH",
                        help="remove approved rows and lose their uncommitted files")
    args = parser.parse_args(argv)
    root = args.root or default_root()
    if not root or not os.path.isdir(root):
        parser.error("give the folder that holds the repos (not inside a git repo, or ROOT is missing)")
    root = os.path.realpath(root)
    print(f"# Worktree sweep: {root}")

    if args.remove or args.force:
        result = remove(root, args.remove, args.force, now, pr_lookup)
        print_free(result)
        print(f"removed {len(result['removed'])}" + (f" ({per_repo(result['removed'])})" if result["removed"] else ""))
        print_failed(result["failed"])
        return 1 if result["failed"] else 0

    if args.apply:
        result = apply(root, now, pr_lookup)
        print_free(result)
        print(f"removed {len(result['removed'])}" + (f" ({per_repo(result['removed'])})" if result["removed"] else ""))
        print_failed(result["failed"])
        print_kept(result["keep"])
        print_ask(result["ask"])
        return 0

    rows = inventory(root, now, pr_lookup)
    auto = [r for r in rows if r["tier"] == "auto"]
    print(f"free space: {shutil.disk_usage(root).free / GIB:.1f} GB (dry run, nothing removed)")
    print(f"would remove {len(auto)}" + (f" ({per_repo(auto)})" if auto else ""))
    for row in auto:
        print(f"- {row['repo']}: {shown(row)} ({row['why']})")
    print_kept([r for r in rows if r["tier"] == "keep"])
    print_ask([r for r in rows if r["tier"] == "ask"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
