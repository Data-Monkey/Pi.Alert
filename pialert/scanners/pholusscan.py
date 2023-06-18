""" use pholus to find more details about a network device """

import subprocess
import re

from const import fullPholusPath, logPath
from helper import checkIPV4, timeNow, updateState
from logger import mylog

#-------------------------------------------------------------------------------

def perform_pholus_scan (db, timeout_sec, user_subnets):
    """ run the Pholus scan on the defined subnets """

    sql = db.sql # TO-DO

    # scan every interface
    for subnet in user_subnets:

        temp = subnet.split("--interface=")

        if len(temp) != 2:
            # pylint: disable-next=line-too-long
            mylog('none', ["[PholusScan] Skip scan (need subnet in format '192.168.1.0/24 --inteface=eth0'), got: ", subnet])
            return

        mask = temp[0].strip()
        interface = temp[1].strip()

        # logging & updating app state
        updateState(db,"Scan: Pholus")
        # pylint: disable-next=line-too-long
        mylog('none', ['[PholusScan] Scan: Pholus for ', str(timeout_sec), 's ('+ str(round(int(timeout_sec) / 60, 1)) +'min)'])
        mylog('verbose', ["[PholusScan] Pholus scan on [interface] ", interface, " [mask] " , mask])

        # the scan always lasts 2x as long, the desired user time from settings needs to be halved
        adjusted_timeout = str(round(int(timeout_sec) / 2, 0))

        # pylint: disable-next=line-too-long
        # python3 -m trace --trace /home/pi/pialert/pholus/pholus3.py eth1 -rdns_scanning  192.168.1.0/24 -stimeout 600
        pholus_args = ['python3',
                       fullPholusPath,
                       interface,
                       "-rdns_scanning", mask,
                       "-stimeout", adjusted_timeout]

        # Execute command
        output = ""

        try:
            # try runnning subprocess with a forced (timeout +30 sec) in case the subprocess hangs
            output = subprocess.check_output (pholus_args,
                                              universal_newlines=True,
                                              stderr=subprocess.STDOUT,
                                              timeout= timeout_sec + 30 )
        except subprocess.CalledProcessError as exception:
            # An error occured, handle it
            mylog('none', ["[PholusScan] Error - Pholus Scan - check logs"])
            mylog('none', ['[PholusScan]', exception.output])

        except subprocess.TimeoutExpired as exception:
            # pylint: disable-next=line-too-long
            mylog('none', ['[PholusScan] Pholus TIMEOUT - the process forcefully terminated as timeout reached'])
            mylog('none', ['[PholusScan] Pholus TIMEOUT exception: ',exception.output])


        if output == "": # check if the subprocess failed
            mylog('none', ['[PholusScan] Scan: Pholus FAIL - check logs'])
        else:
            mylog('verbose', ['[PholusScan] Scan: Pholus SUCCESS'])

        #  check the last run output
        log_file = open(logPath + '/pialert_pholus_lastrun.log', 'r+', encoding="utf8")
        new_lines = log_file.read().split('\n')
        log_file.close()

        # cleanup - select only lines containing a separator to filter out unnecessary data
        new_lines = list(filter(lambda x: '|' in x, new_lines))

        # build SQL query parameters to insert into the DB
        params = []

        for line in new_lines:
            columns = line.split("|")
            if len(columns) == 4:
                params.append((interface + " " + mask,
                               timeNow(),
                               columns[0].replace(" ", ""),
                               columns[1].replace(" ", ""),
                               columns[2].replace(" ", ""),
                               columns[3], ''))

        if len(params) > 0:
            sql.executemany ("""INSERT INTO Pholus_Scan
                                ("Info", "Time", "MAC", "IP_v4_or_v6", "Record_Type", "Value", "Extra")
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                             """, params)
            db.commitDB()

#-------------------------------------------------------------------------------
def clean_result(text):
    """ clean up the results returned by scan"""

    # alternative str.split('.')[0]
    text = text.replace("._airplay", "")
    text = text.replace("._tcp", "")
    text = text.replace(".local", "")
    text = text.replace("._esphomelib", "")
    text = text.replace("._googlecast", "")
    text = text.replace(".lan", "")
    text = text.replace(".home", "")
    # removing last part of e.g. Nest-Audio-ff77ff77ff77ff77ff77ff77ff77ff77
    text = re.sub(r'-[a-fA-F0-9]{32}', '', text)
    # remove trailing dots
    if text.endswith('.'):
        text = text[:-1]

    return text


