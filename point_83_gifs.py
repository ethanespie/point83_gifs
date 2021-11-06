import os
import sys
import re
from datetime import datetime
import requests
import bs4


# TODO: make it so that log file goes in same folder as output (neater/cleaner)
# TODO: more/better exception handling, and other pylint-noted stuff
# TODO: get rid of global vars as much as possible
# TODO: improve at least some of the regex logic
# TODO: unit tests
# TODO: implement class(es)


START_TIME = datetime.now()
FOLDER_AND_LOG_NAME = "Point83GIFs_" + "{:04d}".format(START_TIME.year) + "_" + \
                      "{:02d}".format(START_TIME.month) + "_" + \
                      "{:02d}".format(START_TIME.day) + "_" + \
                      "{:02d}".format(START_TIME.hour) + \
                      "{:02d}".format(START_TIME.minute)
MAX_GIFS_PER_FORUM_PAGE = 100   # max gifs per page; sometimes kept low just for debugging purposes

FORUM_PAGE_NUM = 0              # actual forum page number
ALL_SAVED_GIF_PATHS = []        # paths to GIFs downloaded, with "http" or "https" removed
ALL_FILE_NAMES_SAVED = []       # names of files saved (start with name of thread where first found)
TOTAL_GIFS_DOWNLOADED = 0
TOTAL_THREAD_PAGES_SCRAPED = 0


def initial_setup():
    global FOLDER_AND_LOG_NAME, FORUM_PAGE_NUM

    initial_url = prompt_user_for_which_forum()
    start_page_num = prompt_user_for_start_page()
    FORUM_PAGE_NUM = start_page_num
    max_forum_pgs_to_process = prompt_user_for_total_pages()

    if start_page_num != 1:
        index = (start_page_num - 1) * 30
        initial_url = initial_url + "&topicdays=0&start=" + str(index)

    try:
        res = requests.get(initial_url)  # "downloads" the web page; returns a response object
        res.raise_for_status()  # checks to see if download worked; raises exception if fail
    except requests.exceptions.RequestException as exception:
        print("ERROR:  URL " + initial_url + " could not be located.\n")
        print(exception)
        sys.exit()

    # Delete log if already exists (only needed when script run/cancelled/rerun in same minute)
    try:
        os.remove(FOLDER_AND_LOG_NAME + ".txt")
    except OSError:
        pass

    # Make folder to store downloaded GIFs in
    try:
        os.makedirs(FOLDER_AND_LOG_NAME, exist_ok=True)
    except OSError:
        print("ERROR:  folder \"" + FOLDER_AND_LOG_NAME + "\" could not be created.")
        sys.exit()

    return [res, max_forum_pgs_to_process]


def prompt_user_for_which_forum():
    print("************************")
    print("***** Point83 GIFs *****")
    print("************************")
    while True:
        print("\nSelect which forum to search for GIFs in:")
        print("Westlake Center:                     enter a \"1\".")
        print("Wrenches Gears Lawns and Routes:     enter a \"2\".")
        print("Point83 Navy:                        enter a \"3\".")
        user_input = input("Enter 1, 2, or 3:\n")

        if user_input == "1":
            return "http://www.point83.com/forum/viewforum.php?f=2"
        elif user_input == "2":
            return "http://www.point83.com/forum/viewforum.php?f=4"
        elif user_input == "3":
            return "http://www.point83.com/forum/viewforum.php?f=10"
        else:
            print("ERROR: Invalid entry.")


def prompt_user_for_total_pages():
    while True:
        print("\nHow many pages of the given forum do you want to process?")
        print("Hit [Enter] for the default (all pages).")
        user_input = input("")
        if user_input == "":
            return 1000000
        try:
            val = int(user_input)
            return val
        except:
            print("ERROR: Invalid; enter an integer.")


def prompt_user_for_start_page():
    while True:
        print("\nIf you want to start on an older page of this forum, enter its page number.")
        print("Otherwise, hit [Enter] for the default, page 1.")
        user_input = input("")
        if user_input == "":
            return 1
        try:
            val = int(user_input)
            return val
        except:
            print("ERROR: Invalid; enter an integer.")


