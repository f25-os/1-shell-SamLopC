#!/usr/bin/env python3
# A minimal Unix-like shell implemented with only os, sys, re.
# Features:
# - Prompt from $PS1 (default "$ ")
# - PATH lookup (no execvp; uses execve)
# - Foreground execution with wait; background (&) without wait
# - Builtins: exit, cd
# - I/O redirection: "< infile", "> outfile"
# - Simple pipelines: cmd1 | cmd2 [| cmd3 ...]
# - Error handling:
#     * "<name>: command not found"  (to stderr)
#     * "Program terminated with exit code N." (to stderr)
#
# Important: writes no extraneous output to stdout (fd 1). Prompts go to fd 1,
# but the test harness sets PS1="" to avoid diffs.

import os
import sys
import re
import time

# -----------------------------
# Utility: low-level I/O helpers
# -----------------------------

def eprint(msg: str):
    """Write to stderr (fd 2) without extra formatting."""
    try:
        os.write(2, (msg + "\n").encode())
    except Exception:
        # Best-effort; don't crash on logging.
        pass

def prompt_string() -> str:
    return os.environ.get("PS1", "$ ")

def print_prompt():
    ps1 = prompt_string()
    if ps1:
        try:
            os.write(1, ps1.encode())
        except Exception:
            pass

# -----------------------------
# Parsing
# -----------------------------

_token_re = re.compile(
    r"""
    \s*(
        '[^']*'                |   # single-quoted
        "[^"]*"                |   # double-quoted
        [^ \t\r\n'"]+              # bare token
    )
    """,
    re.VERBOSE,
)

def split_pipeline(line: str):
    """
    Split a command line into pipeline segments by |, honoring quotes.
    Returns list[str] segments (trimmed).
    """
    segs = []
    buf = []
    in_s = False
    in_d = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'" and not in_d:
            in_s = not in_s
            buf.append(ch)
        elif ch == '"' and not in_s:
            in_d = not in_d
            buf.append(ch)
        elif ch == '|' and not in_s and not in_d:
            segs.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        segs.append(''.join(buf).strip())
    # Remove empty segments (e.g., stray pipes)
    return [s for s in segs if s != ""]

def tokenize(cmd: str):
    """
    Split a single pipeline stage into tokens (argv-like) honoring quotes.
    Quotes are removed; no escape processing beyond quotes.
    """
    tokens = []
    i = 0
    while i < len(cmd):
        m = _token_re.match(cmd, i)
        if not m:
            # skip any stray whitespace
            if cmd[i].isspace():
                i += 1
                continue
            # unknown char: treat as a one-char token (best-effort)
            tokens.append(cmd[i])
            i += 1
            continue
        tok = m.group(1)
        i = m.end()
        if len(tok) >= 2 and ((tok[0] == "'" and tok[-1] == "'") or (tok[0] == '"' and tok[-1] == '"')):
            tok = tok[1:-1]
        tokens.append(tok)
    return tokens

def parse_redirections(argv):
    """
    Parse simple redirections in argv: "< infile" and "> outfile".
    Returns (argv_wo_redirs, infile, outfile)

    Only supports separated operators (e.g., 'ls > out', not 'ls>out').
    """
    out = []
    infile = None
    outfile = None
    i = 0
    L = len(argv)
    while i < L:
        t = argv[i]
        if t == '<' and i + 1 < L:
            infile = argv[i + 1]
            i += 2
        elif t == '>' and i + 1 < L:
            outfile = argv[i + 1]
            i += 2
        else:
            out.append(t)
            i += 1
    return out, infile, outfile

def parse_background(line: str):
    """
    Detect background execution if '&' is the last non-space token.
    Returns (line_wo_amp, is_background)
    """
    stripped = line.rstrip()
    # Only treat as background if final token is '&' (possibly after spaces)
    if stripped.endswith('&'):
        # remove the trailing '&'
        # but ensure it's a separate token (preceded by space or pipe)
        # For simplicity given lab scope, assume '&' at end means background
        without = stripped[:-1].rstrip()
        return without, True
    return line, False

# -----------------------------
# PATH lookup (no execvp)
# -----------------------------

def is_executable(fp: str) -> bool:
    try:
        st = os.stat(fp)
    except OSError:
        return False
    # Executable bit must be set; file must be regular or at least stat-able.
    return os.access(fp, os.X_OK)

