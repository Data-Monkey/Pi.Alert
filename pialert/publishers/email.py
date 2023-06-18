""" Pi.Alert module to send notification emails """

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib


import conf
from helper import hide_email, noti_struc
from logger import mylog, print_log

#-------------------------------------------------------------------------------
def check_config ():
    """ check all the required configuration parameters are set """
    if conf.SMTP_SERVER == '' or conf.REPORT_FROM == '' or conf.REPORT_TO == '':
        # pylint: disable-next=line-too-long
        mylog('none', ['[Email Check Config] Error: Email service not set up correctly. Check your pialert.conf SMTP_*, REPORT_FROM and REPORT_TO variables.'])
        return False
    else:
        return True

#-------------------------------------------------------------------------------
def send (msg: noti_struc):
    """ sending the message via email """

    # pylint: disable-next=line-too-long
    mylog('debug', '[Send Email] REPORT_TO: ' + hide_email(str(conf.REPORT_TO)) + '  SMTP_USER: ' + hide_email(str(conf.SMTP_USER)))

    # Compose email
    message = MIMEMultipart('alternative')
    message['Subject'] = 'Pi.Alert Report'
    message['From'] = conf.REPORT_FROM
    message['To'] = conf.REPORT_TO
    message.attach (MIMEText (msg.text, 'plain'))
    message.attach (MIMEText (msg.html, 'html'))

    failed_at = ''

    failed_at = print_log ('SMTP try')

    try:
        # Send mail
        # pylint: disable-next=line-too-long
        failed_at = print_log('Trying to open connection to ' + str(conf.SMTP_SERVER) + ':' + str(conf.SMTP_PORT))

        if conf.SMTP_FORCE_SSL:
            failed_at = print_log('SMTP_FORCE_SSL == True so using .SMTP_SSL()')
            if conf.SMTP_PORT == 0:
                failed_at = print_log('SMTP_PORT == 0 so sending .SMTP_SSL(SMTP_SERVER)')
                smtp_connection = smtplib.SMTP_SSL(conf.SMTP_SERVER)
            else:
                failed_at = print_log('SMTP_PORT == 0 so sending .SMTP_SSL(SMTP_SERVER, SMTP_PORT)')
                smtp_connection = smtplib.SMTP_SSL(conf.SMTP_SERVER, conf.SMTP_PORT)

        else:
            failed_at = print_log('SMTP_FORCE_SSL == False so using .SMTP()')
            if conf.SMTP_PORT == 0:
                failed_at = print_log('SMTP_PORT == 0 so sending .SMTP(SMTP_SERVER)')
                smtp_connection = smtplib.SMTP (conf.SMTP_SERVER)
            else:
                failed_at = print_log('SMTP_PORT == 0 so sending .SMTP(SMTP_SERVER, SMTP_PORT)')
                smtp_connection = smtplib.SMTP (conf.SMTP_SERVER, conf.SMTP_PORT)

        failed_at = print_log('Setting SMTP debug level')

        # Log level set to debug of the communication between SMTP server and client
        if conf.LOG_LEVEL == 'debug':
            smtp_connection.set_debuglevel(1)

        failed_at = print_log( 'Sending .ehlo()')
        smtp_connection.ehlo()

        if not conf.SMTP_SKIP_TLS:
            failed_at = print_log('SMTP_SKIP_TLS == False so sending .starttls()')
            smtp_connection.starttls()
            failed_at = print_log('SMTP_SKIP_TLS == False so sending .ehlo()')
            smtp_connection.ehlo()
        if not conf.SMTP_SKIP_LOGIN:
            failed_at = print_log('SMTP_SKIP_LOGIN == False so sending .login()')
            smtp_connection.login (conf.SMTP_USER, conf.SMTP_PASS)

        failed_at = print_log('Sending .sendmail()')
        smtp_connection.sendmail (conf.REPORT_FROM, conf.REPORT_TO, message.as_string())
        smtp_connection.quit()

    # pylint: disable=line-too-long
    except smtplib.SMTPAuthenticationError as exception:
        mylog('none', ['      ERROR: Failed at - ', failed_at])
        mylog('none', ['      ERROR: Couldn\'t connect to the SMTP server (SMTPAuthenticationError), skipping Email (enable LOG_LEVEL=debug for more logging)'])
        mylog('none', ['      ERROR: ', exception])

    except smtplib.SMTPServerDisconnected as exception:
        mylog('none', ['      ERROR: Failed at - ', failed_at])
        mylog('none', ['      ERROR: Couldn\'t connect to the SMTP server (SMTPServerDisconnected), skipping Email (enable LOG_LEVEL=debug for more logging)'])
        mylog('none', ['      ERROR: ', exception])

    mylog('debug', '[Send Email] Last executed - ' + str(failed_at))
