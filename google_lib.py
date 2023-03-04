"""Uses Google APIs to send email and update spreadsheet.
"""
from __future__ import print_function

import os
import os.path
import base64

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email.mime.text import MIMEText

from googleapiclient import errors

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://mail.google.com/']
CLIENT_TOKEN = '/home/kenjidnb/temp_alert/token.json'


def InitGoogleService(app, version, flags):
    creds =  get_credentials()
    service = build(app, version, credentials=creds)
    return service


def get_credentials():
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time. 
    # When the auth flow runs for the first time, it will generate a URL,
    # which needs to be accessed from the computer that generates it (i.e. not 
    # from a remote computer). When SSH'ing to a headless computer like a 
    # raspberry pi, we can use X11 and open a web browser through it in order 
    # to complete the authorization flow and download the token file.

    creds = None
    if os.path.exists(CLIENT_TOKEN):
        creds = Credentials.from_authorized_user_file(CLIENT_TOKEN, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '/home/kenjidnb/temp_alert/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('/home/kenjidnb/temp_alert/token.json', 'w') as token:
            token.write(creds.to_json())
    print("CREDS", creds)
    return creds


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

