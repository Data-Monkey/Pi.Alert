

import datetime
import json

import socket

import subprocess
import requests
from json2table import convert

# pialert modules
import conf
from const import pialertPath, logPath, apiPath
from helper import noti_struc, generate_mac_links, removeDuplicateNewLines, timeNow, hide_email,  updateState, get_file_content, write_file
from logger import logResult, mylog, print_log


from publishers.email import (check_config as email_check_config, 
                              send as send_email )
from publishers.ntfy  import (check_config as ntfy_check_config,
                              send as send_ntfy )
from publishers.apprise import (check_config as apprise_check_config,
                                send as send_apprise) 
from publishers.webhook import (check_config as webhook_check_config,
                                send as send_webhook) 
from publishers.pushsafer import (check_config as pushsafer_check_config,
                                send as send_pushsafer) 
from publishers.mqtt import (check_config as mqtt_check_config,
                             mqtt_start )


#===============================================================================
# REPORTING
#===============================================================================
# create a json for webhook and mqtt notifications to provide further integration options


json_final = []


#-------------------------------------------------------------------------------
def construct_notifications(db, sqlQuery, tableTitle, skipText = False, suppliedJsonStruct = None):

    if suppliedJsonStruct is None and sqlQuery == "":
        return noti_struc("", "", "")

    table_attributes = {"style" : "border-collapse: collapse; font-size: 12px; color:#70707", "width" : "100%", "cellspacing" : 0, "cellpadding" : "3px", "bordercolor" : "#C0C0C0", "border":"1"}
    headerProps = "width='120px' style='color:blue; font-size: 16px;' bgcolor='#909090' "
    thProps = "width='120px' style='color:#F0F0F0' bgcolor='#909090' "

    build_direction = "TOP_TO_BOTTOM"
    text_line = '{}\t{}\n'

    if suppliedJsonStruct is None:
        json_struc = db.get_table_as_json(sqlQuery)
    else:
        json_struc = suppliedJsonStruct

    jsn  = json_struc.json
    html = ""
    text = ""

    if len(jsn["data"]) > 0:
        text = tableTitle + "\n---------\n"

        # Convert a JSON into an HTML table
        html = convert(jsn, build_direction=build_direction, table_attributes=table_attributes)
        
        # Cleanup the generated HTML table notification
        html = format_table(html, "data", headerProps, tableTitle).replace('<ul>','<ul style="list-style:none;padding-left:0">').replace("<td>null</td>", "<td></td>")

        headers = json_struc.columnNames

        # prepare text-only message
        if skipText == False:

            for device in jsn["data"]:
                for header in headers:
                    padding = ""
                    if len(header) < 4:
                        padding = "\t"
                    text += text_line.format ( header + ': ' + padding, device[header])
                text += '\n'

        #  Format HTML table headers
        for header in headers:
            html = format_table(html, header, thProps)

    return noti_struc(jsn, text, html)




