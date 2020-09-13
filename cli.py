#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import argparse
import json
import os
from lib import github

GITHUB_API_TOKEN = os.environ.get("GITHUB_API_TOKEN")
if GITHUB_API_TOKEN is None:
    print("GITHUB_API_TOKEN not found")
    exit(0)

def main():
    """
    Predicts the score for a single issue or pull request
    """
    parser = argparse.ArgumentParser(prog="fetch")
    parser.add_argument("url", help="issue or pull request url")
    parser.add_argument("viewer_login", help="gitub user login")
    parser.add_argument("--verbose", help="show request detail", action="store_true")

    args = parser.parse_args()

    params = github.fetch(
        url=args.url,
        viewer_login=args.viewer_login,
        github_api_token=GITHUB_API_TOKEN
    )
    if args.verbose:
        print(json.dumps(params))

    

if __name__ == "__main__":
    main()
