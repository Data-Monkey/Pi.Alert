"""
pushsafer platform integration
"""
import requests


import conf
from helper import  noti_struc
from logger import mylog

#-------------------------------------------------------------------------------
def check_config():
    """ check all the required configuration parameters are set """
    if conf.PUSHSAFER_TOKEN == 'ApiKey':
        # pylint: disable-next=line-too-long
        mylog('none', ['[Check Config] Error: Pushsafer service not set up correctly. Check your pialert.conf PUSHSAFER_TOKEN variable.'])
        return False
    else:
        return True

#-------------------------------------------------------------------------------
def send ( msg:noti_struc ):
    """ sending the message to pushsafer """

    url = 'https://www.pushsafer.com/api'
    post_fields = {
        "t" : 'Pi.Alert Message',
        "m" : msg.text,
        "s" : 11,
        "v" : 3,
        "i" : 148,
        "c" : '#ef7f7f',
        "d" : 'a',
        "u" : conf.REPORT_DASHBOARD_URL,
        "ut" : 'Open Pi.Alert',
        "k" : conf.PUSHSAFER_TOKEN,
        }

    try:
        requests.post(url=url, data=post_fields, timeout=10)

    except requests.exceptions.RequestException as exception:
        mylog('none', ['[PUSHSAFER] Error: ', exception])
        return -1

    return 0