def send_notifications (db):

    sql = db.sql  #TO-DO
    global mail_text, mail_html, json_final, changedPorts_json_struc, partial_html, partial_txt, partial_json

    deviceUrl              = conf.REPORT_DASHBOARD_URL + '/deviceDetails.php?mac='
    plugins_report         = False

    # Reporting section
    mylog('verbose', ['[Notification] Check if something to report'])

    # prepare variables for JSON construction
    json_internet = []
    json_new_devices = []
    json_down_devices = []
    json_events = []
    json_ports = []
    json_plugins = []

    # Disable reporting on events for devices where reporting is disabled based on the MAC address
    sql.execute ("""UPDATE Events SET eve_PendingAlertEmail = 0
                    WHERE eve_PendingAlertEmail = 1 AND eve_EventType != 'Device Down' AND eve_MAC IN
                        (
                            SELECT dev_MAC FROM Devices WHERE dev_AlertEvents = 0
						)""")
    sql.execute ("""UPDATE Events SET eve_PendingAlertEmail = 0
                    WHERE eve_PendingAlertEmail = 1 AND eve_EventType = 'Device Down' AND eve_MAC IN
                        (
                            SELECT dev_MAC FROM Devices WHERE dev_AlertDeviceDown = 0
						)""")

    # Open text Template
    mylog('verbose', ['[Notification] Open text Template'])
    template_file = open(pialertPath + '/back/report_template.txt', 'r')
    mail_text = template_file.read()
    template_file.close()

    # Open html Template
    mylog('verbose', ['[Notification] Open html Template'])
    template_file = open(pialertPath + '/back/report_template.html', 'r')
    if conf.newVersionAvailable :
        template_file = open(pialertPath + '/back/report_template_new_version.html', 'r')

    mail_html = template_file.read()
    template_file.close()

    # Report Header & footer
    timeFormated = timeNow().strftime ('%Y-%m-%d %H:%M')
    mail_text = mail_text.replace ('<REPORT_DATE>', timeFormated)
    mail_html = mail_html.replace ('<REPORT_DATE>', timeFormated)

    mail_text = mail_text.replace ('<SERVER_NAME>', socket.gethostname() )
    mail_html = mail_html.replace ('<SERVER_NAME>', socket.gethostname() )

    mylog('verbose', ['[Notification] included sections: ', conf.INCLUDED_SECTIONS ])

    if 'internet' in conf.INCLUDED_SECTIONS :
        # Compose Internet Section
        sqlQuery = """SELECT eve_MAC as MAC,  eve_IP as IP, eve_DateTime as Datetime, eve_EventType as "Event Type", eve_AdditionalInfo as "More info" FROM Events
                        WHERE eve_PendingAlertEmail = 1 AND eve_MAC = 'Internet'
                        ORDER BY eve_DateTime"""

        notiStruc = construct_notifications(db, sqlQuery, "Internet IP change")

        # collect "internet" (IP changes) for the webhook json
        json_internet = notiStruc.json["data"]

        mail_text = mail_text.replace ('<SECTION_INTERNET>', notiStruc.text + '\n')
        mail_html = mail_html.replace ('<INTERNET_TABLE>', notiStruc.html)
        mylog('verbose', ['[Notification] Internet sections done.'])

    if 'new_devices' in conf.INCLUDED_SECTIONS :
        # Compose New Devices Section
        sqlQuery = """SELECT eve_MAC as MAC, eve_DateTime as Datetime, dev_LastIP as IP, eve_EventType as "Event Type", dev_Name as "Device name", dev_Comments as Comments  FROM Events_Devices
                        WHERE eve_PendingAlertEmail = 1
                        AND eve_EventType = 'New Device'
                        ORDER BY eve_DateTime"""

        notiStruc = construct_notifications(db, sqlQuery, "New devices")

        # collect "new_devices" for the webhook json
        json_new_devices = notiStruc.json["data"]

        mail_text = mail_text.replace ('<SECTION_NEW_DEVICES>', notiStruc.text + '\n')
        mail_html = mail_html.replace ('<NEW_DEVICES_TABLE>', notiStruc.html)
        mylog('verbose', ['[Notification] New Devices sections done.'])

    if 'down_devices' in conf.INCLUDED_SECTIONS :
        # Compose Devices Down Section
        sqlQuery = """SELECT eve_MAC as MAC, eve_DateTime as Datetime, dev_LastIP as IP, eve_EventType as "Event Type", dev_Name as "Device name", dev_Comments as Comments  FROM Events_Devices
                        WHERE eve_PendingAlertEmail = 1
                        AND eve_EventType = 'Device Down'
                        ORDER BY eve_DateTime"""

        notiStruc = construct_notifications(db, sqlQuery, "Down devices")

        # collect "new_devices" for the webhook json
        json_down_devices = notiStruc.json["data"]

        mail_text = mail_text.replace ('<SECTION_DEVICES_DOWN>', notiStruc.text + '\n')
        mail_html = mail_html.replace ('<DOWN_DEVICES_TABLE>', notiStruc.html)
        mylog('verbose', ['[Notification] Down Devices sections done.'])

    if 'events' in conf.INCLUDED_SECTIONS :
        # Compose Events Section
        sqlQuery = """SELECT eve_MAC as MAC, eve_DateTime as Datetime, dev_LastIP as IP, eve_EventType as "Event Type", dev_Name as "Device name", dev_Comments as Comments  FROM Events_Devices
                        WHERE eve_PendingAlertEmail = 1
                        AND eve_EventType IN ('Connected','Disconnected',
                            'IP Changed')
                        ORDER BY eve_DateTime"""

        notiStruc = construct_notifications(db, sqlQuery, "Events")

        # collect "events" for the webhook json
        json_events = notiStruc.json["data"]

        mail_text = mail_text.replace ('<SECTION_EVENTS>', notiStruc.text + '\n')
        mail_html = mail_html.replace ('<EVENTS_TABLE>', notiStruc.html)
        mylog('verbose', ['[Notification] Events sections done.'])

    if 'ports' in conf.INCLUDED_SECTIONS :
        # collect "ports" for the webhook json
        mylog('verbose', ['[Notification] Ports: conf.changedPorts_json_struc:', conf.changedPorts_json_struc])
        if conf.changedPorts_json_struc is not None:
            json_ports =  conf.changedPorts_json_struc.json["data"]

        notiStruc = construct_notifications(db, "", "Ports", True, conf.changedPorts_json_struc)
        mylog('verbose', ['[Notification] Ports: notiStruc:', notiStruc ])
        mail_html = mail_html.replace ('<PORTS_TABLE>', notiStruc.html)

        portsTxt = ""
        if conf.changedPorts_json_struc is not None:
            portsTxt = "Ports \n---------\n Ports changed! Check PiAlert for details!\n"

        mail_text = mail_text.replace ('<PORTS_TABLE>', portsTxt )
        mylog('verbose', ['[Notification] Ports sections done.'])    

    if 'plugins' in conf.INCLUDED_SECTIONS and conf.ENABLE_PLUGINS:
        # Compose Plugins Section
        sqlQuery = """SELECT Plugin, Object_PrimaryId, Object_SecondaryId, DateTimeChanged, Watched_Value1, Watched_Value2, Watched_Value3, Watched_Value4, Status from Plugins_Events"""

        notiStruc = construct_notifications(db, sqlQuery, "Plugins")

        # collect "plugins" for the webhook json
        json_plugins = notiStruc.json["data"]

        mail_text = mail_text.replace ('<PLUGINS_TABLE>', notiStruc.text + '\n')
        mail_html = mail_html.replace ('<PLUGINS_TABLE>', notiStruc.html)

        # check if we need to report something
        plugins_report = len(json_plugins) > 0
        mylog('verbose', ['[Notification] Plugins sections done.'])

    json_final = {
                    "internet": json_internet,
                    "new_devices": json_new_devices,
                    "down_devices": json_down_devices,
                    "events": json_events,
                    "ports": json_ports,
                    "plugins": json_plugins,
                    }

    mail_text = removeDuplicateNewLines(mail_text)

    # Create clickable MAC links
    mail_html = generate_mac_links (mail_html, deviceUrl)

    #  Write output emails for debug
    write_file (logPath + '/report_output.json', json.dumps(json_final))
    write_file (logPath + '/report_output.txt', mail_text)
    write_file (logPath + '/report_output.html', mail_html)

    # Send Mail
    if json_internet != [] or json_new_devices != [] or json_down_devices != [] or json_events != [] or json_ports != [] or conf.debug_force_notification or plugins_report:

        mylog('none', ['[Notification] Changes detected, sending reports'])

        msg = noti_struc(json_final, mail_text, mail_html)

        mylog('info', ['[Notification] Udateing API files'])
        send_api()

        if conf.REPORT_MAIL and check_config('email'):
            updateState(db,"Send: Email")
            mylog('info', ['[Notification] Sending report by Email'])
            send_email (msg )
        else :
            mylog('verbose', ['[Notification] Skip email'])
        if conf.REPORT_APPRISE and check_config('apprise'):
            updateState(db,"Send: Apprise")
            mylog('info', ['[Notification] Sending report by Apprise'])
            send_apprise (msg)
        else :
            mylog('verbose', ['[Notification] Skip Apprise'])
        if conf.REPORT_WEBHOOK and check_config('webhook'):
            updateState(db,"Send: Webhook")
            mylog('info', ['[Notification] Sending report by Webhook'])
            send_webhook (msg)
        else :
            mylog('verbose', ['[Notification] Skip webhook'])
        if conf.REPORT_NTFY and check_config('ntfy'):
            updateState(db,"Send: NTFY")
            mylog('info', ['[Notification] Sending report by NTFY'])
            send_ntfy (msg)
        else :
            mylog('verbose', ['[Notification] Skip NTFY'])
        if conf.REPORT_PUSHSAFER and check_config('pushsafer'):
            updateState(db,"Send: PUSHSAFER")
            mylog('info', ['[Notification] Sending report by PUSHSAFER'])
            send_pushsafer (msg)
        else :
            mylog('verbose', ['[Notification] Skip PUSHSAFER'])
        # Update MQTT entities
        if conf.REPORT_MQTT and check_config('mqtt'):
            updateState(db,"Send: MQTT")
            mylog('info', ['[Notification] Establishing MQTT thread'])
            mqtt_start(db)
        else :
            mylog('verbose', ['[Notification] Skip MQTT'])
    else :
        mylog('verbose', ['[Notification] No changes to report'])

    # Clean Pending Alert Events
    sql.execute ("""UPDATE Devices SET dev_LastNotification = ?
                    WHERE dev_MAC IN (SELECT eve_MAC FROM Events
                                      WHERE eve_PendingAlertEmail = 1)
                 """, (datetime.datetime.now(),) )
    sql.execute ("""UPDATE Events SET eve_PendingAlertEmail = 0
                    WHERE eve_PendingAlertEmail = 1""")

    # clear plugin events
    sql.execute ("DELETE FROM Plugins_Events")

    conf.changedPorts_json_struc = None

    # DEBUG - print number of rows updated
    mylog('info', ['[Notification] Notifications changes: ', sql.rowcount])

    # Commit changes
    db.commitDB()


