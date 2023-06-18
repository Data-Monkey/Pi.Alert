""" NMAP used to scan for devices on the network """
import subprocess

import conf
from const import logPath, sql_nmap_scan_all
from helper import json_struc, timeNow, updateState
from logger import append_line_to_file, mylog
#-------------------------------------------------------------------------------

class NmapEntry:
    """ class defininf NMAP devices"""
    def __init__(self, mac, time, port, state, service, name = '', extra = '', index = 0):
        self.mac = mac
        self.time = time
        self.port = port
        self.state = state
        self.service = service
        self.name = name
        self.extra = extra
        self.index = index
        self.hash = str(mac) + str(port)+ str(state)+ str(service)


#-------------------------------------------------------------------------------
def perform_nmap_scan(db, devices_to_scan):
    """
    run nmap scan on a list of devices
    discovers open ports and keeps track existing and new open ports
    """
    if len(devices_to_scan) > 0:

        timeout_sec = conf.NMAP_TIMEOUT
        devices_count = len(devices_to_scan)

        updateState(db,"Scan: Nmap")
        # pylint: disable-next=line-too-long
        mylog('verbose', ['[NMAP Scan] Scan: Nmap for max ', str(timeout_sec), 's ('+ str(round(int(timeout_sec) / 60, 1)) +'min) per device'])
        # pylint: disable-next=line-too-long
        mylog('verbose', ["[NMAP Scan] Estimated max delay: ", (devices_count * int(timeout_sec)), 's ', '(', round((devices_count * int(timeout_sec))/60,1) , 'min)' ])

        device_index = 0
        for device in devices_to_scan:
            # Execute command
            output = ""
            # prepare arguments from user supplied ones
            nmap_args = ['nmap'] + conf.NMAP_ARGS.split() + [device["dev_LastIP"]]

            progress = ' (' + str(device_index+1) + '/' + str(devices_count) + ')'

            try:
                # runnning subprocess with a forced (timeout + 30 sec) in case the subprocess hangs
                output = subprocess.check_output (nmap_args,
                                                  universal_newlines=True,
                                                  stderr=subprocess.STDOUT,
                                                  timeout=timeout_sec + 30)
            except subprocess.CalledProcessError as exception:
                # An error occured, handle it
                mylog('none', ["[NMAP Scan] ", exception.output])
                mylog('none', ["[NMAP Scan] Error - Nmap Scan - check logs", progress])
            except subprocess.TimeoutExpired as exception:
                # pylint: disable-next=line-too-long
                mylog('verbose', ['[NMAP Scan] Nmap TIMEOUT - the process forcefully terminated as timeout reached for ', device["dev_LastIP"], progress])
                mylog('verbose', ['[NMAP Scan] Nmap TIMEOUT - exception', exception.output])

            if output == "": # check if the subprocess failed
                # pylint: disable-next=line-too-long
                mylog('info', ['[NMAP Scan] Nmap FAIL for ', device["dev_LastIP"], progress ,' check logs for details'])
            else:
                # pylint: disable-next=line-too-long
                mylog('verbose', ['[NMAP Scan] Nmap SUCCESS for ', device["dev_LastIP"], progress])

            device_index += 1

            #  check the last run output
            new_lines = output.split('\n')

            # regular logging
            for line in new_lines:
                append_line_to_file (logPath + '/pialert_nmap.log', line +'\n')

            # collect ports / new Nmap Entries
            temp_entries = []

            index = 0
            start_collecting = False
            # duration = ""  # un-used
            for line in new_lines:
                if 'Starting Nmap' in line:
                    if len(new_lines) > index+1 and 'Note: Host seems down' in new_lines[index+1]:
                        break # this entry is empty
                elif 'PORT' in line and 'STATE' in line and 'SERVICE' in line:
                    start_collecting = True
                elif 'PORT' in line and 'STATE' in line and 'SERVICE' in line:
                    start_collecting = False # end reached
                elif start_collecting and len(line.split()) == 3:
                    temp_entries.append(NmapEntry(device["dev_MAC"],
                                                  timeNow(),
                                                  line.split()[0],
                                                  line.split()[1],
                                                  line.split()[2],
                                                  device["dev_Name"]))
                # elif 'Nmap done' in line:
                #    duration = line.split('scanned in ')[1]
            index += 1
            mylog('verbose', ['[NMAP Scan] Ports found by NMAP: ', len(temp_entries)])
            process_discovered_ports(db, device, temp_entries)
        #end for loop



