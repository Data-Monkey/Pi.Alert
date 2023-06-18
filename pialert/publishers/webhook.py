"""
webhook integration
"""
import json
import subprocess

import conf
from const import logPath
from helper import noti_struc, write_file
from logger import logResult, mylog

#-------------------------------------------------------------------------------
def check_config():
    """ check all the required configuration parameters are set """
    if conf.WEBHOOK_URL == '':
        # pylint: disable-next=line-too-long
        mylog('none', ['[Check Config] Error: Webhook service not set up correctly. Check your pialert.conf WEBHOOK_* variables.'])
        return False
    else:
        return True

#-------------------------------------------------------------------------------

def send (msg: noti_struc):
    """ sending the message via webhook """

    # use data type based on specified payload type
    if conf.WEBHOOK_PAYLOAD == 'json':
        payload_data = msg.json
    if conf.WEBHOOK_PAYLOAD == 'html':
        payload_data = msg.html
    if conf.WEBHOOK_PAYLOAD == 'text':
        payload_data = to_text_message(msg.json, conf.INCLUDED_SECTIONS)

    # Define slack-compatible payload
    _json_payload = { "text": payload_data } if conf.WEBHOOK_PAYLOAD == 'text' else {
    "username": "Pi.Alert",
    "text": "There are new notifications",
    "attachments": [{
      "title": "Pi.Alert Notifications",
      "title_link": conf.REPORT_DASHBOARD_URL,
      "text": payload_data
    }]
    }

    # DEBUG - Write the json payload into a log file for debugging
    write_file (logPath + '/webhook_payload.json', json.dumps(_json_payload))

    # Using the Slack-Compatible Webhook endpoint for Discord
    # so that the same payload can be used for both

    if(conf.WEBHOOK_URL.startswith('https://discord.com/api/webhooks/') and
       not conf.WEBHOOK_URL.endswith("/slack")):
        webhook_url = f"{conf.WEBHOOK_URL}/slack"
        curl_params = ["curl","-i","-H",
                       "Content-Type:application/json" ,"-d",
                       json.dumps(_json_payload), webhook_url]
    else:
        webhook_url = conf.WEBHOOK_URL
        curl_params = ["curl","-i","-X", conf.WEBHOOK_REQUEST_METHOD ,"-H",
                       "Content-Type:application/json" ,"-d",
                       json.dumps(_json_payload), webhook_url]

    # execute CURL call
    try:
        # try runnning a subprocess
        mylog('debug', ['[send_webhook] curlParams: ', curl_params])
        process = subprocess.Popen(curl_params, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        stdout, stderr = process.communicate()

        # write stdout and stderr into .log files for debugging if needed
        logResult (stdout, stderr)     # TO-DO should be changed to mylog
    except subprocess.CalledProcessError as exception:
        # An error occured, handle it
        mylog('none', ['[send_webhook]', exception.output])





#-------------------------------------------------------------------------------
def to_text_message(_json, included_sections):
    """ 
    convert json to meaningfull text for webhook messages 
    based on list of sections to include in included_sections
    """

    text = ""
    if len(_json['internet']) > 0 and 'internet' in included_sections:
        text += "INTERNET\n"
        for event in _json['internet']:
            text += f'{event[3]} on {event[2]}. {event[4]}. New address: {event[1]}\n'
    # text += event[3] + ' on ' + event[2] +'. ' + event[4] +'. New address:' + event[1] + '\n'

    if len(_json['new_devices']) > 0 and 'new_devices' in included_sections:
        text += "NEW DEVICES:\n"
        for event in _json['new_devices']:
            if event[4] is None:
                event[4] = event[11]
            #text += event[1] + ' - ' + event[4] + '\n'
            text += f'{event[1]} - {event[4]}\n'

    if len(_json['down_devices']) > 0 and 'down_devices' in included_sections:
        write_file (logPath + '/down_devices_example.log', _json['down_devices'])
        text += 'DOWN DEVICES:\n'
        for event in _json['down_devices']:
            if event[4] is None:
                event[4] = event[11]
            # text += event[1] + ' - ' + event[4] + '\n'
            text += f'{event[1]} - {event[4]}\n'

    if len(_json['events']) > 0 and 'events' in included_sections:
        text += "EVENTS:\n"
        for event in _json['events']:
            if event[8] != "Internet":
                # text += event[8] + " on " + event[1] + " " + event[3] + " at " + event[2] + "\n"
                text += f'{event[8]} on {event[1]} {event[3]} at {event[2]}\n'

    return text
