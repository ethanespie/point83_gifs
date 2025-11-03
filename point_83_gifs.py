"""point_83_gifs.py

Simple scraper to find and download GIFs from point83.com forum threads.

Usage:
- Run the script and follow prompts to pick a forum, start page, and page count.
- GIFs and a log file are written to a timestamped folder.

This module defines:
- Scraper: holds run-time configuration and mutable state.
- Forum/Thread/Page: crawler classes that use a Scraper instance for shared state.
"""

import os
import sys
import re
from datetime import datetime
import requests
import bs4


class Scraper:
    """Orchestrates scraping: configuration, persistent state, logging, and I/O.

    Attributes:
        start_time (datetime): time when the scraper was instantiated.
        folder_and_log_name (str): directory name for saved GIFs and log.
        max_gifs_per_forum_page (int): per-page download cap.
        forum_page_num (int): current forum page number (mutable).
        all_saved_gif_paths (list): unique GIF source paths downloaded.
        all_file_names_saved (list): filenames saved on disk.
        total_gifs_downloaded (int): counter of successful downloads.
        total_thread_pgs_scraped (int): counter of processed thread pages.
    """

    def __init__(self, max_gifs_per_forum_page=100):
        self.start_time = datetime.now()
        self.folder_and_log_name = (
            f"Point83GIFs_{self.start_time.strftime('%Y%m%d_%H%M')}"
        )
        self.max_gifs_per_forum_page = max_gifs_per_forum_page

        # mutable state previously implemented as globals
        self.forum_page_num = 0
        self.all_saved_gif_paths = []
        self.all_file_names_saved = []
        self.total_gifs_downloaded = 0
        self.total_thread_pgs_scraped = 0

    # initial setup (was function)
    def initial_setup(self):
        """Perform initial prompts, validate the starting URL, and create output folder.

        Returns:
            tuple: (requests.Response, int) initial HTTP response and max forum pages to process.

        Exits the program on fatal errors (invalid start URL or folder creation failure).
        """
        initial_url = self.prompt_user_for_which_forum()
        start_page_num = self.prompt_user_for_start_page()
        self.forum_page_num = start_page_num
        max_forum_pgs_to_process = self.prompt_user_for_total_pages()

        if start_page_num != 1:
            index = (start_page_num - 1) * 30
            initial_url = initial_url + "&topicdays=0&start=" + str(index)

        try:
            res = requests.get(initial_url)
            res.raise_for_status()
        except requests.exceptions.RequestException as exception:
            print(f'ERROR:  URL "{initial_url}" could not be located.\n')
            print(exception)
            sys.exit()

        try:
            os.makedirs(self.folder_and_log_name, exist_ok=True)
        except OSError:
            print(f'ERROR:  folder "{self.folder_and_log_name}" could not be created.')
            sys.exit()

        return res, max_forum_pgs_to_process

    # prompt helpers (moved into class)
    def prompt_user_for_which_forum(self):
        """Prompt the user to select which forum to search.

        Returns:
            str: base URL for the selected forum.
        """
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

    def prompt_user_for_total_pages(self):
        """Prompt how many forum pages to process.

        Returns:
            int: number of pages to process (large default for 'all').
        """
        while True:
            print("\nHow many pages of the given forum do you want to process?")
            print("Hit [Enter] for the default (all pages).")
            user_input = input("")
            if user_input == "":
                return 1000000
            try:
                val = int(user_input)
                return val
            except ValueError:
                print("ERROR:  Invalid; enter an integer.")

    def prompt_user_for_start_page(self):
        """Prompt for start page number (allows resuming at older pages).

        Returns:
            int: starting forum page (1 by default).
        """
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
            except ValueError:
                print("ERROR:  Invalid; enter an integer.")

    # save_file now references instance attributes instead of globals
    def save_file(self, thread_name_for_file_names, img_file_name, res):
        """Save a downloaded GIF stream to disk.

        Parameters:
            thread_name_for_file_names (str): sanitized thread identifier used as filename prefix.
            img_file_name (str): original GIF path (sanitized before saving).
            res (requests.Response): response object containing GIF content.

        Returns:
            bool: True when save succeeded, False otherwise.
        """
        img_file_name = re.sub("[^0-9a-zA-Z._]", "-", img_file_name)
        img_file_name = thread_name_for_file_names + "__" + img_file_name

        if len(img_file_name) > 130:
            img_file_name = img_file_name.replace(img_file_name[120:], "_(...).gif")
        self.write_to_log_and_or_console(f"Downloading file: {img_file_name}")
        try:
            dest = os.path.join(self.folder_and_log_name, img_file_name)
            with open(dest, "wb") as image_file:
                for chunk in res.iter_content(100000):
                    image_file.write(chunk)

            try:
                size = os.path.getsize(dest)
            except OSError as e:
                # couldn't stat file
                self.write_to_log_and_or_console(
                    f"ERROR: cannot determine size of '{dest}': {e}"
                )
                return False

            if size == 0:
                try:
                    os.remove(dest)
                except OSError as e:
                    self.write_to_log_and_or_console(
                        f"WARNING: failed to remove zero-byte file '{dest}': {e}"
                    )
                self.write_to_log_and_or_console(
                    "ERROR:  GIF downloaded as a 0 KB file. Deleting file."
                )
                return False
            else:
                self.all_file_names_saved.append(img_file_name)
                return True
        except (OSError, IOError) as e:
            self.write_to_log_and_or_console(
                f"ERROR:  {img_file_name} had a problem saving: {e}"
            )
            return False

    # logging helper
    def write_to_log_and_or_console(self, text):
        """Append a line to the log file and also print it to stdout.

        The method falls back to console output when writing the log file fails.
        """
        log_path = os.path.join(
            self.folder_and_log_name, (self.folder_and_log_name + ".txt")
        )
        try:
            with open(log_path, "a", encoding="utf-8") as text_file:
                text_file.write(text + "\n")
        except (OSError, IOError) as e:
            # fallback: print to console with a note that file write failed
            print(f"(LOG WRITE FAILED: {e})")
            # still print the message so the user sees it
            print(text)
            return
        print(text)

    # write summary
    def write_summary(self):
        """Write a summary of all downloaded GIFs and script statistics to the log and console."""
        self.write_to_log_and_or_console("---------------------------------")
        self.write_to_log_and_or_console('All GIF origin "paths" (sorted): ')
        self.write_to_log_and_or_console("---------------------------------")
        for path in sorted(self.all_saved_gif_paths):
            self.write_to_log_and_or_console(path)

        self.write_to_log_and_or_console("\n--------------------------")
        self.write_to_log_and_or_console("All files saved (sorted): ")
        self.write_to_log_and_or_console("--------------------------")
        for name in sorted(self.all_file_names_saved):
            self.write_to_log_and_or_console(name)

        self.write_to_log_and_or_console(
            f"\nTotal items in ALL_SAVED_GIF_PATHS list....."
            f"{str(len(self.all_saved_gif_paths))}"
        )
        self.write_to_log_and_or_console(
            f"Total GIFs downloaded....." f"{str(self.total_gifs_downloaded)}"
        )
        self.write_to_log_and_or_console(
            f"Total thread-pages scraped....." f"{str(self.total_thread_pgs_scraped)}"
        )

        self.write_to_log_and_or_console(
            f"\nTotal time for script to run, in H:M:S....."
            f"{str(datetime.now() - self.start_time)}"
        )

    # main runner
    def run(self):
        """Execute the full scraping run: setup, process forum pages, and write summary."""
        res, max_forum_pgs_to_process = self.initial_setup()
        forum = Forum(res, max_forum_pgs_to_process, self)
        forum.process_forum()
        self.write_summary()