#-------------------------------------------------------------------------------
def check_config(service):

    if service == 'email':
        return email_check_config()
    
    #    if conf.SMTP_SERVER == '' or conf.REPORT_FROM == '' or conf.REPORT_TO == '':
    #        mylog('none', ['[Check Config] Error: Email service not set up correctly. Check your pialert.conf SMTP_*, REPORT_FROM and REPORT_TO variables.'])
    #        return False
    #    else:
    #        return True

    if service == 'apprise':
        return apprise_check_config()
    
    #    if conf.APPRISE_URL == '' or conf.APPRISE_HOST == '':
    #        mylog('none', ['[Check Config] Error: Apprise service not set up correctly. Check your pialert.conf APPRISE_* variables.'])
    #        return False
    #    else:
    #        return True

    if service == 'webhook':
        return webhook_check_config()
    
    #    if conf.WEBHOOK_URL == '':
    #        mylog('none', ['[Check Config] Error: Webhook service not set up correctly. Check your pialert.conf WEBHOOK_* variables.'])
    #        return False
    #    else:
    #        return True

    if service == 'ntfy':
        return ntfy_check_config ()
    #
    #    if conf.NTFY_HOST == '' or conf.NTFY_TOPIC == '':
    #        mylog('none', ['[Check Config] Error: NTFY service not set up correctly. Check your pialert.conf NTFY_* variables.'])
    #        return False
    #    else:
    #        return True

    if service == 'pushsafer':
        return pushsafer_check_config()

    if service == 'mqtt':
        return mqtt_check_config()

