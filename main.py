import os, requests, json, m3u8, time, utils, threading, shutil

'''
GET https://www.gztv.com/gztv/api/tv/zhonghe HTTP/1.1
Host: www.gztv.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:81.0) Gecko/20100101 Firefox/81.0
Accept: */*
Accept-Language: en-US,en;q=0.5
Accept-Encoding: gzip, deflate, br
X-Requested-With: XMLHttpRequest
Connection: keep-alive
Referer: https://www.gztv.com/tvfile/tv.html
'''
def merge(InputFolder, OutputFilePath):
    FileList = os.listdir(InputFolder)
    FilePathList = []
    for FileName in FileList:
        FilePathList.append(os.path.join(InputFolder, FileName))
        
    # Create a list file which consists the path file of each part.
    # The list file is used by FFMPEG to merge all parts into one mp4 file.
    ListFile = open('list.txt', 'w')
    for FilePath in FilePathList:
        ListFile.write("file '%s'\n"% (FilePath))
    ListFile.close()
    
    print('Merging all parts into one file...')
    cmd = "ffmpeg -f concat -safe 0 -i list.txt -map_metadata -1 -c copy -y %s" % (OutputFilePath)
    os.system(cmd)
    os.remove('list.txt')
    
    for FilePath in FilePathList:
        os.remove(FilePath)
        
    shutil.rmtree(InputFolder)
    
    print('Done!')

def autoMerge(BaseFolder):
    FileNameList = os.listdir(BaseFolder)
    for FileName in FileNameList:
        Path = os.path.join(BaseFolder, FileName)
        if os.path.isdir(Path):
            InputFolder = Path
            OutputFilePath = InputFolder + '.mp4'
            InputFolder = Path
            merge(InputFolder, OutputFilePath)
            
