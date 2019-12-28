import sys
from threading import Thread
import time
import tweets_bs4 as tweets
import json
import html
from pathlib import Path
import datetime
from logger import Logger


ROOT_PATH = './'
CONFIG_FILE_NAME = 'config.json'
CONFIG_FILE_PATH = ROOT_PATH + CONFIG_FILE_NAME
DATA_DIR_NAME = 'data/'
DATA_DIR_PATH = ROOT_PATH + DATA_DIR_NAME


def pubDate_string(date):
    date_str = "%s, %02d %s %04d %02d:%02d:%02d GMT" % (["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][date.weekday()], date.day,
			["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][date.month-1], date.year, date.hour, date.minute, date.second)

    return date_str


def rss_header(feed_name):
    lines = ['<?xml version="1.0" encoding="UTF-8" ?>\n',
             '<rss version="2.0">\n',
             '<channel>\n',
             '  <title>' + feed_name + '</title>\n',
             '  <description>' + feed_name + ' Twitter feed</description>\n',
             '  <link>https://twitter.com/' + feed_name + '</link>\n',
             '  <lastBuildDate>' + pubDate_string(datetime.datetime.now()) + '</lastBuildDate>\n',
             '  <pubDate>' + pubDate_string(datetime.datetime.now()) + '</pubDate>\n',]

    return lines


def seek_rss_file(fh, feed_name, last_id):
    logger = Logger()
    match_line = 'https://twitter.com/%s/status/%d' % (feed_name, last_id)
    while True:
        line = fh.readline()
        if match_line in line:
            match_line = "</item>"
            if match_line == "</item>":
                fh.readline()
                logger.add("MSG: Last entry with ID '{}' is found in '{}' rss file".format(last_id, feed_name))
                break

    return fh


def scrap_tweets(config, feed_names=None):
    logger = Logger()
    logger.add("MSG: 'pubtweet.scrap_tweets' started.")
    if feed_names == None:
        feed_names = config["feeds"].keys()

    err_feeds = []

    for feed_name in feed_names:
        logger.add("MSG: Scrapping '{}'.".format(feed_name))
        feed = config["feeds"][feed_name]
        pages = 1
        last_id = feed["last_id"]
        new_tweets = []
        tweet_fetching_failed = False
        while pages < 5:
            try:
                tws = list(tweets.get_tweets(feed_name, pages=pages))
            except Exception:
                logger.add("ERR: Can not retrieve tweets.")
                tweet_fetching_failed = True
                break

            if last_id != -1:
                index = -1
                i = 0
                for tw in tws:
                    if int(tw["tweetId"]) == last_id:
                        new_tweets = list(tws[:i])

                    i += 1
            else:
                new_tweets = list(tws)

            if len(new_tweets) == 0:
                pages += 1
            else:
                break

        if tweet_fetching_failed:
            continue

        if len(new_tweets) == 0:
            logger.add("MSG: Feed '{}' has no new tweets.".format(feed_name))
            continue
        else:
            logger.add("MSG: Feed '{}' has {} new tweets.".format(feed_name, len(new_tweets)))

        rss_file_name = DATA_DIR_PATH + "{}.rss".format(feed_name)
        rss_file = Path(rss_file_name)

        rss_file_lines = []
        if rss_file.is_file():
            with open(rss_file_name, mode='r', encoding='utf8') as fh:
                rss_file_lines = fh.readlines()

            if not(len(rss_file_lines) > 8 and '<item>' in rss_file_lines[8]):
                logger.add("MSG: RSS file is broken.")
                continue
        else:
            rss_file_lines = [''] * 8

        head = rss_header(feed_name)
        i = 0
        for line in head:
            rss_file_lines[i] = line
            i += 1

        new_lines_index = -1
        j = len(rss_file_lines) - 1
        while True:
            line = rss_file_lines[j]

            if '</item>' in line:
                new_lines_index = j + 1
                break

            if j < i:
                new_lines_index = j + 1
                break

            j -= 1

        rss_file_lines_new = rss_file_lines[:new_lines_index]
        for new_tweet in reversed(new_tweets):
            text = html.escape(new_tweet["text"])
            link = 'https://twitter.com/' + feed_name + '/status/%d' % int(new_tweet["tweetId"])
            title = '    <title>' + text + '</title>\n'
            desc = '    <description>' + text + '</description>\n'
            link_str = '    <link>' + link + '</link>\n'
            guid_str = '    <guid isPermaLink="true">' + link + '</guid>\n'
            pub_date = '    <pubDate>' + pubDate_string(new_tweet["time"]) + '</pubDate>\n'

            rss_file_lines_new.append('  <item>\n')
            rss_file_lines_new.append(title)
            rss_file_lines_new.append(desc)
            rss_file_lines_new.append(link_str)
            rss_file_lines_new.append(guid_str)
            rss_file_lines_new.append(pub_date)
            rss_file_lines_new.append('  </item>\n')

        rss_file_lines_new.append('</channel>\n')
        rss_file_lines_new.append('</rss>\n')

        prev_last_id = feed["last_id"]
        feed["last_id"] = int(new_tweets[0]["tweetId"])
        logger.add("MSG: 'last_id' is changed to '{}' from '{}'".format(feed["last_id"], prev_last_id))

        with open(rss_file_name, mode='w', encoding='utf8') as fh:
            for line in rss_file_lines_new:
                fh.write(line)

        logger.add("MSG: Finished writing RSS file.")

    return {'err_feeds': err_feeds }


def main(argv):
    config = read_config()
    scrap_tweets(config)

    with open('urls.tmp', 'w') as fh:
        for feed in config["feeds"]:
            fh.write(DATA_DIR_PATH + "{}.rss\n".format(feed))

    terminate(config)


if __name__ == "__main__":
    main(sys.argv)


class ScrapperThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self._terminate = False
        self.read_config()
        self.sleep_time = 3
        self.new_req_sleep_time = 10
        # Default refresh period is 2 hours
        self.default_period = 30 * 60 * 1
        self.last_update_time = time.time() - self.default_period
        self.update_period = -1
        self.set_sleep_times()

    def set_sleep_times(self):
        if "update_period" in self.config["settings"]:
            self.update_period = self.config["settings"]["update_period"]
        else:
            self.update_period = self.default_period
            self.config["settings"]["update_period"] = self.update_period

        if "new_req_sleep_time" in self.config["settings"]:
            self.new_req_sleep_time = self.config["settings"]["new_req_sleep_time"]
        else:
            self.new_req_sleep_time = self.default_period
            self.config["settings"]["new_req_sleep_time"] = self.new_req_sleep_time

    def run(self):
        logger = Logger()
        while not self._terminate:
            time_diff = time.time() - self.last_update_time
            if time_diff >= self.update_period:
                err_tweets = scrap_tweets(self.config)
                self.last_update_time = time.time()
                self.write_config()

            time.sleep(self.sleep_time)

        logger.add("MSG: Terminating scrapper thread...")
        self.terminate()

    def terminate(self):
        self.write_config()
        self._terminate = True

    def write_config(self):
        with open(CONFIG_FILE_PATH, 'w') as fh:
            fh.write(json.dumps(self.config, sort_keys=True, indent=4))

    def read_config(self):
        with open(CONFIG_FILE_PATH, 'r') as fh:
            _config = json.load(fh)

        with open(CONFIG_FILE_PATH + '.bak', 'w') as fh:
            fh.write(json.dumps(_config, sort_keys=True, indent=4))

        profile_names_file = _config["profile_names_file"]
        profiles = []
        with open(ROOT_PATH + profile_names_file, 'r') as fh:
            for name in fh.readlines():
                name = name.strip()

                if name and not name.startswith('#'):
                    profiles.append(name)

        for feed_name in list(_config["feeds"].keys()):
            if feed_name not in profiles and feed_name in _config["feeds"]:
                del _config["feeds"][feed_name]

        for profile in profiles:
            if profile not in _config["feeds"]:
                _config["feeds"][profile] = { "last_id": -1 }

        self.config = _config

scrapper_thread = ScrapperThread()

def start_scrapper():
    scrapper_thread.start()

def terminate_scrapper():
    scrapper_thread.terminate()
    scrapper_thread.join()
