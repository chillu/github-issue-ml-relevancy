#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import argparse
import json
import os
from lib import github
from fastai.tabular.all import *

MODEL_PATH='./model/model.pkl'

VIEWER_LOGIN = os.environ.get("VIEWER_LOGIN")
if VIEWER_LOGIN is None:
    print("VIEWER_LOGIN not found")
    exit(0)

GITHUB_API_TOKEN = os.environ.get("GITHUB_API_TOKEN")
if GITHUB_API_TOKEN is None:
    print("GITHUB_API_TOKEN not found")
    exit(0)

# TODO Share with notebook
def _preprocess(df):
    # Fill missing values with zeroes
    df = df.fillna(value=0)
    # Clip outliers in scoring inputs to provide a better range to the regression
    df['viewer_events_count'].clip(upper=3, inplace=True)
    df['viewer_comments_count'].clip(upper=3, inplace=True)
    df['viewer_comments_body_count'].clip(upper=1000, inplace=True)
    # Inconsistencies between githubarchive and Github API, cap to avoid noise
    df['viewer_repo_issues_opened_count'].clip(upper=5, inplace=True)
    df['viewer_repo_pull_requests_opened_count'].clip(upper=5, inplace=True)
    df['creator_repo_issues_opened_count'].clip(upper=5, inplace=True)
    df['creator_repo_pull_requests_opened_count'].clip(upper=5, inplace=True)
    return df

def main():
    """
    Predicts the score for a single issue or pull request
    """
    parser = argparse.ArgumentParser(prog="fetch")
    parser.add_argument("url", help="issue or pull request url")
    parser.add_argument("--verbose", help="show request detail", action="store_true")

    args = parser.parse_args()

    # Retrieve params from Github
    params = github.fetch(
        url=args.url,
        viewer_login=VIEWER_LOGIN,
        github_api_token=GITHUB_API_TOKEN
    )
    if args.verbose:
        print(json.dumps(params))

    # Create DataFrame
    test_df = pd.DataFrame.from_dict([params])
    
    # Reapply preprocessing
    test_df = _preprocess(test_df)

    learn = load_learner(MODEL_PATH)
    row, pred, probs = learn.predict(test_df.iloc[0])

    print('Prediction: %d' % pred)
    

if __name__ == "__main__":
    main()