class Forum:
    """Represents a forum index page and iterates threads within it.

    The Forum instance does not hold global state itself; it references a Scraper
    instance for shared configuration and counters.
    """

    def __init__(self, resp, max_forum_pgs_to_process, scraper: Scraper) -> None:
        self.resp = resp
        self.max_forum_pgs_to_process = max_forum_pgs_to_process
        self.scraper = scraper

    def process_forum(self):
        """Process the current forum page: find thread URIs, instantiate Thread objects,
        and follow 'Next' links until the configured page limit is reached.
        """
        page_num = 1

        forum_next_button = True
        while forum_next_button:
            soup = bs4.BeautifulSoup(self.resp.text, "html.parser")
            viewtopic_anchors = soup.find_all("span", class_="blacklink")
            forum_next_btn_anchors = soup.find_all("a", href=True, string="Next")

            self.scraper.write_to_log_and_or_console(
                f"------------------------\nFORUM PAGE {str(self.scraper.forum_page_num)}"
            )
            self.scraper.write_to_log_and_or_console("------------------------\n")

            all_uris = []
            all_thread_names = []
            for anchor in viewtopic_anchors:
                if str(anchor).find("viewtopic.php?t") != -1:
                    all_uris.append(
                        str(anchor)[
                            str(anchor).find("viewtopic") : str(anchor).find("&")
                        ]
                    )
                    all_thread_names.append(anchor.text)

            for i in range(len(all_uris)):
                thread = Thread(all_uris[i], all_thread_names[i], self.scraper)
                thread.process_thread()

            # go to next page (IF there is one)
            if len(forum_next_btn_anchors) > 0:
                url = f"http://www.point83.com/forum/{forum_next_btn_anchors[0].get('href')}"
                try:
                    self.resp = requests.get(url)
                    self.resp.raise_for_status()
                except requests.exceptions.RequestException:
                    self.scraper.write_to_log_and_or_console(
                        f"\n\nERROR:  URL for forum page number "
                        f"{str(self.scraper.forum_page_num + 1)} ({url}) "
                        f"could not be located."
                    )
                    self.scraper.write_to_log_and_or_console("Exiting process.\n\n")
                    return
                page_num += 1
                self.scraper.forum_page_num += 1
            else:
                forum_next_button = False

            if page_num > self.max_forum_pgs_to_process:
                forum_next_button = False


