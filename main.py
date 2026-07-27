from curseforge import CurseforgeUnauthorized, CurseforgeAuthorized, download_mod_link
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from argparse import ArgumentParser
from zipfile import ZipFile
from logger import get_logger
from shutil import copy2

import asyncio
import logging
import time
import json
import sys
import os

DEBUG = False
DOWNLOAD_THREADS=10

logger = get_logger()


async def download_mods(
    manifest,
    out_dir,
    api_key: str | None
) -> list[tuple[str, None] | tuple[None, Exception, str, str]]:
    logger.info("Start downloading mods")

    cf = CurseforgeUnauthorized() if api_key is None else CurseforgeAuthorized(api_key)
    files = manifest["files"]

    retry_counters: dict[str, int] = {}
    results: list[tuple[str, None] | tuple[None, Exception, str, str]] = []

    progress = logger.createProgress(len(files))

    def submit_one(executor: ThreadPoolExecutor, pid, fid):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(executor, cf.download_file, pid, fid, out_dir)

    with ThreadPoolExecutor(max_workers=DOWNLOAD_THREADS) as executor:
        pending: set[asyncio.Future] = set()

        for file in files:
            pid = file["projectID"]
            fid = file["fileID"]
            pending.add(submit_one(executor, pid, fid))

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

            retry: list[asyncio.Future] = []

            for fut in done:
                result = fut.result()
                # result: (ok_path, None) OR (None, exc, pid, fid)

                if result[1] is None:
                    results.append(result)
                    progress.progress = len(results)
                    progress.render()
                    continue

                _, err, pid, fid = result
                retry_counters[pid] = retry_counters.get(pid, 0) + 1

                if retry_counters[pid] > 2:
                    results.append(result)
                    progress.progress = len(results)
                    progress.render()
                    continue

                logger.info("[projectID: %s] Retrying... %d" % (pid, retry_counters[pid]))
                await asyncio.sleep(1)

                retry.append(submit_one(executor, pid, fid))

            for f in retry:
                pending.add(f)

    
    progress.progress = progress.maxProgress
    progress.render()
    return results


def extract_overrides(zf: ZipFile, dest: str):
    logger.info("Start extracting overrides folder")
    # merge overrides with modpack folder
    try:
        with TemporaryDirectory() as temp_dir:
            for info in zf.filelist:
                if not info.filename.startswith("overrides/") or info.is_dir():
                    continue
                
                extract_tmp_path = os.path.join(temp_dir, info.filename[10:]) # len("overrides/") = 10
                extract_path = os.path.join(dest, info.filename[10:])

                # extract file to tmp
                os.makedirs(os.path.dirname(extract_tmp_path), exist_ok=True)
                with open(extract_tmp_path, "wb") as f:
                    f.write(zf.read(info))

                # copy to dest
                os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                copy2(extract_tmp_path, extract_path)
        
        logger.info("overrides folder sucessfull extracted")

    except KeyError as e:
        logger.info("overrides folder not found. Skip")
        pass # pass, if overrides does't exists


async def main(modpack_filepath):
    if not os.path.exists(modpack_filepath):
        logger.error("Path %s does not exists!" % modpack_filepath)
        exit()

    name = os.path.splitext(modpack_filepath)[0]
    name = os.path.basename(name)
    modpack_dir = 'modpacks/' + name
    os.makedirs(modpack_dir, exist_ok=True)

    # logger.info("Extracting %s to folder %s" % (name, modpack_dir))
    
    # if not os.path.exists(modpack_dir):
    #     with ZipFile(modpack_filepath, 'r') as zf:
    #         zf.extractall(modpack_dir)

    mods_dir = os.path.join(modpack_dir, 'mods')
    os.makedirs(mods_dir, exist_ok=True)

    logger.info("Loading manifest")
    with ZipFile(modpack_filepath, 'r') as zf:
        try:
            manifest_json = zf.read('manifest.json')
        except KeyError as e:
            logger.error(e)
            exit()
        manifest = json.loads(manifest_json)


        logger.info(
            "Modpack info:\n" +
            "  Modpack Name:      %s\n" % manifest["name"] +
            "  Modpack Version:   %s\n" % manifest["version"] +
            "  Author:            %s\n" % manifest["author"] +
            "  Minecraft Version: %s\n" % manifest["minecraft"]["version"]
        )


        with ThreadPoolExecutor() as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                download_mods(manifest, mods_dir, None),
                loop.run_in_executor(executor, extract_overrides, zf, modpack_dir)
            ]
            res_mods, _ = await asyncio.gather(*tasks)

        err_mods = [r for r in res_mods if r[1]]
        if len(err_mods):
            logger.info(
                "This mods has errors:\n" +
                "\n".join([
                    "  Error: %s\n" % str(r[1]) +
                    "  Download Link: %s" % download_mod_link(r[2], r[3])
                    for r in err_mods
                ])
            )

    for filename in os.listdir(mods_dir):
        if not filename.endswith(".zip"): continue
        mod_path = os.path.join(mods_dir, filename)
        
        dest = None
        with ZipFile(mod_path) as zf:
            for info in zf.filelist:
                
                if info.filename.startswith("shaders/"):
                    dest = os.path.join(modpack_dir, "shaderpacks", filename)
                    break
                if info.filename == "pack.mcmeta":
                    dest = os.path.join(modpack_dir, "resourcepacks", filename)
                    break
                dest = None

            if dest is None:
                logger.warning("Unknown ZIP file: " + mod_path)

        if os.path.exists(dest): os.remove(dest)
        if dest:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.rename(mod_path, dest)


    logger.info("Modpack loaded!")


parser = ArgumentParser("Forge Modpack Downloader")
parser.add_argument("modpack", help=".zip file of modpack")
parser.add_argument("-t", "--threads", default=10, type=int, help="count of threads using for downloading a modpack")
parser.add_argument("--debug", action='store_true', help="activate debug mode")

if __name__ == "__main__":
    res = parser.parse_args(sys.argv[1:])

    DEBUG = res.debug
    DOWNLOAD_THREADS = res.threads

    if DEBUG:
        logger.LOGGER.setLevel(logging.DEBUG)
        logger.warning("DEBUG is active")

    asyncio.run(main(res.modpack))