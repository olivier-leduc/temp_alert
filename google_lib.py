"""Uses Google APIs to send email and update spreadsheet.
"""

import base64
import logging
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mimetypes
import os

#from __future__ import print_function
import httplib2
import os

from googleapiclient import discovery
from googleapiclient import errors
import oauth2client.file
from oauth2client import client
from oauth2client import tools

_BUILD = discovery.build

SCOPES = ['https://www.googleapis.com/auth/gmail.compose', 'https://www.googleapis.com/auth/drive']
CLIENT_SECRET_FILE = '/home/pi/credentials/client_secret.json'
APPLICATION_NAME = 'Gmail API Python Quickstart'


def InitGoogleService(app, version, flags):
    credentials =  get_credentials(flags)
    http = credentials.authorize(httplib2.Http())
    service = _BUILD(app, version, http=http, cache_discovery=False)
    return service


def get_credentials(flags):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('/home/pi/temp_alert')
    credential_dir = os.path.join(home_dir, 'credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'google_creds.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, flags)
        print('Storing credentials to ' + credential_path)
    return credentials


def SendMessage(service, user_id, message):
  """Send an email message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message: Message to be sent.

  Returns:
    Sent Message.
  """
  try:
    message = (service.users().messages().send(userId=user_id, body=message)
               .execute())
    print('Message Id: %s' % message['id'])
    return message
  except errors.HttpError as e:
    print('An error occurred: %s' % e)


def CreateMessage(sender, to, subject, message_text):
  """Create a message for an email.

  Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.

  Returns:
    An object containing a base64url encoded email object.
  """
  message = MIMEText(message_text)
  message['to'] = to
  message['from'] = sender
  message['subject'] = subject
  #return {'raw': base64.urlsafe_b64encode(message.as_bytes())}
  b64_bytes = base64.urlsafe_b64encode(message.as_bytes())
  b64_string = b64_bytes.decode()
  return {'raw': b64_string}


def AppendGsheet(service, values, sheet_id):
  """Append rows to Google spreadsheet.

  Args:
    credentials:  oauth2 credentials for accessing the Drive API.
    sheet_id: A string, Titleid of the Gsheet
  Returns:
  """
  request = service.spreadsheets().values().append(
      spreadsheetId=sheet_id,
      range='Sheet1!A1',
      valueInputOption='RAW',
      body={ 'values': values }
  )
  try:
    response = request.execute()
  except errors as e:
    print(e)
    raise
  return response


def ClearSheet(service, sheet_id):
  """Clear rows from given Google spreadsheet.

  Args:
    credentials:  oauth2 credentials for accessing the Drive API.
    sheet_id: A string, Titleid of the Gsheet
  Returns:
  """
  range_all_rows = 'Sheet1!A2:Z'
  request = service.spreadsheets().values().clear(
      spreadsheetId=sheet_id,
      range = range_all_rows,
      body = {}
      )
  try:
    response = request.execute()
  except errors as e:
    print(e)
    raise
  return response


