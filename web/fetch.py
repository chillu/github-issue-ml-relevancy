#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import argparse
import json
import os
import re

from urllib.request import urlopen, Request

GITHUB_API_TOKEN = os.environ.get("GITHUB_API_TOKEN")
if GITHUB_API_TOKEN is None:
    print("GITHUB_API_TOKEN not found")
    exit(0)


def cli(args):
    # Basic query sanitisation
    url = args.url.replace('"', '')
    user = args.user;

    query = """
query { 
  resource(url:"%s") { 
    ...on PullRequest {
      __typename
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
}
    """ % (url)

    if args.verbose:
        print(query)

    req = Request("https://api.github.com/graphql", json.dumps({"query": query}).encode('utf-8'))
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer {}".format(GITHUB_API_TOKEN))

    params = {}
    response = urlopen(req)
    
    # Let Python handle standard exceptions
    resource = json.loads(response.read())["data"]["resource"]

    # Normalise, Github GraphQL doesn't support field aliases
    if 'baseRepository' in resource:
        resource['repository'] = resource['baseRepository']

    params = {
        **get_meta_params(resource),
        **get_content_params(resource, user),
    }

    print(json.dumps(params))

def get_meta_params(resource):
    # Normalise with Bigquery event types
    if (resource['__typename'] == 'PullRequest'):
        event_type = 'PullRequestEvent'
    elif (resource['__typename'] == 'Issue'):
        event_type = 'PullRequestEvent'
    else:
        raise ValueError('Unknown type: %s' % resource['__typename'])

    return {
        'item_id': resource['databaseId'],
        'repo_id': resource['repository']['databaseId'],
        'org_id': resource['repository']['owner']['databaseId'],
        'actor_login': resource['author']['login'],
        'type': event_type,
    }

def get_content_params(resource, user):
    at_mentions = get_at_mentions(resource)
    actors = get_actors(resource)
    comments = resource['comments']['nodes']
    actor_comments = [comment for comment in comments if comment['author']['login'] == user]
    
    # TODO prev_repo_actor_events_count and prev_repo_creator_events_count
    return {
        'is_comment': False,
        'title_chars_count': len(resource['title']),
        'body_chars_count': len(resource['body']),
        'markdown_chars_count': len(re.findall('[#\*]', resource['body'])),
        'all_at_mentions': at_mentions,
        'all_actors': actors,
        'at_mentions_count': len(at_mentions),
        'is_author': resource['author']['login'] == user,
        'is_at_mentioned': '@%s' % user in at_mentions,
        'actor_at_mentions_count': len(
            [at_mention for at_mention in at_mentions if at_mention == '@%s' % user]
        ),
        'events_count': resource['timelineItems']['totalCount'],
        # TODO Track actual events, not just comments
        'actor_events_count': len(actor_comments),
        'comments_count': resource['comments']['totalCount'],
        'comments_body_count': len(''.join([comment['body'] for comment in comments])),
        'actor_comments_body_count': len(''.join([comment['body'] for comment in actor_comments])),
    }

def get_at_mentions(resource):
    bodies = get_bodies(resource)
    return re.findall('(?:^|\s)(@[a-zA-Z0-9-_//]+)', ' '.join(bodies))

def get_bodies(resource):
    return [
        resource['body'],
        *[comment['body'] for comment in resource['comments']['nodes']]
    ]

def get_actors(resource):
    return [
        resource['author']['login'],
        *[comment['author']['login'] for comment in resource['comments']['nodes']]
    ]

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
    cli(args)

if __name__ == "__main__":
    main()