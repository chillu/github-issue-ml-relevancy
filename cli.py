#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import argparse
import json
import os
from lib.fetcher import fetch

GITHUB_API_TOKEN = os.environ.get("GITHUB_API_TOKEN")
if GITHUB_API_TOKEN is None:
    print("GITHUB_API_TOKEN not found")
    exit(0)

def main():
    """
    Fetches params for a single issue or pull request,
    emulating same values as queried through BigQuery on the data set used for model training.
    """
    parser = argparse.ArgumentParser(prog="fetch")
    parser.add_argument("url", help="issue or pull request url")
    parser.add_argument("user", help="gitub user login")
    parser.add_argument("--verbose", help="show request detail", action="store_true")

    args = parser.parse_args()

    res = fetch(
        url=args.url,
        user=args.user,
        github_api_token=GITHUB_API_TOKEN
    )
    print(json.dumps(res))

if __name__ == "__main__":
    main()