import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")

with app.setup:
    from typing import Callable, Optional, Dict, List, Any, Union
    import marimo as mo
    import pandas as pd
    import requests
    import certifi
    import base64
    import time
    import uuid
    import sys
    import os
    import io


@app.cell
def _():
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    from src.utils.load_all_dotenv import (
        load_all_dotenv,
    )

    try:
        load_all_dotenv(os.path.join(parent_dir, "config"), verbose=True)
    except:  # noqa: E722
        load_all_dotenv("config", verbose=True)
    return


@app.cell
def _():
    ted_api_key = os.getenv("TED_API_KEY")
    print(ted_api_key[:5] + "...")
    return (ted_api_key,)


@app.cell
def _():
    # test_urls = [
    #     "https://ted.europa.eu/en/notice/336432-2025/xml",
    #     "https://ted.europa.eu/en/notice/175791-2026/xml",
    #     "https://ted.europa.eu/en/notice/275481-2026/xml",
    #     "https://ted.europa.eu/en/notice/357555-2026/xml",
    #     "https://ted.europa.eu/en/notice/116649-2025/xml",
    #     "https://ted.europa.eu/en/notice/115491-2025/xml",
    # ]
    return


@app.cell
def _():
    test_urls = [
        "https://ted.europa.eu/en/notice/175791-2026/xml",
        "https://ted.europa.eu/en/notice/357555-2026/xml",
        "https://ted.europa.eu/en/notice/275481-2026/xml",
        "https://ted.europa.eu/en/notice/533963-2025/xml",
        "https://ted.europa.eu/en/notice/364945-2026/xml",
        "https://ted.europa.eu/en/notice/854481-2025/xml",
        "https://ted.europa.eu/en/notice/336432-2025/xml",
        "https://ted.europa.eu/en/notice/772623-2025/xml",
        "https://ted.europa.eu/en/notice/356026-2026/xml",
        # "https://ted.europa.eu/en/notice/331119-2025/xml",
        # "https://ted.europa.eu/en/notice/238545-2026/xml",
        # "https://ted.europa.eu/en/notice/225932-2026/xml",
        # "https://ted.europa.eu/en/notice/242135-2026/xml",
        # "https://ted.europa.eu/en/notice/711219-2025/xml",
        # "https://ted.europa.eu/en/notice/613069-2025/xml",
        # "https://ted.europa.eu/en/notice/707453-2025/xml",
        # "https://ted.europa.eu/en/notice/161307-2026/xml",
        # "https://ted.europa.eu/en/notice/696009-2025/xml",
        # "https://ted.europa.eu/en/notice/248979-2026/xml",
        # "https://ted.europa.eu/en/notice/349959-2026/xml",
        # "https://ted.europa.eu/en/notice/752707-2025/xml",
        # "https://ted.europa.eu/en/notice/326608-2026/xml",
        # "https://ted.europa.eu/en/notice/116208-2026/xml",
        # "https://ted.europa.eu/en/notice/814719-2025/xml",
        # "https://ted.europa.eu/en/notice/331377-2026/xml",
        # "https://ted.europa.eu/en/notice/845578-2025/xml",
        # "https://ted.europa.eu/en/notice/376054-2026/xml",
        # "https://ted.europa.eu/en/notice/341520-2026/xml",
        # "https://ted.europa.eu/en/notice/812483-2025/xml",
        # "https://ted.europa.eu/en/notice/72827-2026/xml",
    ]
    return (test_urls,)


@app.cell
def _():
    lang = "en"
    output_format = "PDF"
    return


@app.cell
def _(ted_api_key, test_urls):
    notice_xmls = render_notices_sequential(urls=test_urls, api_key=ted_api_key)
    notice_xmls
    return


@app.cell
def _():
    # notice_xmls_dl = download_files(urls=test_urls)
    # notice_xmls_dl
    return


@app.cell
def _():
    # notice_xmls[0].__dict__
    return


@app.cell
def _():
    # notice_xmls[0]._content
    return


