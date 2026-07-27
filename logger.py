import logging
import sys

CLEAR = "\r\033[2K"
FORMAT = '[%(asctime)s] %(levelname)s: %(message)s'
logging.basicConfig(level=logging.INFO, format=FORMAT)
logger = logging.getLogger()

class Progress:
  name = ""
  symbolProgress = "█"
  symbolEmpty = " "
  pattern = "{name} |{bar}| {precent:.2f}% {progress}/{maxProgress}"

  maxProgress = 100
  progress = 0
  length = 100

  def __init__(self):
    pass

  def render(self):
    filled = max(0, min(round(self.length / self.maxProgress * self.progress), self.length))
    text = self.pattern.format_map({
      "name": self.name,
      "bar": self.symbolProgress * filled + self.symbolEmpty * (self.length - filled),
      "precent": (100 / self.maxProgress * self.progress),
      "progress": self.progress,
      "maxProgress": self.maxProgress
    })
    sys.stdout.write(CLEAR + text + "\r")
    sys.stdout.flush()


_instance = None
def get_logger():
    global _instance
    if _instance is None:
        _instance = Logger()
    return _instance


class Logger:
  progress: Progress = None
  LOGGER = logger

  def info(self, msg: object, *args: object):
    if self.progress:
      sys.stdout.write(CLEAR)
      sys.stdout.flush()
    self.LOGGER.info(msg, *args)
    if self.progress:
      self.progress.render()

  def error(self, msg: object, *args: object):
    if self.progress:
      sys.stdout.write(CLEAR)
      sys.stdout.flush()
    self.LOGGER.error(msg, *args)
    if self.progress:
      self.progress.render()

  def warning(self, msg: object, *args: object):
    if self.progress:
      sys.stdout.write(CLEAR)
      sys.stdout.flush()
    self.LOGGER.warning(msg, *args)
    if self.progress:
      self.progress.render()

  def debug(self, msg: object, *args: object):
    if self.progress:
      sys.stdout.write(CLEAR)
      sys.stdout.flush()
    self.LOGGER.debug(msg, *args)
    if self.progress:
      self.progress.render()

  def createProgress(self, size: int = 100):
    p = self.progress = Progress()
    p.maxProgress = size
    return p