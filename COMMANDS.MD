📜 Samuel Lopez Shell — Command Cheat Sheet

This is a quick reference of all the features supported by **Samuel Lopez Shell**.

---

## Built-in Commands

| **Command**       | **Example**         | **Description**                                      |
|-------------------|---------------------|------------------------------------------------------|
| `exit [code]`     | `exit` / `exit 2`   | Exit the shell with optional exit code (default `0`).|
| `cd [dir]`        | `cd /tmp`           | Change current directory (default: `$HOME`).         |

---

## External Commands

| **Command**        | **Example**          | **Description**                                      |
|--------------------|----------------------|------------------------------------------------------|
| Any executable in `$PATH` | `ls -l`, `cat file.txt` | Finds the program via `$PATH` and runs it in a child process. |
| Invalid command    | `foobar`             | Prints `foobar: command not found` and exit code `127`. |

---

## Redirection

| **Feature**    | **Example**             | **Description**                                      |
|----------------|-------------------------|------------------------------------------------------|
| Output `>`     | `ls > out.txt`          | Redirects stdout of command into a file.             |
| Input `<`      | `cat < in.txt`          | Reads stdin of command from a file.                  |

---

## Pipelines

| **Feature**       | **Example**                    | **Description**                                      |
|-------------------|--------------------------------|------------------------------------------------------|
| Simple pipe       | `ls | sort -r`                 | Connect stdout of one command into stdin of another. |
| Multi-stage pipe  | `cat file | grep abc | wc -l`  | Supports chaining multiple commands with pipes.      |

---

## Background Execution

| **Feature** | **Example**              | **Description**                                      |
|-------------|--------------------------|------------------------------------------------------|
| Background  | `find /etc -print &`     | Run command in background without waiting.           |

---

## Prompt

| **Feature**     | **Example**                                | **Description**                                      |
|-----------------|--------------------------------------------|------------------------------------------------------|
| Prompt string   | `(export PS1="MyShell> "; ./shell.py)`     | Prompt is controlled by `$PS1` (default is `$ `).    |

---

## Startup

| **Feature** | **Description**                                      |
|-------------|------------------------------------------------------|
| Banner      | Prints a colored ASCII “WELCOME TO SAMUEL LOPEZ SHELL” at startup. |

---

## Signals & Exit

| **Key**     | **Action**                    |
|-------------|-------------------------------|
| `Ctrl-C`    | Cancels foreground program (shell keeps running). |
| `Ctrl-D`    | Sends EOF to shell → exits gracefully. |

---

✨ That’s it — your custom shell supports all the basics of a Unix-style shell plus your own personality banner!