"""Overleaf Client"""
##################################################
# MIT License
##################################################
# File: olclient.py
# Description: Overleaf API Wrapper
# Author: Moritz Glöckl (fixes by Donzhu2020)
# License: MIT
# Version: 1.2.1
##################################################

import requests as reqs
from bs4 import BeautifulSoup
import json
import uuid
import re
import html
from pathlib import Path

# Where to get the CSRF Token and where to send the login request to
LOGIN_URL = "https://www.overleaf.com/login"
PROJECT_URL = "https://www.overleaf.com/project"       # The dashboard URL
DOWNLOAD_URL = "https://www.overleaf.com/project/{}/download/zip"   # Download all files as zip
UPLOAD_URL = "https://www.overleaf.com/project/{}/upload"           # Upload files
FOLDER_URL = "https://www.overleaf.com/project/{}/folder"           # Create folders
DELETE_URL = "https://www.overleaf.com/project/{}/doc/{}"           # Delete files
COMPILE_URL = "https://www.overleaf.com/project/{}/compile?enable_pdf_caching=true"
BASE_URL = "https://www.overleaf.com"

PATH_SEP = "/"  # Hardcoded for cross-platform compatibility


class OverleafClient:
    """
    Overleaf API Wrapper.
    Supports login, querying projects, downloading, uploading, and deleting files.
    """

    # ------------------------------------------------------------------ #
    # Static helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def filter_projects(json_content, more_attrs=None):
        """Yield active (non-archived, non-trashed) projects matching extra attrs."""
        more_attrs = more_attrs or {}
        for p in json_content:
            if not p.get("archived") and not p.get("trashed"):
                if all(p.get(k) == v for k, v in more_attrs.items()):
                    yield p

    @staticmethod
    def _find_projects_by_bracket_scan(text):
        """
        Robustly extract the projects JSON array from raw HTML text using
        a bracket-counting approach.  Returns the parsed list or raises.
        """
        for marker in ('&quot;projects&quot;:[', '"projects":['):
            start_pos = text.find(marker)
            if start_pos == -1:
                continue
            start_index = start_pos + len(marker) - 1  # position of '['
            bracket_count = 0
            end_index = -1
            for i in range(start_index, len(text)):
                if text[i] == '[':
                    bracket_count += 1
                elif text[i] == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_index = i + 1
                        break
            if end_index != -1:
                return json.loads(html.unescape(text[start_index:end_index]))
        raise AttributeError(
            "Could not find the projects array in the page (bracket scan failed)."
        )

    # ------------------------------------------------------------------ #
    # Construction / auth
    # ------------------------------------------------------------------ #

    def __init__(self, cookie=None, csrf=None):
        self._cookie = cookie   # Authenticated session cookie
        self._csrf = csrf       # CSRF token required for mutating requests

        # Shared requests.Session for connection reuse & automatic cookie jar
        self._session = reqs.Session()
        if cookie:
            # cookie may be a dict (from olbrowserlogin) or a RequestsCookieJar
            self._session.cookies.update(cookie)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def all_projects(self):
        """
        Return all active (non-archived, non-trashed) projects.
        Tries three extraction strategies in order:
          1. <meta name="ol-projects"> tag
          2. Bracket-count scan for ``"projects":[...]``
          3. Inline ``<script>`` containing ``preloadedProjects``
        """
        r = self._session.get(PROJECT_URL, cookies=self._cookie)
        r.raise_for_status()

        soup = BeautifulSoup(r.content, 'html.parser')

        # Strategy 1 – meta tag (older Overleaf versions)
        meta = soup.find('meta', {'name': 'ol-projects'})
        if meta:
            json_content = json.loads(meta.get('content'))
            return list(self.filter_projects(json_content))

        # Strategy 2 – bracket scan on raw HTML
        try:
            json_content = self._find_projects_by_bracket_scan(r.text)
            return list(self.filter_projects(json_content))
        except AttributeError:
            pass

        # Strategy 3 – inline <script> with preloadedProjects
        script_tag = soup.find('script', string=re.compile(r'preloadedProjects'))
        if script_tag:
            match = re.search(
                r'preloadedProjects\s*=\s*(\[.*?\]);',
                script_tag.string,
                re.DOTALL,
            )
            if match:
                json_content = json.loads(match.group(1))
                return list(self.filter_projects(json_content))
            raise AttributeError("Found preloadedProjects script but could not parse JSON.")

        # Hint at auth failure before giving up
        if "Log In" in r.text or "Sign Up" in r.text or "login" in r.url:
            raise PermissionError(
                "Authentication failed. Your cookie may be expired."
            )
        raise AttributeError(
            "Could not find project list via ol-projects, projects array, or preloadedProjects."
        )

    def get_project(self, project_name):
        """Return the first active project whose name matches *project_name*, or None."""
        return next(
            (p for p in self.all_projects() if p['name'] == project_name),
            None,
        )

    def download_project(self, project_id):
        """Download project as a zip archive and return raw bytes."""
        r = self._session.get(
            DOWNLOAD_URL.format(project_id),
            stream=True,
            cookies=self._cookie,
        )
        r.raise_for_status()
        return r.content

    def get_project_infos(self, project_id):
        """
        Fetch detailed project structure (folder tree, doc ids, …) via HTTP.
        Raises ConnectionError on non-200 responses.
        """
        r = self._session.get(
            "{}/project/{}/project_infos".format(BASE_URL, project_id),
            cookies=self._cookie,
        )
        if r.status_code == 200:
            return r.json()
        raise ConnectionError(
            "Failed to fetch project info. HTTP status: {}".format(r.status_code)
        )

    def create_folder(self, project_id, parent_folder_id, folder_name):
        """
        Create a folder inside *parent_folder_id*.
        Returns the new folder dict, or None if it already exists (HTTP 400).
        Raises requests.HTTPError for other failure codes.
        """
        headers = {"X-Csrf-Token": self._csrf}
        params = {"parent_folder_id": parent_folder_id, "name": folder_name}
        r = self._session.post(
            FOLDER_URL.format(project_id),
            cookies=self._cookie,
            headers=headers,
            json=params,
        )
        if r.ok:
            return r.json()
        if r.status_code == 400:   # FIX: was str(400) – int comparison is correct
            return None            # Folder already exists
        r.raise_for_status()       # FIX: was raise reqs.HTTPError() with no message

    def upload_file(self, project_id, project_infos, file_name, file_size, file):
        """
        Upload *file* to the appropriate folder inside *project_id*.
        Returns True on success, False on failure.

        FIX: status_code is an int, not a string – was `== str(200)`.
        FIX: use r.json() instead of json.loads(r.content).
        """
        folder_id = project_infos['rootFolder'][0]['_id']

        # Navigate / create nested folders when file_name contains path separators
        if PATH_SEP in file_name:
            local_folders = file_name.split(PATH_SEP)[:-1]
            current_overleaf_folder = project_infos['rootFolder'][0]['folders']

            for local_folder in local_folders:
                exists_on_remote = False
                for remote_folder in current_overleaf_folder:
                    if local_folder.lower() == remote_folder['name'].lower():
                        exists_on_remote = True
                        folder_id = remote_folder['_id']
                        current_overleaf_folder = remote_folder['folders']
                        break
                if not exists_on_remote:
                    new_folder = self.create_folder(project_id, folder_id, local_folder)
                    if new_folder:  # FIX: guard against None (already-exists case)
                        current_overleaf_folder.append(new_folder)
                        folder_id = new_folder['_id']
                        current_overleaf_folder = new_folder['folders']

        params = {
            "folder_id": folder_id,
            "_csrf": self._csrf,
            "qquuid": str(uuid.uuid4()),
            "qqfilename": file_name,
            "qqtotalfilesize": file_size,
        }
        r = self._session.post(
            UPLOAD_URL.format(project_id),
            cookies=self._cookie,
            params=params,
            files={"qqfile": file},
        )
        # FIX: r.status_code is an int, not a string
        return r.status_code == 200 and r.json().get("success", False)

    def delete_file(self, project_id, project_infos, file_name):
        """
        Delete *file_name* from *project_id*.
        Returns True on success, False when the file is not found.

        FIX: status_code is an int, not a string – was `== str(204)`.
        FIX: nested path lookup was checking the wrong file name (used the full
             path instead of just the basename when scanning docs).
        """
        file = None

        if PATH_SEP in file_name:
            parts = file_name.split(PATH_SEP)
            local_folders = parts[:-1]
            base_name = parts[-1]          # FIX: capture the actual file basename
            current_overleaf_folder = project_infos['rootFolder'][0]['folders']

            for local_folder in local_folders:
                for remote_folder in current_overleaf_folder:
                    if local_folder.lower() == remote_folder['name'].lower():
                        # FIX: search docs in the matched remote_folder, not a
                        #      previous level, and use base_name not file_name
                        file = next(
                            (v for v in remote_folder['docs']
                             if v['name'] == base_name),
                            None,
                        )
                        current_overleaf_folder = remote_folder['folders']
                        break
        else:
            file = next(
                (v for v in project_infos['rootFolder'][0]['docs']
                 if v['name'] == file_name),
                None,
            )

        if file is None:
            return False

        headers = {"X-Csrf-Token": self._csrf}
        r = self._session.delete(
            DELETE_URL.format(project_id, file['_id']),
            cookies=self._cookie,
            headers=headers,
            json={},
        )
        # FIX: r.status_code is an int, not a string
        return r.status_code == 204

    def download_pdf(self, project_id):
        """
        Compile the project and return (filename, bytes) of the output PDF.
        Returns None if the compile step succeeds but produces no PDF.
        Raises requests.HTTPError on HTTP or compile failure.

        FIX: use r.json() instead of json.loads(r.content).
        FIX: raise informative error when compile status is not "success".
        """
        headers = {"X-Csrf-Token": self._csrf}
        body = {
            "check": "silent",
            "draft": False,
            "incrementalCompilesEnabled": True,
            "rootDoc_id": "",
            "stopOnFirstError": False,
        }
        r = self._session.post(
            COMPILE_URL.format(project_id),
            cookies=self._cookie,
            headers=headers,
            json=body,
        )
        r.raise_for_status()

        compile_result = r.json()      # FIX: was json.loads(r.content)
        if compile_result.get("status") != "success":
            raise reqs.HTTPError(
                "Compile failed with status: {}".format(compile_result.get("status"))
            )

        # Find the first PDF in the output files
        pdf_file = next(
            (v for v in compile_result.get('outputFiles', []) if v['type'] == 'pdf'),
            None,
        )
        if pdf_file is None:
            return None

        dl = self._session.get(
            BASE_URL + pdf_file['url'],
            cookies=self._cookie,
            headers=headers,
        )
        dl.raise_for_status()
        return pdf_file['path'], dl.content
