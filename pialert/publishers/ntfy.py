"""
ntfy platform integration
"""
from base64 import b64encode
import requests

import conf

from logger import mylog
from helper import noti_struc

#-------------------------------------------------------------------------------
def check_config():
    """ check all the required configuration parameters are set """
    if conf.NTFY_HOST == '' or conf.NTFY_TOPIC == '':
        # pylint: disable-next=line-too-long
        mylog('none', ['[Check Config] Error: NTFY service not set up correctly. Check your pialert.conf NTFY_* variables.'])
        return False
    else:
        return True

#-------------------------------------------------------------------------------
def send  (msg: noti_struc):
    """ sending the message to ntfy """

    headers = {
        "Title": "Pi.Alert Notification",
        "Actions": "view, Open Dashboard, "+ conf.REPORT_DASHBOARD_URL,
        "Priority": "urgent",
        "Tags": "warning"
    }
    # if username and password are set generate hash and update header
    if conf.NTFY_USER != "" and conf.NTFY_PASSWORD != "":
	# Generate hash for basic auth
        # usernamepassword = "{}:{}".format(conf.NTFY_USER,conf.NTFY_PASSWORD)
        basichash = b64encode(bytes(conf.NTFY_USER + ':' +
                                    conf.NTFY_PASSWORD, "utf-8")).decode("ascii")

	# add authorization header with hash
        headers["Authorization"] = f'Basic {basichash}'

    try:
        requests.post(url=f'{conf.NTFY_HOST}/{conf.NTFY_TOPIC}',
                      data=msg.text,
                      headers=headers,
                      timeout=10)
    except requests.exceptions.RequestException as exception:
        mylog('none', ['[NTFY] Error: ', exception])
        return -1

    return 0