#-------------------------------------------------------------------------------
# Replacing table headers
def format_table (html, thValue, props, newThValue = ''):

    if newThValue == '':
        newThValue = thValue

    return html.replace("<th>"+thValue+"</th>", "<th "+props+" >"+newThValue+"</th>" )

#-------------------------------------------------------------------------------
def format_report_section (pActive, pSection, pTable, pText, pHTML):


    # Replace section text
    if pActive :
        conf.mail_text = conf.mail_text.replace ('<'+ pTable +'>', pText)
        conf.mail_html = conf.mail_html.replace ('<'+ pTable +'>', pHTML)

        conf.mail_text = remove_tag (conf.mail_text, pSection)
        conf.mail_html = remove_tag (conf.mail_html, pSection)
    else:
        conf.mail_text = remove_section (conf.mail_text, pSection)
        conf.mail_html = remove_section (conf.mail_html, pSection)

#-------------------------------------------------------------------------------
def remove_section (pText, pSection):
    # Search section into the text
    if pText.find ('<'+ pSection +'>') >=0 \
    and pText.find ('</'+ pSection +'>') >=0 :
        # return text without the section
        return pText[:pText.find ('<'+ pSection+'>')] + \
               pText[pText.find ('</'+ pSection +'>') + len (pSection) +3:]
    else :
        # return all text
        return pText