def resolve_command(prog: str):
    """
    If prog includes '/', return as-is (relative/absolute).
    Otherwise search PATH. Return absolute/relative path string or None.
    """
    if '/' in prog:
        return prog if is_executable(prog) else None
    path = os.environ.get('PATH', '')
    for d in path.split(':'):
        if not d:
            d = '.'
        cand = os.path.join(d, prog)
        if is_executable(cand):
            return cand
    return None

# -----------------------------
# Built-ins
# -----------------------------

def is_builtin(argv):
    return len(argv) > 0 and argv[0] in ('exit', 'cd')

def run_builtin(argv):
    """
    Execute builtin in the current process. Returns an exit code int.
    """
    if len(argv) == 0:
        return 0
    cmd = argv[0]
    if cmd == 'exit':
        # If an optional numeric argument is provided, use it
        code = 0
        if len(argv) > 1:
            try:
                code = int(argv[1])
            except ValueError:
                code = 1
        sys.exit(code)
    elif cmd == 'cd':
        # cd [path]; default to $HOME
        path = None
        if len(argv) >= 2:
            path = argv[1]
        else:
            path = os.environ.get('HOME', None)
        if path is None:
            eprint("cd: HOME not set")
            return 1
        try:
            os.chdir(path)
            return 0
        except OSError as e:
            eprint(f"cd: {e}")
            return 1
    return 0

# -----------------------------
# Execution
# -----------------------------

def setup_redirection(infile, outfile):
    """
    In child: apply redirections using dup2. Return True on success, False otherwise.
    """
    # input redirection
    if infile is not None:
        try:
            fd = os.open(infile, os.O_RDONLY)
        except OSError as e:
            eprint(f"{infile}: {e}")
            return False
        try:
            os.dup2(fd, 0)
        finally:
            os.close(fd)
    # output redirection
    if outfile is not None:
        try:
            fd = os.open(outfile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666)
        except OSError as e:
            eprint(f"{outfile}: {e}")
            return False
        try:
            os.dup2(fd, 1)
        finally:
            os.close(fd)
    return True

def exec_program(argv, env):
    """
    In child: resolve argv[0] to a path, then execve. On failure, print required
    message and exit with status 127 (like many shells).
    """
    if len(argv) == 0:
        os._exit(0)

    prog = argv[0]
    path = resolve_command(prog)
    if path is None:
        eprint(f"{prog}: command not found")
        os._exit(127)

    try:
        os.execve(path, argv, env)
    except OSError as e:
        # If execve fails, surface a useful message and exit non-zero.
        eprint(f"{prog}: {e}")
        os._exit(126)

def run_pipeline(stages, is_background):
    """
    Run a list of pipeline stages. Each stage is a dict:
      { "argv": [...], "in": infile_or_None, "out": outfile_or_None }
    If is_background==True, don't wait in the parent.
    Returns the exit code of the last process (or 0 when backgrounded).
    """
    n = len(stages)
    # builtins only execute directly if there is exactly one stage and it's builtin
    if n == 1 and is_builtin(stages[0]["argv"]):
        # Builtins ignore redirection in this simple lab when used alone with no pipes
        # (Typical shells support redirection for builtins; optional for this lab.)
        # Apply redirection around builtin by forking to avoid clobbering parent's fds.
        argv, infile, outfile = stages[0]["argv"], stages[0]["in"], stages[0]["out"]
        if infile is None and outfile is None:
            return run_builtin(argv)
        else:
            # Run builtin in a child so the parent's fds/env remain intact
            pid = os.fork()
            if pid == 0:
                ok = setup_redirection(infile, outfile)
                if not ok:
                    os._exit(1)
                # Execute the builtin now (in child)
                code = run_builtin(argv)
                os._exit(code)
            else:
                if is_background:
                    # Do not wait; return 0 for parent
                    return 0
                _, status = os.waitpid(pid, 0)
                return status_to_exitcode(status)

    # For N>=1 external commands, build N-1 pipes
    pipes = []
    for _ in range(n - 1):
        pipes.append(os.pipe())

    pids = []

    for i, st in enumerate(stages):
        pid = os.fork()
        if pid == 0:
            # Child
            # If not first stage, connect stdin to previous pipe's read end
            if i > 0:
                pr, pw = pipes[i - 1]
                os.dup2(pr, 0)
            # If not last stage, connect stdout to this pipe's write end
            if i < n - 1:
                pr, pw = pipes[i]
                os.dup2(pw, 1)

            # Close all pipe fds in child
            for j, (prj, pwj) in enumerate(pipes):
                try:
                    os.close(prj)
                except OSError:
                    pass
                try:
                    os.close(pwj)
                except OSError:
                    pass

            # Handle redirections for this stage (leftmost/rightmost are typical; we honor per-stage)
            if not setup_redirection(st["in"], st["out"]):
                os._exit(1)

            # Exec program
            exec_program(st["argv"], os.environ)

            # Should never return
            os._exit(127)
        else:
            pids.append(pid)

    # Parent: close all pipe fds
    for pr, pw in pipes:
        try:
            os.close(pr)
        except OSError:
            pass
        try:
            os.close(pw)
        except OSError:
            pass

    # Background: do not wait
    if is_background:
        return 0

    # Foreground: wait for all; return last one's exit code
    last_status = 0
    for pid in pids:
        _, status = os.waitpid(pid, 0)
        last_status = status if pid == pids[-1] else last_status

    return status_to_exitcode(last_status)