@app.cell
def _():
    def _ensure_base64(notice):
        """Return the notice as a base64 ASCII string, encoding it first if it isn't already base64."""
        raw = notice.encode() if isinstance(notice, str) else notice
        try:
            if base64.b64encode(base64.b64decode(raw, validate=True)) == raw:
                return raw.decode("ascii")  # already base64
        except ValueError:
            pass  # not base64 -> fall through and encode
        return base64.b64encode(raw).decode("ascii")


    def render_notices(
        notices,
        language,
        output_format,
        api_key,
        summary=False,
        base_url="https://api.ted.europa.eu",
        timeout=60,
    ):
        """POST each notice to /v3/notices/render.

        Returns a list (one item per notice, in order) of requests.Response,
        or the raised RequestException if that notice's call failed.
        """
        url = f"{base_url.rstrip('/')}/v3/notices/render"
        results = []
        with requests.Session() as session:
            session.headers.update(
                {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
            )
            for notice in notices:
                payload = {
                    "file": _ensure_base64(notice),
                    "language": language,
                    "format": output_format,
                    "summary": summary,
                }
                try:
                    results.append(session.post(url, json=payload, timeout=timeout))
                except requests.RequestException as exc:
                    results.append(exc)
        return results


    def render_notices_async(
        notices,
        language,
        output_format,
        callback_url,
        api_key,
        summary=False,
        base_url="https://api.ted.europa.eu",
        timeout=60,
        download_results=False,
        download_wait=5,
        download_timeout=None,
    ):
        """POST each notice to /v3/notices/render-async.

        The rendered notice is delivered by TED to the callback URL. callback_url may be a
        single string (reused for every notice) or a list matching notices one-to-one.

        By default returns a list (one item per notice, in order) of the acknowledgement
        requests.Response, or the raised RequestException if that notice's POST failed.

        If download_results is True, after all POSTs are sent it waits download_wait seconds
        (default 5, adjustable), then GETs each callback URL and returns the downloaded
        responses in the list instead of the acknowledgement ones.
        """
        url = f"{base_url.rstrip('/')}/v3/notices/render-async"

        if isinstance(callback_url, (list, tuple)):
            callbacks = list(callback_url)
            if len(callbacks) != len(notices):
                raise ValueError(
                    "callback_url list length must match the number of notices"
                )
        else:
            callbacks = [callback_url] * len(notices)

        results = []
        with requests.Session() as session:
            session.headers.update(
                {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
            )
            for notice, cb in zip(notices, callbacks):
                payload = {
                    "file": _ensure_base64(notice),
                    "language": language,
                    "format": output_format,
                    "summary": summary,
                    "callbackUrl": cb,
                }
                try:
                    results.append(session.post(url, json=payload, timeout=timeout))
                except requests.RequestException as exc:
                    results.append(exc)

        if download_results:
            time.sleep(download_wait)
            downloaded = []
            with (
                requests.Session() as dl_session
            ):  # separate session: no TED auth header sent to your callback host
                for cb in callbacks:
                    try:
                        downloaded.append(
                            dl_session.get(
                                cb,
                                timeout=download_timeout
                                if download_timeout is not None
                                else timeout,
                            )
                        )
                    except requests.RequestException as exc:
                        downloaded.append(exc)
            results = downloaded

        return results

    return render_notices, render_notices_async


@app.function
def download_files(urls, timeout=30.0):
    _results = []
    with mo.status.progress_bar(
        total=len(urls),
        title="Downloading files",
        remove_on_exit=True,
    ) as _bar:
        for _url in urls:
            try:
                _resp = requests.get(
                    _url, timeout=timeout, verify=certifi.where()
                )
                _resp.raise_for_status()
                print(_resp.raise_for_status())
                _results.append(_resp.content)
                print(_resp.content)
            except Exception as _exc:
                print(f"Failed {_url}: {_exc}")
                _results.append(None)
            _bar.update()
    return _results


@app.cell
def _(render_notices, render_notices_async):
    def download_notice_xmls(urls, timeout=30.0, retry_waits=(2, 3, 4)):
        _results = []
        with (
            requests.Session() as _session,
            mo.status.progress_bar(
                total=len(urls),
                title="Downloading notices",
                remove_on_exit=True,
            ) as _bar,
        ):
            for _url in urls:
                _content = None
                for _wait in (0, *retry_waits):  # immediate try, then 2s, 3s, 4s
                    if _wait:
                        time.sleep(_wait)
                    try:
                        _resp = _session.get(
                            _url, timeout=timeout, verify=certifi.where()
                        )
                        if _resp.status_code == 202:
                            continue  # under processing -> wait and retry
                        _resp.raise_for_status()
                        print(_resp.raise_for_status())
                        _content = _resp.content
                        print(_content)
                        break
                    except requests.RequestException as _exc:
                        print(f"Failed {_url}: {_exc}")
                _results.append(_content)
                _bar.update()
        return _results


    def render_notices_from_urls(
        urls,
        api_key,
        language="en",
        output_format="PDF",
        summary=False,
        base_url="https://api.ted.europa.eu",
        timeout=60,
        download_timeout=30.0,
    ):
        """Download each XML URL first, then render only the ones that downloaded.

        Returns a list aligned with `urls`: a render Response per URL, or None where the
        download failed after all retries.
        """
        _xmls = download_notice_xmls(urls, timeout=download_timeout)
        _valid = [(_i, _xml) for _i, _xml in enumerate(_xmls) if _xml is not None]
        _rendered = render_notices(
            [_xml for _i, _xml in _valid],
            language,
            output_format,
            api_key,
            summary=summary,
            base_url=base_url,
            timeout=timeout,
        )
        _results = [None] * len(urls)
        for (_i, _xml), _resp in zip(_valid, _rendered):
            _results[_i] = _resp._content
        return _results


    def render_notices_async_from_urls(
        urls,
        api_key,
        callback_url,
        language="en",
        output_format="PDF",
        summary=False,
        base_url="https://api.ted.europa.eu",
        timeout=60,
        download_timeout=30.0,
        download_results=False,
        download_wait=5,
        download_timeout_cb=None,
    ):
        """Download each XML URL first, then async-render only the ones that downloaded.

        Returns a list aligned with `urls`: an async Response (or downloaded result, if
        download_results is True) per URL, or None where the download failed after all retries.
        """
        _xmls = download_notice_xmls(urls, timeout=download_timeout)
        _valid = [(_i, _xml) for _i, _xml in enumerate(_xmls) if _xml is not None]

        if isinstance(callback_url, (list, tuple)):
            _callbacks = [
                callback_url[_i] for _i, _xml in _valid
            ]  # keep callbacks aligned to surviving notices
        else:
            _callbacks = callback_url

        _rendered = render_notices_async(
            [_xml for _i, _xml in _valid],
            language,
            output_format,
            _callbacks,
            api_key,
            summary=summary,
            base_url=base_url,
            timeout=timeout,
            download_results=download_results,
            download_wait=download_wait,
            download_timeout=download_timeout_cb,
        )
        _results = [None] * len(urls)
        for (_i, _xml), _resp in zip(_valid, _rendered):
            _results[_i] = _resp
        return _results

    return


@app.function
def render_notices_sequential(
    urls,
    api_key,
    language="en",
    output_format="PDF",
    summary=False,
    base_url="https://api.ted.europa.eu",
    timeout=60,
    download_timeout=30.0,
    retry_waits=(1, 2, 3),
):
    """Download then render each URL one at a time, logging both steps per file.

    Returns a list aligned with `urls`: the render response content (bytes) per URL,
    or None where the download failed after all retries or the render call failed.
    """

    def _ensure_base64(notice):
        """Return the notice as a base64 ASCII string, encoding it first if it isn't already base64."""
        raw = notice.encode() if isinstance(notice, str) else notice
        try:
            if base64.b64encode(base64.b64decode(raw, validate=True)) == raw:
                return raw.decode("ascii")  # already base64
        except ValueError:
            pass  # not base64 -> fall through and encode
        return base64.b64encode(raw).decode("ascii")

    _render_url = f"{base_url.rstrip('/')}/v3/notices/render"
    _render_headers = {
        "Authorization": f"Bearer {api_key}"
    }  # POST-only, not sent on download GET
    _results = [None] * len(urls)
    with (
        requests.Session() as _session,
        mo.status.progress_bar(
            total=len(urls),
            title="Processing notices",
            remove_on_exit=True,
        ) as _bar,
    ):
        _session.headers.update({"Connection": "close"})  # Added session close
        for _i, _url in enumerate(urls):
            # ---- download ----
            _bar.update(increment=0, subtitle=f"Downloading {_url}")
            _xml = None
            for _wait in (0, *retry_waits):  # immediate try, then 1s, 2s, 3s
                if _wait:
                    time.sleep(_wait)
                try:
                    _resp = _session.get(
                        _url, timeout=download_timeout, verify=certifi.where()
                    )
                    if _resp.status_code == 202:
                        continue  # under processing -> wait and retry
                    _resp.raise_for_status()
                    _xml = _resp.content
                    break
                except requests.RequestException as _exc:
                    print(f"Download failed {_url}: {_exc}")

            # ---- render ----
            if _xml is None:
                print(f"Skipped {_url} (download failed)")
            else:
                _bar.update(increment=0, subtitle=f"Rendering {_url}")
                _payload = {
                    "file": _ensure_base64(_xml),
                    "language": language,
                    "format": output_format,
                    "summary": summary,
                }
                try:
                    _render_resp = _session.post(
                        _render_url,
                        json=_payload,
                        headers=_render_headers,
                        timeout=timeout,
                    )
                    _render_resp.raise_for_status()
                    _results[_i] = _render_resp.content
                except requests.RequestException as _exc:
                    print(f"Render failed {_url}: {_exc}")

            _bar.update()  # advance one file (runs for every URL, success or skip)
    return _results


if __name__ == "__main__":
    app.run()
