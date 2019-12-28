import sys
import time
from blessed import Terminal
import pubtweet
from logger import Logger


def wscr(text):
    """Display ``text`` and flush output."""
    sys.stdout.write(u'{}'.format(text))
    sys.stdout.flush()


def get_inp(term, timeout=5.0):
    return term.inkey(timeout=timeout)


def comp_chr(c1, c2):
    if len(c1) != 1 or len(c2) != 1:
        return False
    if ord(c1) == ord(c2):
        return True
    else:
        return False


def prompt_quit(term):
    wscr(u'Exit? (y/n)')
    inp = get_inp(term)
    wscr(inp)
    if comp_chr(inp, 'y'):
        return True
    else:
        return False


def main(argv, argc):
    """Program entry point."""
    term = Terminal()
    logger = Logger()

    sys.stderr = open('error.log', 'w')

    logger.add("MSG: Starting 'pubtweet'...")
    with term.raw(), term.location():
        inp = term.inkey(timeout=0)
        pubtweet.start_scrapper()
        while True:
            inp = get_inp(term)
            if comp_chr(inp, chr(3)):
                if prompt_quit(term):
                    pubtweet.terminate_scrapper()
                    logger.add("Exiting...")
                    return
                else:
                    wscr('OK!')

            time.sleep(0.05)


if __name__ == '__main__':
    main(sys.argv, len(sys.argv))
