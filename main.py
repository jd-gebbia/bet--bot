#!/usr/bin/env python

"""
bot to retweet all from its following list
"""

# imports
import os, time, json
from sys import exit
# from urlparse import urlparse
from contextlib import contextmanager
import tweepy
import backoff
import shelve

# import exceptions
# from urllib2 import HTTPError


def log(**kwargs):
    print(' '.join( "{0}={1}".format(k,v) for k,v in sorted(kwargs.items()) ))

def update_recent_tweet(friend_id, tweet_id):
    friend_id = str(friend_id)
    d = shelve.open('friend_recent_tweets')  # open -- file may get suffix added by low-level library
    if friend_id in d:
        if d[friend_id] == tweet_id:
            print("{} is the most recent tweet for friend {}".format(tweet_id, friend_id))
        else:
            if d[friend_id] < tweet_id:     # need to update
                d[friend_id] = tweet_id
                print("{} updated to most recent tweet for friend {}".format(tweet_id, friend_id))
            print("{} no_update {}".format(tweet_id, friend_id))
    else:
        d[friend_id] = tweet_id
    d.close()

def get_recent_tweet(friend_id):
    friend_id = str(friend_id)
    d = shelve.open('friend_recent_tweets')  # open -- file may get suffix added by low-level library
    if friend_id not in d:
        d.close()
        return None
    else:
        most_recent = d[friend_id]
        d.close()
        return most_recent
    d.close()

# @contextmanager
# def measure(**kwargs):
#     return
    # start = time.time()
    # status = {'status': 'starting'}
    # log(**dict(kwargs.items() + status.items()))
    # try:
    #     yield
    # except Exception as e:
    #     status = {'status': 'err', 'exception': "'{0}'".format(e)}
    #     log(**dict(kwargs.items() + status.items()))
    #     raise
    # else:
    #     status = {'status': 'ok', 'duration': time.time() - start}
    #     log(**dict(kwargs.items() + status.items()))


def debug_print(text):
    """Print text if debugging mode is on"""
    if os.environ.get('DEBUG'):
        print(text)


def fav_tweet(api,tweet):
    """Attempt to fav a tweet and return True if successful"""

    # sometimes this raises TweepError even if tweet[0]._json['favorited']
    # was False
    try:
        api.create_favorite(id=tweet[0]._json['id'])
    except Exception as e:
        log(at='fav_error', tweet=tweet[0]._json['id'], klass='TweepError', msg="'{0}'".format(str(e)))
        return False

    log(at='favorite', tweet=tweet[0]._json['id'])
    return True


def validate_env():
    # keys = [
    #     'TW_USERNAME',
    #     'TW_CONSUMER_KEY',
    #     'TW_CONSUMER_SECRET',
    #     'TW_ACCESS_TOKEN',
    #     'TW_ACCESS_TOKEN_SECRET',
    #     ]

    # Check for missing env vars
    # for key in keys:
    #     v = os.environ.get(key)
    #     if not v:
    #         log(at='validate_env', status='missing', var=key)
    #         raise ValueError("Missing ENV var: {0}".format(key))

    # Log success
    log(at='validate_env', status='ok')


@backoff.on_exception(backoff.expo, Exception, max_tries=8)
def fetch_friends(api):
    """Fetch friend list from twitter"""
    # with measure(at='fetch_friends'):
    friends = api.get_friend_ids()
    return friends


@backoff.on_exception(backoff.expo, Exception, max_tries=8)
def fetch_mentions(api):
    """Fetch mentions from twitter"""
    # with measure(at='fetch_mentions'):
    replies = api.mentions_timeline()
    return replies

# @backoff.on_exception(backoff.expo, Exception, max_tries=8)
def fetch_friend_tweets(api, friends):
    """Fetch friends' tweeets from twitter"""
    tweets = []

    friend_counter = 0      # Have limit of 100,000 daily requests to user_timeline,
                            # So running at 10 min intervals means 144 requests per friend,
                            #  we can't cover more than 694 friends
                            # ---- also have a limit of 900 requests every 15 mins
    for friend in friends:
        friend_counter
        log(at='fetch_friends_tweets',  user=friend)

        # Get most recent tweet seen
        recent_id = get_recent_tweet(friend)
        # Get recent tweets
        if(recent_id is None):
            tweets=api.user_timeline(user_id=friend, count=20, exclude_replies=True)
        else:
            tweets=api.user_timeline(user_id=friend, count=20, since_id=recent_id, exclude_replies=True)

        # Assess each tweet
        log(at='fetch_friends_tweets',  num_tweets=len(tweets))
        for tweet in reversed(tweets):
            log(at='fetch_friends_tweets',  tweet_id=tweet._json['id'])
            update_recent_tweet(tweet._json['user']['id'], tweet._json['id'])
            filter_or_retweet(api, tweet)
        # fav_tweet(api, tweet)
        # input("..")
    
    # print(tweets)
    return tweets

def filter_or_retweet(api,tweet):
    """Perform retweets while avoiding loops and spam"""
    username = 'bet--bot'
    # normalized_tweet = tweet[0]._json['text'] weet.text.lower().strip()

    # ignore tweet if we've already tweeted it
    if tweet._json['retweeted']:
        log(at='filter', reason='already_retweeted', tweet=tweet._json['id'])
        return

    # Don't try to retweet our own tweets
    if tweet._json['user']['screen_name'].lower() == username.lower():
        log(at='filter', reason='is_my_tweet', tweet=tweet._json['id'])
        return

    log(at='retweet', tweet=tweet._json['id'])
    return api.retweet(id=tweet._json['id'])

def main():
    log(at='main')
    main_start = time.time()

    validate_env()

    # owner_username    = os.environ.get('TW_OWNER_USERNAME')
    # username          = os.environ.get('TW_USERNAME')
    consumer_key      = 'E3sQJtBdGFFyWxD2XKFdWbKqG'
    consumer_secret   = 'sMOXTj8mlqMGCyWQVYw5q8CuTuQXTtXz8EOnE62ZcsVBeCBZK4'
    access_token        = '1489880458405945344-u71wEfPQgcE08t0b3dML2lk1dFFg0n'
    access_token_secret     = 'waUayQtUOR3OhUgKEUdZmy6FoXPHmYnwuTzT9Euev6i9y'


    auth = tweepy.OAuthHandler(consumer_key=consumer_key,
        consumer_secret=consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = tweepy.API(auth, retry_count=3)

    # test authentication
    try:
        api.verify_credentials()
        print("Authentication OK")
    except Exception as e:
        log(at='authentication',  msg="'{0}'".format(str(e)))

    log(at='fetching_from_api')
    friends = fetch_friends(api)
    tweets = fetch_friend_tweets(api, friends)
    log(at='fetched_from_api', friends=len(friends), mentions=len(tweets))

    # Driver loop
    # for tweet in reversed(tweets):
    #     # ignore tweet if it's not from someone we follow and send notification
    #     if tweet[0]._json['user']['id'] not in friends:
    #         if not tweet[0]._json['favorited']: 
    #             prev_seen = "false"
    #             status = fav_tweet(api, tweet)
    #         else:
    #             prev_seen = "true"

    #         log(at='ignore', tweet=tweet[0]._json['id'], reason='not_followed', prev_seen=prev_seen)
    #         continue

    #     try:
    #         filter_or_retweet(api,tweet)
    #     except Exception as e:
    #         log(at='rt_error', klass='Exception', msg="'{0}'".format(str(e)))
    #         debug_print('e: %s' % e)
    #         raise

    log(at='finish', status='ok', duration=time.time() - main_start)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log(at='keyboard_interrupt')
        quit()
    except:
        raise
