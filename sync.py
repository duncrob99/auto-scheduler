from __future__ import print_function

import os.path
import os
import datetime
from datetime import timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from httplib2.error import ServerNotFoundError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.appdata']

def safe_sync():
    try:
        update()
    except RefreshError:
        os.remove('token.json')
        try:
            update()
        except ServerNotFoundError:
            print('No connection to sync server') 
    except ServerNotFoundError:
        print('No connection to sync server') 

def update():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                'credentials.json', SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            auth_url, hi = flow.authorization_url(prompt='consent')
            print('Please go to this URL: {}'.format(auth_url))

            code = input('Enter the authorisation code: ')
            flow.fetch_token(code=code)

            session = flow.authorized_session()

            creds = flow.credentials
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)

    response = service.files().list(spaces='appDataFolder',
                                    fields='nextPageToken, files(id, name, modifiedTime)',
                                    pageSize=10).execute()

    try:
        task_local_modified = datetime.datetime.fromtimestamp(os.path.getmtime('one-off_tasks'), tz=timezone.utc)
    except FileNotFoundError:
        task_local_modified = datetime.datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        fixed_local_modified = datetime.datetime.fromtimestamp(os.path.getmtime('day_fixed_work.txt'), tz=timezone.utc)
    except FileNotFoundError:
        fixed_local_modified = datetime.datetime.fromtimestamp(0, tz=timezone.utc)

    tasks_exist = False
    fixed_exist = False
    task_drive_modified, task_id, fixed_drive_modified, fixed_id = None, None, None, None
    for file in response.get('files', []):
        if file.get('name') == 'one-off_tasks':
            tasks_exist = True
            task_id = file.get('id')
            task_drive_modified = datetime.datetime.strptime(file.get('modifiedTime'),
                                                             '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        elif file.get('name') == 'day_fixed_work.txt':
            fixed_exist = True
            fixed_id = file.get('id')
            fixed_drive_modified = datetime.datetime.strptime(file.get('modifiedTime'),
                                                              '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)

    if not tasks_exist:
        print('Creating flexible task list')
        file_metadata = {
            'name': 'one-off_tasks',
            'parents': ['appDataFolder']
        }
        media = MediaFileUpload('one-off_tasks',
                                resumable=True)
        file = service.files().create(body=file_metadata,
                                      media_body=media,
                                      fields='id').execute()
    elif task_local_modified - task_drive_modified > datetime.timedelta(seconds=1):
        print('Uploading modified task list')
        media = MediaFileUpload('one-off_tasks',
                                resumable=True)
        metadata = {'modifiedTime': task_local_modified.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
        service.files().update(
            fileId=task_id,
            body=metadata,
            media_body=media,
            fields='modifiedTime').execute()
    elif task_local_modified - task_drive_modified < datetime.timedelta(seconds=-1):
        print('Downloading task list')
        downloaded_file = service.files().get_media(fileId=task_id).execute()
        with open("one-off_tasks", "wb") as out_file:
            out_file.write(downloaded_file)
        os.utime('one-off_tasks', (task_drive_modified.timestamp(), task_drive_modified.timestamp()))
    else:
        print('No update required for task list')

    if not fixed_exist:
        print('Creating fixed work list')
        file_metadata = {
            'name': 'day_fixed_work.txt',
            'parents': ['appDataFolder']
        }
        media = MediaFileUpload('day_fixed_work.txt',
                                resumable=True)
        file = service.files().create(body=file_metadata,
                                      media_body=media,
                                      fields='id').execute()
    elif fixed_local_modified - fixed_drive_modified > datetime.timedelta(seconds=1):
        print('Uploading modified fixed work list')
        media = MediaFileUpload('day_fixed_work.txt',
                                resumable=True)
        metadata = {'modifiedTime': fixed_local_modified.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}
        service.files().update(
            fileId=fixed_id,
            body=metadata,
            media_body=media,
            fields='modifiedTime').execute()
    elif fixed_local_modified - fixed_drive_modified < datetime.timedelta(seconds=-1):
        print('Downloading fixed work list')
        downloaded_file = service.files().get_media(fileId=fixed_id).execute()
        with open("day_fixed_work.txt", "wb") as out_file:
            out_file.write(downloaded_file)
        os.utime('day_fixed_work.txt', (fixed_drive_modified.timestamp(), fixed_drive_modified.timestamp()))
    else:
        print('No update required for fixed list')


if __name__ == '__main__':
    update()
