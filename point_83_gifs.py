import os
import sys
import re
from datetime import datetime
import requests
import bs4


START_TIME = datetime.now()
FOLDER_AND_LOG_NAME = f"Point83GIFs_{START_TIME.strftime('%Y%m%d_%H%M')}"

MAX_GIFS_PER_FORUM_PAGE = (
    100  # max gifs per page; sometimes kept low just for debugging purposes
)

FORUM_PAGE_NUM = 0  # actual forum page number
ALL_SAVED_GIF_PATHS = []  # paths to GIFs downloaded, with "http" or "https" removed
ALL_FILE_NAMES_SAVED = (
    []
)  # names of files saved (start with name of thread where first found)
TOTAL_GIFS_DOWNLOADED = 0
TOTAL_THREAD_PGS_SCRAPED = 0


class Forum:
    def __init__(self, resp, max_forum_pgs_to_process) -> None:
        self.resp = resp
        self.max_forum_pgs_to_process = max_forum_pgs_to_process

    def process_forum(self):

        global FORUM_PAGE_NUM  # TEMP
        page_num = 1  # TEMP

        forum_next_button = True
        while forum_next_button:
            soup = bs4.BeautifulSoup(self.resp.text, "html.parser")
            viewtopic_anchors = soup.find_all("span", class_="blacklink")
            # forum_next_btn_anchors = soup.find_all("a", href=True, text="Next")
            forum_next_btn_anchors = soup.find_all("a", href=True, string="Next")

            write_to_log_and_or_console(
                f"------------------------\nFORUM PAGE {str(FORUM_PAGE_NUM)}"
            )
            write_to_log_and_or_console("------------------------\n")

            all_uris = []  # "viewtopic" part of URL of thread
            all_thread_names = []  # actual thread names
            for anchor in viewtopic_anchors:
                if str(anchor).find("viewtopic.php?t") != -1:
                    all_uris.append(
                        str(anchor)[
                            str(anchor).find("viewtopic") : str(anchor).find("&")
                        ]
                    )
                    all_thread_names.append(anchor.text)

            for i in range(len(all_uris)):
                thread = Thread(all_uris[i], all_thread_names[i])
                thread.process_thread()

            # go to next page (IF there is one)
            if len(forum_next_btn_anchors) > 0:
                url = f"http://www.point83.com/forum/{forum_next_btn_anchors[0].get('href')}"
                try:
                    self.resp = requests.get(url)
                    self.resp.raise_for_status()
                except requests.exceptions.RequestException:
                    write_to_log_and_or_console(
                        f"\n\nERROR:  URL for forum page number "
                        f"{str(FORUM_PAGE_NUM + 1)} ({url}) "
                        f"could not be located."
                    )
                    write_to_log_and_or_console("Exiting process.\n\n")
                    return
                page_num += 1
                FORUM_PAGE_NUM += 1
            else:
                forum_next_button = False

            if page_num > self.max_forum_pgs_to_process:
                forum_next_button = False


class Thread:

    def __init__(self, uri, thread_name):
        self.uri = uri
        self.thread_name = thread_name

    def process_thread(self):
        global TOTAL_THREAD_PGS_SCRAPED
        # remove all non-ascii characters:
        thread_name_for_log = re.sub(r"[^\x00-\x7f]", r"", self.thread_name).strip()

        # remove characters which aren't alpha/num/dot/underscore
        thread_name_for_file_names = re.sub(
            "[^0-9a-zA-Z._]", "", self.thread_name
        ).strip()

        thread_page_num = 0
        thread_next_button = True
        while thread_next_button:
            url = f"http://www.point83.com/forum/{self.uri}"
            try:
                res = requests.get(url)
                res.raise_for_status()
            except requests.exceptions.RequestException:
                write_to_log_and_or_console(
                    f'ERROR:  URL for thread "{thread_name_for_log}'
                    f'"\n({url}) could not be located.'
                )
                write_to_log_and_or_console("Moving to next thread.\n")
                return
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            # thread_next_btn_anchors = soup.find_all("a", href=True, text="Next")
            thread_next_btn_anchors = soup.find_all("a", href=True, string="Next")

            if len(thread_next_btn_anchors) > 0 or thread_page_num > 0:
                # (if it's a MULTI-page thread ... note, second part of the above if
                #  statement is needed for the *last* page of the multi-page thread)
                thread_page_num += 1
                write_to_log_and_or_console(
                    f'Searching for GIFs in "{thread_name_for_log}'
                    f'" PAGE {str(thread_page_num)} .......'
                )
                final_thread_name = (
                    thread_name_for_file_names + "_PG" + str(thread_page_num)
                )
                # (if it's the LAST page of multi-pg thread)
                if len(thread_next_btn_anchors) == 0:
                    thread_next_button = False
            else:
                # (if it's a SINGLE-page thread)
                write_to_log_and_or_console(
                    f'Searching for GIFs in "{thread_name_for_log}' f'" .......'
                )
                final_thread_name = thread_name_for_file_names
                thread_next_button = False

            # download all GIFs for this page
            page = Page(soup, final_thread_name)
            page.process_page()

            TOTAL_THREAD_PGS_SCRAPED += 1

            # if there are "Next" buttons, go to next page in thread
            if len(thread_next_btn_anchors) > 0:
                self.uri = thread_next_btn_anchors[0].get("href")


