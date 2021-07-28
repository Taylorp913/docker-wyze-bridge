# RTMP/RTSP/HLS Bridge for Wyze Cam

Docker container to expose a local RTMP, RTSP, and HLS stream for all your Wyze cameras including v3. No Third-party or special firmware required.

Based on [@noelhibbard's script](https://gist.github.com/noelhibbard/03703f551298c6460f2fd0bfdbc328bd#file-readme-md) with [kroo/wyzecam](https://github.com/kroo/wyzecam), [aler9/rtsp-simple-server](https://github.com/aler9/rtsp-simple-server), and [shauntarves/wyze-sdk](https://github.com/shauntarves/wyze-sdk).

##### Compatibility:
Should work on most x64 systems as well as on some arm-based systems like the Raspberry Pi, however, ["LAN mode"](#LAN-Mode) requires a linux-based system due to host mode compatibility.

[See here](#armraspberry-pi-support) for instructions to run on arm.

## Changes in v0.4.2

**Upgrading from v0.3.x to v0.4.0+ may require a new docker-compose.yml**

- Rewritten Dockerfile to slim down final image.


## Usage

##### docker run
If on a linux based system, use your Wyze credentials and run:
```
docker run --network host -e WYZE_EMAIL= -e WYZE_PASSWORD=  mrlt8/wyze-bridge
```
or if on a non-linux system that doesn't support host mode:
```
docker run -p 1935:1935 -p 8554:8554 -p 8888:8888 -e WYZE_EMAIL= -e WYZE_PASSWORD=  mrlt8/wyze-bridge
```

##### Build with docker-compose (recommended)
1. git clone this repo or download the latest [release](https://github.com/mrlt8/docker-wyze-bridge/releases)
1. Copy and rename the sample yml to `docker-compose.yml` 
1. Edit `docker-compose.yml` with your wyze credentials
1. run `docker-composer up`

##### Additional Info
- [Two-Step Verification](#Multi-Factor-Authentication)
- [ARM/Raspberry Pi](#armraspberry-pi-support)
- [LAN mode](#LAN-Mode)

Once you're happy with your config you can use `docker-compose up -d` to run it in detached mode.


## URIs

`camera-nickname` is the name of the camera set in the Wyze app and are converted to lower case with hyphens in place of spaces. 

e.g. 'Front Door' would be `/front-door`


- RTMP:  
```
rtmp://localhost:1935/camera-nickname
```
- RTSP:  
```
rtsp://localhost:8554/camera-nickname
```
- HLS:  
```
http://localhost:8888/camera-nickname/stream.m3u8
```
- HLS can also be viewed in the browser using:
```
http://localhost:8888/camera-nickname
```


## Filtering

The default option will automatically create a stream for all the cameras on your account, but you can use the following environment options in your `docker-compose.yml` to filter the cameras.

All options are cAsE-InSensiTive, and take single or multiple comma separated values.


#### Examples:

- Whitelist by Camera Name (set in the wyze app):
```yaml
environment:
	..
    - FILTER_NAMES=Front Door, Driveway, porch cam
```
- Whitelist by Camera MAC Address:
```yaml
environment:
	..
    - FILTER_MACS=00:aA:22:33:44:55, Aa22334455bB
```
- Whitelist by Camera Model:
```yaml
environment:
	..
    - FILTER_MODEL=WYZEC1-JZ
```
- Whitelist by Camera Model Name:
```yaml
environment:
	..
    - FILTER_MODEL=V2, v3, Pan
```
- Blacklisting:

You can reverse any of these whitelists into blacklists by adding *block, blacklist, exclude, ignore, or reverse* to `FILTER_MODE`. 

```yaml
environment:
	..
    - FILTER_NAMES=Bedroom
    - FILTER_MODE=BLOCK
```

## Multi-Factor Authentication

Two-factor authentication ("Two-Step Verification" in the wyze app) is supported and will automatically be detected, however additional steps are required to enter your verification code.

- Echo the verification code directly to `/tokens/mfa_token`:
```bash
docker exec -it wyze-bridge sh -c 'echo "123456" > /tokens/mfa_token'
```
- Mount `/tokens/` locally and add your verification code to a new file `mfa_token`: 
```YAML
volumes: 
    - ./tokens:/tokens/
```


## ARM/Raspberry Pi Support

The default configuration will use the x64 tutk library, however, you can edit your `docker-compose.yml` to use the 32-bit arm library by setting `dockerfile` as `Dockerfile.arm`:

```YAML
version: '3.8'
services:
    wyze-bridge:
        restart: always
        network_mode: host
        build: 
            context: ./app
            dockerfile: Dockerfile.arm
        environment:
            - WYZE_EMAIL=
            - WYZE_PASSWORD=
```

Alternatively, you can pull a pre-built image using:
```yaml
version: '3.8'
services:
    wyze-bridge:
        restart: always
        network_mode: host
        image: mrlt8/wyze-bridge:latest
        environment:
            - WYZE_EMAIL=
            - WYZE_PASSWORD=
```

## LAN Mode

Like the wyze app, the tutk library will attempt to stream directly from the camera when on the same LAN as the camera in "LAN mode" or relay the stream via the cloud in "relay mode".

LAN mode is more ideal as all streaming will be local and won't use additional bandwidth.

To enable LAN mode, you'll need to be on a linux-based system and modify your docker-compose.yml to enable host network_mode and remove the ports:
```yaml
...
services:
    wyze-bridge:
        restart: always
        network_mode: host
        build: 
        ...
```

You can further restrict streaming to LAN only by adding the `LAN_ONLY` environment variable:
```yaml
...
environment:
	..
    - LAN_ONLY=True
```

## Bitrate and Resolution

Bitrate and resolution of the stream from the wyze camera can be adjusted with `- QUALITY=HD120`.
- Resolution can be set to `SD` (640x360 cams/480x640 doorbell) or `HD` (1920x1080 cam/1296x1728 doorbell). Default - HD.
- Bitrate can be set from 60 to 240 kb/s. Default - 120.
- Bitrate and resolution changes will apply to ALL cameras with the current version.

```yaml
environment:
	..
    - QUALITY=SD60
```

## Custom FFmpeg Commands

You can pass a custom [command](https://ffmpeg.org/ffmpeg.html) to FFmpeg by using `FFMPEG_CMD` in your docker-compose.yml:

```YAML
environment:
	..
    - FFMPEG_CMD=-f h264 -i - -vcodec copy -f flv rtmp://rtsp-server:1935/
```
Additional info:
- The `ffmpeg` command is implied and is optional.
- The camera name will automatically be appended to the command, so you need to end with the rtmp/rtsp url.


## rtsp-simple-server
[rtsp-simple-server](https://github.com/aler9/rtsp-simple-server/blob/main/rtsp-simple-server.yml) options can be customized as an environment variable in your docker-compose.yml by prefixing `RTSP_` to the UPPERCASE parameter. e.g. use `- RTSP_RTSPADDRESS=:8555` to overwrite the the default `rtspAddress`.



## Debugging options

`- DEBUG_FFMPEG=True` Enable additional logging from FFmpeg

`- FRESH_DATA=True` Remove local cache and pull new data from wyze servers.