class ChannelLiveHelper:
    def __init__(self, ChannelURL = None, DestFolder = None):
        if ChannelURL is None:
            print('Null ChannelURL url.')        
            exit(-1)
            
        if DestFolder is None:
            print('Null destination folder.')
            exit(-1)
        
        self.ChannelURL = ChannelURL
        self.ChunkListURL = []
        self.DownloadInProgressURLs = []
        self.DownloadThreadList = []
        self.M3U8URL = None
        self.nChunksDownloaded = 0
        self.nChunksDeleted = 0
        self.DestFolder = DestFolder
        self.nBytesDownloaded = 0
        self.StartTimeStamp = None
        self.CurrentSubFolder = utils.getDatetimeStr().split(' ')[0]
        self.EveningNewsAuto = True  # False means downloading immideately
        self.StatusCurrent = False
        
        print("[%s]Live helper initialized successfully." % (utils.getDatetimeStr()))
        print("Current dest. folder: %s" % (os.path.join(self.DestFolder, self.CurrentSubFolder)))
            
    def start(self):
        while True:
            if self.StatusCurrent:
                self.M3U8URL = self.getM3U8URL()    # Get chunk list URL
                self.refresh()
                self.download()
            else:
                time.sleep(1)
            
    def getM3U8URL(self):
        Session = requests.session()
        Session.trust_env = False
        
        while True:
            Response = Session.get(self.ChannelURL)
            if Response.status_code == 200:
                ResponseJson = json.loads(Response.text)
                M3U8URL = ResponseJson['data']
                print()
                print("[%s]M3U8 url obtained succesfully." % (utils.getDatetimeStr()))
                print(M3U8URL)
                return M3U8URL
            else:
                print('Invalid response when request the M3U8 url.')
                time.sleep(3)
        
    def validate(self, FilePath):
        cmd = 'ffprobe "%s"  -loglevel quiet' % (FilePath)
        status = os.system(cmd)
        if status == 0:
            return True
        else:
            return False
    
    def getAvgDownloadSpeed(self):
        TimeStampNow = time.time()
        TimeSpan = TimeStampNow - self.StartTimeStamp
        try:
            AvgSpeed = self.nBytesDownloaded / TimeSpan
            return AvgSpeed
        except: # divided by 0
            return 0
            
    def refresh(self):
        Session = requests.session()
        Session.trust_env = False
        while True:
            try:
                Response = Session.get(self.M3U8URL)
                if Response.status_code != 200:
                    print('Invalid response.')
                    return False
                else:
                    break
            except:
                print('Error occured when acquiring m3u8 file. Retry')
                time.sleep(3)
                continue
        
        M3U8 = m3u8.loads(Response.text)
        self.M3U8 = M3U8
        return True
    
    def removeStoppedChunkDownloadThread(self):
        for Thread in self.DownloadThreadList:
            ChunkURL = Thread.name
            ChunkFileName = os.path.basename(ChunkURL.split('?')[0])
            ChunkFilePath = os.path.join(self.DestFolder, self.CurrentSubFolder, ChunkFileName)
            
            if not Thread.is_alive():
                if os.path.exists(ChunkFilePath):
                    if self.validate(ChunkFilePath):
                        self.nChunksDownloaded += 1
                        self.nChunksDownloaded += 1
                        self.nBytesDownloaded += os.path.getsize(ChunkFilePath)
                    else:
                        os.remove(ChunkFilePath)
                        self.nChunksDeleted += 1
                        self.ChunkListURL.append(ChunkURL)
                else:
                    self.ChunkListURL.append(ChunkURL)
                    
                self.DownloadThreadList.remove(Thread)
            pass
    
    def getChunk(self, ChunkURL, ChunkFilePath):
        ChunkDownloadThread = threading.Thread(target = utils.download, args = (ChunkURL, ChunkFilePath, ), name = ChunkURL)
        ChunkDownloadThread.start()
        self.DownloadThreadList.append(ChunkDownloadThread)
    
    def download(self):
        while self.StatusCurrent:
            self.CurrentSubFolder = utils.getDatetimeStr().split(' ')[0]
            self.removeStoppedChunkDownloadThread()
            
            AvgDownloadSpeed = self.getAvgDownloadSpeed()
            print("[%s]%d chunks being downloaded, %d downloaded (%0.1f MB, speed: %0.1f M/s), %d deleted." % 
                  (utils.getDatetimeStr(), len(self.DownloadThreadList), self.nChunksDownloaded, 
                   self.nBytesDownloaded/1024/1024, AvgDownloadSpeed/1024/1024, self.nChunksDeleted), \
                end = '\r')
            
            for file in self.M3U8.files:
                ChunkURL = os.path.dirname(self.M3U8URL) + '/' + file
                if ChunkURL not in self.ChunkListURL:
                    self.ChunkListURL.append(ChunkURL)
            
            while len(self.ChunkListURL) > 0:
                ChunkURL = self.ChunkListURL.pop()
                
                if ChunkURL in self.DownloadInProgressURLs:
                    continue
     
                # Attemp to download the chunk
                self.DownloadInProgressURLs.append(ChunkURL)
                ChunkFileName = os.path.basename(ChunkURL.split('?')[0])
                ChunkFilePath = os.path.join(self.DestFolder, self.CurrentSubFolder, ChunkFileName)
                if not os.path.exists(os.path.dirname(ChunkFilePath)):
                    os.mkdir(os.path.dirname(ChunkFilePath))
                if not os.path.exists(ChunkFilePath):
                    self.getChunk(ChunkURL, ChunkFilePath)
        
            time.sleep(5)
            if not self.refresh():
                return False
        pass

NewsHour = 18
DestFolder = r'X:\GZNews'
ChannelURL = r'https://www.gztv.com/gztv/api/tv/zhonghe'
m3u8LiveHelper = ChannelLiveHelper(ChannelURL, DestFolder)

DownloadThread = threading.Thread(target = m3u8LiveHelper.start)
DownloadThread.start()

if m3u8LiveHelper.EveningNewsAuto:
    while True:
        CurrentTime = time.localtime()
        if (CurrentTime.tm_hour == NewsHour-1 and CurrentTime.tm_min >= 58) or \
            CurrentTime.tm_hour == NewsHour or \
                CurrentTime.tm_hour == NewsHour+1:
                    if m3u8LiveHelper.StatusCurrent is False:
                        print("Start.")
                        m3u8LiveHelper.StartTimeStamp = time.time()
                        m3u8LiveHelper.StatusCurrent = True # Recording
                        m3u8LiveHelper.nBytesDownloaded = 0
                        time.sleep(5)
                    else:
                        time.sleep(5)
                        continue
        else:
            if m3u8LiveHelper.StatusCurrent is True:
                m3u8LiveHelper.StatusCurrent = False # Not recording
                print("Stop.")
                autoMerge(DestFolder)
            
            time.sleep(5)
            print('[%s] Waiting for the start of Evening News.' % (utils.getDatetimeStr()), end = '\r') 
            
pass