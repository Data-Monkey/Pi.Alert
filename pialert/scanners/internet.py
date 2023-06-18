""" internet related functions to support Pi.Alert """

import subprocess

import conf
from helper import timeNow, updateState
from logger import append_line_to_file, mylog
from const import logPath
from scanners.dig import get_dynamic_dns_ip, get_internet_ip



# need to find a better way to deal with settings !
#global DDNS_ACTIVE, DDNS_DOMAIN, DDNS_UPDATE_URL, DDNS_USER, DDNS_PASSWORD


#===============================================================================
# INTERNET IP CHANGE
#===============================================================================
def check_internet_ip ( db ):
    """ check the public IP address of the modem """

    # Header
    updateState(db,"Scan: Internet IP")
    mylog('verbose', ['[Internet IP] Check Internet IP started'])

    # Get Internet IP
    mylog('verbose', ['[Internet IP] - Retrieving Internet IP'])
    internet_ip = get_internet_ip()
    # TESTING - Force IP
        # internet_IP = "1.2.3.4"

    # Check result = IP
    if internet_ip == "" :
        mylog('none', ['[Internet IP]    Error retrieving Internet IP'])
        mylog('none', ['[Internet IP]    Exiting...'])
        return False
    mylog('verbose', ['[Internet IP] IP:      ', internet_ip])

    # Get previous stored IP
    mylog('verbose', ['[Internet IP]    Retrieving previous IP:'])
    previous_ip = get_previous_internet_ip (db)
    mylog('verbose', ['[Internet IP]      ', previous_ip])

    # Check IP Change
    if internet_ip != previous_ip :
        mylog('info', ['[Internet IP]    New internet IP: ', internet_ip])
        save_new_internet_ip (db, internet_ip)

    else :
        mylog('verbose', ['[Internet IP]    No changes to perform'])

    # Get Dynamic DNS IP
    if conf.DDNS_ACTIVE :
        mylog('verbose', ['[DDNS]    Retrieving Dynamic DNS IP'])
        dns_ip = get_dynamic_dns_ip()

        # Check Dynamic DNS IP
        if dns_ip == "" or dns_ip == "0.0.0.0" :
            mylog('none', ['[DDNS]     Error retrieving Dynamic DNS IP'])
        mylog('none', ['[DDNS]    ', dns_ip])

        # Check DNS Change
        if dns_ip != internet_ip :
            mylog('none', ['[DDNS]     Updating Dynamic DNS IP'])
            message = set_dynamic_dns_ip ()
            mylog('none', ['[DDNS]        ', message])
        else :
            mylog('verbose', ['[DDNS]     No changes to perform'])
    else :
        mylog('verbose', ['[DDNS]     Skipping Dynamic DNS update'])

#-------------------------------------------------------------------------------
def get_previous_internet_ip (db):
    """ retrieve previos IP from database """

    previous_ip = '0.0.0.0'

    # get previous internet IP stored in DB
    db.sql.execute ("SELECT dev_LastIP FROM Devices WHERE dev_MAC = 'Internet' ")
    result = db.sql.fetchone()

    db.commitDB()

    if  result is not None and len(result) > 0 :
        previous_ip = result[0]

    # return previous IP
    return previous_ip

#-------------------------------------------------------------------------------
def save_new_internet_ip (db, new_ip_address):
    """ write new IP address to DB """
    # Log new IP into logfile
    append_line_to_file (logPath + '/IP_changes.log',
        '['+str(timeNow()) +']\t'+ new_ip_address +'\n')

    prev_ip = get_previous_internet_ip(db)
    # Save event
    db.sql.execute ("""INSERT INTO Events (eve_MAC, eve_IP, eve_DateTime,
                        eve_EventType, eve_AdditionalInfo,
                        eve_PendingAlertEmail)
                    VALUES ('Internet', ?, ?, 'Internet IP Changed',
                        'Previous Internet IP: '|| ?, 1) """,
                    (new_ip_address, timeNow(), prev_ip) )

    # Save new IP
    db.sql.execute ("""UPDATE Devices SET dev_LastIP = ?
                    WHERE dev_MAC = 'Internet' """,
                    (new_ip_address,) )

    # commit changes
    db.commitDB()

#-------------------------------------------------------------------------------
def set_dynamic_dns_ip ():
    """ update DDNS provider """
    try:
        # try runnning a subprocess
        # Update Dynamic IP
        curl_output = subprocess.check_output (['curl', '-s',
            conf.DDNS_UPDATE_URL +
            'username='  + conf.DDNS_USER +
            '&password=' + conf.DDNS_PASSWORD +
            '&hostname=' + conf.DDNS_DOMAIN],
            universal_newlines=True)
    except subprocess.CalledProcessError as exception:
        # An error occured, handle it
        mylog('none', ['[DDNS] ERROR - ',exception.output])
        curl_output = ""

    return curl_output