#-------------------------------------------------------------------------------
def remove_tag (pText, pTag):
    # return text without the tag
    return pText.replace ('<'+ pTag +'>','').replace ('</'+ pTag +'>','')


#-------------------------------------------------------------------------------
# Reporting
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
def send_api():
        mylog('verbose', ['[Send API] Updating notification_* files in ', apiPath])

        write_file(apiPath + 'notification_text.txt'  , mail_text)
        write_file(apiPath + 'notification_text.html'  , mail_html)
        write_file(apiPath + 'notification_json_final.json'  , json.dumps(json_final))


#-------------------------------------------------------------------------------
def skip_repeated_notifications (db):

    # Skip repeated notifications
    # due strfime : Overflow --> use  "strftime / 60"
    mylog('verbose','[Skip Repeated Notifications] Skip Repeated start')
    db.sql.execute ("""UPDATE Events SET eve_PendingAlertEmail = 0
                    WHERE eve_PendingAlertEmail = 1 AND eve_MAC IN
                        (
                        SELECT dev_MAC FROM Devices
                        WHERE dev_LastNotification IS NOT NULL
                          AND dev_LastNotification <>""
                          AND (strftime("%s", dev_LastNotification)/60 +
                                dev_SkipRepeated * 60) >
                              (strftime('%s','now','localtime')/60 )
                        )
                 """ )
    mylog('verbose','[Skip Repeated Notifications] Skip Repeated end')

    db.commitDB()


#===============================================================================
# UTIL
#===============================================================================

#-------------------------------------------------------------------------------
def check_and_run_event(db):
    sql = db.sql # TO-DO
    sql.execute(""" select * from Parameters where par_ID = "Front_Event" """)
    rows = sql.fetchall()

    event, param = ['','']
    if len(rows) > 0 and rows[0]['par_Value'] != 'finished':
        event = rows[0]['par_Value'].split('|')[0]
        param = rows[0]['par_Value'].split('|')[1]
    else:
        return

    if event == 'test':
        handle_test(param)
    if event == 'run':
        handle_run(param)

    # clear event execution flag
    sql.execute ("UPDATE Parameters SET par_Value='finished' WHERE par_ID='Front_Event'")

    # commit to DB
    db.commitDB()

#-------------------------------------------------------------------------------
def handle_run(runType):
    global last_network_scan

    mylog('info', ['[', timeNow(), '] START Run: ', runType])

    if runType == 'ENABLE_ARPSCAN':
        last_network_scan = conf.time_started - datetime.timedelta(hours = 24)

    mylog('info', ['[', timeNow(), '] END Run: ', runType])

#-------------------------------------------------------------------------------
def handle_test(testType):

    mylog('info', ['[', timeNow(), '] START Test: ', testType])

    # Open text sample
    sample_txt = get_file_content(pialertPath + '/back/report_sample.txt')

    # Open html sample
    sample_html = get_file_content(pialertPath + '/back/report_sample.html')

    # Open json sample and get only the payload part
    sample_json_payload = json.loads(get_file_content(pialertPath + '/back/webhook_json_sample.json'))[0]["body"]["attachments"][0]["text"]

    sample_msg = noti_struc(sample_json_payload, sample_txt, sample_html )

    if testType == 'REPORT_MAIL':
        send_email(sample_msg)
    if testType == 'REPORT_WEBHOOK':
        send_webhook (sample_msg)
    if testType == 'REPORT_APPRISE':
        send_apprise (sample_msg)
    if testType == 'REPORT_NTFY':
        send_ntfy (sample_msg)
    if testType == 'REPORT_PUSHSAFER':
        send_pushsafer (sample_msg)

    mylog('info', ['[Test Publishers] END Test: ', testType])