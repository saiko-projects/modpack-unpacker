from http.client import HTTPResponse
from urllib.request import urlopen
from urllib.parse import urlparse, unquote
from tempfile import TemporaryDirectory
from shutil import copy2

from logger import get_logger

import asyncio
import hashlib
import json
import os

logger = get_logger()

class HashMismatchError(Exception):
    def __init__(self, *args, loaded_hash, orig_hash):
        super().__init__(*args)
        self.loaded_hash = loaded_hash
        self.orig_hash = orig_hash


def download_mod_link(project_id: str, file_id: str):
    cf = CurseforgeUnauthorized()
    return cf.API_URI + 'mods/%d/files/%d/download' % (project_id, file_id)


class Curseforge:
    async def download_url(self, project_id: str, file_id: str): pass
    async def file_info(self, project_id: str, file_id: str): pass
    async def download_file(self, project_id: str, file_id: str, dest_dir: str): pass


class CurseforgeAuthorized(Curseforge):
    def __init__(self, api_key: str):
        pass

    async def download_url(self, project_id: str, file_id: str) -> str | None:
        pass
    
    async def file_info(self, project_id: str, file_id: str):
        pass
    
    async def download_file(self, project_id: str, file_id: str, dest_dir: str) -> list[tuple[str, None] | tuple[str | None, Exception, str, str]]:
        pass

class CurseforgeUnauthorized(Curseforge):
    def __init__(self):
        self.API_URI = 'https://www.curseforge.com/api/v1/'
        pass

    def download_file(self, project_id: str, file_id: str, dest_dir: str):
        url = self.API_URI + "mods/%d/files/%d/download" % (project_id, file_id)

        logger.debug("[projectID: %d] Resolving download url..." % project_id)

        try:
            res: HTTPResponse # urllib returns a type depending on the protocol, but by default, it returns an alias of type Any
            with urlopen(url, timeout=60) as res:

                # After redirects from /download, you reached cdn url with filename
                res_url = res.url
                parsed_url = urlparse(res_url)
                path = unquote(parsed_url.path)
                filename = os.path.basename(path)
                dest = os.path.normpath(os.path.join(dest_dir, filename))

                if os.path.exists(dest):
                    logger.debug("CACHED %s (without hashsum)" % dest)
                    return dest, None

                logger.debug("[projectID: %d] Downloading file %s to %s" % (project_id, res_url, dest))
                
                with TemporaryDirectory() as tmp_folder:
                    tmp_dest = os.path.join(tmp_folder, filename)
                    
                    with open(tmp_dest, 'wb') as f:
                        f.write(res.read())
                    copy2(tmp_dest, dest)
                
                return dest, None
        except Exception as err:
            logger.error("[projectID: %d] Error \"%s\"" % (project_id, str(err)))
            return None, err, project_id, file_id
