import json
import sys
import urllib.request


def main() -> None:
    base=(sys.argv[1] if len(sys.argv)>1 else "http://localhost:8000").rstrip("/")
    for path in ("/health","/api/public-config"):
        with urllib.request.urlopen(base+path,timeout=5) as r:
            data=json.load(r)
        print(path,"OK",data)


if __name__ == "__main__":
    main()