def process_discovered_ports(db, device, discovered_ports):
    """
    process ports discovered by nmap
    compare to previosu ports
    update DB
    raise notifications
    """
    sql = db.sql # TO-DO
    # previous Nmap Entries
    old_entries = []
    changed_ports_tmp = []

    mylog('verbose', ['[NMAP Scan] Process ports found by NMAP: ', len(discovered_ports)])

    if len(discovered_ports) > 0:

        #  get all current NMAP ports from the DB
        rows = db.read(sql_nmap_scan_all)

        for row in rows:
            # only collect entries matching the current MAC address
            if row["MAC"] == device["dev_MAC"]:
                old_entries.append(NmapEntry(row["MAC"],
                                             row["Time"],
                                             row["Port"],
                                             row["State"],
                                             row["Service"],
                                             device["dev_Name"],
                                             row["Extra"],
                                             row["Index"]))

        new_entries = []

        # Collect all entries that don't match the ones in the DB
        for discovered_port in discovered_ports:

            found = False

            # Check the new entry is already available in oldEntries
            # and remove from processing if yes
            for old_entry in old_entries:
                if discovered_port.hash == old_entry.hash:
                    found = True

            if not found:
                new_entries.append(discovered_port)

        # pylint: disable-next=line-too-long
        mylog('verbose', ['[NMAP Scan] Nmap newly discovered or changed ports: ', len(new_entries)])

        # collect new ports, find the corresponding old entry and return for notification purposes
        # also update the DB with the new values after deleting the old ones
        if len(new_entries) > 0:

            # params to build the SQL query
            params = []
            indexes_to_delete = ""

            # Find old entry matching the new entry hash
            for new_entry in new_entries:

                found_entry = None

                for old_entry in old_entries:
                    if old_entry.hash == new_entry.hash:
                        indexes_to_delete = indexes_to_delete + str(old_entry.index) + ','
                        found_entry = old_entry

                column_names = ["Name", "MAC", "Port", "State", "Service", "Extra", "NewOrOld"  ]

                # Old entry found
                if found_entry is not None:
                    # Build params for sql query
                    params.append((new_entry.mac,
                                   new_entry.time,
                                   new_entry.port,
                                   new_entry.state,
                                   new_entry.service,
                                   old_entry.extra))
                    # Build JSON for API and notifications
                    changed_ports_tmp.append({
                                            "Name"      : found_entry.name,
                                            "MAC"       : new_entry.mac,
                                            "Port"      : new_entry.port,
                                            "State"     : new_entry.state,
                                            "Service"   : new_entry.service,
                                            "Extra"     : found_entry.extra,
                                            "NewOrOld"  : "New values"
                                        })
                    changed_ports_tmp.append({
                                            "Name"      : found_entry.name,
                                            "MAC"       : found_entry.mac,
                                            "Port"      : found_entry.port,
                                            "State"     : found_entry.state,
                                            "Service"   : found_entry.service,
                                            "Extra"     : found_entry.extra,
                                            "NewOrOld"  : "Old values"
                                        })
                # New entry - no matching Old entry found
                else:
                    # Build params for sql query
                    params.append((new_entry.mac,
                                   new_entry.time,
                                   new_entry.port,
                                   new_entry.state,
                                   new_entry.service,
                                   ''))
                    # Build JSON for API and notifications
                    changed_ports_tmp.append({
                                            "Name"      : "New device",
                                            "MAC"       : new_entry.mac,
                                            "Port"      : new_entry.port,
                                            "State"     : new_entry.state,
                                            "Service"   : new_entry.service,
                                            "Extra"     : "",
                                            "NewOrOld"  : "New device"
                                        })

            conf.changedPorts_json_struc = json_struc({ "data" : changed_ports_tmp}, column_names)

            #  Delete old entries if available
            if len(indexes_to_delete) > 0:
                sql.execute ("""DELETE FROM Nmap_Scan
                                where \"Index\" in (" + indexes_to_delete[:-1] +")""")
                db.commitDB()

            # Insert new values into the DB
            sql.executemany ("""INSERT INTO Nmap_Scan
                                ("MAC", "Time", "Port", "State", "Service", "Extra")
                                VALUES (?, ?, ?, ?, ?, ?)""",
                            params)
            db.commitDB()
