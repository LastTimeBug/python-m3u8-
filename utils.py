import requests, datetime

def download(URL, OutputFilePath = None):
    MAX_RETRY = 10
    retry = 0
    while retry <= MAX_RETRY:
        try:
            # print("Start to download %s" % (URL))  
            # Make the actual request, set the timeout for no data to 10 seconds and enable streaming responses so we don't have to keep the large files in memory
            Session = requests.session()
            Session.trust_env = False
            Response = Session.get(URL, timeout=30, stream=True)

            if OutputFilePath is not None:
                # Open the output file and make sure we write in binary mode
                with open(OutputFilePath, 'wb') as fh:
                    # Walk through the request response in chunks of 1024 * 1024 bytes, so 1MiB
                    for chunk in Response.iter_content(1024 * 1024):
                        # Write the chunk to the file
                        fh.write(chunk)
                        # Optionally we can check here if the download is taking too long
            else:
                return Response.content
        except Exception as ex:
            print(ex)
            print("Download %s timeout. retry." % (URL))
            retry += 1
            continue

        break
    
    # Datetime
def getDatetimeStr():
    Now = datetime.datetime.now()
    NowStr = Now.strftime('%Y-%m-%d %H:%M:%S')
    return NowStr