class Page:
    def __init__(self, soup, thread_name_for_file_names):
        self.soup = soup
        self.thread_name_for_file_names = thread_name_for_file_names
        self.gifs_downloaded = 0
        self.failed_downloads = []

    def process_page(self):
        global TOTAL_GIFS_DOWNLOADED
        gifs = self.soup.find_all("img", src=re.compile(r"\.gif$"))

        for gif in gifs:
            if str(gif).find('src="http') != -1:
                if not self._download_gif(gif):
                    continue

        write_to_log_and_or_console(f"\t{str(self.gifs_downloaded)} GIFs downloaded\n")

    def _download_gif(self, gif):
        global TOTAL_GIFS_DOWNLOADED

        try:
            img_file = gif.get("src")
            file_rsrc = requests.get(img_file)
            file_rsrc.raise_for_status()
        except requests.exceptions.RequestException:
            if gif.get("src") not in self.failed_downloads:
                write_to_log_and_or_console(
                    f"ERROR:  {gif.get('src')} had a problem downloading!"
                )
            self.failed_downloads.append(str(gif.get("src")))
            # (w/o that "if" ^^ and the failed_downloads list:  was writing to log
            # multiple times for a given failed GIF on a given page)
            return False

        # (w/o that "if" ^^ and the failed_downloads list:  was writing to log
        # multiple times for a given failed GIF on a given page)
        img_file = img_file.replace("http://", "")
        img_file = img_file.replace("https://", "")
        # if GIF isn't already in the list of all saved GIFs.....
        if img_file not in ALL_SAVED_GIF_PATHS:
            if self.gifs_downloaded > MAX_GIFS_PER_FORUM_PAGE - 1:
                write_to_log_and_or_console(
                    f"\tMaximum ({str(MAX_GIFS_PER_FORUM_PAGE)}) GIFs "
                    f"already downloaded for this page; moving to next "
                    f"page or thread..."
                )
                return False

            img_file_name = img_file
            if save_file(self.thread_name_for_file_names, img_file_name, file_rsrc):
                ALL_SAVED_GIF_PATHS.append(img_file)
                self.gifs_downloaded += 1
                TOTAL_GIFS_DOWNLOADED += 1
                return True

        return False


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
        res = requests.get(
            initial_url
        )  # "downloads" the web page; returns a response object
        res.raise_for_status()  # checks to see if download worked; raises exception if fail
    except requests.exceptions.RequestException as exception:
        print(f'ERROR:  URL "{initial_url}" could not be located.\n')
        print(exception)
        sys.exit()

    # Make folder to store downloaded GIFs in
    try:
        os.makedirs(FOLDER_AND_LOG_NAME, exist_ok=True)
    except OSError:
        print(f'ERROR:  folder "{FOLDER_AND_LOG_NAME}" could not be created.')
        sys.exit()

    return [res, max_forum_pgs_to_process]


