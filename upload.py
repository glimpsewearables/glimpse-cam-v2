#!/usr/bin/env python
import tinys3, socket, os, time, subprocess, requests, glob, httplib 
from getLines import retKey
import logging
import sys

try: 
    # Sets up log
    logFormat='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s'
    logging.basicConfig(
            filename="uploadLog.log",
            level=logging.INFO,
            format=logFormat
    )

    logger = logging.getLogger()

    # Add --console-log argument to add console logging
    if len(sys.argv) > 1 and sys.argv[1] == '--console-log':
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.setFormatter(logging.Formatter(logFormat))
        logger.addHandler(stdout_handler)

    # Getting Access/Secret Keys
    l = retKey()
    access = l[0]
    secret = l[1]

    USER_ID = socket.gethostname()
    logger.info("Hostname: {}".format(USER_ID))

    # API endpoint to send data
    API_ENDPOINT = "http://api.glimpsewearables.com/api/media/"

    # Cloudinary URL 
    CLOUDINARY_URL = "www.res.cloudinary.com"

    # Cloudinary prefix
    CLOUDINARY_METHOD = "/glimpse-wearables/video/upload"
    
    TO_UPLOAD_PATH = '/home/pi/pikrellcam/media/videos/'
    list = sorted(glob.glob(TO_UPLOAD_PATH + '*.mp4'),key=os.path.getmtime)
    UPLOADED_PATH = '/home/pi/Videos/'
    UPLOAD_COMPLETE_MESSAGE = False

    # Create global HTTP connection since these are expensive 
    # TODO: maybe clean this up in a later iteration 
    httpConn = httplib.HTTPConnection(CLOUDINARY_URL)

    # Starts aws s3 conncetion
    conn = tinys3.Connection(access, secret, tls=True, default_bucket='users-raw-content', endpoint="s3-us-west-2.amazonaws.com")
    logger.info("setup success.")
except:
    logger.error("setup failed.")
    print(sys.exc_info()[0])
    raise

# Hits cloudinary url to trigger file upload from AWS
# Throws httplib.CannotSendRequest, httplib.BadStatusLine, httplib.IncompleteRead
def upload_cloudinary(user_id, filename):

	if not user_id:
		raise httplib.CannotSendRequest("Cloudinary upload called with no user_id.")
	if not filename:
		raise httplib.CannotSendRequest("Cloudinary upload called with no filename.")
	
	req_url = "{}/{}/{}".format(CLOUDINARY_METHOD, user_id, filename)

        try:
            # Use HEAD since no data is required
            httpConn.request("HEAD", req_url)
        except Exception as e:
                raise httplib.CannotSendRequest("Cloudinary request failed for {}.".format(req_url))

        cloudinary_return = False
        cloudinary_attempts = 0

        # Retry Cloudinary trigger until success or at most 3 times
        while not cloudinary_return and cloudinary_attempts < 3:
            cloudinary_attempts += 1
            try:
                resp = httpConn.getresponse()
                if resp.status != 200:
                        # Cloudinary failed, return from method
                        raise httplib.BadStatusLine("Cloudinary HTTP HEAD status {} reason {} for {}.".format(resp.status, resp.reason, req_url))
                else:
                        # Read the response to enabled next request
                        resp.read()
                        cloudinary_return = True
            except httplib.ResponseNotReady as e:
                logger.info("Cloudinary HTTP response for {} not ready after attempt {}, retrying...".format(req_url, cloudinary_attempts))
        
        # The request never returned
        if not cloudinary_return:
                raise httplib.IncompleteRead("Cloudinary HTTP request for {} never returned.".format(req_url))

# Return True if success False if failure
# Function to upload file
def aws_upload(path, filename):
        # Tries to upload video
        with open(path+filename, 'rb') as f:
                conn.upload(filename, f)

        try:
            upload_cloudinary(USER_ID, filename)
            logger.info("Cloudinary trigger upload for {} success.".format(filename))
        except (httplib.CannotSendRequest, httplib.BadStatusLine, httplib.ResponseNotReady) as e:
            logger.error(str(e))

# TODO: refactor this to be asynchronous signals not a loop always running :(
# TODO: add in better logging where possible and more specific exception handling
# TODO: remove unecessary sleeps when stability is established
# TODO: refactor class constants and parameters
while True:
	# Uploads in the presence of wifi. Uploads in chronological order and removes it from the upload folder if successful
	if not subprocess.check_output(['hostname','-I']).isspace():
		# Uploads if there are videos left. Checks for new videos after uploading current list.
		if list:
			item = list[0]
			video = os.path.basename(item)
			# Tries uploading video. Moves video and removes it from the list if successful. Otherwise, it stays in the list
			try:
                                aws_upload(TO_UPLOAD_PATH, video)
                                # does not move video unless AWS upload is exception free
				os.rename(item, UPLOADED_PATH + video)
				list = list[1:]
                                logger.info("AWS upload for {} success.".format(video))
			except Exception as e:
                                logger.error(str(e))
		else:
			list = sorted(glob.glob(TO_UPLOAD_PATH + '*.mp4'),key=os.path.getmtime)
                        if len(list) == 0: 
                            # wait 5 seconds to check for new videos if none
                            if not UPLOAD_COMPLETE_MESSAGE:
                                logger.info("all video uploads are complete.") 
                                UPLOAD_COMPLETE_MESSAGE = True
		            time.sleep(5)
                        elif len(list) > 0: 
                            UPLOAD_COMPLETE_MESSAGE = False
        else:
            # wait a few seconds to check for WiFi
            time.sleep(10) 
