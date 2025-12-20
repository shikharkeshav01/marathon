# # Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# # SPDX-License-Identifier: Apache-2.0
import json
import urllib.parse
import boto3
from botocore.exceptions import ClientError

from bib_extraction import detect_and_tabulate_bibs_easyocr

print('Loading function')

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')


def add_photo(event_name, image_name, bib_numbers):
    table_name = 'marathon-photos'
    table = dynamodb.Table(table_name)

    for number in bib_numbers:
        # ADD image to each bib number
        table_name = 'marathon-photos' 
        response = table.update_item(
            Key={
                'bib_no': number,
                'event_name': event_name  
            },
            # ADD creates the attribute if it doesn’t exist, and merges new values into the set
            UpdateExpression="ADD photos :new_photos",
            ExpressionAttributeValues={
                ':new_photos': set([image_name])
            },
            ReturnValues="ALL_NEW"
        )

def get_photo_from_s3(bucket, key):
    response = s3.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()

def extract_bib_numbers(photo):
    try:
        bib_numbers = detect_and_tabulate_bibs_easyocr(photo, image_name="s3_object")
    except Exception as exc:
        print("[ERROR] Failed to extract bib numbers:", exc)
        bib_numbers = ["unknown"]
    return bib_numbers

def lambda_handler(event, context):
    # print("Received event: " + json.dumps(event, indent=2))
    body= json.loads(event['Records'][0]['body'])
    print("Received body: " + json.dumps(body, indent=2))
    bucket = body['Records'][0]['s3']['bucket']['name']
    s3_key = urllib.parse.unquote_plus(body['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    # Extract event_name and image_name from S3 key hierarchy: "event_name/image_name"
    key_parts = s3_key.split('/', 1)
    if len(key_parts) != 2:
        raise ValueError(f"S3 key '{s3_key}' does not follow expected hierarchy 'event_name/image_name'. Event name not found.")
    
    event_name = key_parts[0]
    image_name = key_parts[1]
    
    if not event_name:
        raise ValueError(f"Event name is empty in S3 key '{s3_key}'. Event name not found.")

    print('Loading image from S3: ',bucket,':', s3_key)

    try:
        photo = get_photo_from_s3(bucket, s3_key)
        print("Photo loaded from S3")
        bib_numbers = extract_bib_numbers(photo)
        print("Bib numbers extracted from photo: ", bib_numbers)
        add_photo(event_name, image_name, bib_numbers)
        return {'statusCode': 200, 'body': json.dumps('Success')}
    except Exception as e:
        print(Exception, ":", e)
        raise e
    
    if __name__ == "__main__":
        with open("event.json", "r") as f:
            event = json.load(f)
        lambda_handler(event, {})