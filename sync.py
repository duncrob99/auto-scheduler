from __future__ import print_function

import os.path
import datetime
from datetime import timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.appdata']


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

    task_local_modified = datetime.datetime.fromtimestamp(os.path.getmtime('one-off_tasks'), tz=timezone.utc)
    fixed_local_modified = datetime.datetime.fromtimestamp(os.path.getmtime('day_fixed_work.txt'), tz=timezone.utc)

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
        modified = datetime.datetime.strptime(file.get('modifiedTime'), '%Y-%m-%dT%H:%M:%S.%fZ')
        print('Found file: %s (%s) [%s]' % (file.get('name'), file.get('id'), modified))

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
        print('File ID: %s' % file.get('id'))
    elif task_local_modified > task_drive_modified:
        print('Uploading modified task list')
        media = MediaFileUpload('one-off_tasks',
                                resumable=True)
        service.files().update(
            fileId=task_id,
            media_body=media,
            fields='modifiedTime').execute()
    else:
        print('Downloading task list')
        downloaded_file = service.files().get_media(fileId=task_id).execute()
        with open("one-off_tasks", "wb") as out_file:
            out_file.write(downloaded_file)
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
        print('File ID: %s' % file.get('id'))
    elif fixed_local_modified > fixed_drive_modified:
        print('Uploading modified fixed work list')
        media = MediaFileUpload('day_fixed_work.txt',
                                resumable=True)
        service.files().update(
            fileId=fixed_id,
            media_body=media,
            fields='modifiedTime').execute()
    else:
        print('Downloading task list')
        downloaded_file = service.files().get_media(fileId=fixed_id).execute()
        with open("day_fixed_work.txt", "wb") as out_file:
            out_file.write(downloaded_file)


if __name__ == '__main__':
    update()
