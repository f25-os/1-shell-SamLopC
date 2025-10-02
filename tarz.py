#!/usr/bin/env python3
"""
tarz.py - A tiny tar-like archiver.

Usage:
  ./tarz.py c archive.tarz files...
  ./tarz.py t archive.tarz
  ./tarz.py x archive.tarz

Supports:
- create (c): pack files/dirs into an archive
- list   (t): show archive contents
- extract(x): extract files

Archive format (text-based, very simple):
  path\n
  size\n
  mode\n
  mtime\n
  raw-bytes (size bytes)
  ----END----\n
"""

import os, sys, stat, time

SEP = b"----END----\n"

def write_file_entry(archive, path, arcname):
    st = os.stat(path)
    size = st.st_size
    mode = st.st_mode
    mtime = int(st.st_mtime)

    with open(path, "rb") as f:
        data = f.read()

    hdr = f"{arcname}\n{size}\n{mode}\n{mtime}\n".encode()
    archive.write(hdr)
    archive.write(data)
    archive.write(SEP)

def create(archname, files):
    with open(archname, "wb") as a:
        for f in files:
            if os.path.isdir(f):
                for root, dirs, fls in os.walk(f):
                    for name in fls:
                        full = os.path.join(root, name)
                        rel = os.path.relpath(full, start=os.path.dirname(f))
                        print(f"Adding {rel}")
                        write_file_entry(a, full, rel)
            else:
                rel = os.path.basename(f)
                print(f"Adding {rel}")
                write_file_entry(a, f, rel)

def list_contents(archname):
    with open(archname, "rb") as a:
        while True:
            header = []
            for _ in range(4):
                line = a.readline()
                if not line:
                    return
                header.append(line.decode().rstrip("\n"))
            path, size, mode, mtime = header
            size = int(size)
            mode = int(mode)
            mtime = int(mtime)
            # skip data
            a.read(size)
            sep = a.readline()
            if sep != SEP:
                print("Archive corruption detected!", file=sys.stderr)
                return
            print(f"{path}\t{size} bytes\tmode={oct(mode)}\tmtime={time.ctime(mtime)}")

def extract(archname):
    with open(archname, "rb") as a:
        while True:
            header = []
            for _ in range(4):
                line = a.readline()
                if not line:
                    return
                header.append(line.decode().rstrip("\n"))
            path, size, mode, mtime = header
            size = int(size)
            mode = int(mode)
            mtime = int(mtime)
            data = a.read(size)
            sep = a.readline()
            if sep != SEP:
                print("Archive corruption detected!", file=sys.stderr)
                return
            # Recreate file
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as out:
                out.write(data)
            os.chmod(path, mode)
            os.utime(path, (mtime, mtime))
            print(f"Extracted {path}")

def usage():
    print(__doc__)
    sys.exit(1)

def main():
    if len(sys.argv) < 3:
        usage()
    cmd = sys.argv[1]
    arch = sys.argv[2]
    if cmd == "c":
        if len(sys.argv) < 4:
            usage()
        create(arch, sys.argv[3:])
    elif cmd == "t":
        list_contents(arch)
    elif cmd == "x":
        extract(arch)
    else:
        usage()

if __name__ == "__main__":
    main()