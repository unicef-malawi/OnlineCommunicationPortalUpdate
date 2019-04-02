# OnlineCommunicationPortalUpdate.py
#
# Olivier Demars - olivier@odc.services
# for UNICEF Malawi
#
# February 2019

# Standard libraries
import os
import sys
import json
import pickle
import os.path
import logging
import base64

# Libraries to be installed with pip
import requests
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Variable file
from OnlineCommunicationPortalUpdateVariables import *


def get_token():

    token_url = "https://www.arcgis.com/sharing/generateToken"
    payload = {'username': ARCGIS_USER,
               'password': base64.b64decode(ARCGIS_PASSWORD).decode("utf-8"),
               'referer': 'www.arcgis.com',
               'f': 'json'}

    try:
        token_response = requests.post(token_url, data=payload)
    except:
        print("Failed to generate token")
        sys.exit()

    try:
        token = json.loads(token_response.content)['token']
    except:
        print("Failed to read token")
        sys.exit()

    return token


def get_data(service_url, token):
    payload = {
        'token': token,
        'f': 'json'
    }

    feature_response = requests.get(service_url, params=payload)

    json_string = feature_response.text
    pydict = json.loads(json_string)

    return pydict


def update_data(service_url, token, data):
    payload = {
        'token': token,
        'text': data,
        'f': 'json'
    }

    feature_response = requests.post(service_url, data=payload)

    json_string = feature_response.text
    pydict = json.loads(json_string)

    return pydict


def google_service_init(api, version, scope, pickle_file, credentials_file):

    creds = None
    # The pickle file  stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, scope)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open(pickle_file, 'wb') as token:
            pickle.dump(creds, token)

    return build(api, version, credentials=creds)


def main():

    logging.info('###   Process Starts')

    # Google Sheet connection
    logging.info('Connection to Google Sheet')
    sheets = google_service_init(
        'sheets',
        'v4',
        ['https://www.googleapis.com/auth/spreadsheets'],
        'Sheets-token.pickle',
        'Sheets-credentials.json'
    )

    # Call the Sheets API
    sheet = sheets.spreadsheets()
    result = sheet.values().get(spreadsheetId=ONLINE_CONTENT_SPREADSHEET_ID,
                                range=ONLINE_CONTENT_RANGE_NAME).execute()
    values = result.get('values', [])

    if not values:
        print('No data found.')
    else:
        feature_list = []
        order_list = []

        json_file_feature = open('json_feature_string.txt', 'w')
        json_file_order = open('json_order_string.txt', 'w')

        # Splash page management
        logging.info('Splash feature creation')
        _splash_feature_dict = {
            'attributes': {
                '__OBJECTID': 0,
                'name': values[0][4],
                'description': values[0][5],
                'icon_color': 'r',
                'pic_url': values[0][6],
                'thumb_url': values[0][8],
                'is_video': False
            },
            'geometry': {
                'x': values[0][12],
                'y': values[0][11],
                'spatialReference': {'wkid': 4326}
            }
        }
        feature_list.append(_splash_feature_dict)

        splash_order_dict = {'id': 0, 'visible': False}
        order_list.append(splash_order_dict)

        # Start OBJECTID counter
        object_id_counter = 1

        logging.info('Processing records')
        for row in reversed(values[1:]):

            # There is a ArcGIS Online 99 points limitation
            if object_id_counter < 100 and len(row) == 13:

                # Get informaton from Google Sheet
                app_id, post_id, published_date, post_url, title, content \
                    = row[0], row[1], row[2], row[3], row[4], row[5]
                photo_url, video_url, thumb_url, post_type, source, latitude, longitude \
                    = row[6], row[7], row[8], row[9], row[10], row[11], row[12]

                if (source != 'Tchop' or post_type != 'video') and (latitude != '0' or longitude != '0'):

                    # Create order information for Storymap
                    order_item = {'id': object_id_counter, 'visible': True}

                    order_list.append(order_item)

                    # Create feature list for Map
                    feature_dict = {}

                    # OBJECT ID
                    attribute_dict = {'__OBJECTID': object_id_counter}

                    # Name
                    if source != 'Tchop':
                        attribute_dict["name"] = '<a href=\'%s\' style='' target=\'”_blank”\'>%s</a>'\
                                                 % (post_url, title)
                    else:
                        attribute_dict["name"] = title

                    # Description
                    attribute_dict["description"] = content

                    # Picture/Photo Url
                    if post_type == 'video':
                        attribute_dict["pic_url"] = video_url
                        attribute_dict["is_video"] = 'true'
                    else:
                        attribute_dict["pic_url"] = photo_url
                        attribute_dict["is_video"] = 'false'

                    # Thumbnail
                    attribute_dict["thumb_url"] = thumb_url

                    # Icon Color
                    if source == 'YouTube':
                        attribute_dict["icon_color"] = 'r'
                    elif source == 'Blogger':
                        attribute_dict["icon_color"] = 'p'
                    elif source == 'Wordpress':
                        attribute_dict["icon_color"] = 'b'
                    else:
                        attribute_dict["icon_color"] = 'g'

                    feature_dict["attributes"] = attribute_dict

                    geometry_dict = {
                        'x': longitude,
                        'y': latitude,
                        'spatialReference': {'wkid': 4326}}

                    feature_dict['geometry'] = geometry_dict

                    feature_list.append(feature_dict)

                    # Update counter for OBJECT_ID
                    object_id_counter = object_id_counter + 1

        # print(json.dumps(feature_list, ensure_ascii=False, indent=4))

        json_file_feature.write(json.dumps(feature_list, ensure_ascii=True, indent=4))
        json_file_feature.close()

        json_file_order.write(json.dumps(order_list, ensure_ascii=True, indent=4))
        json_file_order.close()

        # Update Map
        logging.info('Updating map')
        dict_map = get_data(MAP_DATA_URL, get_token())
        dict_map["operationalLayers"][0]["featureCollection"]["layers"][0]["featureSet"]["features"] = feature_list

        update_data(MAP_UPDATE_URL, get_token(), json.dumps(dict_map))

        # Update Story Map
        logging.info('Updating storymap')
        dict_storymap = get_data(STORYMAP_DATA_URL, get_token())
        dict_storymap["values"]["order"] = order_list

        update_data(STORYMAP_UPDATE_URL, get_token(), json.dumps(dict_storymap))

    logging.info('###   End of Process')


if __name__ == '__main__':

    LOGGING_FORMAT = '%(asctime)s %(levelname)-8s %(message)s'
    logging.basicConfig(level=logging.INFO, filename='logs.txt', filemode='a',
                        datefmt='%Y%m%d %H:%M:%S', format=LOGGING_FORMAT)
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

    main()