def process_forum(resp, max_forum_pgs_to_process):

    global FORUM_PAGE_NUM  # TEMP
    page_num = 1  # TEMP

    forum_next_button = True
    while forum_next_button:
        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        viewtopic_anchors = soup.find_all('span', class_="blacklink")
        forum_next_btn_anchors = soup.find_all('a', href=True, text='Next')

        write_to_log_and_or_console("------------------------" + "\n" + "FORUM PAGE " +
                                    str(FORUM_PAGE_NUM))
        write_to_log_and_or_console("------------------------" + "\n")

        all_uris = []               # "viewtopic" part of URL of thread
        all_thread_names = []       # actual thread names
        for anchor in viewtopic_anchors:
            if str(anchor).find("viewtopic.php?t") != -1:
                all_uris.append(str(anchor)[str(anchor).find("viewtopic"):str(anchor).find("&")])
                all_thread_names.append(anchor.text)

        for i in range(len(all_uris)):
            process_thread(all_uris[i], all_thread_names[i])

        # go to next page (IF there is one)
        if len(forum_next_btn_anchors) > 0:
            url = "http://www.point83.com/forum/" + forum_next_btn_anchors[0].get("href")
            try:
                resp = requests.get(url)
                resp.raise_for_status()
            except requests.exceptions.RequestException:
                write_to_log_and_or_console("\n\nERROR:  URL for forum page number " +
                                            str(FORUM_PAGE_NUM + 1) + " (" + url +
                                            ") could not be located.")
                write_to_log_and_or_console("Exiting process.\n\n")
                return
            page_num += 1
            FORUM_PAGE_NUM += 1
        else:
            forum_next_button = False

        if page_num > max_forum_pgs_to_process:
            forum_next_button = False


def process_thread(uri, thread_name):
    global TOTAL_THREAD_PAGES_SCRAPED
    # remove all non-ascii characters:
    thread_name_for_log = re.sub(r'[^\x00-\x7f]', r"", thread_name).strip()

    # remove characters which aren't alpha/num/dot/underscore
    thread_name_for_file_names = re.sub("[^0-9a-zA-Z._]", "", thread_name).strip()

    thread_page_num = 0
    thread_next_button = True
    while thread_next_button:
        url = "http://www.point83.com/forum/" + uri
        try:
            res = requests.get(url)
            res.raise_for_status()
        except requests.exceptions.RequestException:
            write_to_log_and_or_console("ERROR:  URL for thread \"" + thread_name_for_log +
                                        "\"\n(" + url + ") could not be located.")
            write_to_log_and_or_console("Moving to next thread.\n")
            return
        soup = bs4.BeautifulSoup(res.text, "html.parser")
        thread_next_btn_anchors = soup.find_all('a', href=True, text='Next')

        if len(thread_next_btn_anchors) > 0 or thread_page_num > 0:
            # (if it's a MULTI-page thread ... note, second part of the above if
            #  statement is needed for the *last* page of the multi-page thread)
            thread_page_num += 1
            write_to_log_and_or_console("Searching for GIFs in \"" + thread_name_for_log +
                                        "\" PAGE " + str(thread_page_num) + " .......")
            final_thread_name = thread_name_for_file_names + "_PG" + str(thread_page_num)
            # (if it's the LAST page of multi-pg thread)
            if len(thread_next_btn_anchors) == 0:
                thread_next_button = False
        else:
            # (if it's a SINGLE-page thread)
            write_to_log_and_or_console("Searching for GIFs in \"" + thread_name_for_log +
                                        "\" .......")
            final_thread_name = thread_name_for_file_names
            thread_next_button = False

        # download all GIFs for this page
        process_gifs(soup, final_thread_name)

        TOTAL_THREAD_PAGES_SCRAPED += 1

        # if there are "Next" buttons, go to next page in thread
        if len(thread_next_btn_anchors) > 0:
            uri = thread_next_btn_anchors[0].get("href")