def status_to_exitcode(status: int) -> int:
    """Translate os.waitpid status to a shell-like exit code."""
    # If exited normally, lower 8 bits carry code.
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    # If terminated by signal, return 128+signal (typical convention).
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1

# -----------------------------
# REPL loop
# -----------------------------

def parse_line_into_stages(line: str):
    """
    Convert a command line into a list of pipeline stages (argv/in/out).
    Returns (stages, is_background).
    """
    # detect background
    line2, is_bg = parse_background(line)

    # split pipeline
    segs = split_pipeline(line2)
    stages = []
    for seg in segs:
        argv = tokenize(seg)
        # ignore empty command parts
        if len(argv) == 0:
            continue
        argv, infile, outfile = parse_redirections(argv)
        stages.append({"argv": argv, "in": infile, "out": outfile})
    return stages, is_bg

def show_banner():
    banner = """
\033[1;36m   ____                              _       
  / ___|  __ _ _ __ ___   ___  _ __ | | ___  
  \\\\___ \\\\ / _` | '_ ` _ \\\\ / _ \\\\| '_ \\\\| |/ _ \\\\ 
   ___) | (_| | | | | | | (_) | |_) | |  __/ 
  |____/ \\\\__,_|_| |_| |_|\\\\___/| .__/|_|\\\\___| 
                              |_|            
\033[0m
       \033[1;32mWELCOME TO \033[1;33mSAMUEL LOPEZ SHELL\033[0m
"""
    os.write(1, banner.encode())

def main():
    # Make stdin/stdout/stderr unbuffered behavior consistent
    # (We will interact via os.read/os.write only when needed.)
    show_banner()
    while True:
        try:
            # Print prompt (PS1 may be empty; that's OK)
            print_prompt()
            # Read one line; EOF terminates
            line = sys.stdin.readline()
            if line == '':
                # EOF
                break
            line = line.strip()
            if line == '':
                # blank line; continue
                continue

            stages, is_bg = parse_line_into_stages(line)
            if len(stages) == 0:
                continue

            # If single-stage builtin and not background with redirection handled above
            if len(stages) == 1 and is_builtin(stages[0]["argv"]) and stages[0]["in"] is None and stages[0]["out"] is None:
                rc = run_builtin(stages[0]["argv"])
                # If builtin returns non-zero, print exit line (spec asks printing on failure)
                if rc != 0:
                    eprint(f"Program terminated with exit code {rc}.")
                continue

            # Execute external (or builtin with redir/pipes in a child)
            rc = run_pipeline(stages, is_bg)

            # If foreground and non-zero exit, print the required message
            if not is_bg and rc != 0:
                eprint(f"Program terminated with exit code {rc}.")

        except KeyboardInterrupt:
            # On Ctrl-C: print a newline like bash and reissue prompt
            os.write(1, b"\n")
            continue
        except EOFError:
            break
        except Exception as ex:
            # Do not spew to stdout; keep it terse on stderr.
            eprint(f"error: {ex}")

if __name__ == "__main__":
    main()