def prompt_user_for_which_forum():
    print("************************")
    print("***** Point83 GIFs *****")
    print("************************")
    while True:
        print("\nSelect which forum to search for GIFs in:")
        print('Westlake Center:                     enter a "1".')
        print('Wrenches Gears Lawns and Routes:     enter a "2".')
        print('Point83 Navy:                        enter a "3".')
        user_input = input("Enter 1, 2, or 3:\n")

        if user_input == "1":
            return "http://www.point83.com/forum/viewforum.php?f=2"
        elif user_input == "2":
            return "http://www.point83.com/forum/viewforum.php?f=4"
        elif user_input == "3":
            return "http://www.point83.com/forum/viewforum.php?f=10"
        else:
            print("ERROR:  Invalid entry.")


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
            print("ERROR:  Invalid; enter an integer.")


def prompt_user_for_start_page():
    while True:
        print(
            "\nIf you want to start on an older page of this forum, enter its page number."
        )
        print("Otherwise, hit [Enter] for the default, page 1.")
        user_input = input("")
        if user_input == "":
            return 1
        try:
            val = int(user_input)
            return val
        except:
            print("ERROR:  Invalid; enter an integer.")


def save_file(thread_name_for_file_names, img_file_name, res):
    # replace characters which aren't alpha/num/dot/underscore with hyphen
    img_file_name = re.sub("[^0-9a-zA-Z._]", "-", img_file_name)
    img_file_name = thread_name_for_file_names + "__" + img_file_name

    # Seems that when path + file name (including "C:\") is > 259 characters, produces error
    # For almost all files tried so far, img_file_name was well under 150, but we'll limit it
    # to 130 just to be sure.
    if len(img_file_name) > 130:
        img_file_name = img_file_name.replace(img_file_name[120:], "_(...).gif")
    write_to_log_and_or_console(f"Downloading file: {img_file_name}")
    try:
        image_file = open(os.path.join(FOLDER_AND_LOG_NAME, img_file_name), "wb")
        for chunk in res.iter_content(100000):
            image_file.write(chunk)
        image_file.close()

        # Delete 0 KB sized filed (before, broken links sometimes caused 0 KB files to be downld)
        # TODO: figure out how to prevent the file being downloaded in the first place ^^
        if os.path.getsize(os.path.join(FOLDER_AND_LOG_NAME, img_file_name)) == 0:
            os.remove(os.path.join(FOLDER_AND_LOG_NAME, img_file_name))
            write_to_log_and_or_console(
                "ERROR:  GIF downloaded as a 0 KB file. Deleting file."
            )
            return False
        else:
            ALL_FILE_NAMES_SAVED.append(img_file_name)
            return True
    except:
        write_to_log_and_or_console(f"ERROR:  {img_file_name} had a problem saving!")


def write_summary():
    write_to_log_and_or_console("---------------------------------")
    write_to_log_and_or_console('All GIF origin "paths" (sorted): ')
    write_to_log_and_or_console("---------------------------------")
    for path in sorted(ALL_SAVED_GIF_PATHS):
        write_to_log_and_or_console(path)

    write_to_log_and_or_console("\n--------------------------")
    write_to_log_and_or_console("All files saved (sorted): ")
    write_to_log_and_or_console("--------------------------")
    for name in sorted(ALL_FILE_NAMES_SAVED):
        write_to_log_and_or_console(name)

    write_to_log_and_or_console(
        f"\nTotal items in ALL_SAVED_GIF_PATHS list....."
        f"{str(len(ALL_SAVED_GIF_PATHS))}"
    )
    write_to_log_and_or_console(
        f"Total GIFs downloaded....." f"{str(TOTAL_GIFS_DOWNLOADED)}"
    )
    write_to_log_and_or_console(
        f"Total thread-pages scraped....." f"{str(TOTAL_THREAD_PGS_SCRAPED)}"
    )

    write_to_log_and_or_console(
        f"\nTotal time for script to run, in H:M:S....."
        f"{str(datetime.now() - START_TIME)}"
    )


def write_to_log_and_or_console(text):
    with open(
        os.path.join(FOLDER_AND_LOG_NAME, (FOLDER_AND_LOG_NAME + ".txt")), "a"
    ) as text_file:
        text_file.write(text + "\n")
    print(text)


if __name__ == "__main__":
    resp, max_forum_pgs_to_process = initial_setup()
    forum = Forum(resp, max_forum_pgs_to_process)
    forum.process_forum()
    write_summary()
