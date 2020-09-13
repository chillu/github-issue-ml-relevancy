import re
import json
from urllib.request import urlopen, Request


def fetch(url, viewer_login, date_from=None, date_to=None, github_api_token=None, requester=None):
    """
    Fetches params for a single issue or pull request,
    emulating same values as queried through BigQuery on the data set used for model training.
    """

    if not requester:
        def requester(query):
            req = Request("https://api.github.com/graphql", json.dumps({"query": query}).encode('utf-8'))
            req.add_header("Accept", "application/json")
            req.add_header("Content-Type", "application/json")
            # Closing over github_api_token
            req.add_header("Authorization", "Bearer {}".format(github_api_token))
            # Let Python handle standard exceptions
            return urlopen(req)
    
    item_params = _get_item_params(
        requester,
        url=url,
        viewer_login=viewer_login
    )

    user_params = _get_user_params(
        requester,
        org_id=item_params['org_github_id'],
        creator_login=item_params['creator_login'],
        viewer_login=item_params['viewer_login'],
        repo_name=item_params['repo_name']
    )

    return {
        **item_params,
        **user_params,
    }

def _get_item_params(requester, url, viewer_login):
    # Basic query sanitisation
    url = url.replace('"', '')

    query = """
query { 
    resource(url:"%s") { 
        ...on PullRequest {
        __typename
        url
        title
        body
        databaseId
        author {
            login
        }
        baseRepository {
            name
            databaseId
            owner {
                ...on Organization {
                    name
                    databaseId
                }
                login
            }
        }
        comments(first:100) {
            totalCount
            nodes {
                author {
                    login
                }
                body
                }
            }
            timelineItems(itemTypes:[ISSUE_COMMENT, MERGED_EVENT, CLOSED_EVENT, REOPENED_EVENT]) {
                totalCount
            }
        }
        ...on Issue {
            __typename
            url
            title
            body
            databaseId
            author {
                login
            }
            repository {
                databaseId
                name
                owner {
                    ...on Organization {
                        id
                        databaseId
                        name
                    }
                }
            }
            comments(first:100) {
                totalCount
                nodes {
                    author {
                        login
                    }
                    body
                }
            }
            timelineItems(itemTypes:[ISSUE_COMMENT, CLOSED_EVENT, REOPENED_EVENT]) {
                totalCount
            }
        }
    }
}"""

    response = requester(query % (url))
    resource = json.loads(response.read())["data"]["resource"]

    # Normalise, Github GraphQL doesn't support field aliases
    if 'baseRepository' in resource:
        resource['repository'] = resource['baseRepository']

    # Normalise with Bigquery event types
    if (resource['__typename'] == 'PullRequest'):
        event_type = 'PullRequestEvent'
    elif (resource['__typename'] == 'Issue'):
        event_type = 'PullRequestEvent'
    else:
        raise ValueError('Unknown type: %s' % resource['__typename'])

    at_mentions = _get_at_mentions(resource)
    actors = _get_actors(resource)
    comments = resource['comments']['nodes']
    viewer_comments = [comment for comment in comments if comment['author']['login'] == viewer_login]
    
    return {
        'all_actors': actors,
        'all_at_mentions': at_mentions,
        'at_mentions_count': len(at_mentions),
        'body_chars_count': len(resource['body']),
        'comments_body_count': len(''.join([comment['body'] for comment in comments])),
        'comments_count': resource['comments']['totalCount'],
        'creator_login': resource['author']['login'],
        'events_count': resource['timelineItems']['totalCount'],
        'is_comment': False,
        'item_id': resource['databaseId'],
        'markdown_chars_count': len(re.findall('[#\*]', resource['body'])),
        'org_github_id': resource['repository']['owner']['id'],
        'org_id': resource['repository']['owner']['databaseId'],
        'repo_id': resource['repository']['databaseId'],
        'repo_name': resource['repository']['name'],
        'title_chars_count': len(resource['title']),
        'type': event_type,
        'viewer_at_mentions_count': len([at_mention for at_mention in at_mentions if at_mention == '@%s' % viewer_login]),
        'viewer_comments_body_count': len(''.join([comment['body'] for comment in viewer_comments])),
        # TODO Track actual events, not just comments
        'viewer_comments_count': len(viewer_comments),
        'viewer_events_count': len(viewer_comments),
        'viewer_is_at_mentioned': '@%s' % viewer_login in at_mentions,
        'viewer_is_author': resource['author']['login'] == viewer_login,
        'viewer_login': viewer_login,
    }


def _get_user_params(requester, viewer_login, creator_login, repo_name, org_id):
    query = """
query { 
  user(login:"%s") {
    contributionsCollection(organizationID:"%s", from:"2018-01-01T00:00:00Z") {
      totalIssueContributions
      issueContributionsByRepository(maxRepositories:100) {
        repository {
          name
        }
        contributions(first:1) {
          totalCount
        }
      }
      totalPullRequestContributions
      pullRequestContributionsByRepository(maxRepositories:100) {
        repository {
          name
        }
        contributions(first:1) {
          totalCount
        }
      }
    }
  }
}
    """

    colls = {}
    for login in [viewer_login, creator_login]:
        response = requester(query % (login, org_id))
        data = json.loads(response.read())["data"]
        colls[login] = data['user']['contributionsCollection']

    return {
        'creator_org_pull_requests_opened_count': colls[creator_login]['totalPullRequestContributions'],
        'creator_org_issues_opened_count': colls[creator_login]['totalIssueContributions'],
        'creator_repo_issues_opened_count': _get_contrib_count(colls[creator_login]['issueContributionsByRepository'], repo_name),
        'creator_repo_pull_requests_opened_count': _get_contrib_count(colls[creator_login]['issueContributionsByRepository'], repo_name),
        'viewer_org_pull_requests_opened_count': colls[viewer_login]['totalPullRequestContributions'],
        'viewer_org_issues_opened_count': colls[viewer_login]['totalIssueContributions'],
        'viewer_repo_issues_opened_count': _get_contrib_count(colls[viewer_login]['issueContributionsByRepository'], repo_name),
        'viewer_repo_pull_requests_opened_count': _get_contrib_count(colls[viewer_login]['issueContributionsByRepository'], repo_name),
    }

def _get_contrib_count(items, repo_name):
    return sum(map(lambda item: item['contributions']['totalCount'] if item['repository']['name'] == repo_name else 0, items))

def _get_at_mentions(resource):
    bodies = _get_bodies(resource)
    return re.findall(r'(?:^|\s)(@[a-zA-Z0-9-_//]+)', ' '.join(bodies))

def _get_bodies(resource):
    return [
        resource['body'],
        *[comment['body'] for comment in resource['comments']['nodes']]
    ]

def _get_actors(resource):
    return [
        resource['author']['login'],
        *[comment['author']['login'] for comment in resource['comments']['nodes']]
    ]
