# processor.py
import os, json, boto3, traceback, mimetypes
from googleapiclient.discovery import build
from google.oauth2 import service_account
from bib_extraction import detect_and_tabulate_bibs_easyocr
import uuid

# DynamoDB (schema: EventId (N) PK, DriveUrl (S), Status (S))
ddb = boto3.resource("dynamodb")
# jobs = ddb.Table(os.environ["JOBS_TABLE"])

# S3
s3 = boto3.client("s3")
RAW_BUCKET = os.environ["RAW_BUCKET"]

# Google Drive
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
creds = service_account.Credentials.from_service_account_file(
    os.environ["GDRIVE_SA_PATH"],
    scopes=SCOPES
)
drive = build("drive", "v3", credentials=creds)


def extract_bib_numbers(photo):
    try:
        bib_numbers = detect_and_tabulate_bibs_easyocr(photo, image_name="s3_object")
    except Exception as exc:
        print("[ERROR] Failed to extract bib numbers:", exc)
        bib_numbers = []
    return bib_numbers



def add_photo(event_id, filename, bib_numbers):
    """
    Insert a record into DynamoDB for each bib number found in an image.
    Schema:
      EventImageId (String, uuid4)
      BibId       (String)
      EventId     (String or Number)
      filename    (String)
    """
    table_name = 'MarathonBibImages'
    table = ddb.Table(table_name)
    for bib_id in bib_numbers:
        event_image_id = str(uuid.uuid4())
        item = {
            "EventImageId": event_image_id,
            "BibId": str(bib_id),
            "EventId": str(event_id),
            "filename": filename
        }
        try:
            # Only allow insert if EventImageId doesn't already exist
            table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(EventImageId)"
            )
        except ddb.meta.client.exceptions.ConditionalCheckFailedException:
            # Collision occurred; surface it immediately
            raise RuntimeError(f"UUID collision detected for EventImageId {event_image_id}")


def generateBibIds(event):
    event_id_raw = event.get("eventId")
    file_id = event.get("fileId")

    if event_id_raw is None:
        raise ValueError("Missing eventId")
    if not file_id:
        raise ValueError("Missing fileId")

    # DynamoDB PK is Number, so convert
    try:
        event_id = int(event_id_raw)
    except Exception:
        raise ValueError("eventId must be numeric (string or number)")

    try:
        
        # 1) Download image from Google Drive
        filename, data, mime_type = download_file_from_drive(file_id)

        # 2) Run processing/model
        bib_numbers = extract_bib_numbers(data)

        # 3) Start logic for S3 Upload based on processing
        if bib_numbers:
            folder_name = "ProcessedImages"
            add_photo(event_id, filename, bib_numbers)
        else:
            folder_name = "UnProcessedImages"

        # 4) Upload to S3 with correct extension and content type
        # Using mime_type from Drive if available, else default
        final_content_type = mime_type if mime_type else "image/jpeg"
        s3_key = upload_to_s3(event_id, filename, data, folder_name, content_type=final_content_type)


        return {
            "eventId": str(event_id),
            "fileId": str(file_id),
            "s3Bucket": RAW_BUCKET,
            "s3Key": s3_key,
            "ok": True
        }

    except Exception:
        traceback.print_exc()

        # Minimal schema: mark FAILED, but do NOT overwrite COMPLETED if already set
        try:
            pass
        #     jobs.update_item(
        #         Key={"EventId": event_id},
        #         UpdateExpression="SET #s = :failed",
        #         ConditionExpression="attribute_not_exists(#s) OR #s <> :completed",
        #         ExpressionAttributeNames={"#s": "Status"},
        #         ExpressionAttributeValues={
        #             ":failed": "FAILED",
        #             ":completed": "COMPLETED"
        #         }
        #     )
        except Exception:
            # ignore conditional race / already completed
            pass

        # Re-raise so Step Functions can retry/catch
        raise


def generateReel(event):
    event_id = event.get("eventId")
    reel_s3_key = event.get("reelS3Key")
    reel_config = event.get("reelConfiguration")
    bib_id = event.get("item")

    from boto3.dynamodb.conditions import Key, Attr
    table = ddb.Table('MarathonBibImages')
    
    response = table.query(
        IndexName='EventId-index',
        KeyConditionExpression=Key('EventId').eq(str(event_id)),
        FilterExpression=Attr('BibId').eq(str(bib_id))
    )
    filenames = [item['filename'] for item in response.get('Items', [])]
    overlays = json.loads(reel_config).get("overlays")
    if len(filenames) < len(overlays):
        raise ValueError("Not enough images found for bib_id")
    






    


def download_file_from_drive(file_id):
    # 1) Get file metadata (name + mime type)
    metadata = drive.files().get(
        fileId=file_id,
        fields="name,mimeType"
    ).execute()

    mime_type = metadata["mimeType"]
    filename = metadata["name"]

    # 2) Download image
    data = drive.files().get_media(fileId=file_id).execute()

    # 3) Determine file extension
    ext = os.path.splitext(filename)[1]
    if not ext:
        ext = mimetypes.guess_extension(mime_type) or ""
    
    # Ensure filename has extension if needed (optional based on preference, but keeping filename as is for now)
    return filename, data, mime_type

def upload_to_s3(event_id, filename, data, folder_name, content_type="image/jpeg"):
    s3_key = f"{event_id}/{folder_name}/{filename}"
    s3.put_object(
        Bucket=RAW_BUCKET,
        Key=s3_key,
        Body=data,
        ContentType=content_type
    )
    return s3_key

def lambda_handler(event, context):
    """
    Expected input from Step Functions Map Parameters:
    {
      "eventId": "1001",
      "fileId": "1a2b3c...",
      "imageUrl": "https://drive.google.com/file/d/1a2b3c/view"
    }
    """
    print(json.dumps(event))
    requestType=event.get("eventId")

    if requestType is "PROCESS_IMAGES":
        return generateBibIds(event)
    elif requestType is "GENERATE_REEL":
        return generateReel(event)

    
