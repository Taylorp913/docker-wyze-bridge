import wyzecam, gc, time, subprocess, threading, warnings, os, datetime, pickle, sys, io, wyze_sdk, bottle,cv2

class wyze_bridge:
	def __init__(self):
		print('STARTING DOCKER-WYZE-BRIDGE v0.4.0 BETA', flush=True)
	
	if 'DEBUG_FFMPEG' not in os.environ:
		warnings.filterwarnings("ignore")

	model_names = {'WYZECP1_JEF':'PAN','WYZEC1':'V1','WYZEC1-JZ':'V2','WYZE_CAKP2JFUS':'V3','WYZEDB3':'DOORBELL','WVOD1':'OUTDOOR'}

	def get_env(self,env):
		return [] if not os.environ.get(env) else [x.strip().upper().replace(':','') for x in os.environ[env].split(',')] if ',' in os.environ[env] else [os.environ[env].strip().upper().replace(':','')]

	def env_filter(self,cam):
		return True if cam.nickname.upper() in self.get_env('FILTER_NAMES') or cam.mac in self.get_env('FILTER_MACS') or cam.product_model in self.get_env('FILTER_MODEL') or self.model_names.get(cam.product_model) in self.get_env('FILTER_MODEL') else False

	def twofactor(self):
		self.mfa_token = '/tokens/mfa_token'
		print(f'MFA Token Required\nVisit /auth or Add token to {self.mfa_token}',flush=True)
		while True:
			if os.path.exists(self.mfa_token) and os.path.getsize(self.mfa_token) > 0:
				with open(self.mfa_token,'r+') as f:
					lines = f.read().strip()
					f.truncate(0)
					print(f'Using {lines} as token',flush=True)
					sys.stdin = io.StringIO(lines)
					try:
						response = wyze_sdk.Client(email=os.environ['WYZE_EMAIL'], password=os.environ['WYZE_PASSWORD'])
						return wyzecam.WyzeCredential.parse_obj({'access_token':response._token,'refresh_token':response._refresh_token,'user_id':response._user_id,'phone_id':response._api_client().phone_id})
					except Exception as ex:
						print(f'{ex}\nPlease try again!',flush=True)
			time.sleep(2)

	def authWyze(self,name):
		pkl_data = f'/tokens/{name}.pickle'
		if os.path.exists(pkl_data) and os.path.getsize(pkl_data) > 0:
			if os.environ.get('FRESH_DATA') and ('auth' not in name or not hasattr(self,'auth')):
				print(f'[FORCED REFRESH] Removing local cache for {name}!',flush=True)
				os.remove(pkl_data)
			else:	
				with(open(pkl_data,'rb')) as f:
					print(f'Fetching {name} from local cache...',flush=True)
					return pickle.load(f)
		else:
			print(f'Could not find local cache for {name}',flush=True)
		if not hasattr(self,'auth') and 'auth' not in name:
			self.authWyze('auth')
		while True:
			try:
				print(f'Fetching {name} from wyze api...',flush=True)
				if 'auth' in name:
					try:
						self.auth = data =  wyzecam.login(os.environ["WYZE_EMAIL"], os.environ["WYZE_PASSWORD"])
					except ValueError as ex:
						for err in ex.errors():
							if 'mfa_options' in err['loc']:
								self.auth = data = self.twofactor()
					except Exception as ex:
						[print('Invalid credentials?',flush=True) for err in ex.args if '400 Client Error' in err]
						raise ex
				if 'user' in name:
					data = wyzecam.get_user_info(self.auth)
				if 'cameras' in name:
					data = wyzecam.get_camera_list(self.auth)
				with open(pkl_data,"wb") as f:
					print(f'Saving {name} to local cache...',flush=True)
					pickle.dump(data, f)
				return data
			except Exception as ex:
				print(f'{ex}\nSleeping for 10s...',flush=True)
				time.sleep(10)

	def filtered_cameras(self):
		cams = self.authWyze('cameras')
		self.total_cams = len(cams)
		if 'FILTER_MODE' in os.environ and os.environ['FILTER_MODE'].upper() in ('BLOCK','BLACKLIST','EXCLUDE','IGNORE','REVERSE'):
			filtered = list(filter(lambda cam: not self.env_filter(cam),cams))
			if len(filtered) >0:
				print(f'BLACKLIST MODE ON \nSTARTING {len(filtered)} OF {self.total_cams} CAMERAS')
				return filtered
		if any(key.startswith('FILTER_') for key in os.environ):	
			filtered = list(filter(self.env_filter,cams))
			if len(filtered) > 0:
				print(f'WHITELIST MODE ON \nSTARTING {len(filtered)} OF {self.total_cams} CAMERAS')
				return filtered
		print(f'STARTING ALL {self.total_cams} CAMERAS')
		return cams

	def start_stream(self,camera):
		while True:
			try:
				resolution = 3 if camera.product_model == 'WYZEDB3' else 0
				bitrate = 120
				res = 'HD'
				if os.environ.get('QUALITY'):
					if 'SD' in os.environ['QUALITY'][:2].upper():
						resolution +=1
						res = 'SD'
					if os.environ['QUALITY'][2:].isdigit() and 30 <= int(os.environ['QUALITY'][2:]) <= 240:
						# bitrate = min([30,60,120,150,240], key=lambda x:abs(x-int(os.environ['QUALITY'][2:])))
						bitrate = int(os.environ['QUALITY'][2:])
				with wyzecam.iotc.WyzeIOTCSession(self.tutk_library,self.user,camera,resolution,bitrate) as sess:
					print(f'{datetime.datetime.now().strftime("%Y/%m/%d %X")} [{camera.nickname}] Starting {res} {bitrate}kb/s Stream for WyzeCam {self.model_names.get(camera.product_model)} ({camera.product_model}) running FW: {sess.camera.camera_info["basicInfo"]["firmware"]} from {camera.ip} (WiFi Quality: {sess.camera.camera_info["basicInfo"]["wifidb"]}%)...',flush=True)
					cmd = ('ffmpeg ' + os.environ['FFMPEG_CMD'].strip("\'").strip('\"') + camera.nickname.replace(' ', '-').replace('#', '').lower()).split() if os.environ.get('FFMPEG_CMD') else ['ffmpeg',
						'-hide_banner',
						'-nostats',
						'-loglevel','info' if 'DEBUG_FFMPEG' in os.environ else 'fatal',
						'-f', sess.camera.camera_info['videoParm']['type'].lower(),
						'-r', sess.camera.camera_info['videoParm']['fps'],
						'-err_detect','ignore_err',
						'-avioflags','direct',
						'-flags','low_delay',
						'-fflags','+flush_packets+genpts+discardcorrupt+nobuffer',
						'-i', '-',
						'-map','0:v:0',
						'-vcodec', 'copy', 
						'-rtsp_transport','tcp',
						'-f','rtsp', 'rtsp://rtsp-server:8554/' + camera.nickname.replace(' ', '-').replace('#', '').lower()]
					ffmpeg = subprocess.Popen(cmd,stdin=subprocess.PIPE)
					while ffmpeg.poll() is None:
						for (frame,_) in sess.recv_video_data():
							try:
								ffmpeg.stdin.write(frame)
							except Exception as ex:
								print(f'{datetime.datetime.now().strftime("%Y/%m/%d %X")} [{camera.nickname}] [FFMPEG] {ex}',flush=True)
								break
			except Exception as ex:
				print(f'{datetime.datetime.now().strftime("%Y/%m/%d %X")} [{camera.nickname}] {ex}',flush=True)
				if str(ex) == 'IOTC_ER_CAN_NOT_FIND_DEVICE':
					print(f'{datetime.datetime.now().strftime("%Y/%m/%d %X")} [{camera.nickname}] Camera offline? Sleeping for 10s.',flush=True)
					time.sleep(10)
			finally:
				if 'ffmpeg' in locals():
					print(f'{datetime.datetime.now().strftime("%Y/%m/%d %X")} [{camera.nickname}] Killing FFmpeg...',flush=True)
					ffmpeg.kill()
					time.sleep(0.5)
					ffmpeg.wait()
				gc.collect()
	def mjpeg(self,name):
		cam = [camera for camera in self.cameras if camera.nickname.replace(' ', '-').replace('#', '').lower() == name][0]
		while True:
			try:
				with wyzecam.iotc.WyzeIOTCSession(self.tutk_library,self.user,cam) as sess:
					for (frame, _)  in sess.recv_video_frame_ndarray():
						yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + bytes(cv2.imencode('.jpg', frame)[1]) + b'\r\n')
			except Exception as ex:
				print(f'{datetime.datetime.now().strftime("%Y/%m/%d %X")} [{camera.nickname}] {ex}',flush=True)
				if str(ex) == 'IOTC_ER_CAN_NOT_FIND_DEVICE':
					print(f'{datetime.datetime.now().strftime("%Y/%m/%d %X")} [{camera.nickname}] Camera offline? Sleeping for 10s.',flush=True)
					time.sleep(10)
			finally:
				gc.collect()

	def run(self):
		self.user = self.authWyze('user')
		self.cameras = self.filtered_cameras()
		self.tutk_library = wyzecam.tutk.tutk.load_library()
		wyzecam.tutk.tutk.iotc_initialize(self.tutk_library)
		wyzecam.tutk.tutk.av_initialize(self.tutk_library,len(self.cameras))
		if os.environ.get('HTTP_SERVER'):
			print('!! HTTP_SERVER ENABLED!!', flush=True)
			print('!! RTSP-SIMPLE-SERVER DISABLED!!', flush=True)
		else:
			for camera in self.cameras:
				threading.Thread(target=self.start_stream, args=[camera]).start()

