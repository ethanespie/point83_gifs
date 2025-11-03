"""Unit tests for point_83_gifs module.

These tests exercise user-prompt logic, file I/O helpers, initial setup behavior,
and the Forum/Thread/Page download flow. Network and user input are mocked so
tests run deterministically and without real I/O.
"""
import os
import point_83_gifs as mod


class _FakePageResponse:
    """A minimal fake response object providing .text and raise_for_status().

    Used to simulate HTML page responses in tests without real network calls.
    """

    def __init__(self, text=""):
        self.text = text

    def raise_for_status(self):
        return None


class _FakeGifResponse:
    """A fake response that yields given byte chunks from iter_content().

    Used to simulate streaming GIF responses for save_file tests.
    """

    def __init__(self, chunks):
        self._chunks = list(chunks)

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=65536):
        for c in self._chunks:
            yield c


def test_prompt_user_for_which_forum(monkeypatch):
    inputs = iter(["x", "1"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    s = mod.Scraper()
    url = s.prompt_user_for_which_forum()
    assert "viewforum.php?f=2" in url


def test_prompt_user_for_total_pages_default_and_number(monkeypatch):
    # default
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    s = mod.Scraper()
    assert s.prompt_user_for_total_pages() == 1000000

    # explicit number
    monkeypatch.setattr("builtins.input", lambda prompt="": "5")
    assert s.prompt_user_for_total_pages() == 5


def test_prompt_user_for_start_page_default_and_number(monkeypatch):
    # default
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    s = mod.Scraper()
    assert s.prompt_user_for_start_page() == 1

    # explicit number
    monkeypatch.setattr("builtins.input", lambda prompt="": "3")
    assert s.prompt_user_for_start_page() == 3


def test_write_to_log_and_or_console_and_write_summary(tmp_path):
    s = mod.Scraper()
    # point folder to tmp_path to avoid polluting cwd
    s.folder_and_log_name = str(tmp_path / "out")
    os.makedirs(s.folder_and_log_name, exist_ok=True)

    s.write_to_log_and_or_console("hello world")
    log_file = os.path.join(s.folder_and_log_name, s.folder_and_log_name + ".txt")
    # log file path uses folder name + ".txt" per implementation
    assert os.path.exists(log_file)
    with open(log_file, "r", encoding="utf-8") as fh:
        contents = fh.read()
    assert "hello world" in contents

    # populate some state and call summary
    s.all_saved_gif_paths = ["a.gif", "b.gif"]
    s.all_file_names_saved = ["a__one.gif", "b__two.gif"]
    s.total_gifs_downloaded = 2
    s.total_thread_pgs_scraped = 1
    s.write_summary()
    with open(log_file, "r", encoding="utf-8") as fh:
        contents = fh.read()
    assert "All GIF origin" in contents
    assert "Total GIFs downloaded" in contents


def test_save_file_success_and_zero_byte(tmp_path):
    s = mod.Scraper()
    s.folder_and_log_name = str(tmp_path / "out2")
    os.makedirs(s.folder_and_log_name, exist_ok=True)

    # success case: one chunk
    gif_resp = _FakeGifResponse([b"data"])
    ok = s.save_file("threadname", "image.gif", gif_resp)
    assert ok is True
    saved_files = os.listdir(s.folder_and_log_name)
    # expect at least the gif file and a log file
    assert any(name.endswith(".gif") for name in saved_files)

    # zero-byte case: no chunks -> file removed and False returned
    gif_resp_empty = _FakeGifResponse([])
    ok2 = s.save_file("threadname", "image2.gif", gif_resp_empty)
    assert ok2 is False
    # no leftover zero-byte file with that name
    assert not any("image2.gif" in name for name in os.listdir(s.folder_and_log_name))


def test_initial_setup_creates_folder_and_returns_response(monkeypatch, tmp_path):
    s = mod.Scraper()
    # force the scraper to use a temp folder so os.makedirs writes there
    s.folder_and_log_name = str(tmp_path / "created")

    monkeypatch.setattr(
        s, "prompt_user_for_which_forum", lambda: "http://example.com/forum"
    )
    monkeypatch.setattr(s, "prompt_user_for_start_page", lambda: 1)
    monkeypatch.setattr(s, "prompt_user_for_total_pages", lambda: 2)

    def fake_get(url, *args, **kwargs):
        return _FakePageResponse("<html></html>")

    monkeypatch.setattr(mod.requests, "get", fake_get)
    res, max_pages = s.initial_setup()
    assert isinstance(res, _FakePageResponse)
    assert max_pages == 2
    assert os.path.isdir(s.folder_and_log_name)


def test_forum_process_creates_thread_objects(monkeypatch, tmp_path):
    s = mod.Scraper()
    s.folder_and_log_name = str(tmp_path / "forum_out")
    os.makedirs(s.folder_and_log_name, exist_ok=True)

    # create a forum page with one thread anchor; anchor must include '&' so slicing behaves
    # like original code
    forum_html = (
        '<span class="blacklink"><a href="viewtopic.php?t=123&start=0">T</a></span>'
    )
    resp = _FakePageResponse(forum_html)

    # replace Thread with a dummy that records calls
    recorded = []

    class DummyThread:
        def __init__(self, uri, name, scraper):
            recorded.append((uri, name, scraper is s))

        def process_thread(self):
            recorded.append("processed")

    monkeypatch.setattr(mod, "Thread", DummyThread)
    # ensure requests.get won't be called by process_forum (forum uses resp passed in)
    forum = mod.Forum(resp, max_forum_pgs_to_process=1, scraper=s)
    forum.process_forum()
    assert any("processed" == item for item in recorded)
    # check that created dummy saw the expected uri slice beginning with 'viewtopic'
    assert any(r[0].startswith("viewtopic") for r in recorded if isinstance(r, tuple))


def test_thread_and_page_download_flow(monkeypatch, tmp_path):
    s = mod.Scraper()
    s.folder_and_log_name = str(tmp_path / "thread_out")
    os.makedirs(s.folder_and_log_name, exist_ok=True)

    # thread page HTML contains one gif img and no "Next" link
    page_html = (
        '<html><body><img src="http://cdn.example.com/img/test.gif"></body></html>'
    )

    def fake_get(url, *args, **kwargs):
        # return a page for thread URLs, gif bytes for .gif URLs
        if url.endswith(".gif"):
            return _FakeGifResponse([b"GIFDATA"])
        else:
            return _FakePageResponse(page_html)

    monkeypatch.setattr(mod.requests, "get", fake_get)

    # uri expected by Thread.process_thread (it will prefix with the forum path)
    uri = "viewtopic.php?t=1&start=0"
    thread = mod.Thread(uri, "ThreadName", s)
    thread.process_thread()

    # after processing, scraper should have recorded a saved file and count increment
    assert s.total_gifs_downloaded >= 1
    assert any(name.endswith(".gif") for name in os.listdir(s.folder_and_log_name))
