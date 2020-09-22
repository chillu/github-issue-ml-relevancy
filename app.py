from lib import github
from fastai.tabular.all import *
from flask import Flask, request, jsonify, render_template
import os

MODEL_PATH = './model/model.pkl'

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

app = Flask(__name__, static_url_path='/static')

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/predict', methods=['POST'])
def predict():
    # Retrieve params from Github
    # Let Flask handle error handling on params
    params = github.fetch(
        url=request.form['url'],
        viewer_login=VIEWER_LOGIN,
        github_api_token=GITHUB_API_TOKEN
    )

    # Create DataFrame
    test_df = pd.DataFrame.from_dict([params])

    # Reapply preprocessing
    test_df = _preprocess(test_df)

    learn = load_learner(MODEL_PATH)
    row, pred, probs = learn.predict(test_df.iloc[0])

    return jsonify({'pred': pred.item()})

if __name__ == '__main__':
    app.run(debug=False, port=os.getenv('PORT', 5000))