class http_server:
	@bottle.get('/')
	def index():
		if not hasattr(bridge, 'user'):
			return '<h4>Bridge not authorized</h4><a href="/auth">Enter Verification Code</a>'
		host = bottle.request.get_header('host').split(':')
		html = '<h4>Camera URIs<h4><table><thead><tr><th>Camera</th><th>RTSP</th><th>RTMP</th><th>HLS</th><th>MJPEG</th></tr></thead><tbody>'
		for cam in bridge.cameras:
			name = cam.nickname.replace(' ', '-').replace('#', '').lower()
			html += f'<tr><td><a href="/mjpeg/{name}">{cam.nickname}</a></td><td>rtsp://{host[0]}:8554/{name}</td><td>rtmp://{host[0]}:1935/{name}</td><td>http://{host[0]}:8888/{name}/stream.m3u8</td><td>http://{host[0]}:{host[1]}/{name}</td></tr>'
		html += '</tbody></table>'
		return html
	@bottle.get('/auth')
	def get_auth():
		if hasattr(bridge, 'user') or not hasattr(bridge, 'mfa_token'):
			return 'Verification code not required at this time'
		return '<h4>Enter MFA Verification Code:</h4><form action="/auth" method="post"><input type="text" name="token"><input type="submit" value="Submit"></form>'
	@bottle.post('/auth')
	def post_auth():
		code = bottle.request.forms.get('token')
		with open(bridge.mfa_token,'w') as f:
			f.write(code)
		return f'<h4>Using {code} as the verification code</h4><a href="/">Cameras</a>'
	
	@bottle.get('/mjpeg/<cam_name>')
	def mjpeg(cam_name):
		cameras = bridge.cameras
		cam = [camera for camera in cameras if camera.nickname.replace(' ', '-').replace('#', '').lower() == cam_name][0]
		links = [f'<a href="/mjpeg/{cam.nickname.replace(" ", "-").replace("#", "").lower()}">{cam.nickname}</a>' for cam in cameras]
		return f'<h4>{cam.nickname} ({cam.product_model}) - {cam.ip} </h4>{*links,}<img src="/{cam_name}" style="width: 100vw;">'

	@bottle.get('/<cam_name>')
	def mjpeg(cam_name):
		bottle.response.headers['Content-Type'] = 'multipart/x-mixed-replace; boundary=frame'
		return bridge.mjpeg(cam_name)

	def run():
		bottle.run(host='0.0.0.0', port=8080, debug=True)


if __name__ == "__main__":
	bridge = wyze_bridge()
	if os.environ.get('HTTP_SERVER'):
		threading.Thread(target=http_server.run).start()
	bridge.run()