# Disclaimer - I'm interfacing with a script I didn't write (pholus3.py)
# so it's possible I'm missing types of answers, it's also possible the pholus3.py
# script can be adjusted to provide a better output to interface with it
# Hit me with a PR if you know how! :)

def resolve_device_name_pholus (mac_address, ip_address, results):
    """ resolving adresses using pholus """

    pholus_matches_indexes = []

    index = 0
    for result in results:
        # limiting entries used for name resolution to the ones containing the current IP (v4 only)
        if (result["MAC"] == mac_address and
            result["Record_Type"] == "Answer" and
            result["IP_v4_or_v6"] == ip_address and
            '._googlezone' not in result["Value"]):
            # found entries with a matching MAC address, let's collect indexes
            pholus_matches_indexes.append(index)

        index += 1

    # return if nothing found
    if len(pholus_matches_indexes) == 0:
        return -1

    # we have some entries let's try to select the most useful one

    # airplay matches contain a lot of information
    # Matches for example:
    # pylint: disable-next=line-too-long
    # Brand Tv (50)._airplay._tcp.local. TXT Class:32769 "acl=0 deviceid=66:66:66:66:66:66 features=0x77777,0x38BCB46 rsf=0x3 fv=p20.T-FFFFFF-03.1 flags=0x204 model=XXXX manufacturer=Brand serialNumber=XXXXXXXXXXX protovers=1.1 srcvers=777.77.77 pi=FF:FF:FF:FF:FF:FF psi=00000000-0000-0000-0000-FFFFFFFFFF gid=00000000-0000-0000-0000-FFFFFFFFFF gcgl=0 pk=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    for i in pholus_matches_indexes:
        if ( checkIPV4(results[i]['IP_v4_or_v6']) and
            '._airplay._tcp.local. TXT Class:32769' in str(results[i]["Value"])) :
            return results[i]["Value"].split('._airplay._tcp.local. TXT Class:32769')[0]

    # second best - contains airplay
    # Matches for example:
    # _airplay._tcp.local. PTR Class:IN "Brand Tv (50)._airplay._tcp.local."
    for i in pholus_matches_indexes:
        if ( checkIPV4(results[i]['IP_v4_or_v6']) and
             '_airplay._tcp.local. PTR Class:IN' in results[i]["Value"] and
             ('._googlecast') not in results[i]["Value"] ) :
            return clean_result(results[i]["Value"].split('"')[1])

    # Contains PTR Class:32769
    # Matches for example:
    # 3.1.168.192.in-addr.arpa. PTR Class:32769 "MyPc.local."
    for i in pholus_matches_indexes:
        if ( checkIPV4(results[i]['IP_v4_or_v6']) and
             'PTR Class:32769' in results[i]["Value"] ):
            return clean_result(results[i]["Value"].split('"')[1])

    # Contains AAAA Class:IN
    # Matches for example:
    # DESKTOP-SOMEID.local. AAAA Class:IN "fe80::fe80:fe80:fe80:fe80"
    for i in pholus_matches_indexes:
        if ( checkIPV4(results[i]['IP_v4_or_v6']) and
             'AAAA Class:IN' in results[i]["Value"] ):
            return clean_result(results[i]["Value"].split('.local.')[0])

    # Contains _googlecast._tcp.local. PTR Class:IN
    # Matches for example:
    # pylint: disable-next=line-too-long
    # _googlecast._tcp.local. PTR Class:IN "Nest-Audio-ff77ff77ff77ff77ff77ff77ff77ff77._googlecast._tcp.local."
    for i in pholus_matches_indexes:
        if ( checkIPV4(results[i]['IP_v4_or_v6']) and
             '_googlecast._tcp.local. PTR Class:IN' in results[i]["Value"] and
             ('Google-Cast-Group') not in results[i]["Value"] ):
            return clean_result(results[i]["Value"].split('"')[1])

    # Contains A Class:32769
    # Matches for example:
    # Android.local. A Class:32769 "192.168.1.6"
    for i in pholus_matches_indexes:
        if checkIPV4(results[i]['IP_v4_or_v6']) and ' A Class:32769' in results[i]["Value"]:
            return clean_result(results[i]["Value"].split(' A Class:32769')[0])

    # # Contains PTR Class:IN
    # Matches for example:
    # _esphomelib._tcp.local. PTR Class:IN "ceiling-light-1._esphomelib._tcp.local."
    for i in pholus_matches_indexes:
        if checkIPV4(results[i]['IP_v4_or_v6']) and 'PTR Class:IN' in results[i]["Value"]:
            return clean_result(results[i]["Value"].split('"')[1])

    return -1
