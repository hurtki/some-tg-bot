import logging, sys


# конфиг логгера 
logging.basicConfig(
    level=logging.INFO,  
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,  # to stdout 
)
logger = logging.getLogger(__name__)