def process_gifs(page_soup, thread_name_for_file_names):
    global TOTAL_GIFS_DOWNLOADED
    gifs = page_soup.find_all("img", src=re.compile(r'\.gif$'))
    count = 0
    failed_downloads = []

    for gif in gifs:
        if str(gif).find("src=\"http") != -1:
            try:
                img_file = gif.get("src")
                file_rsrc = requests.get(img_file)
                file_rsrc.raise_for_status()
            except requests.exceptions.RequestException:
                if gif.get("src") not in failed_downloads:
                    write_to_log_and_or_console("ERROR: " + gif.get("src") +
                                                " had a problem downloading!")
                failed_downloads.append(str(gif.get("src")))
                # (w/o that "if" ^^ and the failed_downloads list:  was writing to log
                # multiple times for a given failed GIF on a given page)
                continue

            # remove protocol, then check to see if it's already in list
            # of used paths (ignore if it is), then also remove slashes
            img_file = img_file.replace("http://", "")
            img_file = img_file.replace("https://", "")
            # if GIF isn't already in the list of all saved GIFs.....
            if img_file not in ALL_SAVED_GIF_PATHS:
                # The above if-test was originally before the try statement, but that led to
                # situations where the only remaining gif on page was a previously used one, and
                # log file said "Maximum (X) GIFs already downloaded, (etc) ", where it shouldn't
                # have even considered that gif in the first place.
                # Moving it here did make script take a tad longer to run though
                if count > MAX_GIFS_PER_FORUM_PAGE - 1:
                    write_to_log_and_or_console("\tMaximum (" + str(MAX_GIFS_PER_FORUM_PAGE) +
                                                ") GIFs already downloaded for this page; "
                                                "moving to next page or thread...")
                    break
                img_file_name = img_file
                if save_file(thread_name_for_file_names, img_file_name, file_rsrc):
                    ALL_SAVED_GIF_PATHS.append(img_file)
                    count += 1
                    TOTAL_GIFS_DOWNLOADED += 1

    write_to_log_and_or_console("\t" + str(count) + " GIFs downloaded\n")


def save_file(thread_name_for_file_names, img_file_name, res):
    # replace characters which aren't alpha/num/dot/underscore with hyphen
    img_file_name = re.sub("[^0-9a-zA-Z._]", "-", img_file_name)
    img_file_name = thread_name_for_file_names + "__" + img_file_name

    # Seems that when path + file name (including "C:\") is > 259 characters, produces error
    # For almost all files tried so far, img_file_name was well under 150, but we'll limit it
    # to 130 just to be sure.
    if len(img_file_name) > 130:
        img_file_name = img_file_name.replace(img_file_name[120:], "_(...).gif")
    write_to_log_and_or_console("Downloading file: " + img_file_name)
    try:
        image_file = open(os.path.join(FOLDER_AND_LOG_NAME, img_file_name), "wb")
        for chunk in res.iter_content(100000):
            image_file.write(chunk)
        image_file.close()

        # Delete 0 KB sized filed (before, broken links sometimes caused 0 KB files to be downld)
        # TODO: figure out how to prevent the file being downloaded in the first place ^^
        if os.path.getsize(os.path.join(FOLDER_AND_LOG_NAME, img_file_name)) == 0:
            os.remove(os.path.join(FOLDER_AND_LOG_NAME, img_file_name))
            write_to_log_and_or_console("ERROR: GIF downloaded as a 0 KB file. Deleting file.")
            return False
        else:
            ALL_FILE_NAMES_SAVED.append(img_file_name)
            return True
    except:
        write_to_log_and_or_console("ERROR: " + img_file_name + " had a problem saving!")


def write_summary():
    write_to_log_and_or_console("---------------------------------")
    write_to_log_and_or_console("All GIF origin \"paths\" (sorted): ")
    write_to_log_and_or_console("---------------------------------")
    for path in sorted(ALL_SAVED_GIF_PATHS):
        write_to_log_and_or_console(path)

    write_to_log_and_or_console("\n--------------------------")
    write_to_log_and_or_console("All files saved (sorted): ")
    write_to_log_and_or_console("--------------------------")
    for name in sorted(ALL_FILE_NAMES_SAVED):
        write_to_log_and_or_console(name)

    write_to_log_and_or_console("\nTotal items in ALL_SAVED_GIF_PATHS list....." +
                                str(len(ALL_SAVED_GIF_PATHS)))
    write_to_log_and_or_console("Total GIFs downloaded....." +
                                str(TOTAL_GIFS_DOWNLOADED))
    write_to_log_and_or_console("Total thread-pages scraped....." +
                                str(TOTAL_THREAD_PAGES_SCRAPED))

    write_to_log_and_or_console("\nTotal time for script to run, in H:M:S....." +
                                str(datetime.now() - START_TIME))


def write_to_log_and_or_console(text):
    with open(FOLDER_AND_LOG_NAME + ".txt", "a") as text_file:
        text_file.write(text + "\n")
    print(text)


if __name__ == "__main__":
    INIT_SETUP_RESULT = initial_setup()
    process_forum(INIT_SETUP_RESULT[0], INIT_SETUP_RESULT[1])
    write_summary()
