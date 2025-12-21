# processor.py
import os, json, boto3, traceback, mimetypes
from googleapiclient.discovery import build
from google.oauth2 import service_account
from bib_extraction import detect_and_tabulate_bibs_easyocr
from reel_generation import overlay_images_on_video
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


def download_file(file_id):
    # 1) Get file metadata (name + mime type)
    metadata = drive.files().get(
        fileId=file_id,
        fields="name,mimeType"
    ).execute()

    mime_type = metadata["mimeType"]
    filename = metadata["name"]

    # 2) Download image from Google Drive
    data = drive.files().get_media(fileId=file_id).execute()
    return filename, data, mime_type


def upload_file(s3_key, data):
    # 4) Upload to S3 with correct extension and content type
    s3.put_object(
        Bucket=RAW_BUCKET,
        Key=s3_key,
        Body=data,
        ContentType="image/jpeg"
    )


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
        
        # 1) Download image
        filename, data, mime_type = download_file(file_id)

        # 3) Determine file extension
        ext = os.path.splitext(filename)[1]
        if not ext:
            ext = mimetypes.guess_extension(mime_type) or ""

        # 5) Run your processing/model here if needed
        try:
            bib_numbers = extract_bib_numbers(data)
            
            if bib_numbers or len(bib_numbers) > 0:
                s3_key = f"{event_id}/ProcessedImages/{filename}"
            else:
                s3_key = f"{event_id}/UnProcessedImages/{filename}"

            # 4) Upload to S3
            upload_file(s3_key, data)
            
            add_photo(event_id, filename, bib_numbers)
        
        except Exception:
            s3_key = f"{event_id}/UnProcessedImages/{filename}"
            upload_file(s3_key, data)


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

    print("Generating reel for bib_id", event.get("item"))
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


    # Download background video
    print("Downloading background video")
    local_video_path = os.path.join("/tmp", os.path.basename(reel_s3_key))
    try:
        s3.download_file(RAW_BUCKET, reel_s3_key, local_video_path)
    except Exception as e:
        print(f"Error downloading video: {e}")
        raise e

    # Download images
    local_image_paths = []
    print("Downloading images")
    for filename in filenames:
        local_image_path = os.path.join("/tmp", filename)
        image_s3_key = f"{event_id}/ProcessedImages/{filename}"
        try:
            s3.download_file(RAW_BUCKET, image_s3_key, local_image_path)
            local_image_paths.append(local_image_path)
        except Exception as e:
            print(f"Error downloading image {filename}: {e}")
            # Decide whether to fail hard or skip. Failing hard seems appropriate if we need these images.
            raise e

    for i in range(len(overlays)):
        overlays[i]["image_path"] = local_image_paths[i]
    
    output_path = os.path.join("/tmp", f"{event_id}/ProcessedReels/{bib_id}.mp4")
    print("Overlaying images on video")
    overlay_images_on_video(local_video_path, overlays, output_path)
    print("Uploading processed reel")
    s3.upload_file(output_path, RAW_BUCKET, f"{event_id}/ProcessedReels/{bib_id}.mp4")

    #TODO DynamoDB
    return {
        "eventId": str(event_id),
        "bibId": str(bib_id),
        "s3Bucket": RAW_BUCKET,
        "processedReel": f"{event_id}/ProcessedReels/{bib_id}.mp4",
        "ok": True
    }    

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
    requestType=event.get("requestType")

    if requestType == "PROCESS_IMAGES":
        return generateBibIds(event)
    elif requestType == "GENERATE_REEL":
        return generateReel(event)
    else:
        raise ValueError("Invalid request type")

    