class Thread:
    """Represents a forum thread and iterates its pages to find GIFs.

    It uses the Scraper instance for logging and to record downloaded items.
    """

    def __init__(self, uri, thread_name, scraper: Scraper):
        self.uri = uri
        self.thread_name = thread_name
        self.scraper = scraper

    def process_thread(self):
        """Visit each page in the thread (follows 'Next') and spawn Page objects to download GIFs."""
        # remove all non-ascii characters:
        thread_name_for_log = re.sub(r"[^\x00-\x7f]", r"", self.thread_name).strip()

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
                self.scraper.write_to_log_and_or_console(
                    f'ERROR:  URL for thread "{thread_name_for_log}'
                    f'"\n({url}) could not be located.'
                )
                self.scraper.write_to_log_and_or_console("Moving to next thread.\n")
                return
            soup = bs4.BeautifulSoup(res.text, "html.parser")
            thread_next_btn_anchors = soup.find_all("a", href=True, string="Next")

            if len(thread_next_btn_anchors) > 0 or thread_page_num > 0:
                # (if it's a MULTI-page thread ... note, second part of the above if
                #  statement is needed for the *last* page of the multi-page thread)
                thread_page_num += 1
                self.scraper.write_to_log_and_or_console(
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
                self.scraper.write_to_log_and_or_console(
                    f'Searching for GIFs in "{thread_name_for_log}' f'" .......'
                )
                final_thread_name = thread_name_for_file_names
                thread_next_button = False

            # download all GIFs for this page
            page = Page(soup, final_thread_name, self.scraper)
            page.process_page()

            self.scraper.total_thread_pgs_scraped += 1

            # if there are "Next" buttons, go to next page in thread
            if len(thread_next_btn_anchors) > 0:
                self.uri = thread_next_btn_anchors[0].get("href")


class Page:
    """Processes a single thread page: finds GIF image tags and downloads unique GIFs."""

    def __init__(self, soup, thread_name_for_file_names, scraper: Scraper):
        self.soup = soup
        self.thread_name_for_file_names = thread_name_for_file_names
        self.gifs_downloaded = 0
        self.failed_downloads = []
        self.scraper = scraper

    def process_page(self):
        """Find GIF <img> elements on the provided BeautifulSoup page and attempt downloads."""
        gifs = self.soup.find_all("img", src=re.compile(r"\.gif$"))

        for gif in gifs:
            if str(gif).find('src="http') != -1:
                if not self._download_gif(gif):
                    continue

        self.scraper.write_to_log_and_or_console(
            f"\t{str(self.gifs_downloaded)} GIFs downloaded\n"
        )

    def _download_gif(self, gif):
        """Download a single GIF given an <img> tag and save it via the Scraper.

        Returns:
            bool: True if the GIF was downloaded and recorded, False otherwise.
        """
        try:
            img_file = gif.get("src")
            file_rsrc = requests.get(img_file)
            file_rsrc.raise_for_status()
        except requests.exceptions.RequestException:
            if gif.get("src") not in self.failed_downloads:
                self.scraper.write_to_log_and_or_console(
                    f"ERROR:  {gif.get('src')} had a problem downloading!"
                )
            self.failed_downloads.append(str(gif.get("src")))
            return False

        img_file = img_file.replace("http://", "").replace("https://", "")
        if img_file not in self.scraper.all_saved_gif_paths:
            if self.gifs_downloaded > self.scraper.max_gifs_per_forum_page - 1:
                self.scraper.write_to_log_and_or_console(
                    f"\tMaximum ({str(self.scraper.max_gifs_per_forum_page)}) GIFs "
                    f"already downloaded for this page; moving to next "
                    f"page or thread..."
                )
                return False

            img_file_name = img_file
            if self.scraper.save_file(
                self.thread_name_for_file_names, img_file_name, file_rsrc
            ):
                self.scraper.all_saved_gif_paths.append(img_file)
                self.gifs_downloaded += 1
                self.scraper.total_gifs_downloaded += 1
                return True

        return False


if __name__ == "__main__":
    scraper = Scraper()
    scraper.run()
